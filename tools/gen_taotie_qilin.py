#!/usr/bin/env python3
"""Generate taotie_qilin.svg — 饕餮骑麒麟踏云穿行于上古天界 (animated SVG, pure SMIL).

The script only does the geometry bookkeeping (gait curves, ribbon/flame
morph frames, procedural clouds and stars); the output is a single
self-contained SVG with no scripts and no bitmaps.
"""
import math
import random
import os

random.seed(20261011)

W, H = 1600, 1000
P = 1.2          # gait period (s)
NS = 24          # samples per gait cycle
PITCH_C = (780, 500)
SEAT = (745, 435)
POLL = (1045, 318)


def f(x):
    s = f"{x:.1f}"
    if s.endswith(".0"):
        s = s[:-2]
    if s == "-0":
        s = "0"
    return s


def pt(p):
    return f"{f(p[0])},{f(p[1])}"


# ---------------------------------------------------------------- math helpers
def rot(v, deg):
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return (v[0] * c - v[1] * s, v[0] * s + v[1] * c)


def rot_about(p, deg, c):
    v = rot((p[0] - c[0], p[1] - c[1]), deg)
    return (v[0] + c[0], v[1] + c[1])


def interp(keys, t):
    """Periodic cubic Hermite (Catmull-Rom like) interpolation of pose tuples."""
    n = len(keys)
    t %= 1.0
    ph = [k[0] for k in keys]
    if t < ph[0]:
        t += 1
    i = 0
    for j in range(n):
        if ph[j] <= t:
            i = j

    def get(j):
        q = j % n
        w = j // n
        return ph[q] + w, keys[q][1]

    p0, v0 = get(i - 1)
    p1, v1 = get(i)
    p2, v2 = get(i + 1)
    p3, v3 = get(i + 2)
    u = (t - p1) / (p2 - p1)
    h00 = 2 * u ** 3 - 3 * u ** 2 + 1
    h10 = u ** 3 - 2 * u ** 2 + u
    h01 = -2 * u ** 3 + 3 * u ** 2
    h11 = u ** 3 - u ** 2
    res = []
    for c in range(len(v1)):
        m1 = (v2[c] - v0[c]) / (p2 - p0) * (p2 - p1)
        m2 = (v3[c] - v1[c]) / (p3 - p1) * (p2 - p1)
        res.append(h00 * v1[c] + h10 * m1 + h01 * v2[c] + h11 * m2)
    return res


TAU = 2 * math.pi


def bob(g):
    return -8 * math.cos(TAU * (g - 0.95)) + 1.6 * math.sin(2 * TAU * g)


def pitch(g):
    return -2.4 * math.sin(TAU * (g + 0.05))


def rider_rot(g):
    return 1.5 * math.sin(TAU * (g - 0.12))


def rider_dy(g):
    return 3.2 * math.cos(TAU * (g - 0.02))


def head_nod(g):
    return 3.6 * math.sin(TAU * (g - 0.35))


def samples(fn):
    return [fn(k / NS) for k in range(NS + 1)]


def anim_rot(vals, c=(0, 0), dur=P, begin="0s"):
    v = ";".join(f"{f(a)} {f(c[0])} {f(c[1])}" if c != (0, 0) else f(a) for a in vals)
    return (f'<animateTransform attributeName="transform" type="rotate" values="{v}" '
            f'dur="{dur}s" begin="{begin}" repeatCount="indefinite"/>')


def anim_tr(vals, dur=P, begin="0s"):
    v = ";".join(f"{f(x)} {f(y)}" for x, y in vals)
    return (f'<animateTransform attributeName="transform" type="translate" values="{v}" '
            f'dur="{dur}s" begin="{begin}" repeatCount="indefinite"/>')


# ---------------------------------------------------------------- ribbons / flames
def smooth_open(pts):
    m = len(pts) - 1
    d = [f"M{pt(pts[0])}"]
    for i in range(m):
        p0 = pts[i - 1] if i > 0 else pts[0]
        p1 = pts[i]
        p2 = pts[i + 1]
        p3 = pts[i + 2] if i + 2 <= m else pts[m]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d.append(f"C{pt(c1)} {pt(c2)} {pt(p2)}")
    return "".join(d) + "Z"


def ribbon(root, base, length, widthf, amp, waves, phase, curve=0.0, n=10, aexp=1.4,
           amp2=0.0, waves2=0.0):
    x, y = root
    cl = [(x, y)]
    angs = []
    ds = length / n
    for i in range(n):
        s = (i + 0.5) / n
        th = (base + curve * s + amp * (s ** aexp) * math.sin(TAU * (waves * s - phase))
              + amp2 * (s ** aexp) * math.sin(TAU * (waves2 * s - 2 * phase)))
        r = math.radians(th)
        x += ds * math.cos(r)
        y += ds * math.sin(r)
        cl.append((x, y))
        angs.append(th)
    left, right = [], []
    for i, (px, py) in enumerate(cl):
        s = i / n
        th = angs[0] if i == 0 else angs[-1] if i == n else (angs[i - 1] + angs[i]) / 2
        r = math.radians(th)
        nx, ny = -math.sin(r), math.cos(r)
        w = widthf(s) / 2
        left.append((px + nx * w, py + ny * w))
        right.append((px - nx * w, py - ny * w))
    if widthf(1.0) < 0.3:
        poly = left + right[-2::-1]
    else:
        poly = left + right[::-1]
    return smooth_open(poly), cl[-1]


def ribbon_anim(fill, root, base, length, widthf, amp, waves, dur, offset=0.0, curve=0.0,
                n=10, frames=12, extra="", aexp=1.4, amp2=0.0, waves2=0.0, tip_obj=None):
    ds, tips = [], []
    for k in range(frames + 1):
        d, tip = ribbon(root, base, length, widthf, amp, waves, k / frames + offset, curve, n,
                        aexp, amp2, waves2)
        ds.append(d)
        tips.append(tip)
    s = (f'<path fill="{fill}" {extra} d="{ds[0]}"><animate attributeName="d" '
         f'values="{";".join(ds)}" dur="{dur}s" repeatCount="indefinite"/></path>')
    if tip_obj:
        s += (f'<g>{anim_tr(tips, dur=dur)}{tip_obj}</g>')
    return s


def flame_w(w0):
    return lambda s: w0 * ((1 - s) ** 0.9) * (0.75 + 0.25 * math.sin(math.pi * min(1, s * 1.6)))


def sash_w(w0, w1):
    return lambda s: w0 + (w1 - w0) * s


def thin_w(w0):
    return lambda s: w0 * (1 - s) ** 1.2


