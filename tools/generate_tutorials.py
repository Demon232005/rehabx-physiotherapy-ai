"""Generate RehabX AI hand-rehab tutorial MP4s into frontend/public/tutorials/.

Each exercise gets a short looping H.264 clip (720x480 @ 24 fps, ~6 s) showing a
stylized hand performing exactly the selected movement, with step-by-step
captions. Re-run any time after editing the exercise steps below:

    .venv\\Scripts\\python.exe tools\\generate_tutorials.py

Requires: pillow, opencv-python, numpy (already in the project venv) and the
Cisco OpenH264 DLL in tools/bin/ (auto-downloaded on first run) so that
cv2.VideoWriter can encode browser-compatible H.264 ('avc1').
"""
from __future__ import annotations

import bz2
import math
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = Path(__file__).resolve().parent / "bin"
OUT_DIR = ROOT / "frontend" / "public" / "tutorials"

# ---------------------------------------------------------------------------
# OpenH264 setup (browser-playable H.264 for cv2.VideoWriter)
# ---------------------------------------------------------------------------

def ensure_openh264() -> None:
    dll = BIN_DIR / "openh264-2.5.0-win64.dll"
    if not dll.exists():
        BIN_DIR.mkdir(parents=True, exist_ok=True)
        url = (
            "https://github.com/cisco/openh264/releases/download/"
            "v2.1.1/openh264-2.1.1-win64.dll.bz2"
        )
        print(f"Downloading {url}")
        with urllib.request.urlopen(url, timeout=60) as r:  # noqa: S310
            data = bz2.decompress(r.read())
        dll.write_bytes(data)
    os.environ["PATH"] = str(BIN_DIR) + os.pathsep + os.environ.get("PATH", "")
    os.add_dll_directory(str(BIN_DIR))


ensure_openh264()

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

# ---------------------------------------------------------------------------
# Canvas / palette (matches the RehabX UI)
# ---------------------------------------------------------------------------

W, H, FPS, DUR = 720, 480, 24, 6.0
SS = 2  # supersampling factor for crisp lines
TEAL = (13, 148, 136)
TEAL_DARK = (15, 118, 110)
TEAL_BG = (240, 253, 250)
INK = (15, 23, 42)
SLATE = (100, 116, 139)
WHITE = (255, 255, 255)
AMBER = (217, 119, 6)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for name in (["segoeuib.ttf", "arialbd.ttf"] if bold else ["segoeui.ttf", "arial.ttf"]):
        try:
            return ImageFont.truetype(f"C:\\Windows\\Fonts\\{name}", size)
        except OSError:
            continue
    return ImageFont.load_default()


F_TITLE = _font(30, bold=True)
F_BRAND = _font(17)
F_STEP_N = _font(19, bold=True)
F_STEP = _font(21)
F_SMALL = _font(15)


