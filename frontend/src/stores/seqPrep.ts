/**
 * Prepare sequences tab: tagging, optional DNA view, exports.
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useDesignsStore } from './designs'
import { designsApi } from '../webapi'
import type { Design } from '../types/store'

export type TagZone = 'n' | 'c'

export type PresetTagKind = 'hisN' | 'hisC' | 'flag' | 'cmyc' | 'ha' | 'custom'

export interface PlacedTag {
    id: string
    kind: PresetTagKind
    sequence: string
    label: string
}

export interface PreparedSegment {
    text: string
    cssClass: string
    style?: Record<string, string>
}

export interface PreparedRow {
    row_key: string
    design_id: string
    run_id: string
    run_name: string
    project_id: string
    tag: string
    original_sequence: string
    prepared_aa: string
    prepared_dna: string | null
    segments_aa: PreparedSegment[]
    segments_dna: PreparedSegment[] | null
}

/** Preset row for palette chips and prepared-sequence styling. */
export interface TagPresetDefinition {
    kind: PresetTagKind
    tag_name: string
    sequence: string
    color: string
    background: string
    foreground: string
    zones: ('n' | 'c')[]
}

export const TAG_PRESET_DEFS: readonly TagPresetDefinition[] = [
    {
        kind: 'hisN',
        tag_name: 'His-N',
        sequence: 'HHHHHHSG',
        color: '#1565c0',
        background: 'rgba(21, 101, 192, 0.12)',
        foreground: '#0d47a1',
        zones: ['n']
    },
    {
        kind: 'hisC',
        tag_name: 'His-C',
        sequence: 'GSHHHHHH',
        color: '#1565c0',
        background: 'rgba(21, 101, 192, 0.12)',
        foreground: '#0d47a1',
        zones: ['c']
    },
    {
        kind: 'flag',
        tag_name: 'FLAG',
        sequence: 'DYKDDDDK',
        color: '#2e7d32',
        background: 'rgba(46, 125, 50, 0.12)',
        foreground: '#1b5e20',
        zones: ['n', 'c']
    },
    {
        kind: 'cmyc',
        tag_name: 'cMyc',
        sequence: 'EQKLISEEDL',
        color: '#ef6c00',
        background: 'rgba(239, 108, 0, 0.12)',
        foreground: '#e65100',
        zones: ['n', 'c']
    },
    {
        kind: 'ha',
        tag_name: 'HA',
        sequence: 'YPYDVPDYA',
        color: '#7b1fa2',
        background: 'rgba(123, 31, 162, 0.1)',
        foreground: '#6a1b9a',
        zones: ['n', 'c']
    }
]

export const CUSTOM_TAG_VISUAL = {
    color: '#607d8b',
    background: 'rgba(69, 90, 100, 0.1)',
    foreground: '#37474f'
} as const

const N_TERMINAL_SEGMENT_STYLE: Record<string, string> = {
    display: 'inline-block',
    boxDecorationBreak: 'clone',
    WebkitBoxDecorationBreak: 'clone',
    fontWeight: '600',
    padding: '0.12em 0.28em',
    borderRadius: '4px',
    border: '1px solid #00796b',
    backgroundColor: '#b2dfdb',
    color: '#004d40'
}

const C_TERMINAL_SEGMENT_STYLE: Record<string, string> = {
    display: 'inline-block',
    boxDecorationBreak: 'clone',
    WebkitBoxDecorationBreak: 'clone',
    fontWeight: '600',
    padding: '0.12em 0.28em',
    borderRadius: '4px',
    border: '1px solid #ad1457',
    backgroundColor: '#f8bbd0',
    color: '#880e4f'
}

const ECOLI_CODONS: Record<string, string> = {
    A: 'GCT',
    R: 'CGT',
    N: 'AAC',
    D: 'GAT',
    C: 'TGC',
    Q: 'CAG',
    E: 'GAA',
    G: 'GGT',
    H: 'CAT',
    I: 'ATT',
    L: 'CTG',
    K: 'AAA',
    M: 'ATG',
    F: 'TTC',
    P: 'CCT',
    S: 'TCT',
    T: 'ACC',
    W: 'TGG',
    Y: 'TAT',
    V: 'GTT',
    '*': 'TAA',
    X: 'GCT'
}

