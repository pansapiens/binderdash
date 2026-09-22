"""Filter evaluation for target-contact conditions.

Exercises evaluate_contact_filter and augment_with_target_contacts against
hand-constructed records, so the applicability rules are pinned independently of any
structure parsing.
"""

import polars as pl
import pytest

from backend.filtering.schemas import TargetContactFilterSpec, TargetContactGroup
from backend.filtering.target_contacts import ResidueContact
from backend.filtering.target_contacts_service import (
    RunContext,
    _design_key,
    augment_with_target_contacts,
    evaluate_contact_filter,
)
from backend.filtering.schemas import TargetResidueDto


def _context(run_id="run-1", target_key="tk-1", labels=("A166", "A167", "A170")):
    """A run whose target has three GLU residues, each with 100 Å² of apo surface.

    GLU's Tien maximum is 223 Å², which the percent-unit assertions below rely on.
    """
    return RunContext(
        run_id=run_id,
        run_name=run_id,
        method="rfd",
        binder_chain_ids=["B"],
        target_chain_ids=["A"],
        target_key=target_key,
        residues=[
            TargetResidueDto(
                label=label, chain="A", resseq=int(label[1:]), icode=" ",
                resname="GLU", aa1="E", sasa_apo=100.0,
            )
            for label in labels
        ],
    )


def _contact(d_heavy=4.0, d_ca=9.0, d_cb=7.0, sasa_bound=60.0):
    return ResidueContact(d_ca=d_ca, d_cb=d_cb, d_heavy=d_heavy, sasa_bound=sasa_bound)


def _spec(**overrides):
    base = {
        "residues": ["A166"],
        "scope": "any",
        "metric": "distance",
        "distance_type": "heavy",
        "unit": "angstrom",
        "operator": "<=",
        "value": 5.0,
    }
    return TargetContactFilterSpec(**{**base, **overrides})


class TestDistanceConditions:
    def test_within_threshold_passes(self):
        assert evaluate_contact_filter(_spec(), {"A166": _contact(d_heavy=4.0)}, _context())

    def test_beyond_threshold_fails(self):
        assert not evaluate_contact_filter(_spec(), {"A166": _contact(d_heavy=6.0)}, _context())

    def test_further_than_uses_the_reverse_operator(self):
        spec = _spec(operator=">", value=5.0)
        assert evaluate_contact_filter(spec, {"A166": _contact(d_heavy=6.0)}, _context())
        assert not evaluate_contact_filter(spec, {"A166": _contact(d_heavy=4.0)}, _context())

    def test_distance_type_selects_the_right_measurement(self):
        contacts = {"A166": _contact(d_heavy=4.0, d_cb=7.0, d_ca=9.0)}
        assert evaluate_contact_filter(_spec(distance_type="heavy", value=5.0), contacts, _context())
        assert not evaluate_contact_filter(_spec(distance_type="cb", value=5.0), contacts, _context())
        assert evaluate_contact_filter(_spec(distance_type="cb", value=8.0), contacts, _context())
        assert not evaluate_contact_filter(_spec(distance_type="ca", value=8.0), contacts, _context())

    def test_residue_outside_the_record_cutoff_counts_as_far(self):
        """No record for a residue means it is far from the binder, not unknown."""
        assert not evaluate_contact_filter(_spec(), {}, _context())
        assert evaluate_contact_filter(_spec(operator=">", value=20.0), {}, _context())