def ease(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return 0.5 - 0.5 * math.cos(math.pi * x)


def tri(t: float, hold: float = 0.12) -> float:
    """Smooth 0 -> 1 -> 0 pulse across t in [0, 1)."""
    a = 0.5 - hold / 2
    if t < a:
        return ease(t / a)
    if t < a + hold:
        return 1.0
    return ease(1.0 - (t - a - hold) / a)


def rot(p: tuple[float, float], deg: float, c: tuple[float, float]) -> tuple[float, float]:
    r = math.radians(deg)
    dx, dy = p[0] - c[0], p[1] - c[1]
    return (
        c[0] + dx * math.cos(r) - dy * math.sin(r),
        c[1] + dx * math.sin(r) + dy * math.cos(r),
    )


# ---------------------------------------------------------------------------
# Stylized hand renderer
# ---------------------------------------------------------------------------

class Hand:
    """Segmented stick-hand. All coordinates in final-resolution space."""

    def __init__(self, ox: float, oy: float, s: float = 1.0):
        self.o = (ox, oy)          # wrist pivot
        self.s = s                 # overall scale
        self.finger_len = [0.92, 1.06, 0.99, 0.76]  # index..little rel length
        self.knuck_dx = [-46, -16, 14, 44]
        self.curl = [0.0, 0.0, 0.0, 0.0]            # index..little 0..1
        self.spread = 0.0          # -1 together .. 1 fanned
        self.lift = [0.0, 0.0, 0.0, 0.0]            # upward lift (walking)
        self.thumb = {"out": 0.0, "across": 0.0}    # abduction / flexion-across
        self.palm_angle = 0.0      # rotation about the wrist (deg, cw positive)
        self.squash_x = 1.0        # foreshortening (pronation/supination)
        self.show_forearm = True

    def _pt(self, p: tuple[float, float]) -> tuple[float, float]:
        q = rot(p, self.palm_angle, self.o)
        if self.squash_x != 1.0:
            q = (self.o[0] + (q[0] - self.o[0]) * self.squash_x, q[1])
        return q

    def _finger(self, base, ln, curl, fan, lift=0.0):
        o, s = self.o, self.s
        bx, by = o[0] + base[0] * s, o[1] + base[1] * s
        ang = -90 + fan
        segs = [(0.52, 62), (0.34, 82), (0.24, 48)]  # (frac len, max bend deg)
        pts = [(bx, by)]
        x, y, a = bx, by, ang
        for frac, max_bend in segs:
            L = ln * s * frac * 74
            a += curl * max_bend
            x += L * math.cos(math.radians(a)) * 0.72
            y -= L * math.sin(math.radians(a)) * 0.72
            pts.append((x, y - lift * s * 16))
        return [self._pt(p) for p in pts]

    def _thumb(self):
        o, s = self.o, self.s
        bx, by = o[0] - 58 * s, o[1] + 26 * s
        out, acr = self.thumb["out"], self.thumb["across"]
        ang = -150 - out * 28 + acr * 96
        segs = [(0.55, 30), (0.45, 52)]
        pts = [(bx, by)]
        x, y, a = bx, by, ang
        for frac, max_bend in segs:
            L = 0.62 * s * frac * 74
            a += acr * max_bend + out * max_bend * 0.12
            x += L * math.cos(math.radians(a))
            y -= L * math.sin(math.radians(a))
            pts.append((x, y))
        return [self._pt(p) for p in pts]

    def draw(self, d: ImageDraw.ImageDraw, lw: int = 9):
        s = self.s
        o = self._pt(self.o)
        # forearm
        if self.show_forearm:
            fa = self._pt((self.o[0] - 6 * s, self.o[1] + 150 * s))
            fb = self._pt((self.o[0] + 6 * s, self.o[1] + 150 * s))
            d.line([o, fa], fill=TEAL, width=lw + 6)
            d.line([o, fb], fill=TEAL, width=lw + 6)
        # palm
        pw, ph = 128 * s, 92 * s
        px, py = self._pt((self.o[0] - pw / 2 + 8 * s, self.o[1] - 14 * s))
        pal = [self._pt(p) for p in [
            (self.o[0] - pw / 2 + 8 * s, self.o[1] - 14 * s),
            (self.o[0] + pw / 2 + 8 * s, self.o[1] - 14 * s),
            (self.o[0] + pw / 2 + 2 * s, self.o[1] + ph - 14 * s),
            (self.o[0] - pw / 2 + 14 * s, self.o[1] + ph - 14 * s),
        ]]
        d.polygon(pal, outline=TEAL, width=lw)
        # fingers (back-to-front: little first)
        fans = [-14 - 10 * self.spread, -5 - 3 * self.spread, 5 + 3 * self.spread, 14 + 10 * self.spread]
        order = [3, 2, 1, 0]
        for i in order:
            pts = self._finger(
                (self.knuck_dx[i] * s, -14 * s),
                self.finger_len[i],
                self.curl[i],
                fans[i],
                self.lift[i],
            )
            d.line(pts, fill=TEAL, width=lw, joint="curve")
            d.ellipse([pts[-1][0] - lw / 2, pts[-1][1] - lw / 2,
                       pts[-1][0] + lw / 2, pts[-1][1] + lw / 2], fill=TEAL)
        # thumb on top
        tp = self._thumb()
        d.line(tp, fill=TEAL_DARK, width=lw, joint="curve")
        d.ellipse([tp[-1][0] - lw / 2, tp[-1][1] - lw / 2,
                   tp[-1][0] + lw / 2, tp[-1][1] + lw / 2], fill=TEAL_DARK)
        # wrist joint
        d.ellipse([o[0] - lw, o[1] - lw, o[0] + lw, o[1] + lw], fill=AMBER)


# ---------------------------------------------------------------------------
# Frame composer
# ---------------------------------------------------------------------------

HX, HY = 330, 205  # default hand anchor


def base_canvas(title: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", ((W) * SS, (H) * SS), WHITE)
    d = ImageDraw.Draw(img)
    # soft backdrop circle behind the demonstration area
    d.ellipse([(HX - 165) * SS, (HY - 130) * SS, (HX + 175) * SS, (HY + 215) * SS],
              fill=tuple(c * SS for c in TEAL_BG))
    # header
    d.text((28 * SS, 18 * SS), title, font=F_TITLE, fill=INK)
    d.text((28 * SS, 56 * SS), "RehabX AI · Hand rehabilitation tutorial", font=F_BRAND, fill=TEAL_DARK)
    return img, d


def caption_band(d: ImageDraw.ImageDraw, steps: list[str], t: float):
    idx = min(int(t * len(steps)), len(steps) - 1)
    txt = steps[idx]
    bh = 86
    y0 = (H - bh - 18) * SS
    d.rounded_rectangle([24 * SS, y0, (W - 24) * SS, y0 + bh * SS], radius=14 * SS,
                        fill=(248, 250, 250), outline=(226, 232, 240))
    d.rounded_rectangle([40 * SS, y0 + 24 * SS, 66 * SS, y0 + 50 * SS], radius=7 * SS, fill=TEAL)
    num = str(idx + 1)
    bb = d.textbbox((0, 0), num, font=F_STEP_N)
    d.text((53 * SS - (bb[2] - bb[0]) / 2, y0 + 37 * SS - bb[3] / 2 - bb[1] / 2),
           num, font=F_STEP_N, fill=WHITE)
    # wrap into two lines if needed
    maxw = (W - 160) * SS
    words = txt.split()
    line, lines = "", []
    for wd in words:
        trial = (line + " " + wd).strip()
        if d.textlength(trial, font=F_STEP) > maxw and line:
            lines.append(line)
            line = wd
        else:
            line = trial
    lines.append(line)
    ty = y0 + (bh * SS - len(lines) * 26 * SS) / 2
    for ln_txt in lines[:2]:
        d.text((84 * SS, ty), ln_txt, font=F_STEP, fill=INK)
        ty += 27 * SS
    # step progress dots
    total_w = (len(steps) - 1) * 18 * SS
    x0 = (W - 40) * SS - total_w
    yy = y0 - 14 * SS
    for i in range(len(steps)):
        col = TEAL if i <= idx else (203, 213, 225)
        r = (5 if i == idx else 4) * SS
        d.ellipse([x0 + i * 18 * SS - r, yy - r, x0 + i * 18 * SS + r, yy + r], fill=col)


def finish(img: Image.Image) -> np.ndarray:
    frame = img.resize((W, H), Image.LANCZOS)
    return cv2.cvtColor(np.array(frame), cv2.COLOR_RGB2BGR)


def render(slug: str, title: str, steps: list[str], pose_fn) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{slug}.mp4"
    n = int(FPS * DUR)
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"avc1"), FPS, (W, H))
    if not vw.isOpened():
        raise RuntimeError(f"Could not open VideoWriter for {path} — is the OpenH264 DLL present?")
    for f in range(n):
        t = f / n
        img, d = base_canvas(title)
        pose_fn(d, t)
        caption_band(d, steps, t)
        d.text(((W - 26) * SS, 18 * SS), "▶ TUTORIAL", font=F_BRAND, fill=SLATE, anchor="ra")
        vw.write(finish(img))
    vw.release()
    print(f"  ✓ {path.relative_to(ROOT)} ({path.stat().st_size // 1024} KB)")