let tagIdCounter = 0
function nextTagId(): string {
    tagIdCounter += 1
    return `t-${tagIdCounter}`
}

function getRawSequence(d: Design): string {
    const fields = ['Sequence', 'sequence', 'binder_sequence', 'binder_seq', 'seq'] as const
    for (const f of fields) {
        const v = (d as Record<string, unknown>)[f]
        if (v != null && String(v).trim()) return String(v).trim()
    }
    return ''
}

function segmentClass(kind: PresetTagKind): string {
    if (kind === 'hisN' || kind === 'hisC') return 'seq-seg-his'
    if (kind === 'flag') return 'seq-seg-flag'
    if (kind === 'cmyc') return 'seq-seg-cmyc'
    if (kind === 'ha') return 'seq-seg-ha'
    return 'seq-seg-custom'
}

export function tagPresetVisual(kind: PresetTagKind): {
    borderColor: string
    background: string
    color: string
} {
    const def = TAG_PRESET_DEFS.find(p => p.kind === kind)
    if (def) {
        return { borderColor: def.color, background: def.background, color: def.foreground }
    }
    return {
        borderColor: CUSTOM_TAG_VISUAL.color,
        background: CUSTOM_TAG_VISUAL.background,
        color: CUSTOM_TAG_VISUAL.foreground
    }
}

/** Same chrome for outlined palette buttons and tag chips (see `TAG_PRESET_DEFS`). */
export function tagPresetChromeStyle(kind: PresetTagKind): Record<string, string> {
    const v = tagPresetVisual(kind)
    return {
        borderColor: v.borderColor,
        borderWidth: '1px',
        borderStyle: 'solid',
        backgroundColor: v.background,
        color: v.color
    }
}

/**
 * PrimeVue Chip paints the label in a child `.p-chip-label` with theme token colour, ignoring root `color`.
 * Passthrough sets root + label + remove icon explicitly.
 */
export function tagPresetChipPt(kind: PresetTagKind): {
    root: { style: Record<string, string> }
    label: { style: Record<string, string> }
    removeIcon: { style: Record<string, string> }
} {
    const v = tagPresetVisual(kind)
    return {
        root: { style: tagPresetChromeStyle(kind) },
        label: { style: { color: v.color } },
        removeIcon: { style: { color: v.color } }
    }
}

function segmentStyleForPresetKind(kind: PresetTagKind): Record<string, string> {
    const v = tagPresetVisual(kind)
    return {
        borderWidth: '1px',
        borderStyle: 'solid',
        borderColor: v.borderColor,
        backgroundColor: v.background,
        color: v.color,
        fontWeight: '600',
        padding: '0.1em 0.2em',
        borderRadius: '3px'
    }
}

/** Lowercase, alphanumerics only, other chars → single underscores, trimmed edges. */
export function sanitizeExportOrderNameSegment(raw: string): string {
    const t = raw.trim().toLowerCase()
    if (!t) return ''
    const cleaned = t
        .replace(/[^a-z0-9]+/g, '_')
        .replace(/_+/g, '_')
        .replace(/^_|_$/g, '')
    return cleaned.length > 120 ? cleaned.slice(0, 120) : cleaned
}

/** `YYYYMMDD_HHmmss` in local time, safe for filenames. */
export function formatPreparedExportDatestamp(d = new Date()): string {
    const y = d.getFullYear()
    const mo = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    const h = String(d.getHours()).padStart(2, '0')
    const mi = String(d.getMinutes()).padStart(2, '0')
    const s = String(d.getSeconds()).padStart(2, '0')
    return `${y}${mo}${day}_${h}${mi}${s}`
}

/** `{sanitized_order_or_prepared_sequences}_{datestamp}` — no extension. */
export function preparedExportBasename(orderNameRaw: string): string {
    const seg = sanitizeExportOrderNameSegment(orderNameRaw)
    const prefix = seg || 'prepared_sequences'
    return `${prefix}_${formatPreparedExportDatestamp()}`
}

