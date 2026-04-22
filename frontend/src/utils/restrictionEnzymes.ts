/**
 * Curated list of common Type II restriction enzymes used in cloning and
 * synthetic-biology workflows. Sites come from Biopython's `Bio.Restriction`
 * and are used as the searchable options for the `ExcludeRestrictionSite`
 * DNA optimisation constraint (which maps to dnachisel's `AvoidPattern`
 * with an enzyme name such as "BsaI_site").
 *
 * Ambiguity codes (N, R, Y, W, S, K, M, B, D, H, V) may appear in `site` —
 * dnachisel resolves these via `EnzymeSitePattern` on both strands.
 */

export interface RestrictionEnzyme {
  name: string
  site: string
  /** Rough category used to group common / popular enzymes in the dropdown. */
  category: 'Classic Type II' | 'Golden Gate / Type IIs' | '8-cutter' | 'Other'
}

export const RESTRICTION_ENZYMES: RestrictionEnzyme[] = [
  // Classic 6-cutters
  { name: 'EcoRI', site: 'GAATTC', category: 'Classic Type II' },
  { name: 'BamHI', site: 'GGATCC', category: 'Classic Type II' },
  { name: 'HindIII', site: 'AAGCTT', category: 'Classic Type II' },
  { name: 'XhoI', site: 'CTCGAG', category: 'Classic Type II' },
  { name: 'SalI', site: 'GTCGAC', category: 'Classic Type II' },
  { name: 'KpnI', site: 'GGTACC', category: 'Classic Type II' },
  { name: 'SacI', site: 'GAGCTC', category: 'Classic Type II' },
  { name: 'SacII', site: 'CCGCGG', category: 'Classic Type II' },
  { name: 'PstI', site: 'CTGCAG', category: 'Classic Type II' },
  { name: 'XbaI', site: 'TCTAGA', category: 'Classic Type II' },
  { name: 'NdeI', site: 'CATATG', category: 'Classic Type II' },
  { name: 'NcoI', site: 'CCATGG', category: 'Classic Type II' },
  { name: 'NheI', site: 'GCTAGC', category: 'Classic Type II' },
  { name: 'SpeI', site: 'ACTAGT', category: 'Classic Type II' },
  { name: 'BglII', site: 'AGATCT', category: 'Classic Type II' },
  { name: 'ClaI', site: 'ATCGAT', category: 'Classic Type II' },
  { name: 'SmaI', site: 'CCCGGG', category: 'Classic Type II' },
  { name: 'XmaI', site: 'CCCGGG', category: 'Classic Type II' },
  { name: 'MluI', site: 'ACGCGT', category: 'Classic Type II' },
  { name: 'EcoRV', site: 'GATATC', category: 'Classic Type II' },
  { name: 'SphI', site: 'GCATGC', category: 'Classic Type II' },
  { name: 'HpaI', site: 'GTTAAC', category: 'Classic Type II' },
  { name: 'StuI', site: 'AGGCCT', category: 'Classic Type II' },
  { name: 'DraI', site: 'TTTAAA', category: 'Classic Type II' },
  { name: 'MfeI', site: 'CAATTG', category: 'Classic Type II' },
  { name: 'AvrII', site: 'CCTAGG', category: 'Classic Type II' },
  { name: 'AatII', site: 'GACGTC', category: 'Classic Type II' },
  { name: 'AflII', site: 'CTTAAG', category: 'Classic Type II' },
  { name: 'ApaI', site: 'GGGCCC', category: 'Classic Type II' },
  { name: 'ApaLI', site: 'GTGCAC', category: 'Classic Type II' },
  { name: 'BclI', site: 'TGATCA', category: 'Classic Type II' },
  { name: 'BsrGI', site: 'TGTACA', category: 'Classic Type II' },
  { name: 'BssHII', site: 'GCGCGC', category: 'Classic Type II' },
  { name: 'BstBI', site: 'TTCGAA', category: 'Classic Type II' },
  { name: 'EagI', site: 'CGGCCG', category: 'Classic Type II' },
  { name: 'NarI', site: 'GGCGCC', category: 'Classic Type II' },
  { name: 'KasI', site: 'GGCGCC', category: 'Classic Type II' },
  { name: 'PvuI', site: 'CGATCG', category: 'Classic Type II' },
  { name: 'PvuII', site: 'CAGCTG', category: 'Classic Type II' },
  { name: 'ScaI', site: 'AGTACT', category: 'Classic Type II' },
  { name: 'SnaBI', site: 'TACGTA', category: 'Classic Type II' },
  { name: 'AgeI', site: 'ACCGGT', category: 'Classic Type II' },
  { name: 'NruI', site: 'TCGCGA', category: 'Classic Type II' },
  { name: 'PciI', site: 'ACATGT', category: 'Classic Type II' },
  { name: 'NaeI', site: 'GCCGGC', category: 'Classic Type II' },
  // Golden Gate / Type IIs (cut outside recognition site)
  { name: 'BsaI', site: 'GGTCTC', category: 'Golden Gate / Type IIs' },
  { name: 'BsmBI', site: 'CGTCTC', category: 'Golden Gate / Type IIs' },
  { name: 'Esp3I', site: 'CGTCTC', category: 'Golden Gate / Type IIs' },
  { name: 'SapI', site: 'GCTCTTC', category: 'Golden Gate / Type IIs' },
  { name: 'BspQI', site: 'GCTCTTC', category: 'Golden Gate / Type IIs' },
  { name: 'BbsI', site: 'GAAGAC', category: 'Golden Gate / Type IIs' },
  { name: 'BpiI', site: 'GAAGAC', category: 'Golden Gate / Type IIs' },
  { name: 'AarI', site: 'CACCTGC', category: 'Golden Gate / Type IIs' },
  { name: 'PaqCI', site: 'CACCTGC', category: 'Golden Gate / Type IIs' },
  { name: 'BtgZI', site: 'GCGATG', category: 'Golden Gate / Type IIs' },
  // 8-cutters (useful for unique cloning sites)
  { name: 'NotI', site: 'GCGGCCGC', category: '8-cutter' },
  { name: 'PmeI', site: 'GTTTAAAC', category: '8-cutter' },
  { name: 'PacI', site: 'TTAATTAA', category: '8-cutter' },
  { name: 'AscI', site: 'GGCGCGCC', category: '8-cutter' },
  { name: 'FseI', site: 'GGCCGGCC', category: '8-cutter' },
  { name: 'SbfI', site: 'CCTGCAGG', category: '8-cutter' },
  { name: 'SwaI', site: 'ATTTAAAT', category: '8-cutter' },
  { name: 'SrfI', site: 'GCCCGGGC', category: '8-cutter' }
]

/** Map from enzyme name → recognition site (upper-case). */
export const RESTRICTION_ENZYME_BY_NAME: Record<string, RestrictionEnzyme> =
  Object.fromEntries(RESTRICTION_ENZYMES.map((e) => [e.name, e]))

/** Dropdown options with grouped display. Filterable by name or site. */
export interface RestrictionEnzymeOption {
  label: string
  value: string
  site: string
  category: RestrictionEnzyme['category']
}

export const RESTRICTION_ENZYME_OPTIONS: RestrictionEnzymeOption[] =
  RESTRICTION_ENZYMES.map((e) => ({
    label: `${e.name} (${e.site})`,
    value: e.name,
    site: e.site,
    category: e.category
  }))
