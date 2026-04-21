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
    return `${left} / ${right}`
}

function fmtNum(n: number): string {
    if (!Number.isFinite(n)) return '—'
    const abs = Math.abs(n)
    if (abs >= 1000 || (abs > 0 && abs < 1e-4)) return n.toExponential(3)
    return abs >= 10 ? n.toFixed(2) : n.toFixed(4)
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
