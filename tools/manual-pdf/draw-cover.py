#!/usr/bin/env python3
"""Draw the cover's line drawing of a TS 2068 with a TS-Pico behind it, as SVG.

    draw-cover.py > img/ts2068-line.svg

The drawing is laid out flat, in millimetres-ish model units, and projected
into perspective with two homographies measured from a photograph of the
machine (the top of the case, and the face of the board): four corners each,
in the photo's pixels. Everything else (the keys, the panel, the vent, the
chips) is drawn in the flat model, so the lines come out straight and evenly
spaced. Run it again after changing anything here; the SVG is checked in.
"""
import numpy as np

INK = "#1b1b1b"


def homography(src, dst):
    a = []
    for (x, y), (u, v) in zip(src, dst):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y, -u])
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y, -v])
    h = np.linalg.svd(np.array(a, float))[2][-1]
    return (h / h[-1]).reshape(3, 3)


def proj(h, pts):
    p = np.c_[np.asarray(pts, float), np.ones(len(pts))] @ h.T
    return p[:, :2] / p[:, 2:]


# The top of the case: 375 x 165 model units, corners as photographed.
CW, CD = 375.0, 165.0
TOP = homography([(0, 0), (CW, 0), (CW, CD), (0, CD)],
                 [(411, 171), (1460, 450), (1250, 952), (62, 512)])
# The board's face (u, v in 0..1), corners as photographed.
PCB = homography([(0, 0), (1, 0), (1, 1), (0, 1)],
                 [(1081, 62), (1520, 160), (1459, 412), (1060, 310)])


def up(x, y):
    """The image vector, pointing down, for the case's full height at model point
    (x, y) on its top: interpolated from the thickness of its front face at the
    two front corners, and shorter towards the back."""
    t = x / CW
    front = np.array([11, 33]) * (1 - t) + np.array([-2, 36]) * t
    return front * (0.72 + 0.28 * y / CD)


out = []


def path(pts, fill="none", sw=1.6, close=True, stroke=INK, extra=""):
    d = "M" + " L".join("%.1f,%.1f" % tuple(p) for p in pts) + (" Z" if close else "")
    out.append('<path d="%s" fill="%s" stroke="%s" stroke-width="%.2f" stroke-linejoin="round"'
               ' stroke-linecap="round"%s/>' % (d, fill, stroke, sw, extra))


def top_pts(pts, lift=0.0):
    p = proj(TOP, pts)
    if lift:
        p = p - np.array([up(x, y) for x, y in pts]) * lift
    return p


def rect(x0, y0, x1, y1, n=1):
    """A rectangle in model units, its sides cut into n pieces (perspective
    keeps lines straight, so n=1 is enough)."""
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def line(a, b, sw=1.2, lift=0.0, stroke=INK):
    path(top_pts([a, b], lift), sw=sw, close=False, stroke=stroke)


# ---- The board, behind the case -------------------------------------------
BLUE, BLUE_LINE, CHIP, PICO = "#2f4f9e", "#9fb3e6", "#1b1b1b", "#3d8f5a"
X0, X1, Y0, Y1 = 57.0, 962.0, 35.0, 676.0     # the board, in the bare-board photo's pixels


def pb(pts):
    return proj(PCB, [((x - X0) / (X1 - X0), (y - Y0) / (Y1 - Y0)) for x, y in pts])


def pbox(x0, y0, x1, y1, fill, sw=1.2, stroke=None):
    path(pb(rect(x0, y0, x1, y1)), fill=fill, sw=sw, stroke=stroke or INK)


# The expansion connector and riser the board stands in.
path(pb([(150, 676), (800, 676), (800, 900), (150, 900)]), fill="#2a2a2a", sw=1.4)
path(pb([(60, 676), (960, 676), (960, 700), (60, 700)]), fill="#3d8f5a", sw=1.2)
pbox(X0, Y0, X1, Y1, BLUE, sw=2.4)
# Tracks, suggested: a few long thin lines.
for y in (300, 420, 600, 640):
    path(pb([(140, y), (880, y)]), sw=1.1, close=False, stroke=BLUE_LINE)
for x in (150, 380, 530, 700, 830):
    path(pb([(x, 60), (x, 660)]), sw=1.1, close=False, stroke=BLUE_LINE)
for x0, y0, x1, y1 in [(78, 52, 124, 238), (78, 350, 124, 545), (410, 78, 498, 368), (578, 78, 664, 368),
                       (208, 448, 262, 585), (296, 448, 350, 585), (536, 428, 594, 560), (620, 428, 680, 560),
                       (710, 428, 770, 560), (762, 262, 800, 338)]:
    pbox(x0, y0, x1, y1, CHIP, sw=1.0)
    path(pb([((x0 + x1) / 2 - 7, y0), ((x0 + x1) / 2 + 7, y0), ((x0 + x1) / 2, y0 + 10)]),
         fill=BLUE, sw=.6, stroke=BLUE)                       # the pin-1 notch
pbox(182, 40, 326, 396, PICO, sw=1.2)                         # the Raspberry Pi Pico
pbox(232, 40, 276, 70, "#c9c9c9", sw=.8)                      # its USB socket
pbox(232, 150, 286, 205, CHIP, sw=.8)                         # RP2040
pbox(850, 42, 962, 160, "#c9c9c9", sw=1.0)                    # the SD card socket
pbox(962, 70, 1012, 130, INK, sw=1.0)                         # a card in it
for y in (188, 268, 348):                                     # the three buttons
    pbox(905, y, 955, y + 48, "#d8d8d8", sw=1.0)
    pbox(918, y + 13, 942, y + 35, INK, sw=.6)