# ---------------------------------------------------------------------------
# Pose helpers
# ---------------------------------------------------------------------------

def hand_at(**kw) -> Hand:
    h = Hand(kw.pop("ox", HX), kw.pop("oy", HY), kw.pop("s", 1.0))
    for k, v in kw.items():
        if k == "curl":
            h.curl = v
        elif k == "thumb":
            h.thumb = v
        else:
            setattr(h, k, v)
    return h


def pose_curl(thumb_too=False, invert=False):
    def fn(d, t):
        c = 1 - tri(t) if invert else tri(t)
        h = hand_at(curl=[c] * 4, thumb={"out": 0.0, "across": 0.55 * c if thumb_too else 0.0})
        h.draw(d)
    return fn


def pose_thumb_across():
    def fn(d, t):
        c = tri(t)
        h = hand_at(curl=[0.12] * 4, thumb={"out": 0.0, "across": c})
        h.draw(d)
    return fn


def pose_thumb_out():
    def fn(d, t):
        c = tri(t)
        h = hand_at(curl=[0.08] * 4, thumb={"out": c, "across": 0.0})
        h.draw(d)
    return fn


def pose_spread():
    def fn(d, t):
        sp = tri(t, hold=0.2)
        h = hand_at(curl=[0.05] * 4, spread=sp, thumb={"out": sp * 0.8, "across": 0.0})
        h.draw(d)
    return fn


