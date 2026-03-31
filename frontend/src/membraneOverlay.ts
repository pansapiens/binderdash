export interface MembraneData {
  plane1: [number, number, number]
  plane2: [number, number, number]
  normal: [number, number, number]
  centroid: [number, number, number]
  radius: number
}

function cross(a: number[], b: number[]): number[] {
  return [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  ]
}

function norm3(v: number[]): number {
  return Math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
}

function normalize3(v: number[]): number[] {
  const n = norm3(v)
  if (n < 1e-12) return [0, 0, 1]
  return [v[0] / n, v[1] / n, v[2] / n]
}

/** Outer rim of a disc in 3D (for screen-space fill). */
export function membraneDiscRimPoints(
  center: readonly [number, number, number],
  normal: readonly [number, number, number],
  radius: number,
  segments: number,
): [number, number, number][] {
  const n = normalize3([normal[0], normal[1], normal[2]])
  const aux = Math.abs(n[2]) < 0.9 ? [0, 0, 1] : [0, 1, 0]
  let u = cross(n, aux)
  u = normalize3(u)
  const v = normalize3(cross(n, u))
  const pts: [number, number, number][] = []
  for (let i = 0; i < segments; i++) {
    const theta = (2 * Math.PI * i) / segments
    const c = Math.cos(theta)
    const s = Math.sin(theta)
    pts.push([
      center[0] + radius * (c * u[0] + s * v[0]),
      center[1] + radius * (c * u[1] + s * v[1]),
      center[2] + radius * (c * u[2] + s * v[2]),
    ])
  }
  return pts
}