class TestSasaConditions:
    def test_bound_sasa_absolute(self):
        contacts = {"A166": _contact(sasa_bound=60.0)}
        spec = _spec(metric="sasa_bound", operator="<=", value=70.0)
        assert evaluate_contact_filter(spec, contacts, _context())
        assert not evaluate_contact_filter(
            _spec(metric="sasa_bound", operator="<=", value=50.0), contacts, _context()
        )

    def test_delta_sasa_uses_the_run_apo_reference(self):
        # apo 100, bound 60 -> 40 Å² buried.
        contacts = {"A166": _contact(sasa_bound=60.0)}
        assert evaluate_contact_filter(
            _spec(metric="delta_sasa", operator=">=", value=40.0), contacts, _context()
        )
        assert not evaluate_contact_filter(
            _spec(metric="delta_sasa", operator=">=", value=41.0), contacts, _context()
        )

    def test_per_design_apo_overrides_the_run_reference(self):
        contact = _contact(sasa_bound=60.0)
        contact.sasa_apo = 200.0
        assert evaluate_contact_filter(
            _spec(metric="delta_sasa", operator=">=", value=140.0), {"A166": contact}, _context()
        )

    def test_percent_unit_is_relative_to_the_tien_maximum(self):
        # apo 100, bound 70 -> 30 Å² buried; GLU's maximum is 223 Å², so 13.45%.
        contacts = {"A166": _contact(sasa_bound=70.0)}
        assert evaluate_contact_filter(
            _spec(metric="delta_sasa", unit="percent", operator=">=", value=13.0),
            contacts,
            _context(),
        )
        assert not evaluate_contact_filter(
            _spec(metric="delta_sasa", unit="percent", operator=">=", value=14.0),
            contacts,
            _context(),
        )

    def test_distant_residue_is_unchanged_on_binding(self):
        """A residue with no record is untouched by the binder: ΔSASA 0, bound == apo."""
        context = _context()
        assert evaluate_contact_filter(
            _spec(metric="delta_sasa", operator="<=", value=0.0), {}, context
        )
        assert evaluate_contact_filter(
            _spec(metric="sasa_bound", operator=">=", value=100.0), {}, context
        )


class TestScopes:
    def test_any_needs_one(self):
        spec = _spec(residues=["A166", "A167"], scope="any")
        contacts = {"A166": _contact(d_heavy=4.0), "A167": _contact(d_heavy=9.0)}
        assert evaluate_contact_filter(spec, contacts, _context())

    def test_all_needs_every_one(self):
        spec = _spec(residues=["A166", "A167"], scope="all")
        assert not evaluate_contact_filter(
            spec, {"A166": _contact(d_heavy=4.0), "A167": _contact(d_heavy=9.0)}, _context()
        )
        assert evaluate_contact_filter(
            spec, {"A166": _contact(d_heavy=4.0), "A167": _contact(d_heavy=4.5)}, _context()
        )

    def test_count_needs_min_count(self):
        spec = _spec(residues=["A166", "A167", "A170"], scope="count", min_count=2)
        contacts = {
            "A166": _contact(d_heavy=4.0),
            "A167": _contact(d_heavy=4.0),
            "A170": _contact(d_heavy=9.0),
        }
        assert evaluate_contact_filter(spec, contacts, _context())
        assert not evaluate_contact_filter(
            _spec(residues=["A166", "A167", "A170"], scope="count", min_count=3),
            contacts,
            _context(),
        )

    def test_site_percent_sums_over_the_listed_residues(self):
        # Two GLU, 223 Å² maximum each: 60 Å² buried across the pair is 13.45% of 446.
        spec = _spec(
            residues=["A166", "A167"], scope="site_percent", metric="delta_sasa",
            operator=">=", value=13.0,
        )
        contacts = {"A166": _contact(sasa_bound=70.0), "A167": _contact(sasa_bound=70.0)}
        assert evaluate_contact_filter(spec, contacts, _context())

        weak = {"A166": _contact(sasa_bound=95.0), "A167": _contact(sasa_bound=95.0)}
        assert not evaluate_contact_filter(spec, weak, _context())


class TestApplicability:
    def test_residue_absent_from_this_run_is_exempt(self):
        """Rule 2: a condition naming a residue this target does not have does not
        constrain the design."""
        spec = _spec(residues=["Z999"])
        assert evaluate_contact_filter(spec, {}, _context())

    def test_uncomputed_design_fails(self):
        """Rule 3: the residue exists but nothing was computed, so we cannot say it
        passes. The UI surfaces this as missing coverage."""
        assert not evaluate_contact_filter(_spec(), None, _context())


def _designs_frame(rows):
    return pl.DataFrame(rows, infer_schema_length=None)


