"""Resolving a caller-supplied column name against a heterogeneous design table.

Designs are flat dicts whose columns depend on the method, so "iptm" is
``Average_i_pTM`` for one row and ``design_to_target_iptm`` for the next. The filtering
engine already knows how to build a per-row-resolved expression for that; this wraps it
so every tool resolves names the same way, canonical or raw.
"""

from __future__ import annotations

from typing import Optional

import polars as pl


def canonical_expr(df: pl.DataFrame, name: str) -> Optional[pl.Expr]:
    """An expression yielding ``name``'s value for each row, or ``None`` if unresolvable.

    Canonical resolution takes precedence over a same-named literal column. Several
    canonical names *are* one method's raw column name -- `pae_interaction` is rfd's own
    column -- so preferring the literal would return rfd's values and null for every
    other method, which looks like missing data rather than a resolution failure.
    """
    from ..filtering.engine import _resolve_canonical
    from .vocab import NON_SCORE_METRICS

    # design_id/sequence are aliased per method too, but they are identity columns the
    # cache already normalises; resolving them would swap design_id for bindcraft's
    # "Design" column and break every reference the caller then makes.
    if name not in NON_SCORE_METRICS:
        resolved = _resolve_canonical(df, name)
        if resolved is not None:
            return resolved[0]
    if name in df.columns:
        return pl.col(name)
    return None


def coverage(df: pl.DataFrame, name: str) -> int:
    """How many rows actually have a value for ``name``."""
    expr = canonical_expr(df, name)
    if expr is None:
        return 0
    return int(df.select(expr.is_not_null().sum()).item() or 0)
