"""Compose docs/images/binderdash-hero.png from the screenshots taken by capture.js.

Usage: python3 docs/images/hero/compose.py [screenshot_dir]
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/bdshots")
OUT = Path(__file__).resolve().parent.parent / "binderdash-hero.png"

W = 2400
M = 70  # outer margin
HEADER_CROP_PX = 432  # banner + tab bar, at deviceScaleFactor 2
TABLE_TOP_CROP_PX = 330  # drop the download/column-picker toolbar above the table
VIEWER_CROP = (1096, 2496)  # horizontal slice (left, right) of viewer.png around the structure


def rounded(im, r):
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.size[0] - 1, im.size[1] - 1), r, fill=255)
    out = im.convert("RGBA")
    out.putalpha(mask)
    return out


def paste_card(canvas, im, xy, r=22):
    im = rounded(im, r)
    x, y = xy
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (x + 6, y + 14, x + im.size[0] + 6, y + im.size[1] + 14), r, fill=(40, 20, 80, 90)
    )
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18)))
    canvas.alpha_composite(im, (x, y))
    ImageDraw.Draw(canvas).rounded_rectangle(
        (x, y, x + im.size[0] - 1, y + im.size[1] - 1), r, outline=(210, 205, 225, 255), width=2
    )


def scale_w(im, w):
    return im.resize((w, round(im.size[1] * w / im.size[0])), Image.LANCZOS)


def gradient(w, h, top=(243, 240, 250), bottom=(228, 222, 244)):
    bg = Image.new("RGBA", (w, h))
    draw = ImageDraw.Draw(bg)
    for y in range(h):
        t = y / (h - 1)
        draw.line([(0, y), (w, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)) + (255,))
    return bg


full = Image.open(SRC / "full.png").convert("RGB")
header = scale_w(full.crop((0, 0, full.size[0], HEADER_CROP_PX)), W - 2 * M)

table = Image.open(SRC / "table.png").convert("RGB")
table = scale_w(table.crop((0, TABLE_TOP_CROP_PX, table.size[0], table.size[1])), 1540)

viewer = Image.open(SRC / "viewer.png").convert("RGB")
viewer = scale_w(viewer.crop((VIEWER_CROP[0], 0, VIEWER_CROP[1], viewer.size[1])), 860)

table_y = M + header.size[1] + 50
viewer_y = table_y + 60
height = max(table_y + table.size[1], viewer_y + viewer.size[1]) + M

canvas = gradient(W, height)
paste_card(canvas, header, (M, M))
paste_card(canvas, table, (M, table_y))
paste_card(canvas, viewer, (W - M - viewer.size[0], viewer_y))
canvas.convert("RGB").save(OUT, optimize=True)
print(f"Wrote {OUT} ({W}x{height})")
