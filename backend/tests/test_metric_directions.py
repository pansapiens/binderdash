"""Tests for canonical metric direction helpers in filtering.metrics."""

from __future__ import annotations

from backend.filtering.metrics import default_numeric_operator, higher_is_better


class TestHigherIsBetter:
    def test_canonical_higher(self) -> None:
        assert higher_is_better("iptm") is True
        assert higher_is_better("ipsae") is True
        assert higher_is_better("ptm") is True
        assert higher_is_better("binder_plddt") is True
        assert higher_is_better("hbonds") is True
        assert higher_is_better("delta_sasa") is True

    def test_canonical_lower(self) -> None:
        assert higher_is_better("rmsd") is False
        assert higher_is_better("pae_interaction") is False

    def test_raw_alias_resolves(self) -> None:
        assert higher_is_better("Average_i_pTM") is True
        assert higher_is_better("design_to_target_iptm") is True
        assert higher_is_better("pae_interaction") is False
        assert higher_is_better("Average_i_pAE") is False
        assert higher_is_better("bb_rmsd") is False

    def test_non_score_and_unknown(self) -> None:
        assert higher_is_better("sequence") is None
        assert higher_is_better("design_id") is None
        assert higher_is_better("not_a_real_column") is None


class TestDefaultNumericOperator:
    def test_higher_is_better_uses_gt(self) -> None:
        assert default_numeric_operator("iptm") == ">"
        assert default_numeric_operator("Average_i_pTM") == ">"

    def test_lower_is_better_or_unknown_uses_lt(self) -> None:
        assert default_numeric_operator("rmsd") == "<"
        assert default_numeric_operator("pae_interaction") == "<"
        assert default_numeric_operator("unknown_metric") == "<"
