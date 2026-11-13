"""Cutest picture entry: a chubby round-eared kitten face, drawn with
analytic distance functions (soft edges, no supersampling needed).

Deterministic, standard library only. Writes a PNG to
$MAKEFUN_OUTPUT_DIR/entry.png (or /output/entry.png in the grader).
"""

import math
import os
import struct
import zlib

W = 640
H = 640
AA = 1.8 / W  # edge softness in normalized units


def write_png(path, w, h, rows):
    raw = b"".join(b"\x00" + row for row in rows)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        c += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return c

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 6))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    if t <= 0.0:
        return c1
    if t >= 1.0:
        return c2
    return (lerp(c1[0], c2[0], t), lerp(c1[1], c2[1], t), lerp(c1[2], c2[2], t))


def clamp01(v):
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def cover(d):
    """Coverage from a signed distance (negative inside)."""
    return clamp01(0.5 - d / (2.0 * AA))


def sd_circle(x, y, cx, cy, r):
    return math.hypot(x - cx, y - cy) - r


def sd_ellipse(x, y, cx, cy, rx, ry):
    # Approximate ellipse SDF (good enough for soft-edged blending).
    dx = (x - cx) / rx
    dy = (y - cy) / ry
    k = math.sqrt(dx * dx + dy * dy)
    if k == 0.0:
        return -min(rx, ry)
    return (k - 1.0) * min(rx, ry)


def sd_segment(x, y, ax, ay, bx, by):
    px, py = x - ax, y - ay
    bx2, by2 = bx - ax, by - ay
    t = (px * bx2 + py * by2) / (bx2 * bx2 + by2 * by2)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - bx2 * t, py - by2 * t)


# Palette
BG_CENTER = (255, 243, 238)
BG_EDGE = (250, 205, 224)
DOT = (244, 178, 205)
FUR = (255, 226, 178)        # warm cream
FUR_SHADE = (243, 196, 138)  # soft orange for ear/edge shading
INNER_EAR = (250, 168, 186)
MUZZLE = (255, 246, 233)
EYE = (58, 40, 44)
NOSE = (244, 130, 152)
BLUSH = (250, 150, 168)
LINE = (120, 78, 66)
PATCH = (246, 178, 108)      # ginger patch over one ear/eye side

HEAD = (0.5, 0.545, 0.335)
EAR_L = (0.245, 0.315, 0.105)
EAR_R = (0.755, 0.315, 0.105)


def background(x, y):
    d = math.hypot(x - 0.5, y - 0.46)
    col = mix(BG_CENTER, BG_EDGE, clamp01(d / 0.75))
    # Faint polka dots on a staggered grid.
    gx = (x * 9.0) % 1.0
    gy = (y * 9.0 + (0.5 if int(x * 9.0) % 2 else 0.0)) % 1.0
    dd = math.hypot(gx - 0.5, gy - 0.5)
    col = mix(col, DOT, cover(dd - 0.10) * 0.35)
    return col


