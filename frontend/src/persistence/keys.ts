export const PERSISTENCE_KEYS = {
    designsViewState: 'binderdash:designs-view-state-v1',
    plotsScatterAxes: 'binderdash:plots-scatter-axes-v1',
    viewerControlsPos: 'binderdash-viewer-controls-pos',
    advRefGlobal: 'binderdash-adv-ref-ui-global',
    foldersUi: 'binderdash:folders-ui-v1',
    filteringViewState: 'binderdash:filtering-view-state-v1',
} as const

export function tagPlacementKey(runId: string): string {
    return `binderdash-tag-placement:${runId}`
}

export function advRefKey(runId: string): string {
    return `binderdash-adv-ref:${runId}`
}
