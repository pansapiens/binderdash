/**
 * Twist / vendor short names: base52 FNV-1a 64-bit; pattern uid hashes sorted prepared DNA for the whole set.
 */

const FNV_OFFSET = 14695981039346656037n
const FNV_PRIME = 1099511628211n
const MASK64 = (1n << 64n) - 1n

/** A–Z then a–z (52 symbols). */
const BASE52_ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'

export type ShortNameStrategy =
    | { kind: 'none' }
    | { kind: 'regex'; pattern: string; replacement: string; flags: string }
    | {
          kind: 'splitTake'
          delimiter: string
          indices: number[]
          addPrefix: string
          addSuffix: string
          addHash: boolean
          hashLen: number
      }
    | { kind: 'pattern'; prefix: string; uidLength: number; numberPad: number }
    | {
          kind: 'smartStemHash'
          includeHash: boolean
          hashLen: number
          includeIndex: boolean
          removeCommonPrefix: boolean
          removeCommonSuffix: boolean
          addPrefix: string
          addSuffix: string
      }
    | {
          kind: 'smartRegexStrip'
          prefixPattern: string
          suffixPattern: string
          newPrefix: string
          hashLen: number
      }

export interface ShortNameRowInput {
    row_key: string
    design_id: string
    original_aa: string
    prepared_aa: string
    prepared_dna: string | null
    tag: string
}

export function fnv1a64(input: string): bigint {
    const bytes = new TextEncoder().encode(input)
    let hash = FNV_OFFSET
    for (let i = 0; i < bytes.length; i += 1) {
        hash ^= BigInt(bytes[i])
        hash = (hash * FNV_PRIME) & MASK64
    }
    return hash
}

export function base52(n: bigint, length: number): string {
    const L = Math.max(1, Math.min(32, length))
    let v = n & MASK64
    const chars: string[] = []
    for (let i = 0; i < L; i += 1) {
        const idx = Number(v % 52n)
        chars.push(BASE52_ALPHABET[idx]!)
        v = v / 52n
    }
    return chars.reverse().join('')
}

export function hashBase52(input: string, length = 5): string {
    return base52(fnv1a64(input), length)
}

/** Stable fingerprint for the current prepared set (order-independent). */
export function computeSetFingerprint(rows: ShortNameRowInput[]): string {
    const sorted = [...rows].sort((a, b) => a.design_id.localeCompare(b.design_id))
    const payload = sorted
        .map(
            r =>
                `${r.design_id}\x1f${r.prepared_aa}\x1f${r.prepared_dna ?? ''}\x1f${r.tag}`
        )
        .join('\x1e')
    return hashBase52(payload, 10)
}

/** Allow only [A-Za-z0-9_-]; other runs of chars become single underscore. */
export function sanitizeShortNameSegment(raw: string): string {
    const t = raw.trim()
    if (!t) return ''
    return t
        .replace(/[^A-Za-z0-9_-]+/g, '_')
        .replace(/_+/g, '_')
        .replace(/^_|_$/g, '')
}

function clampHashLen(n: number): number {
    if (!Number.isFinite(n)) return 5
    return Math.max(3, Math.min(10, Math.floor(n)))
}

export interface SmartStemAffixStrip {
    lcpLen: number
    lcsLen: number
}

function longestCommonPrefixLength(strings: string[]): number {
    if (strings.length < 2) return 0
    const first = strings[0]!
    let n = 0
    outer: while (n < first.length) {
        const c = first[n]
        for (let i = 1; i < strings.length; i += 1) {
            const s = strings[i]!
            if (n >= s.length || s[n] !== c) break outer
        }
        n += 1
    }
    return n
}

function longestCommonSuffixLength(strings: string[]): number {
    if (strings.length < 2) return 0
    const minLen = strings.reduce((m, s) => Math.min(m, s.length), strings[0]!.length)
    let n = 0
    outer: while (n < minLen) {
        const c = strings[0]![strings[0].length - 1 - n]
        for (let i = 1; i < strings.length; i += 1) {
            const s = strings[i]!
            if (s[s.length - 1 - n] !== c) break outer
        }
        n += 1
    }
    return n
}