# ---------------------------------------------------------------- clouds
def cloud_puffs(cx, cy, w, h, n, seed, rim="url(#gRim)", fill="url(#gCloudMid)", rimw=2.2,
                flat=False):
    rnd = random.Random(seed)
    circles = []
    for i in range(n):
        u = (i + 0.5) / n
        x = cx - w / 2 + u * w + rnd.uniform(-w / n * 0.3, w / n * 0.3)
        bump = math.sin(math.pi * u)
        r = h * (0.35 + 0.65 * bump) * rnd.uniform(0.7, 1.05)
        y = cy - bump * h * 0.35 + rnd.uniform(-4, 4)
        circles.append((x, y, r))
    # extra lower filler
    for i in range(max(2, n // 2)):
        u = (i + 0.5) / max(2, n // 2)
        x = cx - w * 0.42 + u * w * 0.84
        circles.append((x, cy + h * 0.22, h * 0.5 * rnd.uniform(0.8, 1.15)))
    o = []
    o.append("<g>")
    o.append(f'<g fill="{rim}">' + "".join(
        f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(r + rimw)}"/>' for x, y, r in circles) + "</g>")
    o.append(f'<g fill="{fill}">' + "".join(
        f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(r)}"/>' for x, y, r in circles) + "</g>")
    if flat:
        o.append(f'<rect rx="{f(h * 0.6)}"  x="{f(cx - w / 2 - h * 0.6)}" y="{f(cy + h * 0.3)}" width="{f(w + h * 1.2)}" '
                 f'height="{f(h * 1.2)}" fill="{fill}"/>')
    o.append("</g>")
    return "".join(o)


def scroll_layer(lid, content, dur, attrs=""):
    return (f'<g {attrs}><g>'
            f'<animateTransform attributeName="transform" type="translate" values="0 0;-1600 0" '
            f'dur="{dur}s" repeatCount="indefinite"/>'
            f'<g id="{lid}">{content}</g>'
            f'<use xlink:href="#{lid}" x="1600"/><use xlink:href="#{lid}" x="-1600"/>'
            f'</g></g>')


# ================================================================ DEFS
defs = []
D = defs.append

D("""
<linearGradient id="gSky" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#03050f"/><stop offset=".35" stop-color="#0a1433"/>
  <stop offset=".62" stop-color="#14304f"/><stop offset=".8" stop-color="#173a52"/>
  <stop offset="1" stop-color="#0a1626"/>
</linearGradient>
<radialGradient id="gSkyGlow" cx="790" cy="470" r="620" gradientUnits="userSpaceOnUse">
  <stop offset="0" stop-color="#f5c45a" stop-opacity=".26"/>
  <stop offset=".35" stop-color="#c9863a" stop-opacity=".12"/>
  <stop offset=".7" stop-color="#3a6a8a" stop-opacity=".06"/>
  <stop offset="1" stop-color="#0a1433" stop-opacity="0"/>
</radialGradient>
<radialGradient id="gMoon" cx=".5" cy=".5" r=".5">
  <stop offset="0" stop-color="#fff6d8"/><stop offset=".55" stop-color="#f3d48a"/>
  <stop offset=".8" stop-color="#d79a3c" stop-opacity=".5"/><stop offset="1" stop-color="#d79a3c" stop-opacity="0"/>
</radialGradient>
<linearGradient id="gRidgeFar" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#2b5068"/><stop offset=".5" stop-color="#18324a"/><stop offset="1" stop-color="#0d1c2c"/>
</linearGradient>
<linearGradient id="gRidgeNear" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#1f4250"/><stop offset=".4" stop-color="#132b3a"/><stop offset="1" stop-color="#08131e"/>
</linearGradient>
<linearGradient id="gRock" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#3d6b6a"/><stop offset=".25" stop-color="#22404a"/>
  <stop offset=".7" stop-color="#132634"/><stop offset="1" stop-color="#0b1824" stop-opacity="0"/>
</linearGradient>
<linearGradient id="gRockTop" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#6fa58a"/><stop offset="1" stop-color="#2a5250"/>
</linearGradient>
<linearGradient id="gPalace" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#1e3442"/><stop offset="1" stop-color="#0d1a24"/>
</linearGradient>
<linearGradient id="gCloudFar" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="#7fa6c4" stop-opacity="0"/><stop offset=".2" stop-color="#7fa6c4" stop-opacity=".22"/>
  <stop offset=".8" stop-color="#9ab8cf" stop-opacity=".22"/><stop offset="1" stop-color="#7fa6c4" stop-opacity="0"/>
</linearGradient>
<linearGradient id="gCloudMid" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#a9c8d8"/><stop offset=".35" stop-color="#5f8aa8"/>
  <stop offset=".75" stop-color="#2b4a6c"/><stop offset="1" stop-color="#1a2d4a"/>
</linearGradient>
<linearGradient id="gCloudFront" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#8fb3c9"/><stop offset=".3" stop-color="#40668a"/>
  <stop offset=".7" stop-color="#1b3152"/><stop offset="1" stop-color="#0d1a33"/>
</linearGradient>
<linearGradient id="gCloudSea" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#3a6080" stop-opacity="0"/><stop offset=".2" stop-color="#2b4a6c"/><stop offset="1" stop-color="#101d36"/>
</linearGradient>
<linearGradient id="gRim" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#ffe7a3"/><stop offset=".4" stop-color="#e2b456"/><stop offset="1" stop-color="#6d8fb0" stop-opacity="0"/>
</linearGradient>
<linearGradient id="gRimCyan" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#bff6ee"/><stop offset=".5" stop-color="#6fc7c4"/><stop offset="1" stop-color="#2b4a6c" stop-opacity="0"/>
</linearGradient>
<linearGradient id="gEdgeL" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="#9fbfd4" stop-opacity=".55"/><stop offset=".5" stop-color="#6f93b0" stop-opacity=".18"/>
  <stop offset="1" stop-color="#6f93b0" stop-opacity="0"/>
</linearGradient>
<linearGradient id="gEdgeR" x1="1" y1="0" x2="0" y2="0">
  <stop offset="0" stop-color="#9fbfd4" stop-opacity=".5"/><stop offset=".5" stop-color="#6f93b0" stop-opacity=".16"/>
  <stop offset="1" stop-color="#6f93b0" stop-opacity="0"/>
</linearGradient>
<linearGradient id="gRay" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#ffe2a0" stop-opacity=".13"/><stop offset="1" stop-color="#ffe2a0" stop-opacity="0"/>
</linearGradient>

<!-- creature materials -->
<linearGradient id="gBody" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#3f9a84"/><stop offset=".4" stop-color="#22655d"/>
  <stop offset=".8" stop-color="#143c40"/><stop offset="1" stop-color="#0c2530"/>
</linearGradient>
<linearGradient id="gBodyShade" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#d9ffe9" stop-opacity=".18"/><stop offset=".3" stop-color="#000" stop-opacity="0"/>
  <stop offset=".75" stop-color="#051018" stop-opacity=".25"/><stop offset="1" stop-color="#03080e" stop-opacity=".6"/>
</linearGradient>
<linearGradient id="gScale" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#7fd0b0"/><stop offset=".55" stop-color="#2f7f6c"/><stop offset="1" stop-color="#174a44"/>
</linearGradient>
<linearGradient id="gBelly" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#e9cf7c"/><stop offset="1" stop-color="#8a6420"/>
</linearGradient>
<linearGradient id="gLegNear" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="#143b3c"/><stop offset=".45" stop-color="#3c8c78"/><stop offset="1" stop-color="#1a4a46"/>
</linearGradient>
<linearGradient id="gLegFar" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="#0b2129"/><stop offset=".5" stop-color="#1c4a48"/><stop offset="1" stop-color="#0e2a30"/>
</linearGradient>
<linearGradient id="gHoof" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#5a4a2a"/><stop offset=".5" stop-color="#2a2318"/><stop offset="1" stop-color="#120f0b"/>
</linearGradient>
<linearGradient id="gGold" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#fff2b8"/><stop offset=".35" stop-color="#f0c04e"/>
  <stop offset=".75" stop-color="#b07a1c"/><stop offset="1" stop-color="#6a420c"/>
</linearGradient>
<linearGradient id="gGoldH" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="#7a4c10"/><stop offset=".5" stop-color="#ffe08a"/><stop offset="1" stop-color="#8a5a14"/>
</linearGradient>
<linearGradient id="gBronze" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0" stop-color="#c9a24c"/><stop offset=".3" stop-color="#8a7a3a"/>
  <stop offset=".65" stop-color="#3f5a40"/><stop offset="1" stop-color="#1e2e26"/>
</linearGradient>
<linearGradient id="gBronzeG" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#5f9a78"/><stop offset=".5" stop-color="#2d5644"/><stop offset="1" stop-color="#16271f"/>
</linearGradient>
<linearGradient id="gBlackGold" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0" stop-color="#3b342a"/><stop offset=".5" stop-color="#16130f"/><stop offset="1" stop-color="#07060a"/>
</linearGradient>
<linearGradient id="gSkin" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0" stop-color="#5d8a6a"/><stop offset=".5" stop-color="#2e4f40"/><stop offset="1" stop-color="#18291f"/>
</linearGradient>
<linearGradient id="gFace" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#7aa784"/><stop offset=".45" stop-color="#3f6a54"/><stop offset="1" stop-color="#1e3529"/>
</linearGradient>
<linearGradient id="gVermil" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#e8492e"/><stop offset=".55" stop-color="#a51f1b"/><stop offset="1" stop-color="#4f0c10"/>
</linearGradient>
<linearGradient id="gHorn" x1="0" y1="1" x2="0" y2="0">
  <stop offset="0" stop-color="#4c3a1c"/><stop offset=".45" stop-color="#b8893a"/><stop offset="1" stop-color="#fff0c0"/>
</linearGradient>
<linearGradient id="gAntler" x1="0" y1="1" x2="0" y2="0">
  <stop offset="0" stop-color="#6b4a1a"/><stop offset=".6" stop-color="#d8a84a"/><stop offset="1" stop-color="#fff2c4"/>
</linearGradient>
<linearGradient id="gMouth" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#5a0a0e"/><stop offset="1" stop-color="#1c0306"/>
</linearGradient>
<linearGradient id="gIvory" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#fffbe8"/><stop offset="1" stop-color="#cdb37a"/>
</linearGradient>
<radialGradient id="gEye" cx=".45" cy=".45" r=".6">
  <stop offset="0" stop-color="#fffbe0"/><stop offset=".3" stop-color="#ffd84a"/>
  <stop offset=".7" stop-color="#ff6a1a"/><stop offset="1" stop-color="#8a0a00"/>
</radialGradient>
<radialGradient id="gEyeGlow" cx=".5" cy=".5" r=".5">
  <stop offset="0" stop-color="#ffd25a" stop-opacity=".95"/><stop offset=".4" stop-color="#ff7a20" stop-opacity=".45"/>
  <stop offset="1" stop-color="#ff4a10" stop-opacity="0"/>
</radialGradient>
<radialGradient id="gGlowGold" cx=".5" cy=".5" r=".5">
  <stop offset="0" stop-color="#fff6c8" stop-opacity="1"/><stop offset=".3" stop-color="#ffd166" stop-opacity=".7"/>
  <stop offset="1" stop-color="#ff9a2a" stop-opacity="0"/>
</radialGradient>
<radialGradient id="gGlowCyan" cx=".5" cy=".5" r=".5">
  <stop offset="0" stop-color="#e8fffb" stop-opacity=".9"/><stop offset=".4" stop-color="#7fe6dc" stop-opacity=".4"/>
  <stop offset="1" stop-color="#2a8f9a" stop-opacity="0"/>
</radialGradient>
<radialGradient id="gDot" cx=".5" cy=".5" r=".5">
  <stop offset="0" stop-color="#fff8d8"/><stop offset=".25" stop-color="#ffd36a" stop-opacity=".9"/>
  <stop offset="1" stop-color="#ffb030" stop-opacity="0"/>
</radialGradient>
<radialGradient id="gStar" cx=".5" cy=".5" r=".5">
  <stop offset="0" stop-color="#ffffff"/><stop offset=".3" stop-color="#d8ecff" stop-opacity=".8"/>
  <stop offset="1" stop-color="#9fc4ff" stop-opacity="0"/>
</radialGradient>
<radialGradient id="gHalo" cx="790" cy="470" r="470" gradientUnits="userSpaceOnUse">
  <stop offset="0" stop-color="#ffd27a" stop-opacity=".22"/><stop offset=".55" stop-color="#e0a040" stop-opacity=".08"/>
  <stop offset="1" stop-color="#e0a040" stop-opacity="0"/>
</radialGradient>
<radialGradient id="gWindow" cx=".5" cy=".5" r=".5">
  <stop offset="0" stop-color="#fff0b0"/><stop offset="1" stop-color="#ffb040" stop-opacity="0"/>
</radialGradient>

<!-- flame gradients (userSpace, root to tip) -->
<linearGradient id="gTailRed" gradientUnits="userSpaceOnUse" x1="570" y1="470" x2="300" y2="430">
  <stop offset="0" stop-color="#ffdf7a"/><stop offset=".25" stop-color="#f08a2c"/>
  <stop offset=".6" stop-color="#c8281e"/><stop offset="1" stop-color="#5a0a18" stop-opacity=".2"/>
</linearGradient>
<linearGradient id="gTailGold" gradientUnits="userSpaceOnUse" x1="570" y1="470" x2="330" y2="440">
  <stop offset="0" stop-color="#fff7d0"/><stop offset=".35" stop-color="#ffc94a"/>
  <stop offset=".75" stop-color="#e86a1e"/><stop offset="1" stop-color="#b02018" stop-opacity="0"/>
</linearGradient>
<linearGradient id="gTailCyan" gradientUnits="userSpaceOnUse" x1="570" y1="470" x2="360" y2="440">
  <stop offset="0" stop-color="#f0fffc"/><stop offset=".4" stop-color="#6fe3d4"/>
  <stop offset="1" stop-color="#1a7f8f" stop-opacity="0"/>
</linearGradient>
<linearGradient id="gManeRed" gradientUnits="userSpaceOnUse" x1="0" y1="420" x2="0" y2="250">
  <stop offset="0" stop-color="#ffcf5a"/><stop offset=".35" stop-color="#ef7a28"/>
  <stop offset=".75" stop-color="#c3241c"/><stop offset="1" stop-color="#6a0c18" stop-opacity=".3"/>
</linearGradient>
<linearGradient id="gManeGold" gradientUnits="userSpaceOnUse" x1="0" y1="420" x2="0" y2="270">
  <stop offset="0" stop-color="#fff6c8"/><stop offset=".45" stop-color="#ffcb4a"/>
  <stop offset="1" stop-color="#ff7a20" stop-opacity="0"/>
</linearGradient>
<linearGradient id="gManeCyan" gradientUnits="userSpaceOnUse" x1="0" y1="420" x2="0" y2="290">
  <stop offset="0" stop-color="#e8fffb"/><stop offset=".5" stop-color="#5fd8cc"/>
  <stop offset="1" stop-color="#1a6f8f" stop-opacity="0"/>
</linearGradient>
<linearGradient id="gCape" gradientUnits="userSpaceOnUse" x1="770" y1="0" x2="360" y2="0">
  <stop offset="0" stop-color="#8f1a1c"/><stop offset=".5" stop-color="#6e1018"/><stop offset="1" stop-color="#3a0610"/>
</linearGradient>
<linearGradient id="gCapeHi" gradientUnits="userSpaceOnUse" x1="770" y1="0" x2="380" y2="0">
  <stop offset="0" stop-color="#e2553a" stop-opacity=".7"/><stop offset="1" stop-color="#a81e22" stop-opacity=".1"/>
</linearGradient>
<linearGradient id="gRibbonCyan" gradientUnits="userSpaceOnUse" x1="700" y1="0" x2="460" y2="0">
  <stop offset="0" stop-color="#7fe0d0"/><stop offset=".6" stop-color="#2a9a96"/><stop offset="1" stop-color="#145a6a"/>
</linearGradient>
<linearGradient id="gRibbonRed" gradientUnits="userSpaceOnUse" x1="700" y1="0" x2="480" y2="0">
  <stop offset="0" stop-color="#ff7a4a"/><stop offset=".6" stop-color="#c72a22"/><stop offset="1" stop-color="#6a0c18"/>
</linearGradient>
<linearGradient id="gHair" gradientUnits="userSpaceOnUse" x1="760" y1="0" x2="640" y2="0">
  <stop offset="0" stop-color="#2a1416"/><stop offset=".5" stop-color="#7a1418"/><stop offset="1" stop-color="#e0522a" stop-opacity=".2"/>
</linearGradient>
<linearGradient id="gWhisker" gradientUnits="userSpaceOnUse" x1="1170" y1="0" x2="1000" y2="0">
  <stop offset="0" stop-color="#fff2b8"/><stop offset="1" stop-color="#f0a030" stop-opacity="0"/>
</linearGradient>
<linearGradient id="gFlameV" x1="0" y1="1" x2="0" y2="0">
  <stop offset="0" stop-color="#fff6c8"/><stop offset=".35" stop-color="#ffc040"/>
  <stop offset=".7" stop-color="#e2461e"/><stop offset="1" stop-color="#8a0a18" stop-opacity=".2"/>
</linearGradient>
<linearGradient id="gFlameVC" x1="0" y1="1" x2="0" y2="0">
  <stop offset="0" stop-color="#f4fffd"/><stop offset=".45" stop-color="#6fe3d4"/><stop offset="1" stop-color="#1a6f8f" stop-opacity="0"/>
</linearGradient>

<!-- filters -->
<filter id="fGlow" x="-50%" y="-50%" width="200%" height="200%">
  <feGaussianBlur stdDeviation="3.5" result="b"/>
  <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
</filter>
<filter id="fGlowBig" x="-100%" y="-100%" width="300%" height="300%">
  <feGaussianBlur stdDeviation="9"/>
</filter>
<filter id="fSoft" x="-10%" y="-30%" width="120%" height="160%">
  <feGaussianBlur stdDeviation="2.2"/>
</filter>
<filter id="fMist" x="-20%" y="-60%" width="140%" height="220%">
  <feGaussianBlur stdDeviation="10"/>
</filter>

<!-- patterns -->
<pattern id="pScale" width="26" height="20" patternUnits="userSpaceOnUse" patternTransform="rotate(-8)"><g fill="url(#gScale)" stroke="#f0cf78" stroke-width=".9" stroke-opacity=".8"><path d="M-26,-10C-26,9 0,9 0,-10Z"/><path d="M-20,-5C-18,1 -8,1 -6,-5" fill="none" stroke="#d8fff0" stroke-opacity=".35" stroke-width="1.2"/><path d="M0,-10C0,9 26,9 26,-10Z"/><path d="M6,-5C8,1 18,1 20,-5" fill="none" stroke="#d8fff0" stroke-opacity=".35" stroke-width="1.2"/><path d="M26,-10C26,9 52,9 52,-10Z"/><path d="M32,-5C34,1 44,1 46,-5" fill="none" stroke="#d8fff0" stroke-opacity=".35" stroke-width="1.2"/><path d="M-13,0C-13,19 13,19 13,0Z"/><path d="M-7,5C-5,11 5,11 7,5" fill="none" stroke="#d8fff0" stroke-opacity=".35" stroke-width="1.2"/><path d="M13,0C13,19 39,19 39,0Z"/><path d="M19,5C21,11 31,11 33,5" fill="none" stroke="#d8fff0" stroke-opacity=".35" stroke-width="1.2"/><path d="M-26,10C-26,29 0,29 0,10Z"/><path d="M-20,15C-18,21 -8,21 -6,15" fill="none" stroke="#d8fff0" stroke-opacity=".35" stroke-width="1.2"/><path d="M0,10C0,29 26,29 26,10Z"/><path d="M6,15C8,21 18,21 20,15" fill="none" stroke="#d8fff0" stroke-opacity=".35" stroke-width="1.2"/><path d="M26,10C26,29 52,29 52,10Z"/><path d="M32,15C34,21 44,21 46,15" fill="none" stroke="#d8fff0" stroke-opacity=".35" stroke-width="1.2"/></g></pattern>
<pattern id="pScaleS" width="16" height="12" patternUnits="userSpaceOnUse"><g fill="url(#gScale)" stroke="#f0cf78" stroke-width=".6" stroke-opacity=".7"><path d="M-16,-6C-16,6 0,6 0,-6Z"/><path d="M0,-6C0,6 16,6 16,-6Z"/><path d="M16,-6C16,6 32,6 32,-6Z"/><path d="M-8,0C-8,12 8,12 8,0Z"/><path d="M8,0C8,12 24,12 24,0Z"/><path d="M-16,6C-16,18 0,18 0,6Z"/><path d="M0,6C0,18 16,18 16,6Z"/><path d="M16,6C16,18 32,18 32,6Z"/></g></pattern>
<pattern id="pHui" width="16" height="16" patternUnits="userSpaceOnUse">
  <rect width="16" height="16" fill="#2a3a2c"/>
  <path d="M1,15H15V1H4V12H12V4H7V9H9" fill="none" stroke="#e2b85a" stroke-width="1.3"/>
</pattern>
<pattern id="pLei" width="20" height="20" patternUnits="userSpaceOnUse">
  <rect width="20" height="20" fill="#1c2622"/>
  <path d="M10,10h3v-3h-6v6h9v-9h-12v12h15" fill="none" stroke="#d8ad52" stroke-width="1.1"/>
</pattern>
<pattern id="pLamellar" width="10" height="9" patternUnits="userSpaceOnUse">
  <rect width="10" height="9" fill="#1d2420"/>
  <path d="M1,0h8v6q-4,3 -8,0z" fill="url(#gBronze)" stroke="#e7c062" stroke-width=".5"/>
</pattern>
<pattern id="pClothCloud" width="44" height="30" patternUnits="userSpaceOnUse">
  <path d="M6,20c-4-6 2-12 8-9c2-6 12-6 13,1c6-2 10,5 5,8" fill="none" stroke="#f2c86a" stroke-width="1" stroke-opacity=".55"/>
  <path d="M28,6c-2-3 1-5 4-4" fill="none" stroke="#f2c86a" stroke-width=".8" stroke-opacity=".4"/>
</pattern>

<!-- reusable symbols -->
<path id="lei" d="M0,0h4v-4h-8v8h12v-12h-16v16h20" fill="none" stroke-linecap="square"/>
<path id="ruyi" d="M-40,10C-55,-10 -40,-35 -18,-30C-5,-27 -2,-12 -12,-8C-20,-5 -24,-15 -18,-18M-18,-30C-10,-48 20,-50 28,-30C34,-15 20,-5 12,-12C6,-18 12,-24 18,-22M28,-30C45,-38 62,-20 55,-2C50,10 35,12 -40,10" fill="none" stroke-linecap="round"/>
<path id="spark" d="M0,-7L1.6,-1.6L7,0L1.6,1.6L0,7L-1.6,1.6L-7,0L-1.6,-1.6Z"/>
<path id="hoofFlame" d="M0,0C-9,-6 -11,-20 -4,-32C-3,-23 1,-21 2,-15C5,-24 10,-28 9,-40C17,-26 15,-9 6,0Z"/>
<g id="bell">
  <path d="M0,0V6" stroke="#e8c060" stroke-width="2"/>
  <path d="M-7,18C-7,8 -5,5 0,5C5,5 7,8 7,18Z" fill="url(#gGold)" stroke="#5a3a0c" stroke-width=".8"/>
  <path d="M-8,18H8" stroke="#ffe7a0" stroke-width="2"/><circle cy="21" r="2.2" fill="#ffe08a"/>
  <path d="M-3,10h6M-3,13h6" stroke="#7a4c10" stroke-width=".8"/>
</g>
<g id="tassel">
  <circle r="5" fill="url(#gGold)" stroke="#6a420c" stroke-width=".6"/>
  <path d="M-4,4L-7,26M-2,5L-3,28M0,5L0,29M2,5L3,28M4,4L7,26" stroke="#d8282a" stroke-width="1.6" stroke-linecap="round"/>
  <rect x="-4" y="3" width="8" height="3" fill="#ffe08a"/>
</g>
<g id="pendant">
  <path d="M0,-8L7,0L0,12L-7,0Z" fill="url(#gGold)" stroke="#6a420c" stroke-width=".8"/>
  <circle r="2.6" fill="#5fe3d4"/>
  <path d="M0,12V30M-3,14L-5,30M3,14L5,30" stroke="#ffcc55" stroke-width="1.3" stroke-linecap="round"/>
</g>
""")

# ================================================================ BACKGROUND
bg = []
B = bg.append
B('<rect width="1600" height="1000" fill="url(#gSky)"/>')
B('<rect width="1600" height="1000" fill="url(#gSkyGlow)"/>')
# moon / sun disc behind the scene, upper right
B('<g opacity=".85"><circle cx="1330" cy="170" r="120" fill="url(#gMoon)" opacity=".35"/>'
  '<circle cx="1330" cy="170" r="58" fill="url(#gMoon)">'
  '<animate attributeName="opacity" values=".75;.95;.75" dur="9s" repeatCount="indefinite"/></circle>'
  '<circle cx="1330" cy="170" r="66" fill="none" stroke="#f5d48a" stroke-opacity=".35" stroke-width="1.2"/>'
  '<circle cx="1330" cy="170" r="76" fill="none" stroke="#f5d48a" stroke-opacity=".18" stroke-width="1" stroke-dasharray="2 6"/></g>')

# stars
stars = []
rs = random.Random(5)
for i in range(130):
    x = rs.uniform(10, 1590)
    y = rs.uniform(10, 600) ** 1.0
    if 1230 < x < 1430 and 70 < y < 270:
        continue
    r = rs.choice([0.6, 0.8, 1.0, 1.2, 1.5, 1.9])
    d = rs.uniform(2.2, 7)
    b = -rs.uniform(0, d)
    lo = rs.uniform(0.1, 0.4)
    hi = rs.uniform(0.7, 1)
    stars.append(f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(r * 2.4)}" fill="url(#gStar)" opacity="{f(lo)}">'
                 f'<animate attributeName="opacity" values="{f(lo)};{f(hi)};{f(lo)}" dur="{d:.2f}s" '
                 f'begin="{b:.2f}s" repeatCount="indefinite"/></circle>')
for i in range(9):
    x = rs.uniform(60, 1540)
    y = rs.uniform(30, 420)
    d = rs.uniform(3, 7)
    stars.append(f'<g transform="translate({f(x)},{f(y)})"><g><path d="M0,-9L1,-1L9,0L1,1L0,9L-1,1L-9,0L-1,-1Z" fill="#fff4d0">'
                 f'<animate attributeName="opacity" values=".1;1;.1" dur="{d:.2f}s" begin="{-rs.uniform(0, d):.2f}s" repeatCount="indefinite"/></path>'
                 f'<animateTransform attributeName="transform" type="rotate" values="0;90" dur="{d * 2:.2f}s" repeatCount="indefinite"/></g></g>')
B('<g id="stars">' + "".join(stars) + "</g>")

# god rays from above
rays = []
for i, (x0, w0, ang, d) in enumerate([(620, 70, -14, 11), (760, 110, -4, 14), (900, 80, 8, 9), (1040, 60, 18, 13), (520, 50, -24, 16)]):
    rays.append(f'<path d="M{x0},-20 L{x0 + w0},-20 L{x0 + w0 * 2.4 + ang * 22},760 L{x0 - w0 * 0.6 + ang * 22},760Z" fill="url(#gRay)">'
                f'<animate attributeName="opacity" values=".25;.9;.25" dur="{d}s" begin="-{i * 2.3:.1f}s" repeatCount="indefinite"/></path>')
B('<g style="mix-blend-mode:screen">' + "".join(rays) + "</g>")

# far sky cloud bands (very slow)
bands = []
rb = random.Random(9)
for i in range(9):
    x = rb.uniform(0, 1600)
    y = rb.uniform(120, 520)
    w = rb.uniform(260, 520)
    h = rb.uniform(10, 24)
    bands.append(f'<ellipse cx="{f(x)}" cy="{f(y)}" rx="{f(w / 2)}" ry="{f(h)}" fill="url(#gCloudFar)"/>')
    bands.append(f'<ellipse cx="{f(x + w * 0.15)}" cy="{f(y - h * 0.6)}" rx="{f(w / 3)}" ry="{f(h * 0.5)}" fill="url(#gCloudFar)"/>')
B(scroll_layer("skyBand", "".join(bands), 160, 'opacity=".9"'))


# far ridge (periodic so the loop is seamless)
def ridge(base, amps, step=16):
    pts = []
    for x in range(0, 1601, step):
        y = base
        for k, a, ph in amps:
            y -= a * math.sin(TAU * k * x / 1600 + ph)
        pts.append((x, y))
    d = "M0,1000L" + "L".join(pt(p) for p in pts) + "L1600,1000Z"
    return d


r1 = ridge(650, [(2, 40, 0.3), (5, 26, 1.1), (11, 12, 2.0), (23, 5, 0.4)])
r2 = ridge(720, [(3, 46, 1.7), (7, 22, 0.2), (13, 10, 2.6), (29, 4, 1.3)])
B(scroll_layer("ridgeFar", f'<path d="{r1}" fill="url(#gRidgeFar)" opacity=".75"/>'
               f'<path d="{r1}" fill="none" stroke="#9fd0c8" stroke-opacity=".18" stroke-width="1.2"/>', 220))


def palace(x, y, s, glow=True, kind=0):
    o = [f'<g transform="translate({f(x)},{f(y)}) scale({s})">']
    o.append('<rect x="-62" y="-8" width="124" height="8" fill="#14252f" stroke="#c9a14a" stroke-opacity=".5" stroke-width=".8"/>')
    o.append('<path d="M-50,-8V-14H50V-8" fill="#1b2e38"/>')
    if kind == 0:
        o.append('<rect x="-42" y="-40" width="84" height="26" fill="url(#gPalace)"/>')
        o.append('<path d="M-36,-40V-14M-24,-40V-14M-12,-40V-14M0,-40V-14M12,-40V-14M24,-40V-14M36,-40V-14" stroke="#7a2a22" stroke-width="2"/>')
        o.append('<path d="M-66,-38C-54,-41 -50,-45 -46,-54L46,-54C50,-45 54,-41 66,-38C40,-43 -40,-43 -66,-38Z" fill="#203a46" stroke="#d6ae58" stroke-opacity=".7" stroke-width="1"/>')
        o.append('<rect x="-28" y="-72" width="56" height="18" fill="url(#gPalace)"/>')
        o.append('<path d="M-46,-70C-38,-73 -34,-76 -31,-84L31,-84C34,-76 38,-73 46,-70C28,-74 -28,-74 -46,-70Z" fill="#203a46" stroke="#d6ae58" stroke-opacity=".7" stroke-width="1"/>')
        o.append('<path d="M-31,-84H31M0,-84V-96" stroke="#e8c26a" stroke-width="1.5"/><circle cy="-98" r="2.5" fill="#ffd36a"/>')
        win = [(-30, -32), (-6, -32), (18, -32), (-14, -66), (10, -66)]
    else:
        o.append('<rect x="-18" y="-34" width="36" height="20" fill="url(#gPalace)"/>')
        for lv in range(4):
            yy = -34 - lv * 22
            ww = 40 - lv * 7
            o.append(f'<path d="M{-ww - 8},{yy + 2}C{-ww},{yy} {-ww + 3},{yy - 3} {-ww + 5},{yy - 8}L{ww - 5},{yy - 8}C{ww - 3},{yy - 3} {ww},{yy} {ww + 8},{yy + 2}C{ww - 10},{yy - 2} {-ww + 10},{yy - 2} {-ww - 8},{yy + 2}Z" fill="#203a46" stroke="#d6ae58" stroke-opacity=".7" stroke-width="1"/>')
            if lv < 3:
                o.append(f'<rect x="{-ww + 10}" y="{yy - 22}" width="{2 * ww - 20}" height="14" fill="url(#gPalace)"/>')
        o.append('<path d="M0,-122V-144" stroke="#e8c26a" stroke-width="1.6"/><circle cy="-146" r="3" fill="#ffd36a"/>')
        win = [(-6, -30), (-6, -52), (-6, -74), (-6, -96)]
    if glow:
        for i, (wx, wy) in enumerate(win):
            o.append(f'<rect x="{wx}" y="{wy}" width="12" height="9" fill="#ffcf6a">'
                     f'<animate attributeName="opacity" values=".4;1;.6;.4" dur="{4 + i * 0.7:.1f}s" repeatCount="indefinite"/></rect>')
    o.append("</g>")
    return "".join(o)


def island(x, y, w, seed, top_obj=""):
    rnd = random.Random(seed)
    h = w * rnd.uniform(0.9, 1.25)
    # top surface
    top = [(x - w / 2, y)]
    for i in range(1, 8):
        u = i / 8
        top.append((x - w / 2 + u * w, y - rnd.uniform(4, 18) * math.sin(math.pi * u)))
    top.append((x + w / 2, y))
    # underside jagged
    under = []
    n = 9
    for i in range(1, n):
        u = i / n
        xx = x + w / 2 - u * w
        depth = h * (math.sin(math.pi * u) ** 1.4) * rnd.uniform(0.75, 1.05)
        under.append((xx, y + depth))
    d = "M" + "L".join(pt(p) for p in top) + "L" + "L".join(pt(p) for p in under) + "Z"
    o = [f'<path d="{d}" fill="url(#gRock)"/>']
    # facet lines
    for i in range(4):
        u = rnd.uniform(0.2, 0.8)
        xx = x - w / 2 + u * w
        o.append(f'<path d="M{f(xx)},{f(y + 4)}L{f(xx + rnd.uniform(-10, 10))},{f(y + h * 0.6 * math.sin(math.pi * u))}" stroke="#7fb5a4" stroke-opacity=".18" stroke-width="1.2"/>')
    # grassy/jade top rim
    td = "M" + "L".join(pt(p) for p in top) + f"L{f(x + w / 2 - 6)},{f(y + 8)}L{f(x - w / 2 + 6)},{f(y + 8)}Z"
    o.append(f'<path d="{td}" fill="url(#gRockTop)" opacity=".85"/>')
    o.append(f'<path d="M' + "L".join(pt(p) for p in top) + '" fill="none" stroke="#e9d08a" stroke-opacity=".45" stroke-width="1"/>')
    # small waterfall of mist
    wx = x + rnd.uniform(-w * 0.2, w * 0.2)
    o.append(f'<path d="M{f(wx)},{f(y + 6)}C{f(wx - 2)},{f(y + h * 0.5)} {f(wx + 3)},{f(y + h * 0.8)} {f(wx)},{f(y + h * 1.3)}" '
             f'stroke="#bfe6ee" stroke-opacity=".35" stroke-width="2.5" stroke-dasharray="6 9">'
             f'<animate attributeName="stroke-dashoffset" values="0;-30" dur="1.6s" repeatCount="indefinite"/></path>')
    o.append(top_obj)
    # mist around base
    o.append(f'<ellipse cx="{f(x)}" cy="{f(y + h * 0.35)}" rx="{f(w * 0.75)}" ry="{f(h * 0.12)}" fill="#8fb3c9" opacity=".18"/>')
    return "".join(o)


isl = []
isl.append(island(190, 360, 190, 1, palace(190, 352, 0.95, kind=0)))
isl.append(island(560, 250, 90, 2, palace(560, 244, 0.45, kind=1)))
isl.append(island(1110, 330, 230, 3, palace(1080, 322, 1.05, kind=0) + palace(1165, 324, 0.6, kind=1)))
isl.append(island(1420, 470, 120, 4, palace(1420, 466, 0.55, kind=1)))
isl.append(island(860, 180, 70, 5))
isl.append(island(330, 520, 80, 6))
B(scroll_layer("islands", "".join(isl), 110, 'opacity=".78"'))

B(scroll_layer("ridgeNear", f'<path d="{r2}" fill="url(#gRidgeNear)"/>'
               f'<path d="{r2}" fill="none" stroke="#e2c27a" stroke-opacity=".22" stroke-width="1.2"/>', 140))

# ---------------------------------------------------------------- magic circle (法阵)
CX, CY = 790, 470
mc = []
M = mc.append
M(f'<circle cx="{CX}" cy="{CY}" r="470" fill="url(#gHalo)"/>')
outer = []
O = outer.append
O(f'<circle cx="{CX}" cy="{CY}" r="440" fill="none" stroke="#f0c45a" stroke-width="2.4"/>')
O(f'<circle cx="{CX}" cy="{CY}" r="446" fill="none" stroke="#f0c45a" stroke-width="10" stroke-opacity=".12"/>')
O(f'<circle cx="{CX}" cy="{CY}" r="424" fill="none" stroke="#e0b24e" stroke-width="1"/>')
O(f'<circle cx="{CX}" cy="{CY}" r="360" fill="none" stroke="#e0b24e" stroke-width="1.6"/>')
O(f'<circle cx="{CX}" cy="{CY}" r="372" fill="none" stroke="#e0b24e" stroke-width=".8" stroke-dasharray="2 7"/>')
ticks = []
for i in range(144):
    a = i * 360 / 144
    l = 14 if i % 6 == 0 else 7
    ticks.append(f'<path d="M0,-{424}V-{424 + l}" transform="rotate({f(a)})"/>')
O(f'<g transform="translate({CX},{CY})" stroke="#f0c45a" stroke-width="1.2">' + "".join(ticks) + "</g>")
# 8 trigrams (八卦)
TRI = ["111", "011", "101", "001", "110", "010", "100", "000"]
tg = []
for i, tri in enumerate(TRI):
    a = i * 45
    lines = []
    for j, bit in enumerate(tri):
        yy = -410 + j * 10
        if bit == "1":
            lines.append(f'<rect x="-24" y="{yy}" width="48" height="5"/>')
        else:
            lines.append(f'<rect x="-24" y="{yy}" width="20" height="5"/><rect x="4" y="{yy}" width="20" height="5"/>')
    tg.append(f'<g transform="rotate({a})">' + "".join(lines) + "</g>")
    tg.append(f'<g transform="rotate({a + 22.5}) translate(0,-392) scale(.9)"><use xlink:href="#lei" stroke="#f0c45a" stroke-width="1.6"/>'
              f'<use xlink:href="#lei" stroke="#f0c45a" stroke-width="1.6" transform="translate(22,0) scale(-1,1)"/>'
              f'<use xlink:href="#lei" stroke="#f0c45a" stroke-width="1.6" transform="translate(-22,0) scale(-1,1)"/></g>')
O(f'<g transform="translate({CX},{CY})" fill="#f0c45a">' + "".join(tg) + "</g>")
dots = "".join(f'<circle cx="0" cy="-366" r="2.2" transform="rotate({i * 7.5})"/>' for i in range(48))
O(f'<g transform="translate({CX},{CY})" fill="#ffd36a">{dots}</g>')
M(f'<g>{"".join(outer)}<animateTransform attributeName="transform" type="rotate" values="0 {CX} {CY};360 {CX} {CY}" dur="40s" repeatCount="indefinite"/></g>')

inner = []
I = inner.append
I(f'<circle cx="{CX}" cy="{CY}" r="332" fill="none" stroke="#e0b24e" stroke-width="1.4"/>')
I(f'<circle cx="{CX}" cy="{CY}" r="300" fill="none" stroke="#e0b24e" stroke-width="2"/>')


def star_poly(r, k, rot0):
    return " ".join(pt((CX + r * math.sin(math.radians(rot0 + i * 360 / k)), CY - r * math.cos(math.radians(rot0 + i * 360 / k)))) for i in range(k))


I(f'<polygon points="{star_poly(300, 4, 0)}" fill="none" stroke="#e0b24e" stroke-width="1.4"/>')
I(f'<polygon points="{star_poly(300, 4, 45)}" fill="none" stroke="#e0b24e" stroke-width="1.4"/>')
I(f'<polygon points="{star_poly(212, 6, 0)}" fill="none" stroke="#e0b24e" stroke-width="1"/>')
I(f'<polygon points="{star_poly(212, 6, 30)}" fill="none" stroke="#e0b24e" stroke-width="1"/>')
I(f'<circle cx="{CX}" cy="{CY}" r="212" fill="none" stroke="#f0c45a" stroke-width="1.6"/>')
I(f'<circle cx="{CX}" cy="{CY}" r="150" fill="none" stroke="#f0c45a" stroke-width="1" stroke-dasharray="10 4 2 4"/>')
hu = "".join(f'<g transform="rotate({i * 15}) translate(0,-256) scale(1.1)"><use xlink:href="#lei" stroke="#f0c45a" stroke-width="1.5"/></g>' for i in range(24))
I(f'<g transform="translate({CX},{CY})">{hu}</g>')
# taotie-like eye glyph pairs on inner ring
gl = "".join(f'<g transform="rotate({i * 60 + 30}) translate(0,-318)"><path d="M-14,0C-8,-8 8,-8 14,0C8,8 -8,8 -14,0Z" fill="none" stroke="#ffd36a" stroke-width="1.4"/><circle r="3" fill="#ffd36a"/></g>' for i in range(6))
I(f'<g transform="translate({CX},{CY})">{gl}</g>')
M(f'<g>{"".join(inner)}<animateTransform attributeName="transform" type="rotate" values="360 {CX} {CY};0 {CX} {CY}" dur="60s" repeatCount="indefinite"/></g>')
magic = (f'<g id="magicCircle" opacity=".42" style="mix-blend-mode:screen">{"".join(mc)}'
         f'<animate attributeName="opacity" values=".36;.48;.36" dur="7s" repeatCount="indefinite"/></g>')

# golden particles drifting on arcs
arcs = [
    "M260,640C380,260 1100,140 1360,420",
    "M1340,700C1180,300 520,220 300,470",
    "M420,780C520,520 1080,520 1220,760",
    "M520,180C760,90 1100,140 1260,300",
]
ap = []
ra = random.Random(11)
for i in range(22):
    p = arcs[i % len(arcs)]
    d = ra.uniform(10, 18)
    b = -ra.uniform(0, d)
    r = ra.uniform(3, 6.5)
    ap.append(f'<circle r="{f(r)}" fill="url(#gDot)"><animateMotion path="{p}" dur="{d:.1f}s" begin="{b:.1f}s" repeatCount="indefinite"/>'
              f'<animate attributeName="opacity" values="0;1;.8;0" keyTimes="0;.15;.8;1" dur="{d:.1f}s" begin="{b:.1f}s" repeatCount="indefinite"/></circle>')
arcpart = '<g id="arcParticles">' + "".join(ap) + "</g>"

# mid cloud sea
mid = []
rm = random.Random(21)
xs = [90, 330, 560, 800, 1040, 1270, 1500]
for i, x in enumerate(xs):
    y = 770 + rm.uniform(-20, 25)
    w = rm.uniform(220, 300)
    mid.append(cloud_puffs(x, y, w, rm.uniform(48, 64), 6, 100 + i))
for i, x in enumerate([200, 450, 700, 950, 1200, 1450]):
    mid.append(cloud_puffs(x, 850 + rm.uniform(-10, 15), rm.uniform(260, 320), rm.uniform(55, 70), 7, 200 + i,
                           fill="url(#gCloudFront)"))
for i in range(5):
    x = 160 + i * 330 + rm.uniform(-40, 40)
    mid.append(f'<use xlink:href="#ruyi" transform="translate({f(x)},{f(745 + rm.uniform(-10, 20))}) scale({rm.uniform(0.7, 1.1):.2f})" stroke="#ffe7a3" stroke-opacity=".55" stroke-width="2.2"/>')
midclouds = ('<rect x="0" y="790" width="1600" height="210" fill="url(#gCloudSea)"/>'
             + scroll_layer("midClouds", "".join(mid), 30))

far_mid = []
for i, x in enumerate([200, 520, 860, 1180, 1460]):
    far_mid.append(cloud_puffs(x, 700 + rm.uniform(-15, 15), rm.uniform(260, 340), 40, 7, 300 + i,
                               rim="url(#gRimCyan)", rimw=1.5))
farmidclouds = scroll_layer("farMidClouds", "".join(far_mid), 55, 'opacity=".55"')

# foreground clouds (fast)
fg = []
for i, x in enumerate([120, 470, 820, 1160, 1480]):
    y = 935 + rm.uniform(-15, 15)
    fg.append(cloud_puffs(x, y, rm.uniform(300, 380), rm.uniform(62, 80), 7, 500 + i, fill="url(#gCloudFront)"))
    fg.append(f'<use xlink:href="#ruyi" transform="translate({f(x + rm.uniform(-60, 60))},{f(y - 25)}) scale(1.3)" stroke="#ffe08a" stroke-opacity=".6" stroke-width="2.4"/>')
fgclouds = scroll_layer("fgClouds", "".join(fg), 12)

wisps = []
for i in range(6):
    x = i * 270 + 60
    y = 860 + (i % 3) * 22
    wisps.append(f'<ellipse cx="{x}" cy="{y}" rx="170" ry="14" fill="url(#gCloudFar)" opacity=".9"/>')
fgwisps = scroll_layer("fgWisps", "".join(wisps), 8)

edges = ('<g id="edgeMist">'
         '<rect x="0" y="0" width="260" height="1000" fill="url(#gEdgeL)"><animate attributeName="opacity" values=".7;1;.7" dur="8s" repeatCount="indefinite"/></rect>'
         '<rect x="1340" y="0" width="260" height="1000" fill="url(#gEdgeR)"><animate attributeName="opacity" values="1;.7;1" dur="9s" repeatCount="indefinite"/></rect>'
         '<g filter="url(#fMist)" opacity=".55">'
         '<ellipse cx="40" cy="300" rx="90" ry="200" fill="#9cbad0"><animate attributeName="cy" values="300;340;300" dur="11s" repeatCount="indefinite"/></ellipse>'
         '<ellipse cx="1570" cy="560" rx="80" ry="220" fill="#9cbad0"><animate attributeName="cy" values="560;520;560" dur="13s" repeatCount="indefinite"/></ellipse>'
         '</g></g>')

# ================================================================ THE MOUNT (麒麟)
FRONT = [
    (0.00, (-28, 0, -8)),
    (0.18, (-8, 2, 10)),
    (0.36, (18, 8, 30)),
    (0.48, (30, 42, 48)),
    (0.62, (12, 105, 55)),
    (0.80, (-30, 62, 12)),
    (0.92, (-42, 14, -14)),
]
HIND = [
    (0.00, (-22, -5, -10)),
    (0.18, (-2, 5, 8)),
    (0.36, (22, 14, 28)),
    (0.48, (34, 6, 48)),
    (0.62, (14, -62, 42)),
    (0.80, (-24, -72, 12)),
    (0.92, (-34, -26, -10)),
]
LEN = {"f": (105, 85, 38), "h": (120, 75, 38)}

UPPER = {
    "f": "M-25,-14C-28,26 -17,70 -12,105L12,105C17,70 25,32 23,-16Z",
    "h": "M-36,-34C-44,8 -30,60 -18,95C-13,108 -11,115 -11,120L11,120C15,98 24,70 29,40C33,8 32,-22 22,-40Z",
}
LOWER = {
    "f": "M-11,0C-10,30 -9,60 -9,85L9,85C9,60 10,30 11,0Z",
    "h": "M-11,0C-10,25 -9,50 -9,75L9,75C9,50 10,25 11,0Z",
}
HOOF = ("<path d='M-9,0C-9,10 -8,18 -7,22L8,22C9,16 9,8 9,0Z' fill='{leg}'/>"
        "<path d='M-10,20L14,20C17,25 18,31 16,37L3,38L1,31L-1,38L-11,37C-12,31 -12,25 -10,20Z' fill='url(#gHoof)' stroke='#e2b85a' stroke-width='1.1'/>"
        "<path d='M-9,20.5H13' stroke='#ffd36a' stroke-width='2'/>")


def leg(kind, px, py, phi, near):
    L1, L2, L3 = LEN[kind]
    keys = FRONT if kind == "f" else HIND
    sm = [interp(keys, k / NS) for k in range(NS + 1)]
    begin = f"{-phi * P:.3f}s"
    legfill = "url(#gLegNear)" if near else "url(#gLegFar)"
    sc_op = ".75" if near else ".35"
    gold_op = ".8" if near else ".35"

    def ra(i):
        return anim_rot([s[i] for s in sm], begin=begin)

    up = UPPER[kind]
    lo = LOWER[kind]
    flame_fill = "url(#gFlameV)" if near else "url(#gFlameVC)"
    o = [f'<g transform="translate({px},{py})"><g>{ra(0)}']
    o.append(f'<path d="{up}" fill="{legfill}"/><path d="{up}" fill="url(#pScaleS)" opacity="{sc_op}"/>')
    o.append(f'<path d="{up}" fill="none" stroke="#0a1a1c" stroke-width="1.6"/>')
    if kind == "f":
        o.append(f'<path d="M-14,10C-10,40 -8,70 -6,98" fill="none" stroke="#f0c45a" stroke-opacity="{gold_op}" stroke-width="1.2"/>')
        # elbow flame tuft
        o.append(f'<use xlink:href="#hoofFlame" fill="{flame_fill}" transform="translate(-18,30) rotate(-70) scale(.9)" opacity=".9">'
                 f'<animateTransform attributeName="transform" type="scale" additive="sum" values="1;1.25;.9;1" dur=".45s" repeatCount="indefinite"/></use>')
    else:
        o.append(f'<path d="M20,-20C26,20 18,60 8,100" fill="none" stroke="#f0c45a" stroke-opacity="{gold_op}" stroke-width="1.2"/>')
        o.append(f'<path d="M-30,-10C-34,20 -26,50 -18,70" fill="none" stroke="#bff6e0" stroke-opacity=".25" stroke-width="3"/>')
    o.append(f'<g transform="translate(0,{L1})"><g>{ra(1)}')
    o.append(f'<path d="{lo}" fill="{legfill}"/><path d="{lo}" fill="url(#pScaleS)" opacity="{sc_op}"/>')
    o.append(f'<path d="{lo}" fill="none" stroke="#0a1a1c" stroke-width="1.4"/>')
    o.append(f'<circle r="13" fill="{legfill}" stroke="#0a1a1c" stroke-width="1.2"/>'
             f'<circle r="6" fill="none" stroke="#e9c76a" stroke-opacity="{gold_op}" stroke-width="1.2"/>')
    o.append(f'<g transform="translate(0,{L2})"><g>{ra(2)}')
    # fetlock flame (灵焰)
    o.append(f'<use xlink:href="#hoofFlame" fill="{flame_fill}" transform="translate(-6,10) rotate(-58) scale(1.05)">'
             f'<animateTransform attributeName="transform" type="scale" additive="sum" values="1;1.3;.85;1.15;1" dur=".38s" repeatCount="indefinite"/></use>')
    o.append(HOOF.replace("{leg}", legfill))
    o.append(f'<circle cy="2" r="9.5" fill="{legfill}" stroke="#0a1a1c" stroke-width="1"/>')
    o.append(f'<ellipse cx="3" cy="38" rx="20" ry="5" fill="url(#gGlowGold)" opacity="{".75" if near else ".4"}"/>')
    o.append("</g></g></g></g></g></g>")
    return "".join(o)


def hoof_contact(kind, px, py, phi):
    L1, L2, L3 = LEN[kind]
    keys = FRONT if kind == "f" else HIND
    a1, a2, a3 = interp(keys, 0.0)
    v = rot((3, L3), a3)
    v = (v[0], v[1] + L2)
    v = rot(v, a2)
    v = (v[0], v[1] + L1)
    v = rot(v, a1)
    loc = (px + v[0], py + v[1])
    g = (-phi) % 1
    w = rot_about(loc, pitch(g), PITCH_C)
    return (w[0], w[1] + bob(g))


LEGS = [  # kind, px, py, phase offset, near
    ("h", 632, 512, 0.00, False),
    ("f", 930, 522, 0.62, False),
    ("h", 618, 520, 0.90, True),
    ("f", 946, 530, 0.52, True),
]

# body outline (with neck)
BODY = ("M565,505C548,470 560,432 610,424C660,416 700,438 750,444C800,450 850,438 885,420"
        "C920,400 950,360 985,325C1005,305 1025,295 1045,300L1072,348C1058,382 1030,420 1005,455"
        "C990,480 995,515 980,545C960,575 920,585 880,585C820,592 760,592 700,585"
        "C660,580 630,570 605,555C585,545 572,528 565,505Z")

mount = []
A = mount.append

# --- tail (flame plume) behind everything
tail = []
tail.append('<path d="M575,462C556,452 540,452 520,460C540,470 556,480 575,485Z" fill="#1b4a44"/>')
for (base, length, w0, amp, dur, fill, off, curve) in [
    (188, 260, 46, 26, 1.7, "url(#gTailRed)", 0.0, -14),
    (172, 240, 40, 30, 1.5, "url(#gTailRed)", 0.33, 10),
    (198, 210, 34, 24, 1.3, "url(#gTailGold)", 0.15, -20),
    (180, 220, 30, 28, 1.25, "url(#gTailGold)", 0.55, 4),
    (186, 160, 18, 22, 1.1, "url(#gTailCyan)", 0.4, -8),
]:
    tail.append(ribbon_anim(fill, (568, 470), base, length, flame_w(w0), amp, 1.1, dur, off, curve,
                            n=10, frames=12))
A('<g id="tail">' + "".join(tail) + "</g>")

# --- saddle ribbons (飘带) — behind body so they trail along the flank behind the rider's leg
rib = []
rib.append(ribbon_anim("url(#gRibbonCyan)", (692, 452), 178, 250, sash_w(14, 9), 18, 1.3, 1.6, 0.0, -6,
                       n=12, frames=12, tip_obj='<use xlink:href="#tassel" transform="rotate(90)"/>'))
rib.append(ribbon_anim("url(#gRibbonRed)", (700, 460), 170, 205, sash_w(12, 7), 22, 1.5, 1.35, 0.4, 4,
                       n=12, frames=12, tip_obj='<use xlink:href="#tassel" transform="rotate(80) scale(.85)"/>'))

# --- far legs
for kind, px, py, phi, near in LEGS:
    if not near:
        A(leg(kind, px, py, phi, near))

# --- body
A('<g id="kirinBody">')
A(f'<path d="{BODY}" fill="url(#gBody)"/>')
A(f'<path d="{BODY}" fill="url(#pScale)" opacity=".9"/>')
A('<clipPath id="cBody"><path d="' + BODY + '"/></clipPath>')
A('<g clip-path="url(#cBody)">')
# throat & belly plates (蛇腹)
plates = []
for i in range(9):
    t = i / 8
    x = 1062 - t * 75
    y = 352 + t * 120
    plates.append(f'<path d="M{f(x - 14)},{f(y)}C{f(x - 6)},{f(y + 12)} {f(x + 10)},{f(y + 12)} {f(x + 18)},{f(y - 2)}" fill="none" stroke="#f0c45a" stroke-width="1.4" stroke-opacity=".7"/>')
for i in range(14):
    x = 640 + i * 24
    plates.append(f'<path d="M{x},{570 + 6 * math.sin(i / 13 * math.pi)}c4,14 16,14 20,0" fill="url(#gBelly)" stroke="#6a420c" stroke-width=".8" opacity=".85"/>')
A("".join(plates))
A(f'<rect x="540" y="280" width="560" height="320" fill="url(#gBodyShade)"/>')
# muscle highlights
A('<path d="M900,450C930,470 945,500 945,530" fill="none" stroke="#c8fff0" stroke-opacity=".25" stroke-width="5"/>'
  '<path d="M610,450C640,470 650,500 640,540" fill="none" stroke="#c8fff0" stroke-opacity=".22" stroke-width="5"/>'
  '<path d="M700,450C760,470 840,470 890,440" fill="none" stroke="#c8fff0" stroke-opacity=".15" stroke-width="8"/>')
A("</g>")
A(f'<path d="{BODY}" fill="none" stroke="#06141a" stroke-width="2.2"/>')
A('<path d="M610,424C660,416 700,438 750,444C800,450 850,438 885,420C920,400 950,360 985,325C1005,305 1025,295 1045,300" fill="none" stroke="#ffe7a3" stroke-opacity=".55" stroke-width="1.4"/>')
# dorsal spines
sp = []
for i in range(10):
    t = i / 9
    x = 600 + t * 120
    y = 428 + 12 * t
    sp.append(f'<path d="M{f(x)},{f(y)}l5,-10l6,10z"/>')
A('<g fill="#e9c76a" opacity=".8">' + "".join(sp) + "</g>")
A("</g>")

# --- saddle ribbons drawn over the flank
A('<g id="saddleRibbons">' + "".join(rib) + "</g>")

# --- mane (flowing flame)
roots = [(872, 428), (890, 416), (906, 404), (921, 391), (936, 376), (951, 360), (966, 345), (982, 330), (998, 316), (1015, 305)]
mane = []
for layer, (fill, wmul, lmul, ampd, dur) in enumerate([
        ("url(#gManeRed)", 1.0, 1.0, 22, 1.3), ("url(#gManeGold)", 0.62, 0.78, 26, 1.1), ("url(#gManeCyan)", 0.3, 0.55, 30, 0.9)]):
    for i, r in enumerate(roots):
        base = 212 + i * 2.2
        length = (90 + 30 * math.sin(i * 1.3) + i * 4) * lmul
        mane.append(ribbon_anim(fill, (r[0] + layer * 2, r[1] + layer * 3), base, length, flame_w(30 * wmul), ampd, 1.0,
                                dur, i * 0.09 + layer * 0.2, -18, n=8, frames=10))
A('<g id="mane">' + "".join(mane) + "</g>")

# --- near legs
for kind, px, py, phi, near in LEGS:
    if near:
        A(leg(kind, px, py, phi, near))

# --- body flame tufts (shoulder & haunch)
A('<g opacity=".95">'
  '<use xlink:href="#hoofFlame" fill="url(#gFlameV)" transform="translate(905,555) rotate(-72) scale(1.3)">'
  '<animateTransform attributeName="transform" type="scale" additive="sum" values="1;1.2;.9;1" dur=".5s" repeatCount="indefinite"/></use>'
  '<use xlink:href="#hoofFlame" fill="url(#gFlameVC)" transform="translate(600,500) rotate(-80) scale(1.2)">'
  '<animateTransform attributeName="transform" type="scale" additive="sum" values="1;.88;1.22;1" dur=".55s" repeatCount="indefinite"/></use>'
  '</g>')

# --- tack: crupper, breast collar, saddle cloth, girth, saddle
tack = []
T = tack.append
T('<path d="M684,470C640,474 600,468 572,470" fill="none" stroke="#1d1410" stroke-width="9"/>'
  '<path d="M684,470C640,474 600,468 572,470" fill="none" stroke="url(#gGoldH)" stroke-width="5"/>')
for x in (650, 620, 592):
    T(f'<use xlink:href="#pendant" transform="translate({x},472) scale(.8)"/>')
T('<path d="M826,470C870,490 930,506 982,500" fill="none" stroke="#1d1410" stroke-width="11"/>'
  '<path d="M826,470C870,490 930,506 982,500" fill="none" stroke="url(#gGoldH)" stroke-width="6.5"/>'
  '<path d="M826,470C870,490 930,506 982,500" fill="none" stroke="#7a2a12" stroke-width="1.2" stroke-dasharray="3 6"/>')
for i, (x, y) in enumerate([(870, 490), (918, 502), (958, 504)]):
    T(f'<g transform="translate({x},{y})"><g><use xlink:href="#bell"/>'
      f'<animateTransform attributeName="transform" type="rotate" values="-14;14;-14" keyTimes="0;.5;1" calcMode="spline" '
      f'keySplines=".45 0 .55 1;.45 0 .55 1" dur=".6s" begin="{-i * 0.12:.2f}s" repeatCount="indefinite"/></g></g>')
    T(f'<circle cx="{x}" cy="{y}" r="4" fill="#ffe08a" stroke="#6a420c"/>')
CLOTH = "M680,448C720,452 790,452 832,445C840,470 838,505 830,532C800,548 720,548 688,534C678,505 675,475 680,448Z"
T(f'<path d="{CLOTH}" fill="url(#gVermil)" stroke="#2a0608" stroke-width="2"/>')
T(f'<path d="{CLOTH}" fill="url(#pClothCloud)"/>')
T('<path d="M688,458C722,462 788,462 822,456C829,478 828,505 821,524C796,537 724,537 696,525C688,503 685,480 688,458Z" fill="none" stroke="#f2c86a" stroke-width="1.6"/>')
T('<clipPath id="cCloth"><path d="' + CLOTH + '"/></clipPath>')
T('<rect x="670" y="518" width="180" height="40" fill="url(#pHui)" clip-path="url(#cCloth)"/>')
T('<path d="M688,534C720,548 800,548 830,532" fill="none" stroke="#ffe08a" stroke-width="2.4"/>')
T('<use xlink:href="#ruyi" transform="translate(758,498) scale(.62)" stroke="#ffe08a" stroke-width="2.6"/>')
T('<use xlink:href="#tassel" transform="translate(690,536)"/><use xlink:href="#tassel" transform="translate(828,534)"/>')
T('<path d="M796,536L816,536L820,590L800,591Z" fill="url(#gBlackGold)" stroke="#e2b85a" stroke-width="1.2"/>'
  '<rect x="799" y="556" width="19" height="12" rx="2" fill="none" stroke="#ffd36a" stroke-width="2"/>')
SADDLE = "M688,440C694,420 708,420 718,430C740,440 776,440 796,428C804,416 812,404 822,406C830,416 826,438 816,450L700,456C692,453 686,448 688,440Z"
T(f'<path d="{SADDLE}" fill="url(#gBlackGold)" stroke="#e8c26a" stroke-width="2"/>')
T('<path d="M700,446C740,452 790,450 812,440" fill="none" stroke="#e8c26a" stroke-width="1" stroke-dasharray="4 3"/>'
  '<circle cx="818" cy="414" r="5" fill="#5fe3d4" stroke="#ffe08a" stroke-width="1.5"/>'
  '<circle cx="694" cy="434" r="4" fill="#e8492e" stroke="#ffe08a" stroke-width="1.2"/>')
T('<path d="M772,452L798,560" stroke="#1d1410" stroke-width="5"/><path d="M772,452L798,560" stroke="#c9a14a" stroke-width="2"/>')
A('<g id="tack">' + "".join(tack) + "</g>")

# ---------------------------------------------------------------- kirin head (nodding)
head = []
Hh = head.append
# far antler then near antler (behind skull)
Hh('<g fill="none" stroke-linecap="round" stroke-linejoin="round">'
   '<path d="M1078,282C1076,250 1074,228 1058,206C1048,192 1038,184 1026,170M1066,236C1080,224 1088,210 1088,194M1046,196C1050,180 1058,168 1070,160" stroke="#3a2a12" stroke-width="10"/>'
   '<path d="M1078,282C1076,250 1074,228 1058,206C1048,192 1038,184 1026,170M1066,236C1080,224 1088,210 1088,194M1046,196C1050,180 1058,168 1070,160" stroke="#a8803a" stroke-width="5"/>'
   '<path d="M1060,284C1046,252 1032,226 1004,206C988,196 972,194 952,182M1036,242C1046,226 1050,212 1046,192M1012,214C1010,194 1016,178 1028,166M984,198C972,184 968,168 972,154" stroke="#4a3010" stroke-width="12"/>'
   '<path d="M1060,284C1046,252 1032,226 1004,206C988,196 972,194 952,182M1036,242C1046,226 1050,212 1046,192M1012,214C1010,194 1016,178 1028,166M984,198C972,184 968,168 972,154" stroke="url(#gAntler)" stroke-width="7"/>'
   '<path d="M1056,272C1044,246 1032,226 1008,210" stroke="#fff4c8" stroke-width="1.5" stroke-opacity=".7"/>'
   '</g>')
# mouth interior
Hh('<path d="M1088,344L1182,338L1162,360Z" fill="url(#gMouth)"/>')
Hh('<path d="M1100,348L1104,357L1108,349ZM1116,349L1120,358L1124,350ZM1134,350L1137,357L1140,350ZM1150,350L1152,356L1155,350Z" fill="url(#gIvory)"/>')
Hh('<path d="M1166,341L1170,356L1175,341Z" fill="url(#gIvory)"/>')
HEAD = ("M1032,296C1046,272 1088,262 1122,272C1146,279 1166,292 1180,309C1190,318 1190,333 1180,340"
        "C1168,346 1150,345 1132,345L1092,344L1158,357C1166,359 1166,367 1156,370C1130,377 1095,375 1072,366"
        "C1052,358 1038,340 1034,322C1032,312 1030,304 1032,296Z")
Hh(f'<path d="{HEAD}" fill="url(#gBody)"/>')
Hh('<clipPath id="cHead"><path d="' + HEAD + '"/></clipPath>')
Hh(f'<g clip-path="url(#cHead)"><rect x="1020" y="260" width="180" height="120" fill="url(#pScaleS)" opacity=".7"/>'
   '<path d="M1040,300C1080,300 1130,300 1190,330L1190,260L1030,260Z" fill="#bff6e0" opacity=".12"/>'
   '<rect x="1020" y="340" width="180" height="40" fill="#04121a" opacity=".35"/></g>')
Hh(f'<path d="{HEAD}" fill="none" stroke="#06141a" stroke-width="2"/>')
# snout ridge and nose
Hh('<path d="M1122,272C1146,279 1166,292 1180,309" fill="none" stroke="#ffe7a3" stroke-width="1.6" stroke-opacity=".8"/>'
   '<path d="M1176,318C1170,314 1166,320 1170,324C1174,327 1178,322 1175,320" fill="none" stroke="#1a0c08" stroke-width="2"/>'
   '<path d="M1150,300C1158,296 1164,300 1166,306" fill="none" stroke="#f0c45a" stroke-width="1.4"/>')
# ear & jaw fins
Hh('<path d="M1046,292C1030,278 1010,280 996,290C1012,292 1028,300 1040,306Z" fill="url(#gBronzeG)" stroke="#e8c26a" stroke-width="1.2"/>'
   '<path d="M1040,332L1014,330L1030,342L1006,350L1032,354L1016,366L1048,362Z" fill="url(#gTailGold)" opacity=".9"/>')
# brow ridge & eye
Hh('<circle cx="1098" cy="296" r="22" fill="url(#gEyeGlow)"><animate attributeName="opacity" values=".45;1;.45" dur="2.2s" repeatCount="indefinite"/></circle>')
Hh('<path d="M1083,299C1091,288 1106,286 1115,292C1108,301 1094,304 1083,299Z" fill="url(#gEye)" stroke="#2a0a04" stroke-width="1.2"/>'
   '<path d="M1099,290C1101,294 1101,298 1099,302" stroke="#1a0600" stroke-width="2.4"/>')
Hh('<path d="M1076,292C1088,276 1112,272 1128,282C1112,280 1096,284 1084,296Z" fill="url(#gGold)" stroke="#6a420c" stroke-width=".8"/>'
   '<path d="M1080,284C1070,270 1062,262 1050,260C1062,268 1068,276 1072,288Z" fill="url(#gGold)"/>')
# bridle
Hh('<g fill="none" stroke-linecap="round">'
   '<path d="M1140,282C1148,300 1150,326 1142,348" stroke="#1d1410" stroke-width="7"/>'
   '<path d="M1140,282C1148,300 1150,326 1142,348" stroke="url(#gGoldH)" stroke-width="4"/>'
   '<path d="M1052,300C1076,316 1096,332 1110,346" stroke="#1d1410" stroke-width="6"/>'
   '<path d="M1052,300C1076,316 1096,332 1110,346" stroke="#d8ad52" stroke-width="3"/>'
   '<path d="M1060,288C1090,282 1120,280 1140,282" stroke="#d8ad52" stroke-width="3"/>'
   '<circle cx="1112" cy="349" r="6.5" stroke="#ffe08a" stroke-width="2.6"/>'
   '</g><circle cx="1140" cy="282" r="4" fill="#5fe3d4" stroke="#ffe08a"/><circle cx="1060" cy="288" r="5" fill="#e8492e" stroke="#ffe08a"/>')
# whiskers & beard (flowing)
wh = []
wh.append(ribbon_anim("url(#gWhisker)", (1172, 330), 168, 190, thin_w(5), 20, 1.4, 1.8, 0.0, 12, n=12, frames=12))
wh.append(ribbon_anim("url(#gWhisker)", (1160, 338), 176, 150, thin_w(4), 24, 1.2, 1.5, 0.35, 18, n=12, frames=12))
for i, (r, base, ln) in enumerate([((1086, 368), 150, 70), ((1104, 372), 140, 60), ((1068, 362), 158, 64)]):
    wh.append(ribbon_anim("url(#gTailRed)", r, base, ln, flame_w(16), 26, 1.0, 1.0, i * 0.3, 20, n=7, frames=10))
Hh("".join(wh))
nod = samples(head_nod)
headgrp = f'<g id="kirinHead">{anim_rot(nod, POLL)}{"".join(head)}</g>'
A(headgrp)

# ================================================================ THE RIDER (饕餮)
rider = []
R = rider.append
# cape / 披帛 (flowing behind)
cape_tip = ('<g><path d="M0,-10L9,0L0,16L-9,0Z" fill="url(#gGold)" stroke="#5a3a0c" stroke-width=".8"/><circle r="3.4" fill="#e8492e"/>'
            '<path d="M0,16V36M-4,18L-7,34M4,18L7,34" stroke="#ffd36a" stroke-width="1.4"/></g>')
CAPE = dict(amp=24, waves=1.6, dur=2.2, curve=-10, n=16, frames=16, amp2=8, waves2=2.6)
R(ribbon_anim("url(#gCape)", (764, 300), 182, 430, sash_w(40, 20), CAPE["amp"], CAPE["waves"], CAPE["dur"], 0.0, CAPE["curve"],
              n=CAPE["n"], frames=CAPE["frames"], amp2=CAPE["amp2"], waves2=CAPE["waves2"],
              extra='stroke="#2a0408" stroke-width="1"', tip_obj=cape_tip))
R(ribbon_anim("url(#gCapeHi)", (766, 302), 182, 410, sash_w(12, 4), CAPE["amp"], CAPE["waves"], CAPE["dur"], 0.0, CAPE["curve"],
              n=CAPE["n"], frames=CAPE["frames"], amp2=CAPE["amp2"], waves2=CAPE["waves2"]))
R(ribbon_anim("#ffcf5a", (764, 300), 182, 430, sash_w(3, 2), CAPE["amp"], CAPE["waves"], CAPE["dur"], 0.0, CAPE["curve"],
              n=CAPE["n"], frames=CAPE["frames"], amp2=CAPE["amp2"], waves2=CAPE["waves2"], extra='opacity=".7"'))
# far arm
R('<path d="M772,300C792,318 806,336 816,356C828,366 846,374 870,380L874,392C846,392 820,384 804,370C792,350 778,330 766,316Z" fill="#1b2e24" stroke="#0a120e" stroke-width="1.5"/>'
  '<path d="M820,362L852,372L848,388L816,378Z" fill="url(#pLei)" stroke="#c9a14a" stroke-width="1"/>'
  '<circle cx="874" cy="386" r="9" fill="#24392c" stroke="#0a120e"/>')
# back hair flames behind head
hair = []
for i, (r, base, ln, w0) in enumerate([((752, 188), 196, 120, 34), ((746, 214), 190, 110, 30), ((754, 240), 182, 90, 26), ((762, 170), 204, 100, 26)]):
    hair.append(ribbon_anim("url(#gHair)", r, base, ln, flame_w(w0), 24, 1.1, 1.4, i * 0.22, -10, n=8, frames=10))
for i, (r, base, ln) in enumerate([((752, 196), 194, 80), ((750, 226), 186, 70)]):
    hair.append(ribbon_anim("url(#gTailRed)", r, base, ln, flame_w(14), 28, 1.0, 1.1, i * 0.3, -10, n=7, frames=10))
R("".join(hair))
# torso
TORSO = ("M712,432C700,392 705,342 720,306C730,286 760,272 790,272C820,275 838,295 834,322"
         "C832,352 822,388 800,416C790,432 770,440 745,440Z")
R(f'<path d="{TORSO}" fill="url(#gSkin)" stroke="#0a120e" stroke-width="2"/>')
R('<clipPath id="cTorso"><path d="' + TORSO + '"/></clipPath>')
R('<g clip-path="url(#cTorso)"><rect x="700" y="360" width="140" height="80" fill="url(#pLamellar)"/>'
  '<path d="M700,360H840" stroke="#e7c062" stroke-width="1.5"/></g>')
# chest plate with breathing
chest = ('<path d="M766,298C798,288 828,302 830,326C828,356 816,380 796,396C774,392 754,372 750,346C748,324 754,304 766,298Z" fill="url(#gBronze)" stroke="#ffe08a" stroke-width="1.6"/>'
         '<path d="M770,306C796,298 820,310 822,328C820,352 810,372 796,384C780,380 764,364 760,344C758,326 762,312 770,306Z" fill="url(#pHui)" opacity=".75"/>'
         '<path d="M774,318C786,312 806,314 814,326C810,344 802,356 794,364C784,358 776,344 772,332Z" fill="url(#gBlackGold)" stroke="#e8c26a" stroke-width="1.2"/>'
         # small taotie mask motif on breastplate
         '<path d="M780,330C786,324 792,326 794,332M808,328C804,324 798,326 796,332" fill="none" stroke="#ffd36a" stroke-width="1.6"/>'
         '<circle cx="786" cy="334" r="2.6" fill="#ff7a20"/><circle cx="804" cy="332" r="2.6" fill="#ff7a20"/>'
         '<path d="M795,336V352M786,346C790,352 800,352 804,346" fill="none" stroke="#ffd36a" stroke-width="1.4"/>'
         '<use xlink:href="#lei" transform="translate(778,350) scale(.45)" stroke="#ffd36a" stroke-width="2"/>'
         '<use xlink:href="#lei" transform="translate(812,348) scale(-.45,.45)" stroke="#ffd36a" stroke-width="2"/>')
R(f'<g transform="translate(792,345)"><g><animateTransform attributeName="transform" type="scale" values="1;1.045;1" keyTimes="0;.45;1" '
  f'calcMode="spline" keySplines=".4 0 .6 1;.4 0 .6 1" dur="3.6s" repeatCount="indefinite"/><g transform="translate(-792,-345)">{chest}</g></g></g>')
# near leg straddling the mount
R('<path d="M722,404C760,394 808,428 830,468C836,488 816,500 800,492C780,472 750,458 726,448Z" fill="url(#gSkin)" stroke="#0a120e" stroke-width="2"/>'
  '<path d="M734,410C768,404 806,432 824,464L812,474C794,446 764,426 732,424Z" fill="url(#pLamellar)" opacity=".9"/>'
  '<path d="M798,470C822,478 828,500 822,526C817,546 814,556 814,562L788,562C790,545 790,520 794,494Z" fill="url(#gBronze)" stroke="#0a120e" stroke-width="1.6"/>'
  '<path d="M800,486C816,492 818,508 814,528C812,540 810,548 810,554L794,554C795,540 795,520 798,500Z" fill="url(#pLei)" opacity=".85"/>'
  '<circle cx="812" cy="480" r="14" fill="url(#gGold)" stroke="#5a3a0c" stroke-width="1.2"/>'
  '<path d="M804,478C808,474 812,476 812,480M820,478C816,474 812,476 812,480M806,486C810,490 814,490 818,486" fill="none" stroke="#6a2a0c" stroke-width="1.4"/>'
  '<path d="M784,558L818,555C832,558 842,566 840,575L786,577Z" fill="#1d2b22" stroke="#0a120e" stroke-width="1.4"/>'
  '<path d="M820,575l4,6l3,-6M830,575l4,6l3,-6" fill="#e9dcb0"/>'
  '<path d="M780,580H846C848,570 844,560 836,556" fill="none" stroke="#ffd36a" stroke-width="3"/>')
# armored skirt (tassets) over hip/thigh
R('<g stroke="#ffe08a" stroke-width="1.2">'
  '<path d="M714,404L742,404L746,452L716,446Z" fill="url(#gBronze)"/>'
  '<path d="M742,406L772,408L780,456L748,454Z" fill="url(#gBronzeG)"/>'
  '<path d="M772,408L798,404L812,446L782,456Z" fill="url(#gBronze)"/>'
  '</g>'
  '<path d="M716,446L746,452L780,456L812,446" fill="none" stroke="#e8492e" stroke-width="2"/>')
# belt with taotie buckle
R('<path d="M708,398C740,410 780,410 812,396L814,410C780,424 740,424 710,412Z" fill="url(#gBlackGold)" stroke="#e8c26a" stroke-width="1.4"/>'
  '<g transform="translate(772,410)"><path d="M-14,-9H14L18,0L14,9H-14L-18,0Z" fill="url(#gGold)" stroke="#5a3a0c"/>'
  '<circle cx="-6" cy="-1" r="2.4" fill="#e8492e"/><circle cx="6" cy="-1" r="2.4" fill="#e8492e"/><path d="M-8,5H8" stroke="#5a3a0c" stroke-width="1.4"/></g>')

# ---- taotie head
th = []
TH = th.append
# horns
TH('<path d="M786,186C760,152 734,122 744,86C751,62 776,56 784,72C770,80 764,100 774,126C784,150 800,166 806,180Z" fill="url(#gHorn)" stroke="#3a2a10" stroke-width="1.6"/>'
   '<path d="M782,160L764,152M774,140L756,134M768,118L750,114M766,98L750,96" stroke="#3a2a10" stroke-width="2" stroke-opacity=".6"/>'
   '<path d="M842,182C852,150 874,126 866,98C862,82 844,78 840,90C852,100 854,120 842,140C834,154 830,168 828,182Z" fill="url(#gHorn)" stroke="#3a2a10" stroke-width="1.4" opacity=".92"/>'
   '<path d="M848,150L864,150M852,132L868,130M854,114L868,110" stroke="#3a2a10" stroke-width="1.6" stroke-opacity=".6"/>')
FACE = ("M740,215C738,185 760,165 795,160C830,157 866,170 879,195C891,215 889,240 881,258"
        "C873,280 856,296 831,301C800,306 765,296 752,276C742,260 740,236 740,215Z")
TH(f'<path d="{FACE}" fill="url(#gFace)" stroke="#0a120e" stroke-width="2.2"/>')
TH('<clipPath id="cFace"><path d="' + FACE + '"/></clipPath>')
TH('<g clip-path="url(#cFace)"><path d="M835,150L842,175L835,180L842,200L835,205L841,225L835,232" fill="none" stroke="#e8c26a" stroke-width="2"/>'
   '<path d="M745,160L740,300L760,300C752,260 752,200 770,160Z" fill="#06100c" opacity=".35"/></g>')
# ears
TH('<path d="M746,204C728,196 716,200 708,212C722,214 734,220 744,226Z" fill="url(#gBronzeG)" stroke="#e8c26a" stroke-width="1.2"/>')
# forehead diadem
TH('<path d="M754,182C780,170 830,168 872,184L870,194C830,180 782,182 756,194Z" fill="url(#gGold)" stroke="#5a3a0c" stroke-width="1"/>'
   '<path d="M835,170L844,182L835,196L826,182Z" fill="#5fe3d4" stroke="#ffe08a" stroke-width="1.4"/>'
   '<circle cx="790" cy="184" r="3" fill="#e8492e"/><circle cx="862" cy="186" r="2.4" fill="#e8492e"/>')
# cheek thunder spirals (饕餮纹 motif)
TH('<use xlink:href="#lei" transform="translate(772,246) scale(.75)" stroke="#e8c26a" stroke-width="1.8"/>'
   '<use xlink:href="#lei" transform="translate(870,236) scale(-.55,.55)" stroke="#e8c26a" stroke-width="1.8"/>'
   '<path d="M752,228C760,220 770,222 772,232M880,224C876,218 870,220 868,228" fill="none" stroke="#e8c26a" stroke-width="1.6"/>')
# brows
TH('<path d="M756,206C770,186 802,184 820,200L816,210C800,198 776,198 762,214Z" fill="url(#gBlackGold)" stroke="#e8c26a" stroke-width="1.4"/>'
   '<path d="M846,200C856,188 874,188 882,200L878,208C870,200 858,200 850,208Z" fill="url(#gBlackGold)" stroke="#e8c26a" stroke-width="1.2"/>'
   '<path d="M762,200C756,190 750,186 742,186" fill="none" stroke="#e8c26a" stroke-width="1.4"/>')
# eyes with pulsing glow
TH('<circle cx="790" cy="214" r="26" fill="url(#gEyeGlow)"><animate attributeName="opacity" values=".35;1;.35" dur="2.8s" repeatCount="indefinite"/></circle>'
   '<circle cx="862" cy="212" r="19" fill="url(#gEyeGlow)"><animate attributeName="opacity" values=".35;1;.35" dur="2.8s" repeatCount="indefinite"/></circle>')
TH('<g filter="url(#fGlow)"><ellipse cx="790" cy="214" rx="14" ry="9.5" fill="url(#gEye)" stroke="#2a0400" stroke-width="1.4"/>'
   '<ellipse cx="862" cy="212" rx="9" ry="8" fill="url(#gEye)" stroke="#2a0400" stroke-width="1.2"/>'
   '<ellipse cx="792" cy="214" rx="2.4" ry="7" fill="#1a0400"/><ellipse cx="863" cy="212" rx="2" ry="6" fill="#1a0400"/>'
   '<animate attributeName="opacity" values=".8;1;.8" dur="2.8s" repeatCount="indefinite"/></g>'
   '<circle cx="786" cy="210" r="2" fill="#fff"/><circle cx="859" cy="209" r="1.5" fill="#fff"/>')
# nose
TH('<path d="M832,206L846,206L852,228C866,232 870,246 860,252C852,256 844,250 840,246C836,250 828,256 820,252C810,246 816,232 828,228Z" fill="url(#gFace)" stroke="#0a120e" stroke-width="1.6"/>'
   '<path d="M822,246C816,240 822,234 828,238C831,241 828,245 825,243M858,244C862,238 856,234 852,238C849,241 852,245 855,243" fill="none" stroke="#e8c26a" stroke-width="1.8"/>'
   '<path d="M839,208V240" stroke="#e8c26a" stroke-width="1.4"/><path d="M828,228C834,232 846,232 852,228" fill="none" stroke="#e8c26a" stroke-width="1.2"/>')
# mouth with fangs and tusks
TH('<path d="M764,260C790,272 846,274 882,256C876,282 852,294 820,294C794,294 772,282 764,260Z" fill="url(#gMouth)" stroke="#0a120e" stroke-width="1.6"/>'
   '<path d="M768,262C794,272 846,274 878,259" fill="none" stroke="#e8c26a" stroke-width="1.6"/>')
teeth = "".join(f'<path d="M{x},{263 + 6 * math.sin((x - 764) / 118 * math.pi)}l4,9l4,-9z"/>' for x in range(780, 872, 10))
TH(f'<g fill="url(#gIvory)">{teeth}</g>')
TH('<path d="M790,268L796,290L802,270Z M852,268L846,288L842,270Z" fill="url(#gIvory)" stroke="#5a4a2a" stroke-width=".8"/>'
   '<path d="M776,288C766,276 762,260 768,242C772,258 778,272 786,282Z" fill="url(#gIvory)" stroke="#5a4a2a" stroke-width=".9"/>'
   '<path d="M868,284C878,272 882,258 878,242C872,256 868,268 860,278Z" fill="url(#gIvory)" stroke="#5a4a2a" stroke-width=".9"/>')
# jaw beard plate
TH('<path d="M790,296C810,310 840,308 860,294L852,306C836,318 812,318 796,306Z" fill="url(#gGold)" stroke="#5a3a0c" stroke-width=".9"/>')
R("".join(th))

# ---- near arm
R('<path d="M806,306C828,320 842,340 848,362L834,374C826,354 812,336 796,324Z" fill="url(#gSkin)" stroke="#0a120e" stroke-width="1.8"/>'
  '<path d="M846,356C862,366 876,376 888,382L882,398C864,394 846,384 832,374Z" fill="url(#gSkin)" stroke="#0a120e" stroke-width="1.8"/>'
  '<path d="M848,362L878,378L872,394L840,380Z" fill="url(#pHui)" stroke="#ffe08a" stroke-width="1.4"/>'
  '<path d="M848,362L878,378" stroke="#e8492e" stroke-width="2"/>'
  '<circle cx="841" cy="366" r="9" fill="url(#gGold)" stroke="#5a3a0c"/>')
# arm-loop of the 披帛
R(ribbon_anim("url(#gCape)", (842, 368), 150, 250, sash_w(13, 8), 22, 1.3, 1.9, 0.25, 20, n=12, frames=12,
              extra='stroke="#2a0408" stroke-width=".8"',
              tip_obj='<g><path d="M0,-7L6,0L0,11L-6,0Z" fill="url(#gGold)"/><circle r="2.2" fill="#5fe3d4"/></g>'))
# pauldron
R('<g transform="translate(818,300) scale(.78) translate(-808,-300)"><path d="M766,292C780,262 832,258 848,290C854,312 842,332 826,338C810,324 790,316 770,318Z" fill="url(#gBronze)" stroke="#0a120e" stroke-width="2"/>'
  '<path d="M774,296C788,272 828,270 840,292C844,306 838,320 828,326C814,316 796,310 778,310Z" fill="url(#pHui)" opacity=".85"/>'
  '<path d="M766,292C780,262 832,258 848,290" fill="none" stroke="#ffe08a" stroke-width="2.4"/>'
  '<path d="M772,318C792,316 812,326 826,338" fill="none" stroke="#e8492e" stroke-width="2"/>'
  '<g transform="translate(808,292)"><circle r="11" fill="url(#gBlackGold)" stroke="#ffe08a" stroke-width="1.4"/>'
  '<path d="M-7,-2C-4,-6 -1,-5 0,-1M7,-2C4,-6 1,-5 0,-1M-5,4C-2,7 2,7 5,4" fill="none" stroke="#ffd36a" stroke-width="1.3"/>'
  '<circle cx="-4" cy="-1" r="1.5" fill="#ff6a1a"/><circle cx="4" cy="-1" r="1.5" fill="#ff6a1a"/></g></g>')
# hand gripping reins
HAND = ('<path d="M878,378C890,374 900,380 900,390C898,398 888,402 880,398C874,394 872,384 878,378Z" fill="url(#gSkin)" stroke="#0a120e" stroke-width="1.6"/>'
        '<path d="M884,382L896,384M882,388L897,390M882,394L894,395" stroke="#0a120e" stroke-width="1.4"/>'
        '<path d="M896,383l6,-2l-3,5M896,389l6,-1l-4,5" fill="#e9dcb0"/>')
R(HAND)

rr = samples(rider_rot)
rdy = samples(rider_dy)


def rider_wrap(content, gid=""):
    idattr = f' id="{gid}"' if gid else ""
    return (f'<g{idattr}>{anim_tr([(0, d) for d in rdy])}<g>{anim_rot(rr, SEAT)}{content}</g></g>')


A(rider_wrap("".join(rider), "taotie"))

# ---- reins (connect rider hands to kirin bit; both endpoints are tracked per frame)
def rein_frames(hand_local, bit_local, sag):
    ds = []
    for k in range(NS + 1):
        g = k / NS
        h = rot_about(hand_local, rider_rot(g), SEAT)
        h = (h[0], h[1] + rider_dy(g))
        b = rot_about(bit_local, head_nod(g), POLL)
        mx, my = (h[0] + b[0]) / 2, (h[1] + b[1]) / 2 + sag + 5 * math.sin(TAU * (g - 0.2))
        ds.append(f"M{pt(h)}Q{pt((mx, my))} {pt(b)}")
    return ds


rein_far = rein_frames((874, 386), (1106, 345), 16)
rein_near = rein_frames((890, 389), (1112, 349), 20)


def rein_path(ds, stroke, w, extra=""):
    return (f'<path d="{ds[0]}" fill="none" stroke="{stroke}" stroke-width="{w}" stroke-linecap="round" {extra}>'
            f'<animate attributeName="d" values="{";".join(ds)}" dur="{P}s" repeatCount="indefinite"/></path>')


A(rein_path(rein_near, "#1d1410", 5.5) + rein_path(rein_near, "#c9302a", 3) +
  rein_path(rein_near, "#ffd36a", 1, 'stroke-dasharray="2 5"'))
# fingers over rein
A(rider_wrap('<path d="M884,382C890,380 896,382 898,386M883,389C889,387 896,389 898,392" fill="none" stroke="#24392c" stroke-width="3.2" stroke-linecap="round"/>'))
# far rein drawn behind the neck: insert before body
far_rein = rein_path(rein_far, "#1d1410", 4) + rein_path(rein_far, "#8a1e1c", 2.2)

mount_str = "".join(mount)
# insert far rein right before the kirin body group
mount_str = mount_str.replace('<g id="kirinBody">', far_rein + '<g id="kirinBody">', 1)

bobv = samples(bob)
pitv = samples(pitch)
MOUNT = (f'<g id="mount">{anim_tr([(0, b) for b in bobv])}<g>{anim_rot(pitv, PITCH_C)}{mount_str}</g></g>')

# shadow/glow under mount on clouds
under_glow = (f'<ellipse cx="780" cy="770" rx="300" ry="34" fill="url(#gGlowGold)" opacity=".35">'
              f'<animate attributeName="rx" values="300;270;300" dur="{P}s" repeatCount="indefinite"/>'
              f'<animate attributeName="opacity" values=".3;.45;.3" dur="{P}s" repeatCount="indefinite"/></ellipse>')

# ================================================================ HOOF-STRIKE BURSTS (踏云)
burst_back = []
burst_front = []
rp = random.Random(77)
for kind, px, py, phi, near in LEGS:
    cx_, cy_ = hoof_contact(kind, px, py, phi)
    begin = f"{-phi * P:.3f}s"
    common = f'dur="{P}s" begin="{begin}" repeatCount="indefinite"'
    sc = 1.0 if near else 0.75
    # cloud ring + puffs (under hoof)
    bb = [f'<g transform="translate({f(cx_)},{f(cy_ + 4)}) scale({sc})">']
    bb.append(f'<ellipse rx="6" ry="2" fill="none" stroke="#ffe7a3" stroke-width="2.4" opacity="0">'
              f'<animate attributeName="rx" values="6;74;74" keyTimes="0;.42;1" {common}/>'
              f'<animate attributeName="ry" values="2;15;15" keyTimes="0;.42;1" {common}/>'
              f'<animate attributeName="stroke-width" values="4;.5;.5" keyTimes="0;.42;1" {common}/>'
              f'<animate attributeName="opacity" values="0;1;0;0" keyTimes="0;.03;.42;1" {common}/></ellipse>')
    bb.append(f'<ellipse rx="6" ry="2" fill="none" stroke="#7fe6dc" stroke-width="1.6" opacity="0">'
              f'<animate attributeName="rx" values="4;4;52;52" keyTimes="0;.06;.4;1" {common}/>'
              f'<animate attributeName="ry" values="1;1;10;10" keyTimes="0;.06;.4;1" {common}/>'
              f'<animate attributeName="opacity" values="0;0;.9;0;0" keyTimes="0;.06;.1;.4;1" {common}/></ellipse>')
    for j in range(4):
        dx = -(30 + j * 22) - rp.uniform(0, 10)
        dy = -(6 + rp.uniform(0, 14))
        r0 = rp.uniform(9, 15)
        bb.append(f'<g opacity="0"><animateTransform attributeName="transform" type="translate" values="0 0;{f(dx * .6)} {f(dy)};{f(dx)} {f(dy * 1.4)};{f(dx)} {f(dy * 1.4)}" keyTimes="0;.18;.5;1" {common}/>'
                  f'<animate attributeName="opacity" values="0;.85;0;0" keyTimes="0;.04;.5;1" {common}/>'
                  f'<circle r="{f(r0)}" fill="#c9dcea"><animate attributeName="r" values="{f(r0 * .4)};{f(r0)};{f(r0 * 1.6)};{f(r0 * 1.6)}" keyTimes="0;.15;.5;1" {common}/></circle>'
                  f'<circle cx="{f(r0 * .5)}" cy="{f(-r0 * .3)}" r="{f(r0 * .6)}" fill="#e8f2f8"/></g>')
    bb.append("</g>")
    burst_back.append("".join(bb))
    # flash + sparks (over everything)
    bf = [f'<g transform="translate({f(cx_)},{f(cy_)}) scale({sc})">']
    bf.append(f'<circle r="34" fill="url(#gGlowGold)" opacity="0">'
              f'<animate attributeName="opacity" values="0;1;0;0" keyTimes="0;.03;.28;1" {common}/>'
              f'<animate attributeName="r" values="14;40;30;30" keyTimes="0;.06;.28;1" {common}/></circle>')
    for j in range(8):
        ang = math.radians(rp.uniform(195, 260))  # back (left) and up
        dist = rp.uniform(40, 95)
        ax, ay = math.cos(ang) * dist, math.sin(ang) * dist
        col = rp.choice(["#ffd36a", "#fff2b8", "#ff9a3a", "#7fe6dc"])
        bf.append(f'<g opacity="0"><animateTransform attributeName="transform" type="translate" '
                  f'values="0 0;{f(ax * .65)} {f(ay * .75)};{f(ax * 1.05)} {f(ay * .9 + 6)};{f(ax * 1.05)} {f(ay * .9 + 6)}" keyTimes="0;.18;.45;1" {common}/>'
                  f'<animate attributeName="opacity" values="0;1;0;0" keyTimes="0;.02;.45;1" {common}/>'
                  f'<use xlink:href="#spark" fill="{col}"><animateTransform attributeName="transform" type="scale" values="1.3;.9;.15;.15" keyTimes="0;.15;.45;1" {common}/></use></g>')
    bf.append("</g>")
    burst_front.append("".join(bf))

BURST_BACK = '<g id="hoofClouds">' + "".join(burst_back) + "</g>"
BURST_FRONT = '<g id="hoofSparks" filter="url(#fGlow)">' + "".join(burst_front) + "</g>"

# ================================================================ ASSEMBLE
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 1600 1000" width="1600" height="1000" role="img" aria-labelledby="title desc">
<title id="title">饕餮骑麒麟·踏云穿行上古天界</title>
<desc id="desc">动态矢量插画：身披青铜甲胄的饕餮跨坐鞍上执缰，覆鳞麒麟四蹄交替奔行、落蹄生云溅金，火焰鬃尾与朱红披帛向后飘扬；身后金色法阵内外圈反向旋转，悬浮仙山宫阙与多层云海以视差掠过。纯 SVG + SMIL，无脚本、无位图。</desc>
<defs>{"".join(defs)}</defs>
<g id="background">{"".join(bg)}</g>
{magic}
{farmidclouds}
{arcpart}
{midclouds}
{under_glow}
{BURST_BACK}
{MOUNT}
{BURST_FRONT}
{fgwisps}
{fgclouds}
{edges}
</svg>
'''

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "taotie_qilin.svg")
with open(out, "w", encoding="utf-8") as fh:
    fh.write(svg)
print("wrote", os.path.normpath(out), len(svg), "bytes")
for kind, px, py, phi, near in LEGS:
    print(kind, near, [round(v, 1) for v in hoof_contact(kind, px, py, phi)])
