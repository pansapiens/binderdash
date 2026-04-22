/**
 * Prepare sequences tab: tagging, optional DNA view, exports.
 */

import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { useDesignsStore } from './designs'
import {
    designsApi,
    sequencesApi,
    type CodonTableDetailResponseDto,
    type DnaOptConstraintSpecDto
} from '../webapi'
import type { Design } from '../types/store'
import {
    isoelectricPoint,
    molarExtinctionCoefficient,
    sequenceWarnings
} from '../utils/protParam'
import {
    computeShortNames,
    sanitizeShortNameSegment,
    validateShortNameRegexStrip,
    validateShortNameRegex,
    type ShortNameRowInput,
    type ShortNameStrategy
} from './shortName'

export type TagZone = 'n' | 'c'

export type PresetTagKind = 'hisN' | 'hisC' | 'flag' | 'cmyc' | 'ha' | 'linker' | 'custom'

/**
 * UI-level constraint types shown in the DNA Optimization panel. Most map
 * 1:1 to dnachisel specifications; `ExcludeRestrictionSite` is a convenience
 * wrapper that is serialised to `AvoidPattern` with `pattern: "<enzyme>_site"`
 * just before being sent to the backend (dnachisel recognises the `_site`
 * suffix and resolves it via Biopython's restriction table).
 */
export const OPTIMIZATION_CONSTRAINT_TYPES = [
    'ExcludeRestrictionSite',
    'EnforceGCContent',
    'AvoidHairpins',
    'AvoidPattern',
    'AvoidRareCodons',
    'UniquifyAllKmers'
] as const

export type OptimizationConstraintType = (typeof OPTIMIZATION_CONSTRAINT_TYPES)[number]

export const DEFAULT_TWIST_CONSTRAINTS: DnaOptConstraintSpecDto[] = [
    { type: 'EnforceGCContent', enabled: true, params: { mini: 0.25, maxi: 0.64 } },
    { type: 'EnforceGCContent', enabled: true, params: { mini: 0.25, maxi: 0.75, window: 50 } },
    { type: 'AvoidHairpins', enabled: true, params: { stem_size: 20, hairpin_window: 48 } },
    { type: 'AvoidPattern', enabled: true, params: { pattern: 'AAAAAAAAA' } },
    { type: 'AvoidPattern', enabled: true, params: { pattern: 'TTTTTTTTT' } },
    { type: 'AvoidPattern', enabled: true, params: { pattern: 'GGGGGG' } },
    { type: 'AvoidPattern', enabled: true, params: { pattern: 'CCCCCC' } },
    { type: 'AvoidRareCodons', enabled: true, params: { min_frequency: 0.09 } },
    { type: 'UniquifyAllKmers', enabled: true, params: { k: 12 } },
    { type: 'AvoidPattern', enabled: true, params: { pattern: { type: 'RepeatedKmerPattern', params: { n_repeats: 2, k_size: 20 } } } },
    { type: 'AvoidPattern', enabled: true, params: { pattern: 'GGAGG' } },
    { type: 'AvoidPattern', enabled: true, params: { pattern: 'TAAGGAG' } }
]

/**
 * Translate UI-only constraint types (e.g. `ExcludeRestrictionSite`) into the
 * shape understood by the backend / dnachisel. Unknown types pass through so
 * future additions degrade gracefully.
 */
export function serializeConstraintForBackend(
    c: DnaOptConstraintSpecDto
): DnaOptConstraintSpecDto {
    if (c.type === 'ExcludeRestrictionSite') {
        const enzyme = typeof c.params?.enzyme === 'string' ? c.params.enzyme.trim() : ''
        return {
            type: 'AvoidPattern',
            enabled: c.enabled,
            params: enzyme ? { pattern: `${enzyme}_site` } : { pattern: '' }
        }
    }
    return c
}

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
    /** Space-joined design_id, project_id, run_name for DataTable text filter. */
    design_filter_text: string
    run_id: string
    run_name: string
    project_id: string
    /** For API/cache updates (dedupe with design_id). */
    source_path: string
    tag: string
    original_sequence: string
    prepared_aa: string
    /** AA string for UI: same as prepared_aa except post-stop padding is omitted. */
    prepared_aa_display: string
    prepared_dna: string | null
    segments_aa: PreparedSegment[]
    /** Coloured AA segments for UI: omits post-stop padding only (terminal * follows Include stop). */
    segments_aa_display: PreparedSegment[]
    segments_dna: PreparedSegment[] | null
    extinction_coeff_reduced: number
    extinction_coeff_oxidized: number
    isoelectric_point: number
    warnings: string[]
    /** Twist / vendor short name (≤32 chars after strategy + dedupe). */
    short_name: string
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
    },
    {
        kind: 'linker',
        tag_name: 'G4S',
        sequence: 'GGGGS',
        color: '#aaaaaa',
        background: 'rgba(48, 48, 48, 0.1)',
        foreground: '#aaaaaa',
        zones: ['n', 'c']
    }
]