/** Longest prefix/suffix shared by every `design_id` (requires ≥2 rows). */
export function computeSmartStemAffixStrip(
    rows: ShortNameRowInput[],
    strategy: ShortNameStrategy
): SmartStemAffixStrip | undefined {
    if (strategy.kind !== 'smartStemHash') return undefined
    if (rows.length < 2) return undefined
    const ids = rows.map(r => r.design_id)
    let lcp = 0
    let lcs = 0
    if (strategy.removeCommonPrefix) lcp = longestCommonPrefixLength(ids)
    if (strategy.removeCommonSuffix) lcs = longestCommonSuffixLength(ids)
    if (lcp === 0 && lcs === 0) return undefined
    return { lcpLen: lcp, lcsLen: lcs }
}

function computePatternSetUid(rows: ShortNameRowInput[], uidLength: number): string {
    const uidLen = clampHashLen(uidLength || 5)
    const ntSeqs = rows.map(r => r.prepared_dna ?? '').sort((a, b) => a.localeCompare(b))
    return hashBase52(ntSeqs.join('\x1e'), uidLen)
}

function rawNameForRow(
    row: ShortNameRowInput,
    indexInOrder: number,
    strategy: ShortNameStrategy,
    _rowsInOrder: ShortNameRowInput[],
    maxLen: number,
    smartStemAffixStrip?: SmartStemAffixStrip,
    patternSetUid?: string
): string {
    const id = row.design_id
    const hashInput = row.original_aa || id
    if (strategy.kind === 'none') {
        return id
    }
    if (strategy.kind === 'regex') {
        try {
            const re = new RegExp(strategy.pattern, strategy.flags || '')
            return id.replace(re, strategy.replacement ?? '')
        } catch {
            return id
        }
    }
    if (strategy.kind === 'splitTake') {
        const delim = strategy.delimiter || '_'
        const parts = id.split(delim)
        const out: string[] = []
        for (const idx of strategy.indices) {
            const j = idx - 1
            if (j >= 0 && j < parts.length && parts[j] !== undefined) {
                out.push(parts[j]!)
            }
        }
        let stem = out.length > 0 ? out.join(delim) : id
        const ap = sanitizeShortNameSegment((strategy.addPrefix ?? '').trim())
        const as = sanitizeShortNameSegment((strategy.addSuffix ?? '').trim())
        if (ap) stem = stem ? `${ap}_${stem}` : ap
        if (as) stem = stem ? `${stem}_${as}` : as
        if (!strategy.addHash) return stem
        const hl = clampHashLen(strategy.hashLen)
        const h = hashBase52(hashInput, hl)
        const sep = '_'
        const maxStem = Math.max(1, maxLen - sep.length - h.length)
        return `${stem.slice(0, maxStem)}${sep}${h}`
    }
    if (strategy.kind === 'pattern') {
        const uidLen = clampHashLen(strategy.uidLength || 5)
        const pad = Math.max(0, Math.min(6, Math.floor(strategy.numberPad ?? 0)))
        const uid = patternSetUid ?? computePatternSetUid(_rowsInOrder, uidLen)
        const numRaw = String(indexInOrder + 1)
        const num = pad > 0 ? numRaw.padStart(pad, '0') : numRaw
        const pfx = sanitizeShortNameSegment((strategy.prefix ?? '').trim())
        const raw = pfx ? `${pfx}_${uid}_${num}` : `${uid}_${num}`
        return raw.slice(0, maxLen)
    }
    if (strategy.kind === 'smartStemHash') {
        let idForStem = id
        if (smartStemAffixStrip) {
            const { lcpLen, lcsLen } = smartStemAffixStrip
            if (lcpLen > 0) idForStem = idForStem.slice(lcpLen)
            if (lcsLen > 0) idForStem = idForStem.slice(0, Math.max(0, idForStem.length - lcsLen))
        }
        let stem = sanitizeShortNameSegment(idForStem)
        const ap = sanitizeShortNameSegment((strategy.addPrefix ?? '').trim())
        const as = sanitizeShortNameSegment((strategy.addSuffix ?? '').trim())
        if (ap) stem = stem ? `${ap}_${stem}` : ap
        if (as) stem = stem ? `${stem}_${as}` : as

        const sep = '_'
        const numStr = strategy.includeIndex ? String(indexInOrder + 1) : ''

        if (!strategy.includeHash) {
            const tail = numStr ? `${sep}${numStr}` : ''
            const maxStem = tail ? Math.max(1, maxLen - tail.length) : maxLen
            stem = stem.slice(0, maxStem)
            return stem + tail
        }

        const hl = clampHashLen(strategy.hashLen)
        const h = hashBase52(hashInput, hl)
        const tail = numStr ? `${sep}${h}${sep}${numStr}` : `${sep}${h}`
        const maxStem = Math.max(1, maxLen - tail.length)
        stem = stem.slice(0, maxStem)
        return stem + tail
    }
    if (strategy.kind === 'smartRegexStrip') {
        const hl = clampHashLen(strategy.hashLen)
        const h = hashBase52(hashInput, hl)
        const sep = '_'
        let s = id
        try {
            const p = (strategy.prefixPattern ?? '').trim()
            if (p) s = s.replace(new RegExp(p), '')
        } catch {
            s = id
        }
        try {
            const suf = (strategy.suffixPattern ?? '').trim()
            if (suf) s = s.replace(new RegExp(suf), '')
        } catch {
            /* keep s after prefix strip */
        }
        const droppedStem = sanitizeShortNameSegment(s)
        const customPrefix = sanitizeShortNameSegment(strategy.newPrefix ?? '')
        const stem = customPrefix
            ? droppedStem
                ? `${customPrefix}_${droppedStem}`
                : customPrefix
            : droppedStem
        if (!stem) return h
        const maxStem = Math.max(1, maxLen - sep.length - h.length)
        return `${stem.slice(0, maxStem)}${sep}${h}`
    }
    return id
}