function reverseTranslate(aa: string): string {
    let dna = ''
    for (const ch of aa.toUpperCase()) {
        if (ch === '*') {
            dna += ECOLI_CODONS['*'] || 'TAA'
            continue
        }
        if (/\s/.test(ch)) continue
        dna += ECOLI_CODONS[ch] || ECOLI_CODONS['X']
    }
    return dna
}

export const useSeqPrepStore = defineStore('seqPrep', () => {
    const nTags = ref<PlacedTag[]>([])
    const cTags = ref<PlacedTag[]>([])
    const nTerminalPrefix = ref('')
    const cTerminalSuffix = ref('')
    const includeStop = ref(true)
    const goodOnly = ref(false)
    const extractChain = ref('B')
    const dnaMode = ref(false)
    const postStopPadding = ref('')
    const minDnaFragmentLength = ref(300)
    const customTagInput = ref('')
    const exportOrderName = ref('')
    const extracting = ref(false)

    const presetOptionsN = computed(() => TAG_PRESET_DEFS.filter(d => d.zones.includes('n')))

    const presetOptionsC = computed(() => TAG_PRESET_DEFS.filter(d => d.zones.includes('c')))

    const inputDesigns = computed((): Design[] => {
        const ds = useDesignsStore()
        const sel = ds.selectedDesigns
        let rows: Design[] =
            sel.length > 0 ? [...sel] : [...ds.filteredDesigns]
        if (goodOnly.value) {
            rows = rows.filter(d => d.good === true)
        }
        return rows
    })

    function concatTags(tags: PlacedTag[]): { text: string; segments: PreparedSegment[] } {
        let text = ''
        const segments: PreparedSegment[] = []
        for (const t of tags) {
            if (!t.sequence) continue
            segments.push({
                text: t.sequence,
                cssClass: segmentClass(t.kind),
                style: segmentStyleForPresetKind(t.kind)
            })
            text += t.sequence
        }
        return { text, segments }
    }

    const preparedRows = computed((): PreparedRow[] => {
        const nFix = nTerminalPrefix.value.trim()
        const cFix = cTerminalSuffix.value.trim()
        const { text: nTagStr, segments: nSegs } = concatTags(nTags.value)
        const { text: cTagStr, segments: cSegs } = concatTags(cTags.value)

        return inputDesigns.value.map((d): PreparedRow => {
            const raw = getRawSequence(d)
            const core = raw.replace(/\*+$/g, '').trim()
            const tagCol = String((d as Record<string, unknown>).tag ?? '')
                .trim()
                .toUpperCase()

            const segmentsAa: PreparedSegment[] = []
            let prepared_aa = ''

            if (nFix) {
                prepared_aa += nFix
                segmentsAa.push({
                    text: nFix,
                    cssClass: 'seq-seg-nfix',
                    style: { ...N_TERMINAL_SEGMENT_STYLE }
                })
            }
            if (tagCol === 'N' && nTagStr) {
                prepared_aa += nTagStr
                segmentsAa.push(...nSegs)
            }
            prepared_aa += core
            segmentsAa.push({ text: core, cssClass: 'seq-seg-core' })
            if (tagCol === 'C' && cTagStr) {
                prepared_aa += cTagStr
                segmentsAa.push(...cSegs)
            }
            if (cFix) {
                prepared_aa += cFix
                segmentsAa.push({
                    text: cFix,
                    cssClass: 'seq-seg-cfix',
                    style: { ...C_TERMINAL_SEGMENT_STYLE }
                })
            }
            if (includeStop.value) {
                prepared_aa += '*'
                segmentsAa.push({ text: '*', cssClass: 'seq-seg-stop' })
            }

            const pad = postStopPadding.value.trim().toUpperCase()
            let segments_dna: PreparedSegment[] | null = null
            let prepared_dna: string | null = null

            if (dnaMode.value) {
                let dna = reverseTranslate(prepared_aa)
                const padDna = pad.replace(/[^ACGT]/g, '')
                const bodyLen = dna.length
                if (padDna) {
                    dna += padDna
                }
                const minL = Math.max(0, minDnaFragmentLength.value)
                if (minL > 0 && dna.length < minL && padDna.length > 0) {
                    let i = 0
                    while (dna.length < minL) {
                        dna += padDna[i % padDna.length]
                        i += 1
                    }
                }
                prepared_dna = dna
                segments_dna = [{ text: dna.slice(0, bodyLen), cssClass: 'seq-seg-dna-body' }]
                if (dna.length > bodyLen) {
                    segments_dna.push({
                        text: dna.slice(bodyLen),
                        cssClass: 'seq-seg-padding'
                    })
                }
            } else if (pad.replace(/[^A-Z*]/g, '')) {
                const padAa = pad.replace(/[^A-Z*]/g, '')
                prepared_aa += padAa
                segmentsAa.push({ text: padAa, cssClass: 'seq-seg-padding' })
            }

            return {
                row_key: `${d.run_id}\x1f${d.design_id}\x1f${(d as Record<string, unknown>).source_path ?? ''}`,
                design_id: d.design_id,
                run_id: d.run_id,
                run_name: d.run_name,
                project_id: d.project_id,
                tag: tagCol || '-',
                original_sequence: raw || '(missing)',
                prepared_aa,
                prepared_dna,
                segments_aa: segmentsAa,
                segments_dna
            }
        })
    })

    function addPreset(zone: TagZone, preset: TagPresetDefinition) {
        if (!preset.zones.includes(zone)) return
        const t: PlacedTag = {
            id: nextTagId(),
            kind: preset.kind,
            sequence: preset.sequence,
            label: preset.tag_name
        }
        if (zone === 'n') nTags.value = [...nTags.value, t]
        else cTags.value = [...cTags.value, t]
    }

    function addCustomTag(zone: TagZone) {
        const s = customTagInput.value.trim().toUpperCase().replace(/[^A-Z*]/g, '')
        if (!s) return
        const t: PlacedTag = {
            id: nextTagId(),
            kind: 'custom',
            sequence: s,
            label: 'Custom'
        }
        if (zone === 'n') nTags.value = [...nTags.value, t]
        else cTags.value = [...cTags.value, t]
        customTagInput.value = ''
    }

    function removeTag(zone: TagZone, index: number) {
        if (zone === 'n') {
            nTags.value = nTags.value.filter((_, i) => i !== index)
        } else {
            cTags.value = cTags.value.filter((_, i) => i !== index)
        }
    }

    async function fetchMissingSequences(): Promise<{ ok: number; errors: string[] }> {
        const ds = useDesignsStore()
        const chain = extractChain.value.trim() || 'B'
        const items: {
            run_id: string
            design_id: string
            pdb_file: string
            chain: string
            source_path?: string
        }[] = []
        const errors: string[] = []

        for (const d of inputDesigns.value) {
            if (getRawSequence(d)) continue
            const fn = ds.getStructureFilename(d)
            if (!fn) {
                errors.push(`${d.design_id}: no structure file`)
                continue
            }
            const sp = (d as Record<string, unknown>).source_path
            items.push({
                run_id: d.run_id,
                design_id: d.design_id,
                pdb_file: fn,
                chain,
                source_path: sp != null ? String(sp) : undefined
            })
        }

        if (items.length === 0) {
            return { ok: 0, errors }
        }

        extracting.value = true
        try {
            const res = await designsApi.extractSequences({
                designs: items,
                refresh_cache_after: true
            })
            let ok = 0
            for (const r of res.results) {
                if (r.error) errors.push(`${r.design_id}: ${r.error}`)
                else ok += 1
            }
            await ds.fetchDesigns()
            return { ok, errors }
        } finally {
            extracting.value = false
        }
    }

    return {
        nTags,
        cTags,
        nTerminalPrefix,
        cTerminalSuffix,
        includeStop,
        goodOnly,
        extractChain,
        dnaMode,
        postStopPadding,
        minDnaFragmentLength,
        customTagInput,
        exportOrderName,
        extracting,
        presetOptionsN,
        presetOptionsC,
        inputDesigns,
        preparedRows,
        addPreset,
        addCustomTag,
        removeTag,
        fetchMissingSequences,
        getRawSequence
    }
})