def pose_seq():
    """Individual finger flexion — fingers take turns curling."""

    def fn(d, t):
        curls = [0.0] * 4
        for k in range(4):
            local = ((t * 4 - k * 0.25) % 1.0)
            if t >= 0:
                phase = (t - k * 0.25) * 4 % 1.0
                if 0 <= phase < 1:
                    curls[k] = tri(phase, hold=0.1) if phase < 0.999 else 0
        h = hand_at(curl=curls, thumb={"out": 0, "across": 0})
        h.draw(d)
    return fn


def pose_walk():
    def fn(d, t):
        lifts, curls = [0.0] * 4, [0.04] * 4
        for k in range(4):
            phase = (t * 2 - k * 0.25) % 1.0
            lifts[k] = math.sin(math.pi * min(max(phase, 0), 1))
        h = hand_at(curl=curls, lift=lifts, thumb={"out": 0, "across": 0}, show_forearm=False)
        h.draw(d)
    return fn


def pose_oppose():
    def fn(d, t):
        cyc = (t * 4) % 4  # touch index -> middle -> ring -> little
        k = int(cyc)
        frac = ease(cyc - k)
        reach = 1 - abs(2 * frac - 1)  # out-and-back per fingertip
        # thumb stretches toward successive fingertips
        h = hand_at(curl=[0.06] * 4, thumb={"out": 0.35 + 0.4 * reach, "across": 0.25 + 0.65 * reach})
        h.draw(d)
        # highlight target fingertip
        tgt = [(HX + 46 + dx * 1.0, HY - 108) for dx in (-46, -16, 14, 44)][k]
        d.ellipse([tgt[0] * SS - 9 * SS, tgt[1] * SS - 9 * SS,
                   tgt[0] * SS + 9 * SS, tgt[1] * SS + 9 * SS],
                  outline=AMBER, width=3 * SS)
    return fn


def pose_glide():
    """Tendon gliding: straight -> hook -> table-top -> full fist -> back."""
    poses = [
        ([0.0] * 4, "Straight hand"),
        ([0.0, 0.55, 0.55, 0.55], "Hook fist"),
        ([0.45] * 4, "Table-top"),
        ([1.0] * 4, "Full fist"),
    ]

    def fn(d, t):
        pos = t * 8 % 8  # forward 4, backward 4
        i = int(pos)
        frac = ease(pos - i)
        a, b = poses[min(i, 7) % 4][0], poses[(min(i, 7) + 1) % 4][0]
        if i >= 4:  # reverse direction
            a, b = b, a
        curls = [x + (y - x) * frac for x, y in zip(a, b)]
        h = hand_at(curl=curls, thumb={"out": 0.15, "across": curls[0]})
        h.draw(d)
    return fn