export const CUSTOM_TAG_VISUAL = {
    color: '#aa0000',
    background: 'rgba(69, 90, 100, 0.1)',
    foreground: '#37474f'
} as const

/** Default post-stop padding (lowercase = nucleotides). */
export const DEFAULT_POST_STOP_PADDING =
    'ttgtgttgcgatagcccagtatgatattctaaggcgttacgctgatgaatattctacggaattgccataggcgttgaacgctacacggacgatacgaatt'

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

function buildReverse(
    forward: Record<string, string>,
    primaryStop: string,
    allStopCodons?: string[]
): Record<string, string> {
    const reverse: Record<string, string> = {}
    for (const [aa, codon] of Object.entries(forward)) {
        if (aa === '*') continue
        reverse[codon.toUpperCase()] = aa
    }
    const stops =
        allStopCodons && allStopCodons.length > 0
            ? [...new Set(allStopCodons.map(s => s.toUpperCase()))]
            : [primaryStop.toUpperCase()]
    for (const sc of stops) {
        reverse[sc] = '*'
    }
    return reverse
}

/** Offline / API-failure fallback; matches prior hardcoded E. coli table. */
const FALLBACK_ECOLLI_CODON_TABLE: CodonTable = {
    label: 'E. coli',
    forward: { ...ECOLI_FORWARD },
    reverse: buildReverse(ECOLI_FORWARD, 'TAA', ['TAA', 'TAG', 'TGA']),
    stop: 'TAA'
}

function codonDetailDtoToTable(detail: CodonTableDetailResponseDto): CodonTable {
    const stops = detail.stop_codons.map(s => s.toUpperCase())
    const stop = stops[0] || 'TAA'
    const forward: Record<string, string> = {}
    for (const [aa, freqs] of Object.entries(detail.codons_by_aa)) {
        if (aa === '*') continue
        const pairs = Object.entries(freqs)
        pairs.sort((a, b) => {
            if (b[1] !== a[1]) return b[1] - a[1]
            return a[0].localeCompare(b[0])
        })
        if (pairs.length > 0) {
            forward[aa] = pairs[0][0].toUpperCase()
        }
    }
    if (!forward.X) {
        forward.X = forward.A || forward.L || 'GCT'
    }
    forward['*'] = stop
    const reverse = buildReverse(forward, stop, stops)
    return { label: detail.label, forward, reverse, stop }
}

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
    if (kind === 'linker') return 'seq-seg-linker'
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
 * CSS variables for preset tag chips. `App.vue` uses `!important` on `.p-chip` / `.p-component *`;
 * `PrepareSequencesView` applies these vars with matching `!important` so chips match palette buttons.
 */
