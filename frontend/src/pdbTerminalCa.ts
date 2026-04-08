/**
 * Terminal CA coordinates on a polymer chain (PDB or mmCIF text).
 */
export interface TerminalCaCoords {
  n: { x: number; y: number; z: number }
  c: { x: number; y: number; z: number }
}

function chainMatches(recordChain: string, chainId: string): boolean {
  const a = recordChain.trim().toUpperCase()
  const w = chainId.trim().toUpperCase()
  if (!w) return false
  return a === w || a.startsWith(w) || (a.length > 0 && w.length === 1 && a[0] === w[0])
}

function splitCifDataLine(line: string): string[] {
  const out: string[] = []
  let cur = ''
  let inQuote = false
  for (let i = 0; i < line.length; i++) {
    const ch = line[i]
    if (ch === '"') {
      inQuote = !inQuote
      continue
    }
    if (!inQuote && /\s/.test(ch)) {
      if (cur.length) {
        out.push(cur)
        cur = ''
      }
    } else {
      cur += ch
    }
  }
  if (cur.length) out.push(cur)
  return out
}

/** Prefer mmCIF when an _atom_site category is present; else PDB-style ATOM/HETATM. */
export function detectStructureTextFormat(text: string): 'pdb' | 'mmcif' {
  const head = text.trimStart().slice(0, 16000)
  if (/_atom_site\./i.test(head)) return 'mmcif'
  if (/^HEADER\s/m.test(head) || /^ATOM\s/m.test(head) || /^HETATM\s/m.test(head)) {
    return 'pdb'
  }
  return 'mmcif'
}

export function parseMmcifChainTerminalCA(
  cifText: string,
  chainId: string
): TerminalCaCoords | null {
  const lines = cifText.split(/\r?\n/)
  let i = 0
  while (i < lines.length) {
    const line = lines[i].trim()
    if (line.toLowerCase() === 'loop_') {
      i++
      const colNames: string[] = []
      while (i < lines.length && lines[i].trim().startsWith('_atom_site.')) {
        colNames.push(lines[i].trim())
        i++
      }
      const idx = (name: string) => colNames.indexOf(name)
      const iAtom = idx('_atom_site.label_atom_id')
      const iAuthAtom = idx('_atom_site.auth_atom_id')
      const iAsym = idx('_atom_site.label_asym_id')
      const iAuthAsym = idx('_atom_site.auth_asym_id')
      const iSeq = idx('_atom_site.label_seq_id')
      const iAuthSeq = idx('_atom_site.auth_seq_id')
      const ix = idx('_atom_site.Cartn_x')
      const iy = idx('_atom_site.Cartn_y')
      const iz = idx('_atom_site.Cartn_z')
      const atomIdx = iAtom >= 0 ? iAtom : iAuthAtom
      const asymIdx = iAsym >= 0 ? iAsym : iAuthAsym
      const seqIdx = iSeq >= 0 ? iSeq : iAuthSeq
      if (atomIdx < 0 || asymIdx < 0 || seqIdx < 0 || ix < 0 || iy < 0 || iz < 0) {
        continue
      }
      const bySeq = new Map<number, { x: number; y: number; z: number }>()
      while (i < lines.length) {
        const raw = lines[i]
        const t = raw.trim()
        if (!t || t.startsWith('#') || t.startsWith('loop_') || t.startsWith('_')) break
        const parts = splitCifDataLine(raw)
        if (parts.length <= Math.max(atomIdx, asymIdx, seqIdx, ix, iy, iz)) {
          i++
          continue
        }
        const atom = parts[atomIdx].replace(/^"/, '').replace(/"$/, '').trim()
        if (atom.toUpperCase() !== 'CA') {
          i++
          continue
        }
        const asym = parts[asymIdx].replace(/^"/, '').replace(/"$/, '').trim()
        if (!chainMatches(asym, chainId)) {
          i++
          continue
        }
        const seqRaw = parts[seqIdx].replace(/^"/, '').replace(/"$/, '').trim()
        const seq = parseInt(seqRaw, 10)
        if (Number.isNaN(seq)) {
          i++
          continue
        }
        const x = parseFloat(parts[ix])
        const y = parseFloat(parts[iy])
        const z = parseFloat(parts[iz])
        if (Number.isNaN(x) || Number.isNaN(y) || Number.isNaN(z)) {
          i++
          continue
        }
        bySeq.set(seq, { x, y, z })
        i++
      }
      if (bySeq.size > 0) {
        const sorted = [...bySeq.keys()].sort((a, b) => a - b)
        const n = bySeq.get(sorted[0])
        const c = bySeq.get(sorted[sorted.length - 1])
        if (n && c) return { n, c }
      }
      continue
    }
    i++
  }
  return null
}

export function parseStructureTextTerminalCA(
  text: string,
  chainId: string
): TerminalCaCoords | null {
  const fmt = detectStructureTextFormat(text)
  if (fmt === 'pdb') {
    return parsePdbChainTerminalCA(text, chainId)
  }
  return parseMmcifChainTerminalCA(text, chainId)
}

export function parsePdbChainTerminalCA(
  pdbText: string,
  chainId: string
): TerminalCaCoords | null {
  const bySeq = new Map<number, { x: number; y: number; z: number }>()

  for (const line of pdbText.split(/\r?\n/)) {
    if (!line.startsWith('ATOM') && !line.startsWith('HETATM')) continue
    const recordChain = (line[21] ?? ' ').trim()
    if (!chainMatches(recordChain, chainId)) continue
    const atomName = line.slice(12, 16).trim()
    if (atomName !== 'CA') continue
    const resSeq = parseInt(line.slice(22, 26).trim(), 10)
    if (Number.isNaN(resSeq)) continue
    const x = parseFloat(line.slice(30, 38))
    const y = parseFloat(line.slice(38, 46))
    const z = parseFloat(line.slice(46, 54))
    if (Number.isNaN(x) || Number.isNaN(y) || Number.isNaN(z)) continue
    bySeq.set(resSeq, { x, y, z })
  }

  if (bySeq.size === 0) return null
  const sorted = [...bySeq.keys()].sort((a, b) => a - b)
  const n = bySeq.get(sorted[0])
  const c = bySeq.get(sorted[sorted.length - 1])
  if (!n || !c) return null
  return { n, c }
}