def pose_wrist(deg: float, both_sides=False):
    def fn(d, t):
        a = (tri(t, hold=0.15) * 2 - 1) * deg if both_sides else (deg * tri(t, hold=0.15))
        h = hand_at(palm_angle=a, curl=[0.07] * 4, thumb={"out": 0.1, "across": 0})
        h.draw(d)
    return fn


def pose_circles():
    def fn(d, t):
        a = 360 * t
        d.ellipse([(HX - 120) * SS, (HY - 120) * SS, (HX + 120) * SS, (HY + 120) * SS],
                  outline=(203, 213, 225), width=2 * SS)
        ax = HX + 120 * math.cos(math.radians(a))
        ay = HY + 120 * math.sin(math.radians(a))
        d.line([HX * SS, HY * SS, ax * SS, ay * SS], fill=(203, 213, 225), width=2 * SS)
        h = hand_at(ox=HX + 120 * math.cos(math.radians(a)),
                    oy=HY + 120 * math.sin(math.radians(a)),
                    palm_angle=-a, curl=[0.12] * 4, thumb={"out": 0.1, "across": 0},
                    show_forearm=True)
        h.draw(d)
    return fn


def pose_flip(start_up: bool):
    """Forearm pronation/supination — palm flips via foreshortening + arrow."""

    def fn(d, t):
        p = tri(t, hold=0.2)
        sq = 1.0 - 0.68 * p
        h = hand_at(squash_x=sq, curl=[0.1] * 4, thumb={"out": 0.1, "across": 0})
        h.draw(d)
        # rotation arrow
        cx, cy, r = (HX + 150), (HY + 40), 64
        box = [(cx - r) * SS, (cy - r) * SS, (cx + r) * SS, (cy + r) * SS]
        a0, a1 = (-90, 200) if start_up else (-200, 90)
        sweep = a0 + (a1 - a0) * p
        d.arc(box, start=min(a0, sweep), end=max(a0, sweep), fill=AMBER, width=4 * SS)
        tipa = math.radians(sweep)
        tx, ty = cx + r * math.cos(tipa), cy + r * math.sin(tipa)
        d.ellipse([(tx - 6) * SS, (ty - 6) * SS, (tx + 6) * SS, (ty + 6) * SS], fill=AMBER)
        label = "palm ↓" if (start_up and p > 0.5) or (not start_up and p < 0.5) else "palm ↑"
        d.text(((cx) * SS, (cy + r + 14) * SS), label, font=F_SMALL, fill=SLATE, anchor="ma")
    return fn


def pose_grip():
    def fn(d, t):
        c = tri(t, hold=0.25)
        h = hand_at(ox=HX - 40, curl=[c] * 4, thumb={"out": 0.0, "across": 0.75 * c})
        h.draw(d)
        br = (26 - 9 * c) * 1.0
        d.ellipse([(HX + 55 - br) * SS, (HY + 30 - br) * SS,
                   (HX + 55 + br) * SS, (HY + 30 + br) * SS],
                  fill=(204, 251, 241), outline=TEAL, width=int(3 * SS))
    return fn


def pose_towel():
    def fn(d, t):
        twist = tri(t, hold=0.15)
        y = HY + 60
        # rolled towel as two crossing bands between two fists
        for sgn in (-1, 1):
            bow = sgn * twist * 34
            pts = []
            for i in range(13):
                u = i / 12
                x = HX - 150 + 300 * u
                yy = y + bow * math.sin(math.pi * u)
                pts.append((x * SS, yy * SS))
            d.line(pts, fill=TEAL, width=10 * SS, joint="curve")
        for fx in (HX - 150, HX + 150):
            d.rounded_rectangle([(fx - 26) * SS, (y - 30) * SS, (fx + 26) * SS, (y + 30) * SS],
                                radius=12 * SS, outline=TEAL_DARK, width=int(6 * SS))
        arrows = [("⟲", -1), ("⟳", 1)]
        for i, (sym, sgn) in enumerate(arrows):
            ax = (HX - 150 if i == 0 else HX + 150) + sgn * 0
            d.text((ax * SS, (y + 52) * SS), sym, font=_font(26), fill=AMBER, anchor="mm")
    return fn


