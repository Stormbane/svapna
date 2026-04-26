"""Renders the body's display lambda to a PNG for preview.

Mirrors the C++ lambda in `embodiment/firmware/narada-body.yaml`.
This is a re-implementation — drift risk: keep in sync when the
lambda changes. Useful for iterating on visuals without flashing
the device.

Usage:
    python scripts/render_preview.py
    python scripts/render_preview.py --hour 14 --out daytime.png
    python scripts/render_preview.py --hour 18 --cloud 80 --rain 1.5
    python scripts/render_preview.py --live           # query device state
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "embodiment" / "assets" / "fonts"

# Constants matching the firmware lambda
COLS = 44
ROWS = 16
CELL_W = 7
CELL_H = 14
SCREEN_W = 320
SCREEN_H = 240
HORIZON_ROW = 11
N_STARS = 25
N_TREES = 12
MAX_CLOUDS = 4

# Plant config (mirrors the t_* arrays in the lambda).
T_COLS    = [ 4, 14, 22, 30,   8, 18, 33, 39,    2,  9, 35, 42]
T_H       = [ 1,  2,  1,  2,   4,  3,  5,  3,    7,  6,  7,  6]
T_CW      = [ 1,  1,  1,  1,   3,  3,  3,  3,    7,  5,  7,  5]
T_PLANE   = [ 0,  0,  0,  0,   1,  1,  1,  1,    2,  2,  2,  2]
T_TRUNK_H = [ 0,  0,  0,  0,   1,  0,  2,  1,    2,  2,  2,  2]
T_LEAN    = [ 0,  0,  0,  0,   0,  0,  0,  0,    0,  0,  0,  0]

# Cloud templates (mirrors CLOUD_MAIN/TOP/* in the lambda).
CLOUD_MAIN = ["~~-.", "----~~.", ".~~~~~.", "~~.~"]
CLOUD_TOP  = ["",     "~~~.",     "",         "___"]
CLOUD_TOP_OFFSET = [0, 1, 0, 1]
CLOUD_Y = [1, 4, 2, 5]
CLOUD_W = [4, 4, 6, 4]

# Star positions seeded once for stable layout (mirror of xorshift seed
# 0xa11ce5 in the lambda, but Python doesn't need to match exactly).
import random
def _seeded_stars():
    rng = random.Random(0xa11ce5)
    stars = []
    for _ in range(N_STARS):
        x = rng.randrange(COLS)
        y = rng.randrange(7)
        phase = rng.uniform(0, 2 * math.pi)
        stars.append((x, y, phase))
    return stars
STARS = _seeded_stars()

def _seeded_tree_phases():
    rng = random.Random(0xb00c11)
    return [rng.uniform(0, 2 * math.pi) for _ in range(N_TREES)]
TREE_PHASES = _seeded_tree_phases()


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _bilinear_tint(valence: float, arousal: float):
    """Same bilinear blend as the lambda for the mood accent color."""
    v = (valence + 1.0) * 0.5
    a = arousal
    def b(c00, c10, c01, c11):
        r = ((1 - v) * (1 - a) * c00 + v * (1 - a) * c10
             + (1 - v) * a * c01 + v * a * c11)
        return int(_clamp(r, 0, 255))
    return (
        b(0x4A, 0xC4, 0xB0, 0x7A),
        b(0x55, 0x96, 0x40, 0x50),
        b(0x60, 0x2A, 0x60, 0x8C),
    )


def _sky_color(hour: float, lightning: bool):
    if lightning:
        return (0x90, 0x90, 0xB0)
    if 4.5 <= hour < 6.0:    return (0x30, 0x18, 0x44)
    if 6.0 <= hour < 7.0:    return (0x60, 0x24, 0x40)
    if 7.0 <= hour < 8.0:    return (0x58, 0x38, 0x40)
    if 8.0 <= hour < 16.0:   return (0x20, 0x40, 0x70)
    if 16.0 <= hour < 17.0:  return (0x40, 0x30, 0x40)
    if 17.0 <= hour < 18.0:  return (0x70, 0x28, 0x20)
    if 18.0 <= hour < 19.0:  return (0x50, 0x18, 0x30)
    if 19.0 <= hour < 20.0:  return (0x28, 0x14, 0x40)
    return (0x08, 0x0E, 0x18)


@dataclass
class State:
    hour: float = 12.0
    mood_valence: float = 0.3
    mood_arousal: float = 0.4
    sleep_pressure: float = 0.3
    restlessness: float = 0.2
    attention_mode: str = "diffuse"
    wind_kmh: float = 0.0
    wind_dir: float = 0.0
    precip: float = 0.0
    cloud_pct: float = 0.0
    weather_code: int = 0
    now_ms: float = 0.0
    lightning: bool = False
    tree_species: str = "pine"   # "pine" | "oak" | "mixed"
    ufo_mode: str = "grey"        # "grey" | "mood" | "outline"


def render(state: State) -> Image.Image:
    img = Image.new("RGB", (SCREEN_W, SCREEN_H))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(str(FONT_DIR / "IBMPlexMono-Regular.ttf"), 12)
    bigfont = ImageFont.truetype(str(FONT_DIR / "IBMPlexMono-Medium.ttf"), 28)

    now_ms = state.now_ms
    is_day = (state.hour >= 6.0 and state.hour < 18.0)

    # Background — sky band + grass band.
    sky = _sky_color(state.hour, state.lightning)
    grass = (0x10, 0x16, 0x10)
    draw.rectangle((0, 0, SCREEN_W, HORIZON_ROW * CELL_H), fill=sky)
    draw.rectangle((0, HORIZON_ROW * CELL_H, SCREEN_W, SCREEN_H), fill=grass)

    tint = _bilinear_tint(state.mood_valence, state.mood_arousal)

    def put(col, row, color, ch):
        if col < 0 or col >= COLS or row < 0 or row >= ROWS:
            return
        draw.text((col * CELL_W, row * CELL_H), ch, font=font, fill=color)

    # Sun position (12-hour parabola; mirror of lambda).
    sun_x = -1
    sun_y = -1
    sun_glyph = "o"
    if is_day:
        t_day = (state.hour - 6.0) / 12.0
        sun_x = int(t_day * (COLS - 1))
        sun_y = int(round(6.0 - math.sin(math.pi * t_day) * 6.0))
        sun_y = _clamp(sun_y, 0, 6)
        sun_glyph = "@" if sun_y >= 5 else "O" if sun_y >= 3 else "o"

    # Stars at night (cloud_pct < 50%).
    if (not is_day) and state.cloud_pct < 50.0:
        for sx, sy, phase in STARS:
            b = (math.sin(now_ms / 700.0 + phase) + 1.0) * 0.5
            if b > 0.65:    g = "*"
            elif b > 0.30: g = "."
            else:           g = None
            if g:
                put(sx, sy, (0xD4, 0xCC, 0xB8), g)

    def render_celestial(cx, cy, body_col, pulse_period_ms, body_r):
        if cx < 0 or cy < 0:
            return
        px = cx * CELL_W + CELL_W // 2
        py = cy * CELL_H + CELL_H // 2
        pulse = (math.sin(now_ms / pulse_period_ms) + 1.0) * 0.5

        def add_clamp(base, bonus):
            return int(_clamp(base + bonus, 0, 255))

        # Outer glow — additive on sky_bg.
        outer_r = int(body_r * (2.6 + pulse * 0.8))
        outer_k = 0.20 + pulse * 0.15
        outer = (
            add_clamp(sky[0], body_col[0] * outer_k),
            add_clamp(sky[1], body_col[1] * outer_k),
            add_clamp(sky[2], body_col[2] * outer_k),
        )
        draw.ellipse((px - outer_r, py - outer_r, px + outer_r, py + outer_r),
                     fill=outer)
        # Mid glow — stronger additive lift.
        mid_r = int(body_r * (1.6 + pulse * 0.3))
        mid_k = 0.45 + pulse * 0.20
        mid = (
            add_clamp(sky[0], body_col[0] * mid_k),
            add_clamp(sky[1], body_col[1] * mid_k),
            add_clamp(sky[2], body_col[2] * mid_k),
        )
        draw.ellipse((px - mid_r, py - mid_r, px + mid_r, py + mid_r), fill=mid)
        # Sharp body — full color.
        draw.ellipse((px - body_r, py - body_r, px + body_r, py + body_r),
                     fill=body_col)

    # Sun. Min row 1 (top padding), radius 6 (~20% larger).
    if is_day and state.cloud_pct < 75.0 and sun_x >= 0:
        if sun_y < 1:
            sun_y = 1
        render_celestial(sun_x, sun_y, (0xF4, 0xD0, 0x60), 1500.0, 6)

    # Moon. Same top padding + bigger body radius 5.
    if (not is_day) and state.cloud_pct < 75.0:
        if state.hour >= 18.0:
            t_night = (state.hour - 18.0) / 12.0
        elif state.hour < 6.0:
            t_night = (state.hour + 6.0) / 12.0
        else:
            t_night = 0.5
        moon_x = int(t_night * (COLS - 1))
        moon_y = int(round(6.0 - math.sin(math.pi * t_night) * 6.0))
        moon_y = _clamp(moon_y, 1, 6)
        render_celestial(moon_x, moon_y, (0xC8, 0xCC, 0xD8), 2400.0, 5)

    # Clouds — wispy multi-line shapes. ceil-style count so any cloud
    # cover gives at least one cloud; 32% gives 2 not 1.
    is_raining = state.precip > 0.05
    n_clouds = math.ceil(state.cloud_pct / 30.0)
    n_clouds = _clamp(n_clouds, 0, MAX_CLOUDS)
    cc = (0x46, 0x4C, 0x5A) if is_raining else (0x6A, 0x72, 0x80)
    # Simple cloud x positions for preview (snapshot — no animation drift).
    for c in range(n_clouds):
        # Spread roughly evenly across screen.
        base_x = (c * 11 + int((now_ms / 100) % COLS)) % (COLS + 8) - 4
        idx = c & 3
        y = CLOUD_Y[c]
        main = CLOUD_MAIN[idx]
        for k, ch in enumerate(main):
            if is_raining:
                if ch == '~': ch = '='
                elif ch == '-': ch = '+'
            put(base_x + k, y, cc, ch)
        top = CLOUD_TOP[idx]
        if top and y > 0:
            for k, ch in enumerate(top):
                if is_raining and ch == '~': ch = '='
                put(base_x + CLOUD_TOP_OFFSET[idx] + k, y - 1, cc, ch)

    # Grass — wave-pattern density gradient.
    row_density = [0]*10 + [10, 20, 35, 50, 65, 78]
    wind_east = math.sin(math.radians(state.wind_dir))
    wind_dir_sign = 1.0 if wind_east >= 0 else -1.0
    wave_speed = wind_dir_sign * (0.6 + state.wind_kmh / 8.0)
    wave_pos = (now_ms / 1000.0) * wave_speed
    for row in range(10, ROWS):
        dens = row_density[row]
        row_phase = (row - 10) * 0.4
        for col in range(COLS):
            h = (col * 2654435761 + row * 1597334677) & 0xFFFFFFFF
            roll = (h >> 8) % 100
            if roll >= dens:
                continue
            ph = (col - wave_pos) * 0.30 + row_phase
            wv = math.sin(ph)
            if wv > 0.55:    g = "'"
            elif wv > 0.05:  g = ","
            elif wv > -0.55: g = ":"
            else:             g = "."
            put(col, row, (0x46, 0x60, 0x32), g)

    # Trees — three planes, triangular crowns.
    plane_blend = [0.65, 0.35, 0.0]
    plane_sway  = [0.0,  0.6,  1.0]
    sway_amp = _clamp(state.wind_kmh / 25.0, 0.0, 3.0)
    for t in range(N_TREES):
        p = T_PLANE[t]
        base_col = T_COLS[t]
        h = T_H[t]
        cw = T_CW[t]
        pb = plane_blend[p]
        tree_color = (
            int(tint[0] * (1 - pb) + 0x10 * pb),
            int(tint[1] * (1 - pb) + 0x16 * pb),
            int(tint[2] * (1 - pb) + 0x10 * pb),
        )
        trunk_color = (
            int(0x55 * (1 - pb) + 0x10 * pb),
            int(0x38 * (1 - pb) + 0x16 * pb),
            int(0x20 * (1 - pb) + 0x10 * pb),
        )
        if p == 0:
            for rk in range(h):
                r = HORIZON_ROW - rk
                g = "*" if rk == 0 else ("'" if (t & 1) else ",")
                put(base_col, r, tree_color, g)
            continue

        wind_sway = math.sin(now_ms / 800.0 + TREE_PHASES[t]) * sway_amp
        micro_a   = math.sin(now_ms / 4500.0 + TREE_PHASES[t] * 1.5) * 0.6
        micro_b   = math.sin(now_ms / 1700.0 + TREE_PHASES[t] * 2.3) * 0.5
        crown_sway = (wind_sway + micro_a + micro_b) * plane_sway[p]
        trunk_sway = (wind_sway * 0.4 + (micro_a + micro_b) * 0.5) * plane_sway[p]
        crown_dx = round(crown_sway) + T_LEAN[t]
        trunk_dx = round(trunk_sway)

        trunk_h = T_TRUNK_H[t]
        if trunk_h > h - 1:
            trunk_h = h - 1
        crown_h = max(1, h - trunk_h)
        crown_top = max(0, ROWS - h)
        trunk_top = min(ROWS, crown_top + crown_h)
        trunk_w = 2 if (p == 2 and trunk_h >= 2) else 1

        # Trunk
        trunk_glyphs = ["|", "!"]
        for r in range(trunk_top, ROWS):
            for dx in range(trunk_w):
                gi = (r + dx + t + int(now_ms / 4000)) & 1
                put(base_col + trunk_dx + dx, r, trunk_color, trunk_glyphs[gi])

        # Crown shape depends on species.
        is_oak = (state.tree_species == "oak") or \
                 (state.tree_species == "mixed" and (t & 1))
        for rk in range(crown_h):
            r = crown_top + rk
            if is_oak:
                frac = (rk + 1) / (crown_h + 1)
                sw = math.sin(math.pi * frac)
                w_here = int(round(cw * sw))
                w_here = _clamp(w_here, 1, cw)
            else:
                w_here = 1 + (rk * (cw - 1)) // max(1, crown_h - 1)
                w_here = _clamp(w_here, 1, cw)
            half_l = w_here // 2
            half_r = w_here - 1 - half_l
            for k in range(-half_l, half_r + 1):
                if is_oak:
                    if k == -half_l or k == half_r:    g = "*"
                    elif k == 0 and w_here >= 3:        g = "O"
                    else:                                g = "o"
                else:
                    g = "*"
                put(base_col + crown_dx + k, r, tree_color, g)

    # Tight clear-zones — only behind wordmark and behind line band.
    draw.rectangle((110,  98, 110 + 100,  98 + 30), fill=sky)
    draw.rectangle((118, 145, 118 +  84, 145 +  8), fill=sky)
    breath = math.sin((now_ms % 4000.0) / 4000.0 * 2 * math.pi)
    delta = int(breath * 55)
    narada = (
        _clamp(0xD4 + delta, 0, 255),
        _clamp(0xCC + delta, 0, 255),
        _clamp(0xB8 + delta, 0, 255),
    )
    # Center NARADA at (160, 112). PIL anchor "mm" centers the text.
    draw.text((160, 112), "NARADA", font=bigfont, fill=narada, anchor="mm")
    line_extra = int(breath * 8)
    draw.line((120 - line_extra, 148, 200 + line_extra, 148), fill=tint)

    # UFO presence indicator — pixel saucer + `@` indicator only.
    if state.attention_mode != "inward":
        ufo_t = (now_ms % 90000.0) / 90000.0
        ufo_cx = int(ufo_t * (COLS - 5)) + 3
        ufo_y_top = round(math.sin(now_ms / 2200.0) + 1.0)
        ufo_y_bot = ufo_y_top + 1
        if ufo_cx - 2 >= 0 and ufo_cx + 2 < COLS and ufo_y_bot < HORIZON_ROW:
            mode = state.ufo_mode
            if mode == "mood":
                dome_fill = tuple(int(c * 0.7) for c in tint)
                disc_fill = tuple(int(c * 0.45) for c in tint)
                glyph_at  = tint
            else:
                dome_fill = (0x88, 0x8C, 0x98)
                disc_fill = (0x5A, 0x5E, 0x68)
                glyph_at  = (0xE0, 0xE4, 0xEA)
            body_cx = ufo_cx * CELL_W + CELL_W // 2

            # Disc (oval): rectangle + cap circles
            disc_cy = ufo_y_bot * CELL_H + 4
            disc_half_w = (5 * CELL_W) // 2
            disc_half_h = 3
            rect_x = body_cx - disc_half_w + disc_half_h
            rect_w = (disc_half_w - disc_half_h) * 2
            rect_y = disc_cy - disc_half_h
            rect_h = disc_half_h * 2
            if mode == "outline":
                draw.rectangle((rect_x, rect_y, rect_x + rect_w, rect_y + rect_h),
                               outline=disc_fill)
                draw.ellipse((body_cx - disc_half_w + disc_half_h - disc_half_h,
                              disc_cy - disc_half_h,
                              body_cx - disc_half_w + disc_half_h + disc_half_h,
                              disc_cy + disc_half_h), outline=disc_fill)
                draw.ellipse((body_cx + disc_half_w - disc_half_h - disc_half_h,
                              disc_cy - disc_half_h,
                              body_cx + disc_half_w - disc_half_h + disc_half_h,
                              disc_cy + disc_half_h), outline=disc_fill)
            else:
                draw.rectangle((rect_x, rect_y, rect_x + rect_w, rect_y + rect_h),
                               fill=disc_fill)
                draw.ellipse((body_cx - disc_half_w + disc_half_h - disc_half_h,
                              disc_cy - disc_half_h,
                              body_cx - disc_half_w + disc_half_h + disc_half_h,
                              disc_cy + disc_half_h), fill=disc_fill)
                draw.ellipse((body_cx + disc_half_w - disc_half_h - disc_half_h,
                              disc_cy - disc_half_h,
                              body_cx + disc_half_w - disc_half_h + disc_half_h,
                              disc_cy + disc_half_h), fill=disc_fill)

            # Dome
            dome_cy = ufo_y_top * CELL_H + CELL_H - 4
            if mode == "outline":
                draw.ellipse((body_cx - 9, dome_cy - 9, body_cx + 9, dome_cy + 9),
                             outline=dome_fill)
            else:
                draw.ellipse((body_cx - 9, dome_cy - 9, body_cx + 9, dome_cy + 9),
                             fill=dome_fill)

            # @ indicator (centered on dome)
            draw.text((body_cx, dome_cy + 1), "@", font=font, fill=glyph_at,
                      anchor="mm")

    return img


def _live_state() -> State:
    """Pull current state from the device via aioesphomeapi."""
    import asyncio
    from aioesphomeapi import APIClient

    async def go():
        c = APIClient("192.168.86.35", 6053, password="")
        await c.connect(login=True)
        entities, _ = await c.list_entities_services()
        by_key = {e.key: e for e in entities if type(e).__name__ == "TextSensorInfo"}
        seen: dict[str, str] = {}
        def on_state(s):
            if type(s).__name__ == "TextSensorState" and s.key in by_key:
                seen[by_key[s.key].name] = s.state
        c.subscribe_states(on_state)
        await asyncio.sleep(2.0)
        await c.disconnect()
        return seen

    seen = asyncio.run(go())
    def f(name, default):
        try: return float(seen.get(name, default))
        except: return default
    s = State()
    s.mood_valence    = f("Mood Valence", s.mood_valence)
    s.mood_arousal    = f("Mood Arousal", s.mood_arousal)
    s.sleep_pressure  = f("Vitality Sleep Pressure", s.sleep_pressure)
    s.restlessness    = f("Vitality Restlessness", s.restlessness)
    s.attention_mode  = seen.get("Attention Mode", s.attention_mode)
    s.wind_kmh        = f("Weather Wind Speed Kmh", s.wind_kmh)
    s.wind_dir        = f("Weather Wind Direction Deg", s.wind_dir)
    s.precip          = f("Weather Precipitation Mm Hr", s.precip)
    s.cloud_pct       = f("Weather Cloud Cover Pct", s.cloud_pct)
    s.weather_code    = int(f("Weather Code", s.weather_code))
    return s


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--out", default="preview.png")
    p.add_argument("--hour", type=float, default=None,
                   help="Brisbane hour 0..24 (default: now)")
    p.add_argument("--mood-valence", type=float, default=0.3)
    p.add_argument("--mood-arousal", type=float, default=0.4)
    p.add_argument("--wind-kmh", type=float, default=14.0)
    p.add_argument("--wind-dir", type=float, default=180.0)
    p.add_argument("--precip", type=float, default=0.0)
    p.add_argument("--cloud", type=float, default=30.0)
    p.add_argument("--code", type=int, default=1)
    p.add_argument("--attention", default="diffuse",
                   choices=["diffuse", "outward", "inward"])
    p.add_argument("--lightning", action="store_true")
    p.add_argument("--tree-species", default="pine",
                   choices=["pine", "oak", "mixed"])
    p.add_argument("--ufo-mode", default="grey",
                   choices=["grey", "mood", "outline"])
    p.add_argument("--anim-ms", type=float, default=None,
                   help="Animation timestamp (default: real time)")
    p.add_argument("--live", action="store_true",
                   help="Pull current state from device")
    args = p.parse_args()

    if args.live:
        s = _live_state()
        s.tree_species = args.tree_species
        s.ufo_mode = args.ufo_mode
    else:
        s = State(
            mood_valence=args.mood_valence,
            mood_arousal=args.mood_arousal,
            wind_kmh=args.wind_kmh,
            wind_dir=args.wind_dir,
            precip=args.precip,
            cloud_pct=args.cloud,
            weather_code=args.code,
            attention_mode=args.attention,
            lightning=args.lightning,
            tree_species=args.tree_species,
            ufo_mode=args.ufo_mode,
        )

    if args.hour is None:
        try:
            import zoneinfo
            now = datetime.now(zoneinfo.ZoneInfo("Australia/Brisbane"))
        except Exception:
            now = datetime.now()
        s.hour = now.hour + now.minute / 60.0
    else:
        s.hour = args.hour

    if args.anim_ms is None:
        import time as _t
        s.now_ms = (_t.time() * 1000) % 1_000_000
    else:
        s.now_ms = args.anim_ms

    img = render(s)
    img.save(args.out)
    print(f"Wrote {args.out}  (hour={s.hour:.1f}, cloud={s.cloud_pct:.0f}%, "
          f"wind={s.wind_kmh:.1f} km/h @ {s.wind_dir:.0f}°)")


if __name__ == "__main__":
    main()