export function tagPresetChipCssVars(kind: PresetTagKind): Record<string, string> {
    const v = tagPresetVisual(kind)
    return {
        '--ps-chip-border': v.borderColor,
        '--ps-chip-bg': v.background,
        '--ps-chip-fg': v.color
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
        for (let i = 0; i < low.length; i += 3) {
            const tri = low.slice(i, i + 3)
            if (tri.length < 3) {
                const up = tri.toUpperCase()
                dna += up
                bodyBuf += up
                continue
            }
            const up = tri.toUpperCase()
            if (codonTable.reverse[up] === '*') {
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
    /** AA view/export: when false, omit post-stop padding (NT view ignores). */
    const showPostStopPadding = ref(true)
    const postStopPadding = ref(DEFAULT_POST_STOP_PADDING)
    const postStopPadUpToNucleotideLength = ref<number | null>(300)
    const minDnaFragmentLength = ref(300)
    const customTagInput = ref('')
    const exportOrderName = ref('')
    const extracting = ref(false)
    const codonTableOptions = ref<{ label: string; value: string }[]>([])
    const codonTablesById = ref<Record<string, CodonTable>>({})
    const codonTablesListLoading = ref(false)
    const codonTablesDetailLoading = ref(false)
    const selectedCodonTable = ref('')
    let codonTableListLoaded = false
    const codonDetailInflight = new Map<string, Promise<void>>()
    let codonDetailLoadCount = 0

    const activeCodonTable = computed((): CodonTable => {
        const id = selectedCodonTable.value
        const t = id ? codonTablesById.value[id] : undefined
        return t ?? FALLBACK_ECOLLI_CODON_TABLE
    })

    async function fetchCodonTableDetail(tableId: string): Promise<void> {
        if (!tableId || codonTablesById.value[tableId]) return
        const existing = codonDetailInflight.get(tableId)
        if (existing) {
            await existing
            return
        }
        const run = (async () => {
            codonDetailLoadCount += 1
            codonTablesDetailLoading.value = true
            try {
                const d = await sequencesApi.getCodonTable(tableId)
                const table = codonDetailDtoToTable(d)
                const next = { ...codonTablesById.value, [tableId]: table }
                if (d.value !== tableId) {
                    next[d.value] = table
                }
                codonTablesById.value = next
            } catch {
                codonTablesById.value = {
                    ...codonTablesById.value,
                    [tableId]: FALLBACK_ECOLLI_CODON_TABLE
                }
            } finally {
                codonDetailLoadCount -= 1
                codonTablesDetailLoading.value = codonDetailLoadCount > 0
            }
        })()
        codonDetailInflight.set(tableId, run)
        try {
            await run
        } finally {
            codonDetailInflight.delete(tableId)
        }
    }

    async function ensureCodonTablesLoaded(): Promise<void> {
        if (!codonTableListLoaded) {
            codonTablesListLoading.value = true
            try {
                const res = await sequencesApi.listCodonTables()
                codonTableOptions.value = res.items
                codonTableListLoaded = true
                const preferred = res.items.find(i => i.value === 'e_coli_316407')
                if (
                    !selectedCodonTable.value ||
                    !res.items.some(i => i.value === selectedCodonTable.value)
                ) {
                    selectedCodonTable.value = preferred?.value ?? res.items[0]?.value ?? ''
                }
            } catch {
                codonTableOptions.value = [{ label: 'E. coli (offline)', value: 'e_coli_316407' }]
                codonTablesById.value = { e_coli_316407: FALLBACK_ECOLLI_CODON_TABLE }
                selectedCodonTable.value = 'e_coli_316407'
                codonTableListLoaded = true
            } finally {
                codonTablesListLoading.value = false
            }
        }
    }

    watch(selectedCodonTable, id => {
        if (!id) return
        void fetchCodonTableDetail(id)
    })

    /** Twist-style cap: auto short-name strategy when prepare set design_ids are all within this length. */
    const SHORT_NAME_AUTO_DESIGN_ID_LEN = 32

    let applyingAutoShortNameStrategy = false
    const shortNameStrategyAutoManaged = ref(true)

    const shortNameKind = ref<ShortNameStrategy['kind']>('none')
    const shortNameMaxLen = ref(32)
    const shortNameRegexPattern = ref('^batch-[0-9]')
    const shortNameRegexReplacement = ref('')
    const shortNameRegexFlags = ref('g')
    const shortNameSplitDelimiter = ref('_')
    const shortNameSplitIndices = ref('1,2,3')
    const shortNameSplitAddHash = ref(false)
    const shortNamePatternPrefix = ref('design')
    const shortNamePatternUidLength = ref(5)
    const shortNamePatternNumberPad = ref(0)
    const shortNameSmartHashLen = ref(5)
    const shortNameSmartStemIncludeHash = ref(true)
    const shortNameSmartStemIncludeIndex = ref(false)
    const shortNameSmartStemRemoveCommonPrefix = ref(false)
    const shortNameSmartStemRemoveCommonSuffix = ref(true)
    const shortNameSmartStemAddPrefix = ref('')
    const shortNameSmartStemAddSuffix = ref('')
    const shortNameStripPrefixRegex = ref('^batch-\\d+_')
    const shortNameStripSuffixRegex = ref('')
    const shortNameStripNewPrefix = ref('')

    const effectiveShortNameStrategy = computed((): ShortNameStrategy => {
        const k = shortNameKind.value
        if (k === 'regex') {
            return {
                kind: 'regex',
                pattern: shortNameRegexPattern.value,
                replacement: shortNameRegexReplacement.value,
                flags: shortNameRegexFlags.value
            }
        }
        if (k === 'splitTake') {
            const parts = shortNameSplitIndices.value
                .split(/[,\s]+/)
                .map(s => parseInt(s.trim(), 10))
                .filter(n => Number.isFinite(n) && n > 0)
            return {
                kind: 'splitTake',
                delimiter: shortNameSplitDelimiter.value || '_',
                indices: parts.length > 0 ? parts : [1, 2, 3],
                addHash: shortNameSplitAddHash.value,
                hashLen: shortNameSmartHashLen.value
            }
        }
        if (k === 'pattern') {
            return {
                kind: 'pattern',
                prefix: shortNamePatternPrefix.value,
                uidLength: shortNamePatternUidLength.value,
                numberPad: shortNamePatternNumberPad.value
            }
        }
        if (k === 'smartStemHash') {
            return {
                kind: 'smartStemHash',
                includeHash: shortNameSmartStemIncludeHash.value,
                hashLen: shortNameSmartHashLen.value,
                includeIndex: shortNameSmartStemIncludeIndex.value,
                removeCommonPrefix: shortNameSmartStemRemoveCommonPrefix.value,
                removeCommonSuffix: shortNameSmartStemRemoveCommonSuffix.value,
                addPrefix: shortNameSmartStemAddPrefix.value,
                addSuffix: shortNameSmartStemAddSuffix.value
            }
        }
        if (k === 'smartRegexStrip') {
            return {
                kind: 'smartRegexStrip',
                prefixPattern: shortNameStripPrefixRegex.value,
                suffixPattern: shortNameStripSuffixRegex.value,
                newPrefix: shortNameStripNewPrefix.value,
                hashLen: shortNameSmartHashLen.value
            }
        }
        return { kind: 'none' }
    })

    const validationErrors = computed((): string[] => {
        const errs: string[] = []
        const strat = effectiveShortNameStrategy.value
        const reErr = validateShortNameRegex(strat)
        if (reErr) errs.push(reErr)
        const stripErr = validateShortNameRegexStrip(strat)
        if (stripErr) errs.push(stripErr)
        for (const t of [...nTags.value, ...cTags.value]) {
            if (t.kind === 'custom') {
                const e = validateMixedSequence(t.sequence, `Tag "${t.label}"`)
                if (e) errs.push(e)
            }
        }
        const fields = [
            [nTerminalPrefix.value, 'N-terminal prefix'],
            [cTerminalSuffix.value, 'C-terminal suffix']
        ] as const
        for (const [val, name] of fields) {
            const e = validateMixedSequence(val.trim(), name)
            if (e) errs.push(e)
        }
        const padTrim = postStopPadding.value.trim()
        const padTargetVal = postStopPadUpToNucleotideLength.value
        const usePadTarget =
            padTargetVal != null && Number.isFinite(padTargetVal) && padTargetVal > 0
        if (usePadTarget) {
                const e = validateMixedSequence(padTrim, 'Post-stop padding')
                if (e) errs.push(e)
                const { dna: padUnit } = mixedToDnaSegments(padTrim, activeCodonTable.value, 'seq-seg-dna-body')
                if (padUnit.length === 0) {
                    errs.push(
                        'Post-stop padding: must expand to at least one nucleotide to pad to a target length'
                    )
                }
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

    const prepareSetShortNameFingerprint = computed(() =>
        [...inputDesigns.value]
            .map(d => {
                const sp = String((d as Record<string, unknown>).source_path ?? '')
                return `${d.run_id}\x1f${d.design_id}\x1f${sp}`
            })
            .sort((a, b) => a.localeCompare(b))
            .join('\x1e')
    )

    function applyAutoShortNameStrategyIfManaged(): void {
        if (!shortNameStrategyAutoManaged.value) return
        const rows = inputDesigns.value
        if (rows.length === 0) return
        const allWithin = rows.every(
            d => String(d.design_id ?? '').length <= SHORT_NAME_AUTO_DESIGN_ID_LEN
        )
        const next: ShortNameStrategy['kind'] = allWithin ? 'none' : 'smartStemHash'
        if (shortNameKind.value === next) return
        applyingAutoShortNameStrategy = true
        shortNameKind.value = next
        applyingAutoShortNameStrategy = false
    }

    watch(
        prepareSetShortNameFingerprint,
        () => {
            applyAutoShortNameStrategyIfManaged()
        },
        { immediate: true }
    )

    watch(shortNameKind, () => {
        if (applyingAutoShortNameStrategy) return
        shortNameStrategyAutoManaged.value = false
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

    function buildMainDnaForRow(
        table: CodonTable,
        nFix: string,
        cFix: string,
        tagCol: string,
        core: string,
        includeStop: boolean
    ): { mainDna: string; mainSegChunks: PreparedSegment[][] } {
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
        if (includeStop) {
            const stop = table.stop
            mainDnaChunks.push(stop)
            mainSegChunks.push([{ text: stop, cssClass: 'seq-seg-stop' }])
        }

        return { mainDna: mainDnaChunks.join(''), mainSegChunks }
    }

    const preparedRowsInternal = computed((): Omit<PreparedRow, 'short_name'>[] => {
        const table = activeCodonTable.value
        const nFix = nTerminalPrefix.value.trim()
        const cFix = cTerminalSuffix.value.trim()
        const padRaw = postStopPadding.value.trim()
        const padTargetVal = postStopPadUpToNucleotideLength.value
        const usePostStopPadTarget =
            padTargetVal != null && Number.isFinite(padTargetVal) && padTargetVal > 0
        const padTargetBp = usePostStopPadTarget ? Math.floor(Number(padTargetVal)) : 0

        return inputDesigns.value.map((d): Omit<PreparedRow, 'short_name'> => {
            const raw = getRawSequence(d)
            const core = raw.replace(/\*+$/g, '').trim()
            const tagCol = String((d as Record<string, unknown>).tag ?? '')
                .trim()
                .toUpperCase()

            const segmentsAa: PreparedSegment[] = []
            const segmentsAaDisplay: PreparedSegment[] = []
            const aaExportParts: string[] = []
            const aaExportPartsDisplay: string[] = []

            if (nFix) {
                const { segments, exportText } = mixedToAaSegments(
                    nFix,
                    'seq-seg-nfix',
                    { ...N_TERMINAL_SEGMENT_STYLE },
                    table
                )
                segmentsAa.push(...segments)
                segmentsAaDisplay.push(...segments)
                aaExportParts.push(exportText)
                aaExportPartsDisplay.push(exportText)
            }
            if (tagCol === 'N') {
                appendTagsAa(nTags.value, segmentsAa, aaExportParts, table)
                appendTagsAa(nTags.value, segmentsAaDisplay, aaExportPartsDisplay, table)
            }
            segmentsAa.push({ text: core, cssClass: 'seq-seg-core' })
            segmentsAaDisplay.push({ text: core, cssClass: 'seq-seg-core' })
            aaExportParts.push(core)
            aaExportPartsDisplay.push(core)
            if (tagCol === 'C') {
                appendTagsAa(cTags.value, segmentsAa, aaExportParts, table)
                appendTagsAa(cTags.value, segmentsAaDisplay, aaExportPartsDisplay, table)
            }
            if (cFix) {
                const { segments, exportText } = mixedToAaSegments(
                    cFix,
                    'seq-seg-cfix',
                    { ...C_TERMINAL_SEGMENT_STYLE },
                    table
                )
                segmentsAa.push(...segments)
                segmentsAaDisplay.push(...segments)
                aaExportParts.push(exportText)
                aaExportPartsDisplay.push(exportText)
            }
            if (includeStop.value) {
                segmentsAa.push({ text: '*', cssClass: 'seq-seg-stop' })
                segmentsAaDisplay.push({ text: '*', cssClass: 'seq-seg-stop' })
                aaExportParts.push('*')
                aaExportPartsDisplay.push('*')
            }

            const needMainDnaForPad =
                dnaMode.value || (usePostStopPadTarget && padRaw.length > 0)
            let mainDna = ''
            let mainSegChunks: PreparedSegment[][] = []
            if (needMainDnaForPad) {
                const optDna = !optimizationStale.value ? optimizedDnaByDesign.value[d.design_id] : undefined
                if (optDna) {
                    mainDna = optDna
                    // Re-apply feature colouring: build the original segment layout (same
                    // nucleotide lengths since optimisation preserves translation) and reslice
                    // the optimised sequence across those boundaries.
                    const { mainSegChunks: origChunks } = buildMainDnaForRow(
                        table, nFix, cFix, tagCol, core, includeStop.value
                    )
                    let offset = 0
                    mainSegChunks = origChunks.map(chunk =>
                        chunk.map(seg => {
                            const slice = optDna.slice(offset, offset + seg.text.length)
                            offset += seg.text.length
                            return { ...seg, text: slice }
                        })
                    )
                } else {
                    ;({ mainDna, mainSegChunks } = buildMainDnaForRow(
                        table,
                        nFix,
                        cFix,
                        tagCol,
                        core,
                        includeStop.value
                    ))
                }
            }

            let numFullPadRepeats = 0
            let padRemainderBp = 0
            let padUnitDna = ''
            if (usePostStopPadTarget && padRaw) {
                const unit = mixedToDnaSegments(padRaw, table, 'seq-seg-dna-body')
                padUnitDna = unit.dna
                const padUnitLen = padUnitDna.length
                if (padUnitLen > 0 && mainDna.length < padTargetBp) {
                    const remaining = padTargetBp - mainDna.length
                    numFullPadRepeats = Math.floor(remaining / padUnitLen)
                    padRemainderBp = remaining % padUnitLen
                }
            }

            for (let pr = 0; pr < numFullPadRepeats; pr += 1) {
                const { segments, exportText } = mixedToAaSegments(
                    padRaw,
                    'seq-seg-padding',
                    undefined,
                    table
                )
                segmentsAa.push(...segments)
                aaExportParts.push(exportText)
            }
            if (padRemainderBp > 0 && padUnitDna.length > 0) {
                const partialDna = padUnitDna.slice(0, padRemainderBp)
                const { segments, exportText } = mixedToAaSegments(
                    partialDna.toLowerCase(),
                    'seq-seg-padding',
                    undefined,
                    table
                )
                segmentsAa.push(...segments)
                aaExportParts.push(exportText)
            }

            let prepared_aa = aaExportParts.join('')
            const prepared_aa_display = aaExportPartsDisplay.join('')

            const ext = molarExtinctionCoefficient(prepared_aa)
            const pi = isoelectricPoint(prepared_aa)
            const warns = sequenceWarnings(prepared_aa)
            const optError = !optimizationStale.value ? optimizedErrorsByDesign.value[d.design_id] : undefined
            if (optError) {
                warns.push(`DNA Opt: ${optError}`)
            }

            let segments_dna: PreparedSegment[] | null = null
            let prepared_dna: string | null = null

            if (dnaMode.value) {
                let dna = mainDna
                const padSegChunks: PreparedSegment[][] = []
                if (
                    usePostStopPadTarget &&
                    padRaw &&
                    padUnitDna.length > 0 &&
                    (numFullPadRepeats > 0 || padRemainderBp > 0)
                ) {
                    const { segments: padSegsFull } = mixedToDnaSegments(
                        padRaw,
                        table,
                        'seq-seg-dna-body'
                    )
                    for (let pr = 0; pr < numFullPadRepeats; pr += 1) {
                        dna += padUnitDna
                        padSegChunks.push(mergeDnaSegments(padSegsFull, 'seq-seg-padding'))
                    }
                    if (padRemainderBp > 0) {
                        const partial = padUnitDna.slice(0, padRemainderBp)
                        dna += partial
                        padSegChunks.push([{ text: partial, cssClass: 'seq-seg-padding' }])
                    }
                }

                const bodyLen = dna.length
                const padDnaOnly =
                    usePostStopPadTarget && padRaw
                        ? padRaw.replace(/[^aAcCgGtT]/g, '').toUpperCase()
                        : ''
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
                design_filter_text: [d.design_id, d.project_id, d.run_name].filter(Boolean).join(' '),
                run_id: d.run_id,
                run_name: d.run_name,
                project_id: d.project_id,
                source_path: String((d as Record<string, unknown>).source_path ?? ''),
                tag: tagCol || '-',
                original_sequence: raw || '(missing)',
                prepared_aa,
                prepared_aa_display,
                prepared_dna,
                segments_aa: segmentsAa,
                segments_aa_display: segmentsAaDisplay,
                segments_dna,
                extinction_coeff_reduced: ext.reduced,
                extinction_coeff_oxidized: ext.oxidized,
                isoelectric_point: pi,
                warnings: warns
            }
        })
    })

    const shortNameComputation = computed(() => {
        const rows = preparedRowsInternal.value
        const inputs = rows.map(
            (r): ShortNameRowInput => ({
                row_key: r.row_key,
                design_id: r.design_id,
                original_aa: r.original_sequence,
                prepared_aa: r.prepared_aa,
                prepared_dna: r.prepared_dna,
                tag: r.tag
            })
        )
        return computeShortNames(inputs, effectiveShortNameStrategy.value, shortNameMaxLen.value)
    })

    const preparedRows = computed((): PreparedRow[] => {
        const rows = preparedRowsInternal.value
        const { map } = shortNameComputation.value
        return rows.map(r => {
            const sn =
                map.get(r.row_key) ??
                (sanitizeShortNameSegment(r.design_id) || r.design_id)
            return { ...r, short_name: sn }
        })
    })

    let shortNamePersistTimer: ReturnType<typeof setTimeout> | null = null
    async function flushShortNamesToBackend(): Promise<void> {
        const rows = preparedRowsInternal.value
        if (rows.length === 0) return
        const strat = effectiveShortNameStrategy.value
        try {
            if (strat.kind === 'none') {
                return
            }
            const { map } = shortNameComputation.value
            await designsApi.updateShortNames({
                updates: rows.map(r => ({
                    run_id: r.run_id,
                    design_id: r.design_id,
                    source_path: r.source_path || undefined,
                    short_name: map.get(r.row_key) ?? null
                })),
                refresh_cache_after: false
            })
        } catch {
            /* offline or auth; short names still work in-session */
        }
    }

    watch(
        () => [
            shortNameKind.value,
            shortNameMaxLen.value,
            preparedRowsInternal.value,
            effectiveShortNameStrategy.value
        ],
        () => {
            if (shortNamePersistTimer) clearTimeout(shortNamePersistTimer)
            shortNamePersistTimer = setTimeout(() => {
                void flushShortNamesToBackend()
            }, 450)
        },
        { deep: true }
    )

    async function clearShortNames(): Promise<void> {
        applyingAutoShortNameStrategy = true
        shortNameKind.value = 'none'
        applyingAutoShortNameStrategy = false
        const rows = preparedRowsInternal.value
        if (rows.length === 0) return
        try {
            await designsApi.updateShortNames({
                updates: rows.map(r => ({
                    run_id: r.run_id,
                    design_id: r.design_id,
                    source_path: r.source_path || undefined,
                    short_name: null
                })),
                refresh_cache_after: false
            })
            const ds = useDesignsStore()
            await ds.fetchDesigns()
        } catch {
            /* ignore */
        }
    }

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

    const optimizationConstraints = ref<DnaOptConstraintSpecDto[]>(JSON.parse(JSON.stringify(DEFAULT_TWIST_CONSTRAINTS)))
    const optimizationMethod = ref<string>('match_codon_usage')
    const optimizedDnaByDesign = ref<Record<string, string>>({})
    const optimizedErrorsByDesign = ref<Record<string, string>>({})
    const optimizing = ref(false)
    const optimizationGlobalError = ref<string | null>(null)
    const optimizationStale = ref(false)
    /** True after at least one successful per-sequence optimisation in this session (used for stale messaging). */
    const optimizationEverSucceeded = ref(false)

    watch([nTags, cTags, nTerminalPrefix, cTerminalSuffix, includeStop, selectedCodonTable, optimizationConstraints], () => {
        optimizationStale.value = true
    }, { deep: true })

    async function runOptimization() {
        const seqs: Record<string, string> = {}
        for (const row of preparedRows.value) {
            if (row.prepared_aa_display) {
                seqs[row.design_id] = row.prepared_aa_display
            }
        }
        if (Object.keys(seqs).length === 0) {
            optimizationGlobalError.value = 'No sequences in scope to optimise.'
            return
        }

        optimizing.value = true
        optimizationGlobalError.value = null
        try {
            const req = {
                sequences: seqs,
                codon_table_id: selectedCodonTable.value || FALLBACK_ECOLLI_CODON_TABLE.label,
                method: optimizationMethod.value,
                constraints: optimizationConstraints.value.map(serializeConstraintForBackend)
            }
            const res = await sequencesApi.optimizeDna(req)
            const optMap: Record<string, string> = {}
            const errMap: Record<string, string> = {}
            for (const r of res.results) {
                if (r.optimized_dna) {
                    optMap[r.design_id] = r.optimized_dna
                }
                if (r.error) {
                    errMap[r.design_id] = r.error
                }
            }
            optimizedDnaByDesign.value = optMap
            optimizedErrorsByDesign.value = errMap
            optimizationStale.value = false
            optimizationEverSucceeded.value = Object.keys(optMap).length > 0
        } catch (e: any) {
            optimizationGlobalError.value = String(e)
        } finally {
            optimizing.value = false
        }
    }

    function resetConstraintsToDefaults() {
        optimizationConstraints.value = JSON.parse(JSON.stringify(DEFAULT_TWIST_CONSTRAINTS))
    }

    function addConstraint() {
        optimizationConstraints.value.push({
            type: 'ExcludeRestrictionSite',
            enabled: true,
            params: { enzyme: 'NdeI' }
        })
    }

    function removeConstraint(idx: number) {
        optimizationConstraints.value.splice(idx, 1)
    }

    const shortNameDedupeCount = computed(() => shortNameComputation.value.dedupeCount)

    return {
        nTags,
        cTags,
        nTerminalPrefix,
        cTerminalSuffix,
        includeStop,
        goodOnly,
        extractChain,
        dnaMode,
        showPostStopPadding,
        postStopPadding,
        postStopPadUpToNucleotideLength,
        minDnaFragmentLength,
        customTagInput,
        exportOrderName,
        extracting,
        codonTableOptions,
        codonTablesListLoading,
        codonTablesDetailLoading,
        selectedCodonTable,
        activeCodonTable,
        optimizationConstraints,
        optimizationMethod,
        optimizedDnaByDesign,
        optimizedErrorsByDesign,
        optimizing,
        optimizationGlobalError,
        optimizationStale,
        optimizationEverSucceeded,
        ensureCodonTablesLoaded,
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
        getRawSequence,
        runOptimization,
        resetConstraintsToDefaults,
        addConstraint,
        removeConstraint,
        shortNameKind,
        shortNameMaxLen,
        shortNameRegexPattern,
        shortNameRegexReplacement,
        shortNameRegexFlags,
        shortNameSplitDelimiter,
        shortNameSplitIndices,
        shortNameSplitAddHash,
        shortNamePatternPrefix,
        shortNamePatternUidLength,
        shortNamePatternNumberPad,
        shortNameSmartHashLen,
        shortNameSmartStemIncludeHash,
        shortNameSmartStemIncludeIndex,
        shortNameSmartStemRemoveCommonPrefix,
        shortNameSmartStemRemoveCommonSuffix,
        shortNameSmartStemAddPrefix,
        shortNameSmartStemAddSuffix,
        shortNameStripPrefixRegex,
        shortNameStripSuffixRegex,
        shortNameStripNewPrefix,
        effectiveShortNameStrategy,
        shortNameDedupeCount,
        clearShortNames
    }
})