def pose_elbow():
    ex, ey = HX + 40, HY + 150  # elbow pivot

    def fn(d, t):
        flex = tri(t, hold=0.18)
        ang = -88 + flex * 176  # forearm direction: down -> up
        r = math.radians(ang)
        hx, hy = ex + 170 * math.cos(r), ey + 170 * math.sin(r)
        d.line([(ex * SS, ey * SS), (ex * SS, (ey + 120) * SS)], fill=SLATE, width=int(10 * SS))
        d.line([ex * SS, ey * SS, hx * SS, hy * SS], fill=TEAL, width=int(11 * SS))
        d.ellipse([ex * SS - 8 * SS, ey * SS - 8 * SS, ex * SS + 8 * SS, ey * SS + 8 * SS], fill=AMBER)
        # hand at the end of the forearm
        h = Hand(hx, hy, 0.62)
        h.palm_angle = ang + 90
        h.show_forearm = False
        h.curl = [0.12] * 4
        h.thumb = {"out": 0.1, "across": 0}
        h.draw(d)
        deg = int(flex * 145)
        d.arc([(ex - 60) * SS, (ey - 60) * SS, (ex + 60) * SS, (ey + 60) * SS],
              start=ang, end=-88, fill=AMBER, width=4 * SS)
        d.text(((ex - 105) * SS, (ey + 8) * SS), f"≈{deg}°", font=F_STEP_N, fill=TEAL_DARK)
    return fn


# ---------------------------------------------------------------------------
# Exercise definitions (steps mirror src/lib/exerciseLibrary.ts)
# ---------------------------------------------------------------------------