def shade(x, y):
    col = background(x, y)

    hx, hy, hr = HEAD

    # Ears (behind head).
    for (ex, ey, er) in (EAR_L, EAR_R):
        col = mix(col, FUR_SHADE, cover(sd_circle(x, y, ex, ey, er)))
        col = mix(col, FUR, cover(sd_circle(x, y, ex, ey, er - 0.012)))
        col = mix(col, INNER_EAR, cover(sd_circle(x, y, ex, ey + 0.012, er * 0.55)))

    # Head with a soft shaded rim.
    dh = sd_circle(x, y, hx, hy, hr)
    col = mix(col, FUR_SHADE, cover(dh + 0.016))
    col = mix(col, FUR, cover(dh))

    # Soft ambient shading: a gentle warm shadow pooling at the chin and
    # along the lower cheeks, clipped to the head so the face feels round
    # and plush rather than flat.
    dchin = sd_ellipse(x, y, 0.5, 0.845, 0.205, 0.075)
    col = mix(col, FUR_SHADE, cover(max(dchin, dh)) * 0.38)
    for cx in (0.255, 0.745):
        dcheek = sd_ellipse(x, y, cx, 0.700, 0.075, 0.115)
        col = mix(col, FUR_SHADE, cover(max(dcheek, dh)) * 0.22)

    # Ginger patch over the left ear and the top-left of the head.
    dp = sd_ellipse(x, y, 0.335, 0.335, 0.150, 0.120)
    col = mix(col, PATCH, cover(max(dp, dh)) * 0.9)

    # Forehead stripes.
    for sx in (0.455, 0.5, 0.545):
        ds = sd_segment(x, y, sx, 0.235, sx + (sx - 0.5) * 0.25, 0.315) - 0.0075
        col = mix(col, PATCH, cover(max(ds, dh)) * 0.85)

    # Muzzle.
    dm = sd_ellipse(x, y, 0.5, 0.665, 0.155, 0.105)
    col = mix(col, MUZZLE, cover(dm) * 0.95)

    # Blush.
    for bx in (0.272, 0.728):
        db = sd_ellipse(x, y, bx, 0.630, 0.058, 0.034)
        col = mix(col, BLUSH, cover(db) * 0.65)

    # Eyes: big glossy ellipses. A soft amber-brown crescent glows at the
    # bottom of each iris (clipped to the eye), then three highlights of
    # decreasing size give the classic wet, sparkling look.
    for ex in (0.368, 0.632):
        de = sd_ellipse(x, y, ex, 0.520, 0.0375, 0.052)
        col = mix(col, EYE, cover(de))
        dglow = sd_ellipse(x, y, ex, 0.552, 0.028, 0.020)
        col = mix(col, (146, 96, 74), cover(max(dglow, de)) * 0.55)
        dhl = sd_circle(x, y, ex - 0.013, 0.500, 0.0135)
        col = mix(col, (255, 255, 255), cover(dhl))
        dh2 = sd_circle(x, y, ex + 0.011, 0.540, 0.0065)
        col = mix(col, (255, 255, 255), cover(dh2) * 0.9)
        dh3 = sd_circle(x, y, ex + 0.004, 0.490, 0.0042)
        col = mix(col, (255, 255, 255), cover(dh3) * 0.95)

    # Nose: small rounded heart-ish blob, plus a tiny shine.
    dn = sd_ellipse(x, y, 0.5, 0.628, 0.031, 0.021)
    col = mix(col, NOSE, cover(dn))
    dshine = sd_circle(x, y, 0.490, 0.621, 0.007)
    col = mix(col, (255, 255, 255), cover(dshine) * 0.8)

    # Mouth: two little arcs under the nose, drawn as an upside-down W of
    # short curved strokes (approximated with arc distance).
    for side in (-1.0, 1.0):
        cx = 0.5 + side * 0.026
        cy = 0.648
        d = abs(math.hypot(x - cx, y - cy) - 0.026)
        if y >= cy - 0.004:
            col = mix(col, LINE, cover(d - 0.0045) * 0.9)
    # Vertical philtrum line from nose to mouth.
    dph = sd_segment(x, y, 0.5, 0.645, 0.5, 0.662) - 0.004
    col = mix(col, LINE, cover(dph) * 0.9)

    # Whiskers: three long ones per cheek, plus a shorter, finer fourth
    # whisker angled up above them for a wispier look.
    for side in (-1.0, 1.0):
        for k, (dy, tilt) in enumerate(((0.585, -0.030), (0.625, 0.0), (0.665, 0.030))):
            ax = 0.5 + side * 0.185
            bx = 0.5 + side * 0.335
            dw = sd_segment(x, y, ax, dy, bx, dy + tilt) - 0.0028
            col = mix(col, LINE, cover(max(dw, dh)) * 0.55)
        dw4 = sd_segment(x, y, 0.5 + side * 0.175, 0.552,
                         0.5 + side * 0.295, 0.552 - 0.048) - 0.0020
        col = mix(col, LINE, cover(max(dw4, dh)) * 0.45)

    return col


def main():
    rows = []
    for j in range(H):
        y = (j + 0.5) / H
        row = bytearray(W * 3)
        for i in range(W):
            x = (i + 0.5) / W
            r, g, b = shade(x, y)
            k = i * 3
            row[k] = max(0, min(255, int(r + 0.5)))
            row[k + 1] = max(0, min(255, int(g + 0.5)))
            row[k + 2] = max(0, min(255, int(b + 0.5)))
        rows.append(bytes(row))
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    write_png(os.path.join(out_dir, "entry.png"), W, H, rows)


if __name__ == "__main__":
    main()