function uniqueify(
    baseRaw: string,
    maxLen: number,
    used: Set<string>
): { name: string; deduped: boolean } {
    const base = sanitizeShortNameSegment(baseRaw).slice(0, maxLen)
    let candidate = base || 'x'
    candidate = candidate.slice(0, maxLen)
    if (!used.has(candidate)) {
        used.add(candidate)
        return { name: candidate, deduped: false }
    }
    let n = 2
    let deduped = true
    while (true) {
        const suf = `_${n}`
        let stem = sanitizeShortNameSegment(baseRaw)
        while (stem.length + suf.length > maxLen && stem.length > 0) {
            stem = stem.slice(0, -1)
        }
        candidate = (stem || 'x') + suf
        candidate = candidate.slice(0, maxLen)
        if (!used.has(candidate)) {
            used.add(candidate)
            return { name: candidate, deduped }
        }
        n += 1
        if (n > 999999) {
            candidate = hashBase52(`${baseRaw}\x1f${n}`, Math.min(8, maxLen))
            if (!used.has(candidate)) {
                used.add(candidate)
                return { name: candidate, deduped: true }
            }
        }
    }
}

export interface ComputeShortNamesResult {
    map: Map<string, string>
    dedupeCount: number
}

export function computeShortNames(
    rows: ShortNameRowInput[],
    strategy: ShortNameStrategy,
    maxLen: number
): ComputeShortNamesResult {
    const cap = Math.max(8, Math.min(64, maxLen))
    const smartStemAffixStrip = computeSmartStemAffixStrip(rows, strategy)
    const patternSetUid =
        strategy.kind === 'pattern' ? computePatternSetUid(rows, strategy.uidLength || 5) : undefined
    const used = new Set<string>()
    const map = new Map<string, string>()
    let dedupeCount = 0
    for (let i = 0; i < rows.length; i += 1) {
        const row = rows[i]!
        const raw = rawNameForRow(row, i, strategy, rows, cap, smartStemAffixStrip, patternSetUid)
        const { name, deduped } = uniqueify(raw, cap, used)
        if (deduped) dedupeCount += 1
        map.set(row.row_key, name)
    }
    return { map, dedupeCount }
}

export function validateShortNameRegex(strategy: ShortNameStrategy): string | null {
    if (strategy.kind !== 'regex') return null
    try {
        new RegExp(strategy.pattern, strategy.flags || '')
        return null
    } catch (e) {
        return `Short name regex: invalid pattern (${String(e)})`
    }
}

export function validateShortNameRegexStrip(strategy: ShortNameStrategy): string | null {
    if (strategy.kind !== 'smartRegexStrip') return null
    const pre = (strategy.prefixPattern ?? '').trim()
    const suf = (strategy.suffixPattern ?? '').trim()
    if (!pre && !suf) {
        return 'Short name: enter at least one of prefix regex or suffix regex'
    }
    if (pre) {
        try {
            new RegExp(pre)
        } catch (e) {
            return `Short name prefix regex: invalid (${String(e)})`
        }
    }
    if (suf) {
        try {
            new RegExp(suf)
        } catch (e) {
            return `Short name suffix regex: invalid (${String(e)})`
        }
    }
    return null
}