class TestAugmentWithTargetContacts:
    @pytest.fixture
    def patched(self, monkeypatch):
        """Stub the cached-record loader so these tests need no repository or structures."""
        from backend.filtering import target_contacts_service as svc

        state = {"contexts": {}, "records": {}}

        def fake_load(run_ids):
            return svc.ContactData(
                records={k: v for k, v in state["records"].items()},
                contexts={k: v for k, v in state["contexts"].items() if k in run_ids},
            )

        monkeypatch.setattr(svc, "load_contact_data", fake_load)
        return state

    def test_condition_becomes_a_boolean_column_and_spec(self, patched):
        patched["contexts"] = {"run-1": _context()}
        patched["records"] = {
            _design_key("run-1", "d1"): {"A166": _contact(d_heavy=4.0)},
            _design_key("run-1", "d2"): {"A166": _contact(d_heavy=9.0)},
        }
        df = _designs_frame(
            [
                {"run_id": "run-1", "design_id": "d1", "source_path": None},
                {"run_id": "run-1", "design_id": "d2", "source_path": None},
            ]
        )
        groups = [TargetContactGroup(target_key="tk-1", filters=[_spec()])]

        out, specs, labels, _warnings = augment_with_target_contacts(df, groups, ["run-1"])

        assert specs[0].column == "__tc_0_0"
        assert out["__tc_0_0"].to_list() == [True, False]
        assert "A166" in labels["__tc_0_0"]

    def test_design_outside_the_group_scope_is_exempt(self, patched):
        """Rule 1: with one group per target, a design is only constrained by the
        conditions written against its own target."""
        patched["contexts"] = {
            "run-1": _context("run-1", "tk-1"),
            "run-2": _context("run-2", "tk-2", labels=("B142",)),
        }
        patched["records"] = {
            _design_key("run-1", "d1"): {"A166": _contact(d_heavy=9.0)},
            _design_key("run-2", "d2"): {"B142": _contact(d_heavy=9.0)},
        }
        df = _designs_frame(
            [
                {"run_id": "run-1", "design_id": "d1", "source_path": None},
                {"run_id": "run-2", "design_id": "d2", "source_path": None},
            ]
        )
        groups = [TargetContactGroup(target_key="tk-1", filters=[_spec(residues=["A166"])])]

        out, _specs, _labels, _warnings = augment_with_target_contacts(df, groups, ["run-1", "run-2"])

        # run-1's design fails the condition; run-2's is not in scope, so it passes.
        assert out["__tc_0_0"].to_list() == [False, True]

    def test_two_groups_constrain_their_own_targets(self, patched):
        """The equivalent-residue case: A166 on one target, B142 on the other."""
        patched["contexts"] = {
            "run-1": _context("run-1", "tk-1"),
            "run-2": _context("run-2", "tk-2", labels=("B142",)),
        }
        patched["records"] = {
            _design_key("run-1", "d1"): {"A166": _contact(d_heavy=4.0)},
            _design_key("run-2", "d2"): {"B142": _contact(d_heavy=9.0)},
        }
        df = _designs_frame(
            [
                {"run_id": "run-1", "design_id": "d1", "source_path": None},
                {"run_id": "run-2", "design_id": "d2", "source_path": None},
            ]
        )
        groups = [
            TargetContactGroup(target_key="tk-1", label="X", filters=[_spec(residues=["A166"])]),
            TargetContactGroup(target_key="tk-2", label="Y", filters=[_spec(residues=["B142"])]),
        ]

        out, specs, labels, _warnings = augment_with_target_contacts(df, groups, ["run-1", "run-2"])

        assert len(specs) == 2
        assert out["__tc_0_0"].to_list() == [True, True]   # run-2 exempt from group 0
        assert out["__tc_1_0"].to_list() == [True, False]  # run-1 exempt from group 1
        assert labels["__tc_1_0"].startswith("Y:")

    def test_explicit_run_ids_override_target_matching(self, patched):
        patched["contexts"] = {
            "run-1": _context("run-1", "tk-1"),
            "run-2": _context("run-2", "tk-1"),
        }
        patched["records"] = {
            _design_key("run-1", "d1"): {"A166": _contact(d_heavy=9.0)},
            _design_key("run-2", "d2"): {"A166": _contact(d_heavy=9.0)},
        }
        df = _designs_frame(
            [
                {"run_id": "run-1", "design_id": "d1", "source_path": None},
                {"run_id": "run-2", "design_id": "d2", "source_path": None},
            ]
        )
        groups = [TargetContactGroup(target_key="tk-1", run_ids=["run-1"], filters=[_spec()])]

        out, _specs, _labels, _warnings = augment_with_target_contacts(df, groups, ["run-1", "run-2"])

        assert out["__tc_0_0"].to_list() == [False, True]

    def test_no_groups_leaves_the_frame_untouched(self, patched):
        df = _designs_frame([{"run_id": "run-1", "design_id": "d1", "source_path": None}])
        out, specs, labels, warnings = augment_with_target_contacts(df, [], ["run-1"])
        assert out.columns == df.columns
        assert (specs, labels, warnings) == ([], {}, [])
