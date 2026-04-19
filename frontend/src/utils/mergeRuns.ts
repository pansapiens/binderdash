import type { Run } from '../types/store'

/** Matches backend persistence `run_group_key` / `merge_runs` grouping. */
export function runGroupKey(run: Run): string {
    const projectId = run.project_id ?? 'unknown'
    const runName = run.metadata?.name ?? 'unknown'
    return `${projectId}/${runName}`
}

type RunWithMerge = Run & {
    merged_paths?: string[]
    merged_pdb_files?: string[]
    pdb_files?: string[]
}

/** Mirrors `merge_runs` in `backend/routers/runs.py`. */
export function mergeRuns(runs: Run[]): Run[] {
    const mergedRuns: Record<string, RunWithMerge> = {}

    for (const run of runs) {
        const groupKey = runGroupKey(run)
        const pdbFiles = [...((run as RunWithMerge).pdb_files ?? [])]

        if (!mergedRuns[groupKey]) {
            mergedRuns[groupKey] = {
                ...run,
                metadata: { ...run.metadata },
                merged_paths: [run.path],
                merged_pdb_files: pdbFiles
            }
        } else {
            const existing = mergedRuns[groupKey]
            existing.merged_paths!.push(run.path)
            existing.merged_pdb_files!.push(...pdbFiles)
            existing.metadata = {
                ...existing.metadata,
                merged_count: existing.merged_paths!.length,
                total_pdb_count: existing.merged_pdb_files!.length
            }
        }
    }

    const result: Run[] = []
    for (const run of Object.values(mergedRuns)) {
        const { merged_pdb_files: _m, ...rest } = run
        result.push(rest as Run)
    }
    return result
}
