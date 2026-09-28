import type { RankingMetricDto } from '../webapi'

/** How a list of ranking metrics is turned into one order.
 * `simple` — list order is primary, secondary, … (weights ignored).
 * `worst_rank` — BoltzGen Algorithm 2: worst scaled rank across metrics. */
export type RankingMode = 'simple' | 'worst_rank'

export interface RankingPreset {
    key: string
    label: string
    mode: RankingMode
    metrics: RankingMetricDto[]
}

export const RANKING_MODES: { key: RankingMode; label: string }[] = [
    { key: 'simple', label: 'Simple ranking' },
    {
        key: 'worst_rank',
        label: 'Weighted-Worst-Rank-Across-Metrics (Boltzgen-style)'
    }
]

/** Fresh-state default under Simple ranking. Canonical names resolve per method
 * (see backend/filtering/metrics.py METRIC_ALIASES): iptm, binder pLDDT, binder RMSD.
 * `higher_is_better` flags must stay aligned with METRIC_DIRECTIONS there. */
export const SIMPLE_IPTM_PLDDT_RMSD_METRICS: RankingMetricDto[] = [
    { column: 'iptm', weight: 1, higher_is_better: true, enabled: true },
    { column: 'binder_plddt', weight: 1, higher_is_better: true, enabled: true },
    { column: 'rmsd', weight: 1, higher_is_better: false, enabled: true }
]

/** Same order as the ipTM preset, with ipSAE as the primary key. */
export const SIMPLE_IPSAE_PLDDT_RMSD_METRICS: RankingMetricDto[] = [
    { column: 'ipsae', weight: 1, higher_is_better: true, enabled: true },
    { column: 'binder_plddt', weight: 1, higher_is_better: true, enabled: true },
    { column: 'rmsd', weight: 1, higher_is_better: false, enabled: true }
]

export const IPTM_ONLY_METRICS: RankingMetricDto[] = [
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

export const DEFAULT_RANKING_MODE: RankingMode = 'simple'
export const DEFAULT_RANKING_METRICS: RankingMetricDto[] = SIMPLE_IPTM_PLDDT_RMSD_METRICS

export const RANKING_PRESETS: RankingPreset[] = [
    {
        key: 'iptm_plddt_rmsd',
        label: 'ipTM + Binder pLDDT + Binder RMSD',
        mode: 'simple',
        metrics: SIMPLE_IPTM_PLDDT_RMSD_METRICS
    },
    {
        key: 'ipsae_plddt_rmsd',
        label: 'ipSAE + Binder pLDDT + Binder RMSD',
        mode: 'simple',
        metrics: SIMPLE_IPSAE_PLDDT_RMSD_METRICS
    },
    { key: 'iptm', label: 'iptm only', mode: 'simple', metrics: IPTM_ONLY_METRICS },
    { key: 'boltzgen', label: 'BoltzGen defaults', mode: 'worst_rank', metrics: BOLTZGEN_RANKING_METRICS },
    { key: 'iptm_worst', label: 'iptm only', mode: 'worst_rank', metrics: IPTM_ONLY_METRICS }
]

/** 1 → "1st", 2 → "2nd", … for the simple-ranking priority label. */
export function rankingOrdinal(position: number): string {
    const mod100 = position % 100
    if (mod100 >= 11 && mod100 <= 13) return `${position}th`
    switch (position % 10) {
        case 1:
            return `${position}st`
        case 2:
            return `${position}nd`
        case 3:
            return `${position}rd`
        default:
            return `${position}th`
    }
}
