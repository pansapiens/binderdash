import { Vec3, Vec4 } from 'molstar/lib/mol-math/linear-algebra.js'

export type TagMarkerCameraProject = (out: Vec4, point: Vec3) => Vec4

export type TagOverlayMode = 'N' | 'C'

/**
 * Paints a screen-space marker at the projected terminus CA. No Mol* state transforms.
 */
export function paintTagMarkerScreenOverlay(
  ctx: CanvasRenderingContext2D,
  tagOverlay: TagOverlayMode,
  project: TagMarkerCameraProject,
  bufferWidth: number,
  bufferHeight: number,
  worldX: number,
  worldY: number,
  worldZ: number,
  radiusPx = 9,
): void {
  ctx.clearRect(0, 0, bufferWidth, bufferHeight)
  const tmpV = Vec3()
  const tmpP = Vec4()
  Vec3.set(tmpV, worldX, worldY, worldZ)
  project(tmpP, tmpV)
  if (tmpP[3] <= 0) return
  const sx = tmpP[0]
  const sy = bufferHeight - tmpP[1]
  const stroke = tagOverlay === 'N' ? 'rgba(30, 90, 200, 0.95)' : 'rgba(120, 0, 0, 0.95)'
  const fill = 'rgba(220, 40, 40, 0.55)'
  ctx.beginPath()
  ctx.arc(sx, sy, radiusPx, 0, Math.PI * 2)
  ctx.fillStyle = fill
  ctx.fill()
  ctx.strokeStyle = stroke
  ctx.lineWidth = 2
  ctx.stroke()
}
