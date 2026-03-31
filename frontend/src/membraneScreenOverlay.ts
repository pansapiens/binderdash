import { Vec3, Vec4 } from 'molstar/lib/mol-math/linear-algebra.js'

import { membraneDiscRimPoints, type MembraneData } from './membraneOverlay'

/** Visual-only scale for on-screen membrane discs (PDBTM radius is unchanged in data). */
const MEMBRANE_VISUAL_RADIUS_SCALE = 1.2

export type MembraneCameraProject = (out: Vec4, point: Vec3) => Vec4

/**
 * Paints semi-transparent membrane discs using the same projection as Mol*’s WebGL canvas
 * (drawing-buffer pixel coordinates). No Mol* state transforms — avoids “No suitable parent”.
 */
export function paintMembraneScreenOverlay(
  ctx: CanvasRenderingContext2D,
  project: MembraneCameraProject,
  bufferWidth: number,
  bufferHeight: number,
  data: MembraneData,
  segments = 64,
): void {
  ctx.clearRect(0, 0, bufferWidth, bufferHeight)
  const tmpV = Vec3()
  const tmpP = Vec4()
  const r = data.radius * MEMBRANE_VISUAL_RADIUS_SCALE
  const rims = [
    membraneDiscRimPoints(data.plane1, data.normal, r, segments),
    membraneDiscRimPoints(data.plane2, data.normal, r, segments),
  ]
  for (const rim of rims) {
    ctx.beginPath()
    let n = 0
    for (const pt of rim) {
      Vec3.set(tmpV, pt[0], pt[1], pt[2])
      project(tmpP, tmpV)
      if (tmpP[3] <= 0) continue
      const sx = tmpP[0]
      const sy = bufferHeight - tmpP[1]
      if (n === 0) ctx.moveTo(sx, sy)
      else ctx.lineTo(sx, sy)
      n++
    }
    if (n < 3) continue
    ctx.closePath()
    ctx.fillStyle = 'rgba(200, 160, 80, 0.32)'
    ctx.fill()
    ctx.strokeStyle = 'rgba(130, 100, 50, 0.55)'
    ctx.lineWidth = 1
    ctx.stroke()
  }
}
