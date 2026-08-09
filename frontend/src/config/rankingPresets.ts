import type { RankingMetricDto } from '../webapi'

export interface RankingPreset {
    key: string
    label: string
    metrics: RankingMetricDto[]
}

/** Fresh-state default — what a new Filtering-tab session starts with (see
 * stores/filtering.ts) and what the "iptm" preset re-applies. */
export const DEFAULT_RANKING_METRICS: RankingMetricDto[] = [
    { column: 'iptm', weight: 1, higher_is_better: true, enabled: true }
]

/**
 * BoltzGen's own `Filter` task default ranking recipe (repos/boltzgen/src/boltzgen/
 * task/filter/filter.py, `self.metrics` with its own defaults `from_inverse_folded=
 * True, use_affinity=False`):
 *   design_to_target_iptm: 1, design_ptm: 1, neg_min_design_to_target_pae: 1,
 *   plip_hbonds_refolded: 2, plip_saltbridge_refolded: 2, delta_sasa_refolded: 2
 * (all "higher is better" in boltzgen's own ranking — pae is pre-negated there).
 *
 * Reproduced here using Binderdash's canonical cross-method column names (see
 * backend/filtering/metrics.py's METRIC_ALIASES) where one exists, so the preset also
 * works against non-boltzgen runs whose method has an equivalent metric — including
 * `delta_sasa`, which resolves to boltzgen's `delta_sasa_refolded` or bindcraft's
 * `Average_dSASA` (both "buried/change in interface SASA upon complex formation",
 * just computed by each provider's own pipeline). This is intentionally a different
 * column from Binderdash's own independently-computed `binderdash_delta_sasa` (as-
 * generated structure, any method) — see structural_metrics.py and METRIC_ALIASES'
 * own comments on why those are kept distinct rather than unified.
 */
export const BOLTZGEN_RANKING_METRICS: RankingMetricDto[] = [
    { column: 'iptm', weight: 1, higher_is_better: true, enabled: true },
    { column: 'ptm', weight: 1, higher_is_better: true, enabled: true },
    { column: 'pae_interaction', weight: 1, higher_is_better: false, enabled: true },
    { column: 'hbonds', weight: 2, higher_is_better: true, enabled: true },
    { column: 'saltbridge', weight: 2, higher_is_better: true, enabled: true },
    { column: 'delta_sasa', weight: 2, higher_is_better: true, enabled: true }
]

export const RANKING_PRESETS: RankingPreset[] = [
    { key: 'iptm', label: 'iptm only (default)', metrics: DEFAULT_RANKING_METRICS },
    { key: 'boltzgen', label: 'BoltzGen defaults', metrics: BOLTZGEN_RANKING_METRICS }
]
