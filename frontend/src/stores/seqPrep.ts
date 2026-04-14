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

export interface CodonTable {
    label: string
    forward: Record<string, string>
    reverse: Record<string, string>
    stop: string
}

const ECOLI_FORWARD: Record<string, string> = {
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

function buildReverse(forward: Record<string, string>, stop: string): Record<string, string> {
    const reverse: Record<string, string> = {}
    for (const [aa, codon] of Object.entries(forward)) {
        if (aa === '*') continue
        reverse[codon.toUpperCase()] = aa
    }
    reverse[stop.toUpperCase()] = '*'
    return reverse
}

export const CODON_TABLES: Record<string, CodonTable> = {
    ecoli: {
        label: 'E. coli',
        forward: { ...ECOLI_FORWARD },
        reverse: buildReverse(ECOLI_FORWARD, 'TAA'),
        stop: 'TAA'
    }
}

export const CODON_TABLE_OPTIONS: { label: string; value: string }[] = Object.entries(CODON_TABLES).map(
    ([value, t]) => ({ label: t.label, value })
)

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

const VALID_NUC = new Set(['a', 'c', 'g', 't'])

export function validateMixedSequence(s: string, fieldName: string): string | null {
    for (const ch of s) {
        if (ch >= 'A' && ch <= 'Z') continue
        if (ch === '*') continue
        if (VALID_NUC.has(ch)) continue
        if (/\s/.test(ch)) continue
        return `${fieldName}: invalid character '${ch}'`
    }
    return null
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

function isLowerNuc(c: string): boolean {
    return VALID_NUC.has(c)
}

function isUpperAa(c: string): boolean {
    return (c >= 'A' && c <= 'Z') || c === '*'
}

type MixedRun = { type: 'upper' | 'lower'; text: string }

function splitMixedRuns(mixed: string): MixedRun[] {
    const runs: MixedRun[] = []
    let i = 0
    const n = mixed.length
    while (i < n) {
        const c = mixed[i]
        if (/\s/.test(c)) {
            i += 1
            continue
        }
        const lower = isLowerNuc(c)
        const upper = isUpperAa(c)
        if (!lower && !upper) {
            i += 1
            continue
        }
        const start = i
        if (lower) {
            while (i < n && isLowerNuc(mixed[i])) i += 1
            runs.push({ type: 'lower', text: mixed.slice(start, i) })
        } else {
            while (i < n && isUpperAa(mixed[i])) i += 1
            runs.push({ type: 'upper', text: mixed.slice(start, i) })
        }
    }
    return runs
}

function mixedToAaSegments(
    mixed: string,
    cssClass: string,
    style: Record<string, string> | undefined,
    codonTable: CodonTable
): { segments: PreparedSegment[]; exportText: string } {
    const segments: PreparedSegment[] = []
    let exportText = ''
    const runs = splitMixedRuns(mixed)
    for (const run of runs) {
        if (run.type === 'upper') {
            if (!run.text) continue
            let buf = ''
            const flushBuf = () => {
                if (!buf) return
                const seg: PreparedSegment = style
                    ? { text: buf, cssClass, style: { ...style } }
                    : { text: buf, cssClass }
                segments.push(seg)
                exportText += buf
                buf = ''
            }
            for (const ch of run.text) {
                if (ch === '*') {
                    flushBuf()
                    segments.push({ text: '*', cssClass: 'seq-seg-stop' })
                    exportText += '*'
                } else {
                    buf += ch
                }
            }
            flushBuf()
            continue
        }
        const low = run.text
        const full = Math.floor(low.length / 3)
        for (let t = 0; t < full; t += 1) {
            const tri = low.slice(t * 3, t * 3 + 3).toUpperCase()
            const aa = codonTable.reverse[tri] ?? 'X'
            const ch = aa === '*' ? '*' : aa
            segments.push({
                text: ch,
                cssClass: ch === '*' ? 'seq-seg-stop' : cssClass,
                style: ch === '*' ? undefined : style ? { ...style } : undefined
            })
            exportText += ch
        }
        const rem = low.slice(full * 3)
        if (rem) {
            segments.push({ text: rem, cssClass: 'seq-seg-nuc-remainder' })
            exportText += '-'.repeat(rem.length)
        }
    }
    return { segments, exportText }
}

function literalAaToDnaSegments(
    aa: string,
    codonTable: CodonTable,
    bodyCssClass = 'seq-seg-dna-body',
    bodyStyle?: Record<string, string>
): { dna: string; segments: PreparedSegment[] } {
    let dna = ''
    const segments: PreparedSegment[] = []
    let bodyBuf = ''
    const flushBody = () => {
        if (bodyBuf) {
            const seg: PreparedSegment = bodyStyle
                ? { text: bodyBuf, cssClass: bodyCssClass, style: { ...bodyStyle } }
                : { text: bodyBuf, cssClass: bodyCssClass }
            segments.push(seg)
            bodyBuf = ''
        }
    }
    for (const ch of aa) {
        if (/\s/.test(ch)) continue
        if (ch === '*') {
            flushBody()
            const stop = codonTable.stop
            dna += stop
            segments.push({ text: stop, cssClass: 'seq-seg-stop' })
        } else {
            const u = ch.toUpperCase()
            if (u >= 'A' && u <= 'Z') {
                const codon = codonTable.forward[u] || codonTable.forward['X']
                dna += codon
                bodyBuf += codon
            }
        }
    }
    flushBody()
    return { dna, segments }
}

function mixedToDnaSegments(
    mixed: string,
    codonTable: CodonTable,
    bodyCssClass: string,
    bodyStyle?: Record<string, string>
): { dna: string; segments: PreparedSegment[] } {
    let dna = ''
    const segments: PreparedSegment[] = []
    let bodyBuf = ''
    const flushBody = () => {
        if (bodyBuf) {
            const seg: PreparedSegment = bodyStyle
                ? { text: bodyBuf, cssClass: bodyCssClass, style: { ...bodyStyle } }
                : { text: bodyBuf, cssClass: bodyCssClass }
            segments.push(seg)
            bodyBuf = ''
        }
    }
    const runs = splitMixedRuns(mixed)
    for (const run of runs) {
        if (run.type === 'upper') {
            const sub = literalAaToDnaSegments(run.text, codonTable, bodyCssClass, bodyStyle)
            dna += sub.dna
            for (const s of sub.segments) {
                if (s.cssClass === 'seq-seg-stop') {
                    flushBody()
                    segments.push(s)
                } else if (s.cssClass === bodyCssClass) {
                    bodyBuf += s.text
                }
            }
            continue
        }
        const low = run.text
        const stopU = codonTable.stop.toUpperCase()
        for (let i = 0; i < low.length; i += 3) {
            const tri = low.slice(i, i + 3)
            if (tri.length < 3) {
                const up = tri.toUpperCase()
                dna += up
                bodyBuf += up
                continue
            }
            const up = tri.toUpperCase()
            if (up === stopU) {
                flushBody()
                dna += up
                segments.push({ text: up, cssClass: 'seq-seg-stop' })
            } else {
                dna += up
                bodyBuf += up
            }
        }
    }
    flushBody()
    return { dna, segments }
}

function mergeDnaSegments(segments: PreparedSegment[], bodyClass: string): PreparedSegment[] {
    const out: PreparedSegment[] = []
    let buf = ''
    let bufStyle: Record<string, string> | undefined
    const flush = () => {
        if (buf) {
            const seg: PreparedSegment = bufStyle
                ? { text: buf, cssClass: bodyClass, style: { ...bufStyle } }
                : { text: buf, cssClass: bodyClass }
            out.push(seg)
            buf = ''
            bufStyle = undefined
        }
    }
    for (const s of segments) {
        if (s.cssClass === 'seq-seg-stop') {
            flush()
            out.push(s)
        } else {
            buf += s.text
            if (!bufStyle && s.style) {
                bufStyle = s.style
            }
        }
    }
    flush()
    return out
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
    const selectedCodonTable = ref<string>('ecoli')

    const activeCodonTable = computed((): CodonTable => {
        const t = CODON_TABLES[selectedCodonTable.value]
        return t ?? CODON_TABLES.ecoli
    })

    const validationErrors = computed((): string[] => {
        const errs: string[] = []
        for (const t of [...nTags.value, ...cTags.value]) {
            if (t.kind === 'custom') {
                const e = validateMixedSequence(t.sequence, `Tag "${t.label}"`)
                if (e) errs.push(e)
            }
        }
        const fields = [
            [nTerminalPrefix.value, 'N-terminal prefix'],
            [cTerminalSuffix.value, 'C-terminal suffix'],
            [postStopPadding.value, 'Post-stop padding']
        ] as const
        for (const [val, name] of fields) {
            const e = validateMixedSequence(val.trim(), name)
            if (e) errs.push(e)
        }
        return errs
    })

    const canDownload = computed(() => validationErrors.value.length === 0)

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

    function appendTagsAa(
        tags: PlacedTag[],
        segmentsAa: PreparedSegment[],
        aaExportParts: string[],
        table: CodonTable
    ) {
        for (const t of tags) {
            if (!t.sequence) continue
            if (t.kind === 'custom') {
                const { segments, exportText } = mixedToAaSegments(
                    t.sequence,
                    segmentClass(t.kind),
                    segmentStyleForPresetKind(t.kind),
                    table
                )
                segmentsAa.push(...segments)
                aaExportParts.push(exportText)
            } else {
                segmentsAa.push({
                    text: t.sequence,
                    cssClass: segmentClass(t.kind),
                    style: segmentStyleForPresetKind(t.kind)
                })
                aaExportParts.push(t.sequence)
            }
        }
    }

    function appendTagsDna(
        tags: PlacedTag[],
        dnaParts: string[],
        segParts: PreparedSegment[][],
        table: CodonTable
    ) {
        for (const t of tags) {
            if (!t.sequence) continue
            const tagCssClass = segmentClass(t.kind)
            const tagStyle = segmentStyleForPresetKind(t.kind)
            if (t.kind === 'custom') {
                const { dna, segments } = mixedToDnaSegments(t.sequence, table, tagCssClass, tagStyle)
                dnaParts.push(dna)
                segParts.push(mergeDnaSegments(segments, tagCssClass))
            } else {
                const { dna, segments } = literalAaToDnaSegments(t.sequence, table, tagCssClass, tagStyle)
                dnaParts.push(dna)
                segParts.push(segments)
            }
        }
    }

    const preparedRows = computed((): PreparedRow[] => {
        const table = activeCodonTable.value
        const nFix = nTerminalPrefix.value.trim()
        const cFix = cTerminalSuffix.value.trim()
        const padRaw = postStopPadding.value.trim()

        return inputDesigns.value.map((d): PreparedRow => {
            const raw = getRawSequence(d)
            const core = raw.replace(/\*+$/g, '').trim()
            const tagCol = String((d as Record<string, unknown>).tag ?? '')
                .trim()
                .toUpperCase()

            const segmentsAa: PreparedSegment[] = []
            const aaExportParts: string[] = []

            if (nFix) {
                const { segments, exportText } = mixedToAaSegments(
                    nFix,
                    'seq-seg-nfix',
                    { ...N_TERMINAL_SEGMENT_STYLE },
                    table
                )
                segmentsAa.push(...segments)
                aaExportParts.push(exportText)
            }
            if (tagCol === 'N') {
                appendTagsAa(nTags.value, segmentsAa, aaExportParts, table)
            }
            segmentsAa.push({ text: core, cssClass: 'seq-seg-core' })
            aaExportParts.push(core)
            if (tagCol === 'C') {
                appendTagsAa(cTags.value, segmentsAa, aaExportParts, table)
            }
            if (cFix) {
                const { segments, exportText } = mixedToAaSegments(
                    cFix,
                    'seq-seg-cfix',
                    { ...C_TERMINAL_SEGMENT_STYLE },
                    table
                )
                segmentsAa.push(...segments)
                aaExportParts.push(exportText)
            }
            if (includeStop.value) {
                segmentsAa.push({ text: '*', cssClass: 'seq-seg-stop' })
                aaExportParts.push('*')
            }

            if (padRaw) {
                const { segments, exportText } = mixedToAaSegments(padRaw, 'seq-seg-padding', undefined, table)
                segmentsAa.push(...segments)
                aaExportParts.push(exportText)
            }

            let prepared_aa = aaExportParts.join('')

            let segments_dna: PreparedSegment[] | null = null
            let prepared_dna: string | null = null

            if (dnaMode.value) {
                const mainDnaChunks: string[] = []
                const mainSegChunks: PreparedSegment[][] = []

                if (nFix) {
                    const { dna, segments } = mixedToDnaSegments(
                        nFix,
                        table,
                        'seq-seg-nfix',
                        { ...N_TERMINAL_SEGMENT_STYLE }
                    )
                    mainDnaChunks.push(dna)
                    mainSegChunks.push(mergeDnaSegments(segments, 'seq-seg-nfix'))
                }
                if (tagCol === 'N') {
                    appendTagsDna(nTags.value, mainDnaChunks, mainSegChunks, table)
                }
                {
                    const { dna, segments } = literalAaToDnaSegments(core, table)
                    mainDnaChunks.push(dna)
                    mainSegChunks.push(mergeDnaSegments(segments, 'seq-seg-dna-body'))
                }
                if (tagCol === 'C') {
                    appendTagsDna(cTags.value, mainDnaChunks, mainSegChunks, table)
                }
                if (cFix) {
                    const { dna, segments } = mixedToDnaSegments(
                        cFix,
                        table,
                        'seq-seg-cfix',
                        { ...C_TERMINAL_SEGMENT_STYLE }
                    )
                    mainDnaChunks.push(dna)
                    mainSegChunks.push(mergeDnaSegments(segments, 'seq-seg-cfix'))
                }
                if (includeStop.value) {
                    const stop = table.stop
                    mainDnaChunks.push(stop)
                    mainSegChunks.push([{ text: stop, cssClass: 'seq-seg-stop' }])
                }

                let dna = mainDnaChunks.join('')
                const padSegChunks: PreparedSegment[][] = []
                if (padRaw) {
                    const { dna: padDna, segments: padSegs } = mixedToDnaSegments(padRaw, table, 'seq-seg-dna-body')
                    dna += padDna
                    padSegChunks.push(mergeDnaSegments(padSegs, 'seq-seg-padding'))
                }

                const bodyLen = dna.length
                const padDnaOnly = padRaw.replace(/[^aAcCgGtT]/g, '').toUpperCase()
                const minL = Math.max(0, minDnaFragmentLength.value)
                if (minL > 0 && dna.length < minL && padDnaOnly.length > 0) {
                    let i = 0
                    while (dna.length < minL) {
                        dna += padDnaOnly[i % padDnaOnly.length]
                        i += 1
                    }
                }
                prepared_dna = dna

                const flatSegs: PreparedSegment[] = []
                for (const chunk of mainSegChunks) {
                    flatSegs.push(...chunk)
                }
                for (const chunk of padSegChunks) {
                    flatSegs.push(...chunk)
                }
                if (dna.length > bodyLen) {
                    const extra = dna.slice(bodyLen)
                    flatSegs.push({ text: extra, cssClass: 'seq-seg-padding' })
                }
                segments_dna = flatSegs
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
        const s = customTagInput.value.trim()
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
        selectedCodonTable,
        activeCodonTable,
        validationErrors,
        canDownload,
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
