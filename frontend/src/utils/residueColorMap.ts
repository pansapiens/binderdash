/**
 * Per-residue colour maps for the target contact map in the structure viewer.
 *
 * The mean burial over a design set that hit several different epitopes averages into a
 * blur, so the gradient range is the user's control rather than a fixed auto-scale:
 * clamping min/max, or normalising to the observed range, is what pulls a weak second
 * epitope out of the noise. A boolean mode drops the magnitude entirely and shows only
 * which residues are contacted at all.
 */

export interface RgbColor {
    r: number
    g: number
    b: number
}

export interface ResidueValue {
    /** Auth chain identifier, as written in the structure file. */
    chain: string
    /** Auth residue number. */
    resseq: number
    /** null when no design produced a value for this residue. */
    value: number | null
}

export interface ResidueColor extends RgbColor {
    chain: string
    resseq: number
}

export type PaletteName = 'heat' | 'viridis' | 'blue_red'

/**
 * Control points, interpolated in RGB. Chosen so the low end is a muted grey-blue that
 * reads as "background" against the default chain colouring, not as a signal.
 */
const PALETTES: Record<PaletteName, RgbColor[]> = {
    heat: [
        { r: 220, g: 224, b: 230 },
        { r: 253, g: 231, b: 118 },
        { r: 244, g: 152, b: 53 },
        { r: 189, g: 42, b: 36 },
    ],
    viridis: [
        { r: 68, g: 1, b: 84 },
        { r: 59, g: 82, b: 139 },
        { r: 33, g: 145, b: 140 },
        { r: 94, g: 201, b: 98 },
        { r: 253, g: 231, b: 37 },
    ],
    blue_red: [
        { r: 49, g: 104, b: 179 },
        { r: 233, g: 236, b: 240 },
        { r: 189, g: 42, b: 36 },
    ],
}

export const PALETTE_OPTIONS: { label: string; value: PaletteName }[] = [
    { label: 'Heat', value: 'heat' },
    { label: 'Viridis', value: 'viridis' },
    { label: 'Blue → red', value: 'blue_red' },
]

/** Residues with no value at all, and the non-selected rest of the structure. */
export const NO_DATA_COLOR: RgbColor = { r: 200, g: 200, b: 200 }

export function colorAt(t: number, palette: PaletteName = 'heat'): RgbColor {
    const stops = PALETTES[palette] ?? PALETTES.heat
    const clamped = Math.min(1, Math.max(0, Number.isFinite(t) ? t : 0))
    const span = (stops.length - 1) * clamped
    const lower = Math.min(stops.length - 2, Math.floor(span))
    const frac = span - lower
    const a = stops[lower]
    const b = stops[lower + 1]
    return {
        r: Math.round(a.r + (b.r - a.r) * frac),
        g: Math.round(a.g + (b.g - a.g) * frac),
        b: Math.round(a.b + (b.b - a.b) * frac),
    }
}

/** `linear-gradient(...)` stops for the legend swatch. */
export function gradientCss(palette: PaletteName, steps = 12): string {
    const stops: string[] = []
    for (let i = 0; i < steps; i++) {
        const c = colorAt(i / (steps - 1), palette)
        stops.push(`rgb(${c.r},${c.g},${c.b}) ${Math.round((i / (steps - 1)) * 100)}%`)
    }
    return `linear-gradient(to right, ${stops.join(', ')})`
}

export interface ColorMapOptions {
    palette?: PaletteName
    /** Gradient lower bound; values at or below it get the first palette colour. */
    min?: number | null
    /** Gradient upper bound; values at or above it get the last. */
    max?: number | null
    /** Ignore min/max and stretch the gradient over the observed range. */
    normalize?: boolean
    /** Low values are the interesting ones (distance), so invert the ramp. */
    invert?: boolean
    /** Boolean mode: colour contacts one way and everything else another. */
    boolean?: boolean
    /** Contact test for boolean mode; `invert` makes it <= rather than >=. */
    threshold?: number
    contactColor?: RgbColor
    nonContactColor?: RgbColor
}

export interface ColorMapResult {
    colors: ResidueColor[]
    /** The range actually used, for the legend. */
    domain: [number, number]
}

/** The gradient bounds actually applied, given explicit limits and/or normalisation. */
export function resolveDomain(
    values: ResidueValue[],
    options: ColorMapOptions = {}
): [number, number] {
    const present = values
        .map(v => v.value)
        .filter((v): v is number => v != null && Number.isFinite(v))
    const observedLow = present.length ? Math.min(...present) : 0
    const observedHigh = present.length ? Math.max(...present) : 1

    let low = options.normalize ? observedLow : options.min ?? observedLow
    let high = options.normalize ? observedHigh : options.max ?? observedHigh
    if (!Number.isFinite(low)) low = observedLow
    if (!Number.isFinite(high)) high = observedHigh
    // A zero-width domain would divide by zero and paint everything the top colour.
    if (high <= low) high = low + 1e-6
    return [low, high]
}

export function buildColorMap(
    values: ResidueValue[],
    options: ColorMapOptions = {}
): ColorMapResult {
    const domain = resolveDomain(values, options)
    const [low, high] = domain
    const palette = options.palette ?? 'heat'
    const contact = options.contactColor ?? { r: 189, g: 42, b: 36 }
    const nonContact = options.nonContactColor ?? { r: 220, g: 224, b: 230 }

    const colors: ResidueColor[] = []
    for (const residue of values) {
        let color: RgbColor
        if (residue.value == null || !Number.isFinite(residue.value)) {
            color = NO_DATA_COLOR
        } else if (options.boolean) {
            const threshold = options.threshold ?? 0
            const isContact = options.invert
                ? residue.value <= threshold
                : residue.value >= threshold
            color = isContact ? contact : nonContact
        } else {
            let t = (residue.value - low) / (high - low)
            if (options.invert) t = 1 - t
            color = colorAt(t, palette)
        }
        colors.push({ chain: residue.chain, resseq: residue.resseq, ...color })
    }
    return { colors, domain }
}
