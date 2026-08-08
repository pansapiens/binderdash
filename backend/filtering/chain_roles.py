"""Resolve which structure chains are the (fixed) target vs. the (designed) binder.

Structural metrics (delta-SASA, hydrophobic patch, h-bonds/salt-bridges — see
``structural_metrics.py``) need to know which chains form the interface and which
side is the binder. A few methods have a well-known fixed convention (see
``run_discovery.get_target_sequence``); everything else needs a heuristic.

Heuristic: across a handful of sampled designs from the *same run*, the target
sequence does not change design-to-design, while the binder sequence does (it's
the whole point of the run). So a chain ID present with an identical sequence in
every sampled structure is (very likely) the target; a chain ID whose sequence
varies across samples is (very likely) a binder chain. Two or more independent
samples are required to tell the two apart at all — with only one structure,
every chain trivially looks "identical across all samples".
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..util.pdb_to_fasta import get_chain_sequences

# Methods with a fixed, well-known target chain convention (see
# run_discovery.get_target_sequence). The binder is inferred as "every other chain".
KNOWN_TARGET_CHAINS: Dict[str, List[str]] = {
    "bindcraft": ["A"],
    "rfd": ["B"],
}

DEFAULT_SAMPLE_SIZE = 5


@dataclass
class ChainRoleGuess:
    target_chain_ids: List[str] = field(default_factory=list)
    binder_chain_ids: List[str] = field(default_factory=list)
    # Chain IDs we couldn't confidently classify: either not present in every
    # sampled structure, or too few samples (<2) to distinguish "identical" from
    # "only ever seen once".
    ambiguous_chain_ids: List[str] = field(default_factory=list)
    sampled_count: int = 0


def guess_target_binder_chains_from_sequences(
    chain_sequences_per_structure: List[Dict[str, str]],
) -> ChainRoleGuess:
    """Pure-logic core of the heuristic, operating on already-extracted per-structure
    chain-id -> sequence dicts (see ``get_chain_sequences``). Kept separate from file
    I/O so it's cheap to unit test.
    """
    n = len(chain_sequences_per_structure)
    if n == 0:
        return ChainRoleGuess(sampled_count=0)

    all_chain_ids = sorted({c for cs in chain_sequences_per_structure for c in cs})

    target: List[str] = []
    binder: List[str] = []
    ambiguous: List[str] = []

    for chain_id in all_chain_ids:
        seqs = [cs.get(chain_id) for cs in chain_sequences_per_structure]
        if any(s is None for s in seqs) or n < 2:
            ambiguous.append(chain_id)
            continue
        if len(set(seqs)) == 1:
            target.append(chain_id)
        else:
            binder.append(chain_id)

    return ChainRoleGuess(
        target_chain_ids=target,
        binder_chain_ids=binder,
        ambiguous_chain_ids=ambiguous,
        sampled_count=n,
    )


def guess_target_binder_chains(
    structure_paths: List[str],
    sample_size: int = DEFAULT_SAMPLE_SIZE,
    random_state: int = 0,
) -> ChainRoleGuess:
    """Sample up to ``sample_size`` structures from a run and guess chain roles.

    Structures that fail to parse (or contribute no chains) are silently skipped;
    the guess is based on whatever subset was successfully read.
    """
    if not structure_paths:
        return ChainRoleGuess(sampled_count=0)

    rng = random.Random(random_state)
    sample = (
        structure_paths
        if len(structure_paths) <= sample_size
        else rng.sample(structure_paths, sample_size)
    )

    chain_sequences_per_structure = []
    for path in sample:
        try:
            chain_seqs = get_chain_sequences(path)
        except Exception:
            continue
        if chain_seqs:
            chain_sequences_per_structure.append(chain_seqs)

    return guess_target_binder_chains_from_sequences(chain_sequences_per_structure)


def resolve_chain_roles(
    method: str,
    structure_paths: List[str],
    sample_size: int = DEFAULT_SAMPLE_SIZE,
    random_state: int = 0,
) -> ChainRoleGuess:
    """Chain roles for a run: known per-method convention if there is one, else the
    sampled-sequence-identity heuristic.
    """
    known_target = KNOWN_TARGET_CHAINS.get(method)
    if known_target and structure_paths:
        try:
            chain_seqs = get_chain_sequences(structure_paths[0])
        except Exception:
            chain_seqs = None
        if chain_seqs:
            target = [c for c in known_target if c in chain_seqs]
            binder = [c for c in chain_seqs if c not in target]
            return ChainRoleGuess(
                target_chain_ids=target, binder_chain_ids=binder, sampled_count=1
            )

    return guess_target_binder_chains(
        structure_paths, sample_size=sample_size, random_state=random_state
    )


# Per-run in-memory cache: resolving roles for a large run means sampling and parsing
# a handful of structure files, so it's worth memoizing across the many designs of the
# same run within a single request/session. Cleared whenever the design cache is
# refreshed (see cache.refresh_designs_cache), since re-ingest could change which
# structures/chains a run has.
_CHAIN_ROLE_CACHE: Dict[str, ChainRoleGuess] = {}


def resolve_chain_roles_cached(
    run_id: str,
    method: str,
    structure_paths: List[str],
    sample_size: int = DEFAULT_SAMPLE_SIZE,
    random_state: int = 0,
) -> ChainRoleGuess:
    cached = _CHAIN_ROLE_CACHE.get(run_id)
    if cached is not None:
        return cached
    guess = resolve_chain_roles(
        method, structure_paths, sample_size=sample_size, random_state=random_state
    )
    _CHAIN_ROLE_CACHE[run_id] = guess
    return guess


def clear_chain_role_cache(run_id: Optional[str] = None) -> None:
    if run_id is None:
        _CHAIN_ROLE_CACHE.clear()
    else:
        _CHAIN_ROLE_CACHE.pop(run_id, None)