# ---- The case --------------------------------------------------------------
H = 1.0      # the case's height, in units of up()
KEY = 0.24   # how far the key tops stand above the panel
front = [(0, CD), (CW, CD)]
p_front = np.vstack([top_pts(front), top_pts(front[::-1], -H)])
path(p_front, fill="#c4c2bc", sw=2.4)                       # front face
right = [(CW, CD), (CW, 0)]
p_right = np.vstack([top_pts(right), top_pts(right[::-1], -H)])
path(p_right, fill="#d6d4cf", sw=2.4)                       # right end
path(top_pts(rect(0, 0, CW, CD)), fill="#f1f0ec", sw=2.6)   # top

# The raised back: the badge, the vent, the step.
path(top_pts(rect(6, 22.5, 29, 28)), fill=INK, sw=.8)       # TIMEX
path(top_pts(rect(30, 22.5, 82, 28)), fill="none", sw=.9)   # sinclair 2068
for x in np.arange(9, 27, 3.6):                              # T I M E X, as ticks
    line((x, 23.6), (x + 2.4, 23.6), sw=0.9, stroke="#3fa9de")
path(top_pts(rect(0.8, 33, CW - 0.8, 50)), fill="#e2e1dc", sw=1.2)
for x in np.arange(3.2, CW - 2, 2.9):
    line((x, 34.5), (x, 48.5), sw=1.1)
line((0, 57.5), (CW, 57.5), sw=1.4)

# The keyboard panel: the colour bar, the grid, the keys.
path(top_pts(rect(1, 60.5, 262, 156.5)), fill="#e9e8e4", sw=1.4)
COLOURS = [None, "#2b6fd1", "#d8262e", "#c43fb5", "#36a046", "#2fb3d8", "#e3c21c", "#ffffff", None, None, None, None]
bar_x = [1] + [16.2 + 20.4 * k - 1.7 for k in range(1, 12)] + [262]
for k, (a, b) in enumerate(zip(bar_x, bar_x[1:])):
    path(top_pts(rect(a + .5, 61.2, b - .5, 66.2)), fill=INK, sw=.5)
    c = COLOURS[k] if k < len(COLOURS) else None
    if c:
        m = (a + b) / 2
        line((m - 4, 63.7), (m + 4, 63.7), sw=1.6, stroke=c)
for y in (84, 101.5, 119.5, 137):
    line((1, y), (262, y), sw=1.2)

ROWS = [  # y of the key tops, then the keys as (x0, x1)
    (69.0, [(16.2 + 20.4 * k, 33.2 + 20.4 * k) for k in range(10)]),
    (86.4, [(26.2 + 20.4 * k, 43.2 + 20.4 * k) for k in range(10)]),
    (104.0, [(31.2 + 20.4 * k, 48.2 + 20.4 * k) for k in range(9)] + [(215, 245)]),
    (122.2, [(15, 34)] + [(41.2 + 20.4 * k, 58.2 + 20.4 * k) for k in range(7)]
     + [(184.5, 201), (205, 221.5), (225, 244.5)]),
]
row_band = [(66.2, 84), (84, 101.5), (101.5, 119.5), (119.5, 137)]
for (ky, keys), (b0, b1) in zip(ROWS, row_band):
    for (a0, a1), (n0, n1) in zip(keys, keys[1:]):
        m = (a1 + n0) / 2
        line((m, b0), (m, b1), sw=1.1)
    for i, (x0, x1) in enumerate(keys):
        y0, y1 = ky, ky + 11.5
        base = top_pts(rect(x0, y0, x1, y1))
        topk = top_pts(rect(x0, y0, x1, y1), KEY)
        # skirt: the front and right sides between top and base
        path([topk[3], topk[2], base[2], base[3]], fill="#cfcdc7", sw=1.3)
        path([topk[1], topk[2], base[2], base[1]], fill="#dddbd6", sw=1.3)
        dark = ROWS.index((ky, keys)) == 3 and x0 == 184.5          # SYMBOL SHIFT is black
        path(topk, fill=INK if dark else "#fbfaf6", sw=1.6)
        if not dark and not (x1 - x0 > 25):
            stripe = top_pts(rect(x0 + 2.5, y0 + 6.6, x1 - 2.5, y0 + 8.2), KEY)
            path(stripe, fill="#3a3a3a", sw=.4, stroke="#3a3a3a")

# The space bar, and PERSONAL COLOR COMPUTER's three stripes.
sb = (64, 141, 200, 151)
base = top_pts(rect(*sb)); topk = top_pts(rect(*sb), KEY * .8)
path([topk[3], topk[2], base[2], base[3]], fill="#cfcdc7", sw=1.3)
path(topk, fill="#fbfaf6", sw=1.2)
for x0, c in ((13, "#d8262e"), (25, "#36a046"), (37, "#2fb3d8")):
    path(top_pts(rect(x0, 144.6, x0 + 10, 146.4)), fill=c, sw=.3, stroke=c)

# The cartridge door, its LIFT TO OPEN line and the TCC badge.
path(top_pts(rect(265, 60.5, CW - 1.5, 160.5)), fill="#ecebe7", sw=1.4)
line((265, 158), (CW - 1.5, 158), sw=1.1)
line((281, 151.5), (342, 151.5), sw=1.0, stroke="#555")
path(top_pts(rect(344, 149.6, 360, 153.4)), fill="#d8262e", sw=.4, stroke="#d8262e")

pts = np.vstack([proj(TOP, rect(0, 0, CW, CD)), proj(PCB, rect(0, 0, 1, 1))])
x0, y0 = pts.min(0) - 10
x1, y1 = pts.max(0) + 60
print('<svg xmlns="http://www.w3.org/2000/svg" viewBox="%.0f %.0f %.0f %.0f">' % (x0, y0, x1 - x0, y1 - y0))
print("\n".join(out))
print("</svg>")
