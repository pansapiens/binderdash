import backend.filtering.chain_roles as chain_roles_mod
from backend.filtering.chain_roles import (
    ChainRoleGuess,
    clear_chain_role_cache,
    guess_target_binder_chains_from_sequences,
    resolve_chain_roles,
    resolve_chain_roles_cached,
)


class TestGuessFromSequences:
    def test_target_identical_binder_varies(self):
        samples = [
            {"A": "TARGETSEQ", "B": "BINDERAAA"},
            {"A": "TARGETSEQ", "B": "BINDERBBB"},
            {"A": "TARGETSEQ", "B": "BINDERCCC"},
        ]
        guess = guess_target_binder_chains_from_sequences(samples)
        assert guess.target_chain_ids == ["A"]
        assert guess.binder_chain_ids == ["B"]
        assert guess.ambiguous_chain_ids == []
        assert guess.sampled_count == 3

    def test_single_sample_is_ambiguous(self):
        # With only one observation, "identical across all samples" is trivially true
        # for every chain, so we can't distinguish target from binder at all.
        samples = [{"A": "TARGETSEQ", "B": "BINDERAAA"}]
        guess = guess_target_binder_chains_from_sequences(samples)
        assert guess.target_chain_ids == []
        assert guess.binder_chain_ids == []
        assert set(guess.ambiguous_chain_ids) == {"A", "B"}

    def test_no_samples(self):
        guess = guess_target_binder_chains_from_sequences([])
        assert guess == ChainRoleGuess(sampled_count=0)

    def test_chain_missing_from_some_samples_is_ambiguous(self):
        samples = [
            {"A": "TARGETSEQ", "B": "BINDERAAA"},
            {"A": "TARGETSEQ"},  # chain B missing this time
        ]
        guess = guess_target_binder_chains_from_sequences(samples)
        assert guess.target_chain_ids == ["A"]
        assert guess.binder_chain_ids == []
        assert guess.ambiguous_chain_ids == ["B"]

    def test_multi_chain_binder_and_multi_chain_target(self):
        samples = [
            {"A": "T1", "B": "T2", "C": "BIND1", "D": "BIND2"},
            {"A": "T1", "B": "T2", "C": "BIND3", "D": "BIND4"},
        ]
        guess = guess_target_binder_chains_from_sequences(samples)
        assert guess.target_chain_ids == ["A", "B"]
        assert guess.binder_chain_ids == ["C", "D"]

    def test_all_chains_identical_across_samples_all_target(self):
        # Degenerate case: nothing varies (e.g. duplicate/identical designs sampled).
        samples = [{"A": "SEQ1", "B": "SEQ2"}, {"A": "SEQ1", "B": "SEQ2"}]
        guess = guess_target_binder_chains_from_sequences(samples)
        assert guess.target_chain_ids == ["A", "B"]
        assert guess.binder_chain_ids == []


