/**
 * Read terminal CA coordinates for a polymer chain directly from Mol*'s
 * loaded state tree, avoiding a second network request for the CIF/PDB file.
 */
import { StructureElement, StructureProperties } from 'molstar/lib/mol-model/structure'
import type { TerminalCaCoords } from './pdbTerminalCa'

function chainMatches(authAsymId: string, wantChain: string): boolean {
    const a = authAsymId.trim().toUpperCase()
    const w = wantChain.trim().toUpperCase()
    if (!a || !w) return false
    return a === w || a.startsWith(w) || (w.length === 1 && a[0] === w[0])
}

/**
 * Extract first/last CA atom coordinates for a given binder chain from the
 * primary loaded Mol* structure. Returns null when the structure is not yet
 * available or the chain has no CA atoms.
 */
export function extractTerminalCaFromMolstarPlugin(
    plugin: any,
    chain: string
): TerminalCaCoords | null {
    const hierarchy = plugin?.managers?.structure?.hierarchy?.current
    const structures = hierarchy?.structures
    if (!structures || structures.length === 0) return null

    for (const entry of structures) {
        const structure = entry?.cell?.obj?.data
        if (!structure) continue
        const coords = extractTerminalCaFromStructure(structure, chain)
        if (coords) return coords
    }
    return null
}

function extractTerminalCaFromStructure(structure: any, chain: string): TerminalCaCoords | null {
    const loc = StructureElement.Location.create(structure)
    let nSeq = Number.POSITIVE_INFINITY
    let cSeq = Number.NEGATIVE_INFINITY
    let nPos: { x: number; y: number; z: number } | null = null
    let cPos: { x: number; y: number; z: number } | null = null

    for (const unit of structure.units) {
        loc.unit = unit
        const elements = unit.elements
        const count = elements.length
        for (let i = 0; i < count; i++) {
            loc.element = elements[i]
            const authAsym = StructureProperties.chain.auth_asym_id(loc)
            if (!authAsym || !chainMatches(String(authAsym), chain)) continue
            const atomName = StructureProperties.atom.label_atom_id(loc)
            if (atomName !== 'CA') continue
            const seq = StructureProperties.residue.auth_seq_id(loc)
            if (typeof seq !== 'number' || Number.isNaN(seq)) continue
            const x = StructureProperties.atom.x(loc)
            const y = StructureProperties.atom.y(loc)
            const z = StructureProperties.atom.z(loc)
            if (Number.isNaN(x) || Number.isNaN(y) || Number.isNaN(z)) continue
            if (seq < nSeq) {
                nSeq = seq
                nPos = { x, y, z }
            }
            if (seq > cSeq) {
                cSeq = seq
                cPos = { x, y, z }
            }
        }
    }

    if (!nPos || !cPos) return null
    return { n: nPos, c: cPos }
}
