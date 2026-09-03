import type { Run } from '../types/store'
import { resolvePrimaryScoreChip } from '../config/pipelineDisplay'

/** Legacy key before rename to ``trajectory_count`` (older ingested ``run_json``). */
function trajectoryTotal(data: Run): number | undefined {
    const m = data.metadata as Run['metadata'] & { attempt_count?: number }
    if (typeof m.trajectory_count === 'number') return m.trajectory_count
    if (typeof m.attempt_count === 'number') return m.attempt_count
    return undefined
}

/** Accepted or filtered designs / pre-filter total (trajectories or designs). */
export function formatAcceptedTotalText(data: Run): string {
    const a = data.metadata?.pdb_count
    const t = trajectoryTotal(data)
    const left = typeof a === 'number' ? String(a) : '—'
    const right = typeof t === 'number' ? String(t) : '—'
    const base = `${left} / ${right}`
    const targets = data.metadata?.target_count
    if (typeof targets === 'number' && targets > 1) {
        return `${base} (${targets} targets)`
    }
    return base
}

function fmtNum(n: number): string {
    if (!Number.isFinite(n)) return '—'
    const abs = Math.abs(n)
    if (abs >= 1000 || (abs > 0 && abs < 1e-4)) return n.toExponential(3)
    return abs >= 10 ? n.toFixed(2) : n.toFixed(4)
}

/** Resolve a Saved Set's source_run_ids to display names — falls back to the raw ID
 * for a run no longer present (e.g. deleted since the set was created). */
export function resolveSourceRunNames(sourceRunIds: string[] | undefined, runs: Run[]): string[] {
    if (!sourceRunIds || sourceRunIds.length === 0) return []
    const byId = new Map(runs.map((r) => [r.run_id, r]))
    return sourceRunIds.map((id) => byId.get(id)?.metadata?.name ?? id)
}

/** Short "Source Runs" column text — full names when there are only a couple, else a count
 * (see resolveSourceRunNames for the full list, e.g. for a tooltip). */
export function formatSourceRunNames(sourceRunIds: string[] | undefined, runs: Run[]): string {
    const names = resolveSourceRunNames(sourceRunIds, runs)
    if (names.length === 0) return '—'
    if (names.length <= 2) return names.join(', ')
    return `${names.length} runs`
}

export function primaryScoreDisplay(data: Run): {
    numbersLine: string
    column: string
    chipLabel: string
    title: string
    tagStyle: Record<string, string>
} | null {
    const s = data.metadata?.primary_score_stats
    if (!s) return null
    const { chipLabel, tagColors } = resolvePrimaryScoreChip(s.column)
    const numbersLine = `${fmtNum(s.mean)} ± ${fmtNum(s.stddev)} [${fmtNum(s.min)} - ${fmtNum(s.max)}]`
    const title = `${s.column}: N=${s.count}, mean=${fmtNum(s.mean)} ± ${fmtNum(s.stddev)} (σ), [${fmtNum(s.min)} - ${fmtNum(s.max)}], median=${fmtNum(s.median)}`
    return {
        numbersLine,
        column: s.column,
        chipLabel,
        title,
        tagStyle: { background: tagColors.background, color: tagColors.color },
    }
}