class TestResolveChainRoles:
    def test_known_convention_bindcraft(self, monkeypatch):
        monkeypatch.setattr(
            "backend.filtering.chain_roles.get_chain_sequences",
            lambda path: {"A": "TARGETSEQ", "B": "BINDERSEQ"},
        )
        guess = resolve_chain_roles("bindcraft", ["fake_path.pdb"])
        assert guess.target_chain_ids == ["A"]
        assert guess.binder_chain_ids == ["B"]
        assert guess.sampled_count == 1

    def test_known_convention_rfd(self, monkeypatch):
        monkeypatch.setattr(
            "backend.filtering.chain_roles.get_chain_sequences",
            lambda path: {"A": "BINDERSEQ", "B": "TARGETSEQ"},
        )
        guess = resolve_chain_roles("rfd", ["fake_path.pdb"])
        assert guess.target_chain_ids == ["B"]
        assert guess.binder_chain_ids == ["A"]

    def test_unknown_method_falls_back_to_heuristic(self, monkeypatch):
        samples = iter(
            [
                {"A": "TARGETSEQ", "B": "BINDERAAA"},
                {"A": "TARGETSEQ", "B": "BINDERBBB"},
            ]
        )
        monkeypatch.setattr(
            "backend.filtering.chain_roles.get_chain_sequences", lambda path: next(samples)
        )
        guess = resolve_chain_roles("rfd3", ["p1.pdb", "p2.pdb"], sample_size=5)
        assert guess.target_chain_ids == ["A"]
        assert guess.binder_chain_ids == ["B"]

    def test_no_structures(self):
        guess = resolve_chain_roles("bindcraft", [])
        assert guess.sampled_count == 0

    def test_parse_failure_skipped(self, monkeypatch):
        def flaky(path):
            if path == "bad.pdb":
                raise ValueError("corrupt file")
            return {"A": "TARGETSEQ", "B": "BINDERSEQ"}

        monkeypatch.setattr("backend.filtering.chain_roles.get_chain_sequences", flaky)
        guess = resolve_chain_roles("rfd3", ["bad.pdb", "good.pdb"], sample_size=5)
        # Only one of the two paths parsed successfully, so we still can't tell target
        # from binder (need >=2 successful samples) — but the failure itself is handled
        # gracefully rather than raising.
        assert guess.sampled_count == 1
        assert set(guess.ambiguous_chain_ids) == {"A", "B"}


class TestResolveChainRolesCached:
    def setup_method(self):
        clear_chain_role_cache()

    def teardown_method(self):
        clear_chain_role_cache()

    def test_caches_by_run_id(self, monkeypatch):
        calls = []

        def tracked(path):
            calls.append(path)
            return {"A": "TARGETSEQ", "B": "BINDERSEQ"}

        monkeypatch.setattr("backend.filtering.chain_roles.get_chain_sequences", tracked)
        first = resolve_chain_roles_cached("run-1", "bindcraft", ["p1.pdb"])
        second = resolve_chain_roles_cached("run-1", "bindcraft", ["p1.pdb"])
        assert first == second
        assert len(calls) == 1  # second call was served from cache, no re-parse

    def test_different_runs_cached_independently(self, monkeypatch):
        monkeypatch.setattr(
            "backend.filtering.chain_roles.get_chain_sequences",
            lambda path: {"A": "TARGETSEQ", "B": "BINDERSEQ"},
        )
        guess_a = resolve_chain_roles_cached("run-a", "bindcraft", ["p1.pdb"])
        guess_b = resolve_chain_roles_cached("run-b", "rfd", ["p2.pdb"])
        # bindcraft's convention is target=A; rfd's is target=B — same input chains,
        # different per-run cache entries should reflect each method's own convention.
        assert guess_a.target_chain_ids == ["A"]
        assert guess_b.target_chain_ids == ["B"]

    def test_clear_single_run(self, monkeypatch):
        calls = []

        def tracked(path):
            calls.append(path)
            return {"A": "TARGETSEQ", "B": "BINDERSEQ"}

        monkeypatch.setattr("backend.filtering.chain_roles.get_chain_sequences", tracked)
        resolve_chain_roles_cached("run-1", "bindcraft", ["p1.pdb"])
        clear_chain_role_cache("run-1")
        resolve_chain_roles_cached("run-1", "bindcraft", ["p1.pdb"])
        assert len(calls) == 2  # cache was cleared, so it recomputed

    def test_clear_all(self, monkeypatch):
        monkeypatch.setattr(
            "backend.filtering.chain_roles.get_chain_sequences",
            lambda path: {"A": "TARGETSEQ", "B": "BINDERSEQ"},
        )
        resolve_chain_roles_cached("run-1", "bindcraft", ["p1.pdb"])
        resolve_chain_roles_cached("run-2", "bindcraft", ["p2.pdb"])
        clear_chain_role_cache()
        assert chain_roles_mod._CHAIN_ROLE_CACHE == {}