EXERCISES: list[tuple[str, str, list[str], object]] = [
    ("finger-flexion", "Finger Flexion",
     ["Rest your forearm on a table, palm up",
      "Keep your wrist straight",
      "Slowly bend your fingers into a gentle fist",
      "Hold briefly, then slowly open your hand"],
     pose_curl(thumb_too=True)),

    ("finger-extension", "Finger Extension",
     ["Start with fingers gently bent",
      "Slowly straighten and lift the fingers",
      "Open the hand fully without strain",
      "Relax and repeat"],
     pose_curl(invert=True)),

    ("finger-spreading", "Finger Spreading",
     ["Lay your palm flat, fingers together",
      "Spread the fingers apart comfortably",
      "Hold the open position briefly",
      "Bring the fingers back together"],
     pose_spread()),

    ("finger-walking", "Finger Walking",
     ["Place your palm flat on a table",
      "Lift and place one finger at a time",
      "'Walk' your hand forward",
      "Walk the hand back to the start"],
     pose_walk()),

    ("fist-open-close", "Fist Opening and Closing",
     ["Support your forearm, hand relaxed",
      "Close into a gentle full fist",
      "Keep the thumb wrapped outside",
      "Open the hand fully, then repeat"],
     pose_curl(thumb_too=True)),

    ("thumb-opposition", "Thumb Opposition",
     ["Hold your palm facing up",
      "Touch the thumb to the index fingertip",
      "Continue to middle, ring and little finger",
      "Reverse the sequence back down"],
     pose_oppose()),

    ("thumb-flexion", "Thumb Flexion",
     ["Rest your hand palm-up, relaxed",
      "Reach the thumb across the palm",
      "Touch near the little-finger base",
      "Return the thumb slowly"],
     pose_thumb_across()),

    ("thumb-extension", "Thumb Extension",
     ["Hand resting flat, fingers relaxed",
      "Move the thumb away from the palm",
      "Hold the stretched position briefly",
      "Return the thumb alongside the hand"],
     pose_thumb_out()),

    ("wrist-flexion", "Wrist Flexion",
     ["Forearm on a table, hand free at the edge",
      "Keep fingers relaxed",
      "Bend the hand down at the wrist",
      "Lift it back up within a pain-free range"],
     pose_wrist(34)),

    ("wrist-extension", "Wrist Extension",
     ["Forearm supported, palm facing down",
      "Lift the back of the hand upward",
      "Raise until you feel a mild stretch",
      "Lower slowly and repeat"],
     pose_wrist(-34)),

    ("wrist-rotation", "Wrist Rotation",
     ["Elbow bent, hand relaxed",
      "Circle the hand clockwise slowly",
      "Keep the forearm still",
      "Repeat anticlockwise after a pause"],
     pose_circles()),

    ("wrist-ulnar-radial-deviation", "Wrist Deviations",
     ["Hand resting on its side, thumb up",
      "Tip the hand toward the little finger",
      "Return through the middle",
      "Tip toward the thumb side"],
     pose_wrist(26, both_sides=True)),

    ("gentle-grip-release", "Gentle Grip / Release",
     ["Hold a soft ball or rolled sock",
      "Squeeze gently — never to pain",
      "Hold the squeeze for 3 seconds",
      "Release fully and open the hand"],
     pose_grip()),

    ("towel-wring", "Towel Wringing",
     ["Hold a rolled towel with both hands",
      "Twist one hand toward you",
      "Twist the other hand away",
      "Reverse directions and repeat"],
     pose_towel()),

    ("thumb-abduction", "Thumb Abduction",
     ["Hand flat, palm facing up",
      "Lift the thumb away from the fingers",
      "Hold the open web-space briefly",
      "Return the thumb gently"],
     pose_thumb_out()),

    ("wrist-ulnar-deviation", "Wrist Ulnar Deviation",
     ["Forearm supported, thumb pointing up",
      "Tip the hand toward the little finger",
      "Stay within a pain-free arc",
      "Return upright slowly"],
     pose_wrist(24)),

    ("wrist-radial-deviation", "Wrist Radial Deviation",
     ["Forearm supported, thumb pointing up",
      "Tip the hand toward the thumb side",
      "Keep the motion small and smooth",
      "Return to the middle"],
     pose_wrist(-24)),

    ("individual-finger-flexion", "Individual Finger Flexion",
     ["Palm facing up, fingers relaxed",
      "Bend one finger into the palm",
      "Straighten it fully before the next",
      "Work through every finger in turn"],
     pose_seq()),

    ("tendon-gliding", "Tendon Gliding",
     ["Start with a straight hand",
      "Bend into a hook fist",
      "Form a table-top at 90 degrees",
      "Finish into a full fist — then reverse"],
     pose_glide()),

    ("forearm-pronation", "Forearm Pronation",
     ["Elbow bent at 90°, tucked at your side",
      "Start with the thumb pointing up",
      "Rotate so the palm faces the floor",
      "Hold briefly, then rotate back"],
     pose_flip(start_up=True)),

    ("forearm-supination", "Forearm Supination",
     ["Elbow bent at 90°, tucked at your side",
      "Start with the palm facing down",
      "Rotate so the palm faces the ceiling",
      "Hold briefly, then rotate back"],
     pose_flip(start_up=False)),

    ("elbow-flexion-extension", "Elbow Flexion / Extension",
     ["Sit tall, arm at your side",
      "Bend the elbow, hand toward shoulder",
      "Keep the upper arm still",
      "Straighten the elbow slowly"],
     pose_elbow()),
]


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    only = set(sys.argv[1:])
    print(f"Rendering {len(EXERCISES)} tutorials → {OUT_DIR.relative_to(ROOT)}")
    for slug, title, steps, pose in EXERCISES:
        if only and slug not in only:
            continue
        render(slug, title, steps, pose)
    print("Done.")


if __name__ == "__main__":
    main()
