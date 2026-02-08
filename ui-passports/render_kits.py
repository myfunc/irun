from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True)
class Theme:
    key: str
    name: str
    # Core
    bg0: tuple[int, int, int, int]
    bg1: tuple[int, int, int, int]
    panel: tuple[int, int, int, int]
    panel2: tuple[int, int, int, int]
    outline: tuple[int, int, int, int]
    text: tuple[int, int, int, int]
    text_muted: tuple[int, int, int, int]
    accent: tuple[int, int, int, int]
    danger: tuple[int, int, int, int]
    ok: tuple[int, int, int, int]
    # Effects
    shadow: tuple[int, int, int, int]
    glow: tuple[int, int, int, int]
    dither_a: tuple[int, int, int, int]
    dither_b: tuple[int, int, int, int]

@dataclass(frozen=True)
class Variant:
    key: str
    name: str
    # Layout
    margin: int
    pad: int
    # Framing
    outline_w: int
    shadow_off: int
    shadow_alpha: int
    # Style extras
    bevel: bool
    glow_outline_w: int


THEMES: list[Theme] = [
    Theme(
        key="ps1_amber",
        name="Passport A: PS1 Dev Console (Amber)",
        bg0=(10, 13, 18, 255),
        bg1=(16, 19, 26, 255),
        panel=(18, 23, 30, 235),
        panel2=(24, 30, 40, 235),
        outline=(210, 170, 70, 255),
        text=(246, 232, 188, 255),
        text_muted=(190, 180, 150, 255),
        accent=(255, 196, 64, 255),
        danger=(255, 92, 92, 255),
        ok=(120, 220, 140, 255),
        shadow=(0, 0, 0, 150),
        glow=(255, 196, 64, 60),
        dither_a=(18, 23, 30, 235),
        dither_b=(14, 18, 24, 235),
    ),
    Theme(
        key="ps2_cyan",
        name="Passport B: PS2 Minimal Industrial (Cyan)",
        bg0=(12, 12, 14, 255),
        bg1=(18, 18, 22, 255),
        panel=(26, 26, 30, 235),
        panel2=(34, 34, 40, 235),
        outline=(90, 92, 98, 255),
        text=(236, 238, 244, 255),
        text_muted=(170, 175, 188, 255),
        accent=(70, 220, 230, 255),
        danger=(255, 86, 120, 255),
        ok=(120, 230, 160, 255),
        shadow=(0, 0, 0, 140),
        glow=(70, 220, 230, 55),
        dither_a=(26, 26, 30, 235),
        dither_b=(22, 22, 26, 235),
    ),
    Theme(
        key="crt_lime",
        name="Passport C: CRT HUD (Lime)",
        bg0=(6, 10, 8, 255),
        bg1=(10, 16, 12, 255),
        panel=(10, 16, 12, 228),
        panel2=(14, 22, 16, 228),
        outline=(90, 220, 120, 255),
        text=(210, 255, 220, 255),
        text_muted=(130, 190, 150, 255),
        accent=(120, 255, 160, 255),
        danger=(255, 92, 92, 255),
        ok=(120, 255, 160, 255),
        shadow=(0, 0, 0, 160),
        glow=(120, 255, 160, 55),
        dither_a=(10, 16, 12, 228),
        dither_b=(8, 13, 10, 228),
    ),
]

VARIANTS: list[Variant] = [
    Variant(
        key="compact_hardline",
        name="Variant D: Compact Hardline",
        margin=10,
        pad=6,
        outline_w=2,
        shadow_off=2,
        shadow_alpha=135,
        bevel=False,
        glow_outline_w=2,
    ),
    Variant(
        key="bevel_shadow",
        name="Variant E: Bevel + Heavy Shadow",
        margin=14,
        pad=8,
        outline_w=1,
        shadow_off=4,
        shadow_alpha=170,
        bevel=True,
        glow_outline_w=1,
    ),
    Variant(
        key="airy_minimal",
        name="Variant F: Airy Minimal",
        margin=18,
        pad=10,
        outline_w=1,
        shadow_off=1,
        shadow_alpha=110,
        bevel=False,
        glow_outline_w=1,
    ),
]

_FONT_CACHE: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def _candidate_font_paths() -> list[Path]:
    # Prefer a mono font for PS1/PS2-ish UI. Use fonts that are likely present
    # without introducing repo-shipped assets (Pillow bundles DejaVu on most installs).
    candidates: list[Path] = []
    try:
        import PIL  # type: ignore

        pil_dir = Path(PIL.__file__).resolve().parent
        candidates.extend(
            [
                pil_dir / "fonts" / "DejaVuSansMono.ttf",
                pil_dir / "fonts" / "DejaVuSans.ttf",
            ]
        )
    except Exception:
        pass

    # macOS common fonts (ttf/ttc).
    candidates.extend(
        [
            Path("/System/Library/Fonts/Menlo.ttc"),
            Path("/System/Library/Fonts/Supplemental/Menlo.ttc"),
            Path("/System/Library/Fonts/SFNSMono.ttf"),
            Path("/Library/Fonts/Menlo.ttc"),
        ]
    )
    # Linux-ish defaults (harmless on macOS; existence checked).
    candidates.extend(
        [
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ]
    )
    return candidates


def load_ui_font(*, size: int) -> ImageFont.ImageFont:
    # Cache by (path, size). Fall back to PIL bitmap default.
    for p in _candidate_font_paths():
        try:
            if not p.exists():
                continue
            key = (str(p), int(size))
            if key in _FONT_CACHE:
                return _FONT_CACHE[key]
            f = ImageFont.truetype(str(p), size=int(size))
            _FONT_CACHE[key] = f
            return f
        except Exception:
            continue
    return ImageFont.load_default()


def _hex(c: tuple[int, int, int, int]) -> str:
    return "#%02X%02X%02X" % (c[0], c[1], c[2])


def draw_dither_rect(
    d: ImageDraw.ImageDraw,
    *,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    a: tuple[int, int, int, int],
    b: tuple[int, int, int, int],
    step: int = 2,
) -> None:
    for y in range(y0, y1, step):
        for x in range(x0, x1, step):
            c = a if ((x // step + y // step) % 2 == 0) else b
            d.rectangle([x, y, min(x + step - 1, x1 - 1), min(y + step - 1, y1 - 1)], fill=c)


def outline_rect(
    d: ImageDraw.ImageDraw,
    *,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    color: tuple[int, int, int, int],
    w: int = 1,
) -> None:
    for i in range(w):
        d.rectangle([x0 + i, y0 + i, x1 - 1 - i, y1 - 1 - i], outline=color)


def drop_shadow_rect(
    d: ImageDraw.ImageDraw,
    *,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    shadow: tuple[int, int, int, int],
    off: int = 2,
) -> None:
    d.rectangle([x0 + off, y0 + off, x1 + off, y1 + off], fill=shadow)

def bevel_rect(
    d: ImageDraw.ImageDraw,
    *,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    light: tuple[int, int, int, int],
    dark: tuple[int, int, int, int],
) -> None:
    # Cheap PS1/PS2-ish bevel: 1px light top/left, 1px dark bottom/right.
    d.line([(x0, y0), (x1 - 1, y0)], fill=light)
    d.line([(x0, y0), (x0, y1 - 1)], fill=light)
    d.line([(x0, y1 - 1), (x1 - 1, y1 - 1)], fill=dark)
    d.line([(x1 - 1, y0), (x1 - 1, y1 - 1)], fill=dark)


def text(
    d: ImageDraw.ImageDraw,
    *,
    x: int,
    y: int,
    s: str,
    color: tuple[int, int, int, int],
    font: ImageFont.ImageFont,
    shadow: tuple[int, int, int, int] | None = None,
    shadow_off: int = 1,
) -> None:
    if shadow is not None:
        d.text((x + shadow_off, y + shadow_off), s, font=font, fill=shadow)
    d.text((x, y), s, font=font, fill=color)

def _text_width(font: ImageFont.ImageFont, s: str) -> int:
    try:
        box = font.getbbox(s)  # type: ignore[attr-defined]
        return int(box[2] - box[0])
    except Exception:
        return int(font.getlength(s)) if hasattr(font, "getlength") else len(s) * 7


def _text_height(font: ImageFont.ImageFont, s: str = "Ag") -> int:
    try:
        box = font.getbbox(s)  # type: ignore[attr-defined]
        return int(box[3] - box[1])
    except Exception:
        return 10


def fit_font_for_width(*, s: str, max_w: int, start_size: int) -> ImageFont.ImageFont:
    # Shrink font size until the string fits. If we're on the PIL bitmap default,
    # we can't resize; caller should elide.
    for size in range(int(start_size), 7, -1):
        f = load_ui_font(size=size)
        if _text_width(f, s) <= max_w:
            return f
    return load_ui_font(size=8)


def elide_to_width(font: ImageFont.ImageFont, s: str, max_w: int) -> str:
    if _text_width(font, s) <= max_w:
        return s
    if max_w <= _text_width(font, "..."):
        return "..."
    out = s
    while out:
        out = out[:-1]
        cand = out + "..."
        if _text_width(font, cand) <= max_w:
            return cand
    return "..."

def text_fit(
    d: ImageDraw.ImageDraw,
    *,
    x: int,
    y: int,
    s: str,
    color: tuple[int, int, int, int],
    max_w: int,
    start_size: int = 12,
    shadow: tuple[int, int, int, int] | None = None,
) -> None:
    f = fit_font_for_width(s=s, max_w=max_w, start_size=start_size)
    s2 = elide_to_width(f, s, max_w)
    text(d, x=x, y=y, s=s2, color=color, font=f, shadow=shadow)


def text_in_box(
    d: ImageDraw.ImageDraw,
    *,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    pad_x: int,
    s: str,
    color: tuple[int, int, int, int],
    start_size: int = 12,
    shadow: tuple[int, int, int, int] | None = None,
) -> None:
    # Fits text to width and centers it vertically within the box.
    max_w = max(10, (x1 - x0) - (pad_x * 2))
    f = fit_font_for_width(s=s, max_w=max_w, start_size=start_size)
    s2 = elide_to_width(f, s, max_w)
    th = _text_height(f)
    cy = y0 + ((y1 - y0) // 2)
    y = int(cy - (th / 2))
    text(d, x=x0 + pad_x, y=y, s=s2, color=color, font=f, shadow=shadow)


def scanlines(img: Image.Image, strength: int = 18) -> None:
    # Darken every other row a bit.
    px = img.load()
    w, h = img.size
    for y in range(0, h, 2):
        for x in range(w):
            r, g, b, a = px[x, y]
            r = max(0, r - strength)
            g = max(0, g - strength)
            b = max(0, b - strength)
            px[x, y] = (r, g, b, a)


def vignette(img: Image.Image, amount: float = 0.22) -> None:
    w, h = img.size
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    maxd = (cx * cx + cy * cy) ** 0.5
    px = img.load()
    for y in range(h):
        dy = y - cy
        for x in range(w):
            dx = x - cx
            d = (dx * dx + dy * dy) ** 0.5 / maxd
            k = 1.0 - amount * (d ** 1.6)
            r, g, b, a = px[x, y]
            px[x, y] = (int(r * k), int(g * k), int(b * k), a)


def draw_kit(theme: Theme, *, base_w: int = 640, base_h: int = 360) -> Image.Image:
    img = Image.new("RGBA", (base_w, base_h), theme.bg0)
    d = ImageDraw.Draw(img)
    font = load_ui_font(size=12)

    # Background gradient bands (PS1/PS2-ish, no smooth gradients).
    for y in range(0, base_h, 6):
        t = y / (base_h - 1)
        c = (
            int(theme.bg0[0] * (1 - t) + theme.bg1[0] * t),
            int(theme.bg0[1] * (1 - t) + theme.bg1[1] * t),
            int(theme.bg0[2] * (1 - t) + theme.bg1[2] * t),
            255,
        )
        d.rectangle([0, y, base_w, min(base_h, y + 6)], fill=c)

    # Header strip.
    drop_shadow_rect(d, x0=12, y0=10, x1=base_w - 12, y1=44, shadow=theme.shadow, off=2)
    draw_dither_rect(
        d,
        x0=12,
        y0=10,
        x1=base_w - 12,
        y1=44,
        a=theme.panel2,
        b=theme.panel,
        step=2,
    )
    outline_rect(d, x0=12, y0=10, x1=base_w - 12, y1=44, color=theme.outline, w=1)
    text(
        d,
        x=20,
        y=18,
        s=theme.name,
        color=theme.text,
        font=font,
        shadow=theme.shadow,
    )
    text(
        d,
        x=20,
        y=32,
        s="UI Kit (procedural, 16:9). Components + states.",
        color=theme.text_muted,
        font=font,
    )

    # Left column: Window + List.
    win_x0, win_y0, win_x1, win_y1 = 18, 56, 310, 334
    drop_shadow_rect(d, x0=win_x0, y0=win_y0, x1=win_x1, y1=win_y1, shadow=theme.shadow, off=3)
    draw_dither_rect(d, x0=win_x0, y0=win_y0, x1=win_x1, y1=win_y1, a=theme.panel, b=theme.dither_b, step=2)
    outline_rect(d, x0=win_x0, y0=win_y0, x1=win_x1, y1=win_y1, color=theme.outline, w=1)

    # Titlebar.
    d.rectangle([win_x0, win_y0, win_x1, win_y0 + 18], fill=theme.accent)
    outline_rect(d, x0=win_x0, y0=win_y0, x1=win_x1, y1=win_y0 + 18, color=theme.outline, w=1)
    text(d, x=win_x0 + 6, y=win_y0 + 5, s="WINDOW / PANEL", color=(10, 10, 10, 255), font=font)

    # List box.
    list_x0, list_y0, list_x1, list_y1 = win_x0 + 10, win_y0 + 34, win_x1 - 10, win_y1 - 86
    draw_dither_rect(d, x0=list_x0, y0=list_y0, x1=list_x1, y1=list_y1, a=theme.panel2, b=theme.panel, step=2)
    outline_rect(d, x0=list_x0, y0=list_y0, x1=list_x1, y1=list_y1, color=theme.outline, w=1)

    items = [
        "New Game",
        "Continue",
        "Map Selector",
        "Key Bindings",
        "Settings",
        "Quit",
    ]
    sel = 2
    y = list_y0 + 6
    for i, it in enumerate(items):
        if i == sel:
            d.rectangle([list_x0 + 2, y - 1, list_x1 - 2, y + 11], fill=theme.glow)
            outline_rect(d, x0=list_x0 + 2, y0=y - 1, x1=list_x1 - 2, y1=y + 11, color=theme.accent, w=1)
            text(d, x=list_x0 + 8, y=y, s="> " + it, color=theme.text, font=font)
        else:
            text(d, x=list_x0 + 8, y=y, s="  " + it, color=theme.text_muted, font=font)
        y += 14

    # Tooltip.
    tip_x0, tip_y0, tip_x1, tip_y1 = list_x0 + 18, list_y1 + 8, list_x1, list_y1 + 44
    drop_shadow_rect(d, x0=tip_x0, y0=tip_y0, x1=tip_x1, y1=tip_y1, shadow=theme.shadow, off=2)
    draw_dither_rect(d, x0=tip_x0, y0=tip_y0, x1=tip_x1, y1=tip_y1, a=theme.panel2, b=theme.panel, step=2)
    outline_rect(d, x0=tip_x0, y0=tip_y0, x1=tip_x1, y1=tip_y1, color=theme.outline, w=1)
    text(d, x=tip_x0 + 6, y=tip_y0 + 6, s="Tooltip: explains the focused item.", color=theme.text, font=font)
    text(d, x=tip_x0 + 6, y=tip_y0 + 20, s="Rule: always present, never overlaps cursor.", color=theme.text_muted, font=font)

    # Footer status bar.
    st_x0, st_y0, st_x1, st_y1 = win_x0 + 10, win_y1 - 44, win_x1 - 10, win_y1 - 14
    draw_dither_rect(d, x0=st_x0, y0=st_y0, x1=st_x1, y1=st_y1, a=theme.panel2, b=theme.panel, step=2)
    outline_rect(d, x0=st_x0, y0=st_y0, x1=st_x1, y1=st_y1, color=theme.outline, w=1)
    # Status text tends to be long; keep it neatly inside the bar.
    text_in_box(
        d,
        x0=st_x0,
        y0=st_y0,
        x1=st_x1,
        y1=st_y1,
        pad_x=6,
        s="Status: importing bundle...",
        color=theme.text_muted,
        start_size=11,
        shadow=None,
    )

    # Right column: Controls + States.
    col_x0, col_y0, col_x1, col_y1 = 326, 56, base_w - 18, 334
    drop_shadow_rect(d, x0=col_x0, y0=col_y0, x1=col_x1, y1=col_y1, shadow=theme.shadow, off=3)
    draw_dither_rect(d, x0=col_x0, y0=col_y0, x1=col_x1, y1=col_y1, a=theme.panel, b=theme.dither_b, step=2)
    outline_rect(d, x0=col_x0, y0=col_y0, x1=col_x1, y1=col_y1, color=theme.outline, w=1)

    text(d, x=col_x0 + 10, y=col_y0 + 8, s="CONTROLS", color=theme.text, font=font, shadow=theme.shadow)

    # Buttons row.
    btn_y = col_y0 + 26
    btn_w = 86
    btn_h = 18

    def button(x: int, y: int, label: str, *, state: str) -> None:
        if state == "default":
            fill_a, fill_b = theme.panel2, theme.panel
            out = theme.outline
            txt = theme.text
        elif state == "hover":
            fill_a, fill_b = theme.glow, theme.panel2
            out = theme.accent
            txt = theme.text
        elif state == "pressed":
            fill_a, fill_b = theme.panel, theme.panel2
            out = theme.accent
            txt = theme.text
        elif state == "disabled":
            fill_a, fill_b = theme.panel, theme.panel
            out = theme.outline
            txt = theme.text_muted
        elif state == "danger":
            fill_a, fill_b = (theme.danger[0], theme.danger[1], theme.danger[2], 50), theme.panel2
            out = theme.danger
            txt = theme.text
        else:
            fill_a, fill_b = theme.panel2, theme.panel
            out = theme.outline
            txt = theme.text

        draw_dither_rect(d, x0=x, y0=y, x1=x + btn_w, y1=y + btn_h, a=fill_a, b=fill_b, step=2)
        outline_rect(d, x0=x, y0=y, x1=x + btn_w, y1=y + btn_h, color=out, w=1)
        text(d, x=x + 6, y=y + 5, s=label, color=txt, font=font)

    button(col_x0 + 10, btn_y, "Button", state="default")
    button(col_x0 + 104, btn_y, "Hover", state="hover")
    button(col_x0 + 198, btn_y, "Pressed", state="pressed")
    button(col_x0 + 292, btn_y, "Disabled", state="disabled")

    # Toggle.
    t_y = btn_y + 32
    text(d, x=col_x0 + 10, y=t_y, s="Toggle:", color=theme.text_muted, font=font)
    # OFF
    draw_dither_rect(d, x0=col_x0 + 68, y0=t_y - 2, x1=col_x0 + 130, y1=t_y + 14, a=theme.panel2, b=theme.panel, step=2)
    outline_rect(d, x0=col_x0 + 68, y0=t_y - 2, x1=col_x0 + 130, y1=t_y + 14, color=theme.outline, w=1)
    text(d, x=col_x0 + 86, y=t_y + 2, s="OFF", color=theme.text_muted, font=font)
    # ON
    draw_dither_rect(d, x0=col_x0 + 138, y0=t_y - 2, x1=col_x0 + 200, y1=t_y + 14, a=theme.glow, b=theme.panel2, step=2)
    outline_rect(d, x0=col_x0 + 138, y0=t_y - 2, x1=col_x0 + 200, y1=t_y + 14, color=theme.accent, w=1)
    text(d, x=col_x0 + 160, y=t_y + 2, s="ON", color=theme.text, font=font)

    # Slider.
    s_y = t_y + 24
    text(d, x=col_x0 + 10, y=s_y, s="Slider:", color=theme.text_muted, font=font)
    track_x0, track_y0 = col_x0 + 68, s_y + 4
    track_x1, track_y1 = col_x0 + 292, s_y + 10
    d.rectangle([track_x0, track_y0, track_x1, track_y1], fill=theme.panel2)
    outline_rect(d, x0=track_x0, y0=track_y0, x1=track_x1, y1=track_y1, color=theme.outline, w=1)
    val = 0.66
    knob_x = int(track_x0 + (track_x1 - track_x0) * val)
    d.rectangle([knob_x - 3, track_y0 - 3, knob_x + 3, track_y1 + 3], fill=theme.accent)
    outline_rect(d, x0=knob_x - 3, y0=track_y0 - 3, x1=knob_x + 3, y1=track_y1 + 3, color=theme.outline, w=1)
    text(d, x=track_x1 + 8, y=s_y, s="66", color=theme.text, font=font)

    # Text entry.
    e_y = s_y + 24
    text(d, x=col_x0 + 10, y=e_y, s="Entry:", color=theme.text_muted, font=font)
    ex0, ey0, ex1, ey1 = col_x0 + 68, e_y - 2, col_x0 + 292, e_y + 14
    draw_dither_rect(d, x0=ex0, y0=ey0, x1=ex1, y1=ey1, a=(240, 240, 240, 40), b=theme.panel2, step=2)
    outline_rect(d, x0=ex0, y0=ey0, x1=ex1, y1=ey1, color=theme.outline, w=1)
    text_fit(
        d,
        x=ex0 + 6,
        y=e_y + 2,
        s="mouse_sensitivity = 0.11",
        color=theme.text,
        max_w=(ex1 - 6) - (ex0 + 6),
        start_size=12,
        shadow=None,
    )

    # Dropdown.
    dd_y = e_y + 24
    text(d, x=col_x0 + 10, y=dd_y, s="Dropdown:", color=theme.text_muted, font=font)
    dx0, dy0, dx1, dy1 = col_x0 + 68, dd_y - 2, col_x0 + 292, dd_y + 14
    draw_dither_rect(d, x0=dx0, y0=dy0, x1=dx1, y1=dy1, a=theme.panel2, b=theme.panel, step=2)
    outline_rect(d, x0=dx0, y0=dy0, x1=dx1, y1=dy1, color=theme.outline, w=1)
    text(d, x=dx0 + 6, y=dd_y + 2, s="profile: surf_bhop", color=theme.text, font=font)
    text(d, x=dx1 - 16, y=dd_y + 2, s="v", color=theme.text_muted, font=font)

    # Progress / meters.
    m_y = dd_y + 26
    text(d, x=col_x0 + 10, y=m_y, s="Meters:", color=theme.text_muted, font=font)

    def meter(x: int, y: int, w: int, label: str, v: float, color: tuple[int, int, int, int]) -> None:
        text(d, x=x, y=y, s=label, color=theme.text_muted, font=font)
        x0, y0, x1, y1 = x + 84, y + 4, x + 84 + w, y + 10
        d.rectangle([x0, y0, x1, y1], fill=theme.panel2)
        outline_rect(d, x0=x0, y0=y0, x1=x1, y1=y1, color=theme.outline, w=1)
        fill_w = int((x1 - x0) * v)
        d.rectangle([x0 + 1, y0 + 1, x0 + max(1, fill_w) - 1, y1 - 1], fill=color)

    meter(col_x0 + 10, m_y, 140, "HP", 0.78, theme.ok)
    meter(col_x0 + 10, m_y + 16, 140, "ARM", 0.35, theme.accent)
    meter(col_x0 + 10, m_y + 32, 140, "HEAT", 0.62, theme.danger)

    # Small hints.
    hint_y = col_y1 - 44
    draw_dither_rect(d, x0=col_x0 + 10, y0=hint_y, x1=col_x1 - 10, y1=col_y1 - 12, a=theme.panel2, b=theme.panel, step=2)
    outline_rect(d, x0=col_x0 + 10, y0=hint_y, x1=col_x1 - 10, y1=col_y1 - 12, color=theme.outline, w=1)
    text(d, x=col_x0 + 16, y=hint_y + 6, s="Nav: visible focus. No hidden states. Big hit targets.", color=theme.text_muted, font=font)

    # Optional CRT pass.
    if theme.key == "crt_lime":
        scanlines(img, strength=18)
        vignette(img, amount=0.28)

    return img


def draw_kit_variant(theme: Theme, variant: Variant, *, base_w: int = 640, base_h: int = 360) -> Image.Image:
    img = Image.new("RGBA", (base_w, base_h), theme.bg0)
    d = ImageDraw.Draw(img)
    font = load_ui_font(size=12)

    # Background gradient bands (no smooth gradients).
    for y in range(0, base_h, 6):
        t = y / (base_h - 1)
        c = (
            int(theme.bg0[0] * (1 - t) + theme.bg1[0] * t),
            int(theme.bg0[1] * (1 - t) + theme.bg1[1] * t),
            int(theme.bg0[2] * (1 - t) + theme.bg1[2] * t),
            255,
        )
        d.rectangle([0, y, base_w, min(base_h, y + 6)], fill=c)

    m = int(variant.margin)
    shadow = (0, 0, 0, int(variant.shadow_alpha))

    # Header strip.
    drop_shadow_rect(d, x0=m, y0=m, x1=base_w - m, y1=m + 34, shadow=shadow, off=variant.shadow_off)
    draw_dither_rect(
        d,
        x0=m,
        y0=m,
        x1=base_w - m,
        y1=m + 34,
        a=theme.panel2,
        b=theme.panel,
        step=2,
    )
    outline_rect(d, x0=m, y0=m, x1=base_w - m, y1=m + 34, color=theme.outline, w=variant.outline_w)
    if variant.bevel:
        bevel_rect(d, x0=m, y0=m, x1=base_w - m, y1=m + 34, light=theme.text_muted, dark=shadow)
    text_fit(
        d,
        x=m + 10,
        y=m + 6,
        s=f"{theme.name} / {variant.name}",
        color=theme.text,
        max_w=(base_w - m - 10) - (m + 10),
        start_size=12,
        shadow=shadow,
    )
    text_fit(
        d,
        x=m + 10,
        y=m + 20,
        s="UI kit: layout + spacing + framing variants.",
        color=theme.text_muted,
        max_w=(base_w - m - 10) - (m + 10),
        start_size=11,
        shadow=None,
    )

    # Two columns.
    top = m + 46
    bottom = base_h - m
    gap = 14 if variant.pad >= 10 else 12
    col_gap = 16 if variant.pad >= 10 else 14
    left_x0 = m
    left_x1 = int(base_w * 0.49)
    right_x0 = left_x1 + col_gap
    right_x1 = base_w - m

    # Left: window.
    win_x0, win_y0, win_x1, win_y1 = left_x0, top, left_x1, bottom
    drop_shadow_rect(d, x0=win_x0, y0=win_y0, x1=win_x1, y1=win_y1, shadow=shadow, off=variant.shadow_off)
    draw_dither_rect(d, x0=win_x0, y0=win_y0, x1=win_x1, y1=win_y1, a=theme.panel, b=theme.dither_b, step=2)
    outline_rect(d, x0=win_x0, y0=win_y0, x1=win_x1, y1=win_y1, color=theme.outline, w=variant.outline_w)
    if variant.bevel:
        bevel_rect(d, x0=win_x0, y0=win_y0, x1=win_x1, y1=win_y1, light=theme.text_muted, dark=shadow)

    # Titlebar.
    tb_h = 18
    d.rectangle([win_x0, win_y0, win_x1, win_y0 + tb_h], fill=theme.accent)
    outline_rect(
        d,
        x0=win_x0,
        y0=win_y0,
        x1=win_x1,
        y1=win_y0 + tb_h,
        color=theme.outline,
        w=variant.outline_w,
    )
    text(d, x=win_x0 + variant.pad, y=win_y0 + 5, s="WINDOW / LIST", color=(10, 10, 10, 255), font=font)

    # List box (variant pad affects margins).
    list_x0 = win_x0 + variant.pad
    list_y0 = win_y0 + tb_h + gap
    list_x1 = win_x1 - variant.pad
    list_y1 = win_y1 - (variant.pad + 78)
    draw_dither_rect(d, x0=list_x0, y0=list_y0, x1=list_x1, y1=list_y1, a=theme.panel2, b=theme.panel, step=2)
    outline_rect(d, x0=list_x0, y0=list_y0, x1=list_x1, y1=list_y1, color=theme.outline, w=variant.outline_w)

    items = ["New Game", "Continue", "Map Selector", "Key Bindings", "Settings", "Quit"]
    sel = 2
    y = list_y0 + variant.pad
    row_h = 14 if variant.pad <= 8 else 15
    for i, it in enumerate(items):
        if i == sel:
            d.rectangle([list_x0 + 2, y - 1, list_x1 - 2, y + 11], fill=theme.glow)
            outline_rect(
                d,
                x0=list_x0 + 2,
                y0=y - 1,
                x1=list_x1 - 2,
                y1=y + 11,
                color=theme.accent,
                w=variant.glow_outline_w,
            )
            text(d, x=list_x0 + 8, y=y, s="> " + it, color=theme.text, font=font)
        else:
            text(d, x=list_x0 + 8, y=y, s="  " + it, color=theme.text_muted, font=font)
        y += row_h

    # Tooltip.
    tip_x0 = list_x0 + 18
    tip_y0 = list_y1 + gap
    tip_x1 = list_x1
    tip_y1 = tip_y0 + 36
    drop_shadow_rect(d, x0=tip_x0, y0=tip_y0, x1=tip_x1, y1=tip_y1, shadow=shadow, off=max(1, variant.shadow_off - 1))
    draw_dither_rect(d, x0=tip_x0, y0=tip_y0, x1=tip_x1, y1=tip_y1, a=theme.panel2, b=theme.panel, step=2)
    outline_rect(d, x0=tip_x0, y0=tip_y0, x1=tip_x1, y1=tip_y1, color=theme.outline, w=variant.outline_w)
    if variant.bevel:
        bevel_rect(d, x0=tip_x0, y0=tip_y0, x1=tip_x1, y1=tip_y1, light=theme.text_muted, dark=shadow)
    text(d, x=tip_x0 + variant.pad, y=tip_y0 + 6, s="Tooltip: focus explanation.", color=theme.text, font=font)
    text(d, x=tip_x0 + variant.pad, y=tip_y0 + 20, s="Rule: anchored, non-overlapping.", color=theme.text_muted, font=font)

    # Footer status bar.
    st_x0 = list_x0
    st_y0 = win_y1 - (variant.pad + 34)
    st_x1 = list_x1
    st_y1 = st_y0 + 18
    draw_dither_rect(d, x0=st_x0, y0=st_y0, x1=st_x1, y1=st_y1, a=theme.panel2, b=theme.panel, step=2)
    outline_rect(d, x0=st_x0, y0=st_y0, x1=st_x1, y1=st_y1, color=theme.outline, w=variant.outline_w)
    text_in_box(
        d,
        x0=st_x0,
        y0=st_y0,
        x1=st_x1,
        y1=st_y1,
        pad_x=variant.pad,
        s="Status: importing bundle...",
        color=theme.text_muted,
        start_size=11,
        shadow=None,
    )

    # Right: controls.
    col_x0, col_y0, col_x1, col_y1 = right_x0, top, right_x1, bottom
    drop_shadow_rect(d, x0=col_x0, y0=col_y0, x1=col_x1, y1=col_y1, shadow=shadow, off=variant.shadow_off)
    draw_dither_rect(d, x0=col_x0, y0=col_y0, x1=col_x1, y1=col_y1, a=theme.panel, b=theme.dither_b, step=2)
    outline_rect(d, x0=col_x0, y0=col_y0, x1=col_x1, y1=col_y1, color=theme.outline, w=variant.outline_w)
    if variant.bevel:
        bevel_rect(d, x0=col_x0, y0=col_y0, x1=col_x1, y1=col_y1, light=theme.text_muted, dark=shadow)

    text(d, x=col_x0 + variant.pad, y=col_y0 + variant.pad, s="CONTROLS", color=theme.text, font=font, shadow=shadow)

    # Buttons: ensure they fit (adaptive 4-wide -> 2x2).
    btn_labels = [("Button", "default"), ("Hover", "hover"), ("Pressed", "pressed"), ("Disabled", "disabled")]
    btn_h = 18
    btn_y = col_y0 + 26
    inner_x0 = col_x0 + variant.pad
    inner_x1 = col_x1 - variant.pad
    avail = inner_x1 - inner_x0
    gap_x = 10 if variant.pad <= 8 else 12
    n = 4
    btn_w = int((avail - gap_x * (n - 1)) / n)
    grid = "row"
    if btn_w < 66:
        grid = "2x2"
        n = 2
        btn_w = int((avail - gap_x * (n - 1)) / n)

    def button(x: int, y: int, label: str, *, state: str) -> None:
        if state == "default":
            fill_a, fill_b = theme.panel2, theme.panel
            out = theme.outline
            txt = theme.text
        elif state == "hover":
            fill_a, fill_b = theme.glow, theme.panel2
            out = theme.accent
            txt = theme.text
        elif state == "pressed":
            fill_a, fill_b = theme.panel, theme.panel2
            out = theme.accent
            txt = theme.text
        elif state == "disabled":
            fill_a, fill_b = theme.panel, theme.panel
            out = theme.outline
            txt = theme.text_muted
        else:
            fill_a, fill_b = theme.panel2, theme.panel
            out = theme.outline
            txt = theme.text

        draw_dither_rect(d, x0=x, y0=y, x1=x + btn_w, y1=y + btn_h, a=fill_a, b=fill_b, step=2)
        outline_rect(d, x0=x, y0=y, x1=x + btn_w, y1=y + btn_h, color=out, w=variant.outline_w)
        if variant.bevel:
            bevel_rect(d, x0=x, y0=y, x1=x + btn_w, y1=y + btn_h, light=theme.text_muted, dark=shadow)
        text_in_box(
            d,
            x0=x,
            y0=y,
            x1=x + btn_w,
            y1=y + btn_h,
            pad_x=6,
            s=label,
            color=txt,
            start_size=12,
            shadow=None,
        )

    if grid == "row":
        x = inner_x0
        for label, st in btn_labels:
            button(x, btn_y, label, state=st)
            x += btn_w + gap_x
        next_y = btn_y + 32
    else:
        x0 = inner_x0
        x1 = inner_x0 + btn_w + gap_x
        button(x0, btn_y, "Button", state="default")
        button(x1, btn_y, "Hover", state="hover")
        button(x0, btn_y + 24, "Pressed", state="pressed")
        button(x1, btn_y + 24, "Disabled", state="disabled")
        next_y = btn_y + 56

    # Checkbox (compact toggle).
    t_y = next_y
    text(d, x=inner_x0, y=t_y, s="Checkbox:", color=theme.text_muted, font=font)

    cb_size = 14
    cb_x0 = inner_x0 + 76
    cb_y0 = t_y - 1
    # Unchecked.
    draw_dither_rect(
        d,
        x0=cb_x0,
        y0=cb_y0,
        x1=cb_x0 + cb_size,
        y1=cb_y0 + cb_size,
        a=theme.panel2,
        b=theme.panel,
        step=2,
    )
    outline_rect(d, x0=cb_x0, y0=cb_y0, x1=cb_x0 + cb_size, y1=cb_y0 + cb_size, color=theme.outline, w=variant.outline_w)
    if variant.bevel:
        bevel_rect(d, x0=cb_x0, y0=cb_y0, x1=cb_x0 + cb_size, y1=cb_y0 + cb_size, light=theme.text_muted, dark=shadow)
    text_in_box(
        d,
        x0=cb_x0 + cb_size + 6,
        y0=cb_y0,
        x1=cb_x0 + cb_size + 6 + 110,
        y1=cb_y0 + cb_size,
        pad_x=0,
        s="Fullscreen",
        color=theme.text_muted,
        start_size=12,
        shadow=None,
    )

    # Checked (focused).
    cb2_x0 = cb_x0 + 180
    draw_dither_rect(
        d,
        x0=cb2_x0,
        y0=cb_y0,
        x1=cb2_x0 + cb_size,
        y1=cb_y0 + cb_size,
        a=theme.glow,
        b=theme.panel2,
        step=2,
    )
    outline_rect(d, x0=cb2_x0, y0=cb_y0, x1=cb2_x0 + cb_size, y1=cb_y0 + cb_size, color=theme.accent, w=variant.glow_outline_w)
    # Check mark (chunky).
    d.rectangle([cb2_x0 + 3, cb_y0 + 6, cb2_x0 + 6, cb_y0 + 9], fill=theme.accent)
    d.rectangle([cb2_x0 + 6, cb_y0 + 4, cb2_x0 + 11, cb_y0 + 9], fill=theme.accent)
    text_in_box(
        d,
        x0=cb2_x0 + cb_size + 6,
        y0=cb_y0,
        x1=cb2_x0 + cb_size + 6 + 90,
        y1=cb_y0 + cb_size,
        pad_x=0,
        s="VSync",
        color=theme.text,
        start_size=12,
        shadow=None,
    )

    # Slider.
    s_y = t_y + 24
    text(d, x=inner_x0, y=s_y, s="Slider:", color=theme.text_muted, font=font)
    track_x0, track_y0 = inner_x0 + 58, s_y + 4
    track_x1, track_y1 = inner_x1 - 40, s_y + 10
    d.rectangle([track_x0, track_y0, track_x1, track_y1], fill=theme.panel2)
    outline_rect(d, x0=track_x0, y0=track_y0, x1=track_x1, y1=track_y1, color=theme.outline, w=variant.outline_w)
    val = 0.66
    knob_x = int(track_x0 + (track_x1 - track_x0) * val)
    d.rectangle([knob_x - 3, track_y0 - 3, knob_x + 3, track_y1 + 3], fill=theme.accent)
    outline_rect(d, x0=knob_x - 3, y0=track_y0 - 3, x1=knob_x + 3, y1=track_y1 + 3, color=theme.outline, w=variant.outline_w)
    text(d, x=track_x1 + 8, y=s_y, s="66", color=theme.text, font=font)

    # Entry + Dropdown.
    e_y = s_y + 24
    text(d, x=inner_x0, y=e_y, s="Entry:", color=theme.text_muted, font=font)
    ex0, ey0, ex1, ey1 = inner_x0 + 58, e_y - 2, inner_x1, e_y + 14
    draw_dither_rect(d, x0=ex0, y0=ey0, x1=ex1, y1=ey1, a=(240, 240, 240, 40), b=theme.panel2, step=2)
    outline_rect(d, x0=ex0, y0=ey0, x1=ex1, y1=ey1, color=theme.outline, w=variant.outline_w)
    text_in_box(
        d,
        x0=ex0,
        y0=ey0,
        x1=ex1,
        y1=ey1,
        pad_x=6,
        s="mouse_sensitivity = 0.11",
        color=theme.text,
        start_size=12,
        shadow=None,
    )

    dd_y = e_y + 22
    text(d, x=inner_x0, y=dd_y, s="Dropdown:", color=theme.text_muted, font=font)
    dx0, dy0, dx1, dy1 = inner_x0 + 58, dd_y - 2, inner_x1, dd_y + 14
    draw_dither_rect(d, x0=dx0, y0=dy0, x1=dx1, y1=dy1, a=theme.panel2, b=theme.panel, step=2)
    outline_rect(d, x0=dx0, y0=dy0, x1=dx1, y1=dy1, color=theme.outline, w=variant.outline_w)
    text_in_box(
        d,
        x0=dx0,
        y0=dy0,
        x1=dx1 - 18,
        y1=dy1,
        pad_x=6,
        s="profile: surf_bhop",
        color=theme.text,
        start_size=12,
        shadow=None,
    )
    text(d, x=dx1 - 16, y=dd_y + 2, s="v", color=theme.text_muted, font=font)

    # Meters.
    m_y = dd_y + 24
    text(d, x=inner_x0, y=m_y, s="Meters:", color=theme.text_muted, font=font)

    def meter(x: int, y: int, w: int, label: str, v: float, color: tuple[int, int, int, int]) -> None:
        text(d, x=x, y=y, s=label, color=theme.text_muted, font=font)
        x0, y0, x1, y1 = x + 54, y + 4, x + 54 + w, y + 10
        d.rectangle([x0, y0, x1, y1], fill=theme.panel2)
        outline_rect(d, x0=x0, y0=y0, x1=x1, y1=y1, color=theme.outline, w=variant.outline_w)
        fill_w = int((x1 - x0) * v)
        d.rectangle([x0 + 1, y0 + 1, x0 + max(1, fill_w) - 1, y1 - 1], fill=color)

    meter(inner_x0, m_y, 132, "HP", 0.78, theme.ok)
    meter(inner_x0, m_y + 16, 132, "ARM", 0.35, theme.accent)
    meter(inner_x0, m_y + 32, 132, "HEAT", 0.62, theme.danger)

    # Bottom hint bar.
    hint_y0 = col_y1 - (variant.pad + 26)
    draw_dither_rect(d, x0=inner_x0, y0=hint_y0, x1=inner_x1, y1=col_y1 - variant.pad, a=theme.panel2, b=theme.panel, step=2)
    outline_rect(d, x0=inner_x0, y0=hint_y0, x1=inner_x1, y1=col_y1 - variant.pad, color=theme.outline, w=variant.outline_w)
    text_fit(
        d,
        x=inner_x0 + variant.pad,
        y=hint_y0 + 6,
        s="Spacing is standardized. Buttons always fit.",
        color=theme.text_muted,
        max_w=(inner_x1 - variant.pad) - (inner_x0 + variant.pad),
        start_size=11,
        shadow=None,
    )

    # Optional CRT pass.
    if theme.key == "crt_lime":
        scanlines(img, strength=18)
        vignette(img, amount=0.28)

    return img


def write_passport_md(theme: Theme, out_path: Path) -> None:
    md = []
    md.append(f"# {theme.name}\n")
    md.append("\n")
    md.append("## Intent\n")
    md.append("- Minimal PS1/PS2-era UI: flat panels, hard edges, clear focus, high readability while moving.")
    md.append("- Procedural-only: no shipped fonts/textures required for the baseline kit.")
    md.append("- Suitable for boomer-shooter style menus/HUD and in-game debug panels.\n")
    md.append("## Tokens (Core)\n")
    md.append(f"- bg0: `{_hex(theme.bg0)}`")
    md.append(f"- bg1: `{_hex(theme.bg1)}`")
    md.append(f"- panel: `{_hex(theme.panel)}`")
    md.append(f"- panel2: `{_hex(theme.panel2)}`")
    md.append(f"- outline: `{_hex(theme.outline)}`")
    md.append(f"- text: `{_hex(theme.text)}`")
    md.append(f"- text_muted: `{_hex(theme.text_muted)}`")
    md.append(f"- accent: `{_hex(theme.accent)}`")
    md.append(f"- ok: `{_hex(theme.ok)}`")
    md.append(f"- danger: `{_hex(theme.danger)}`\n")
    md.append("## Typography (Procedural Baseline)\n")
    md.append("- Base grid: 640x360 logical pixels, scaled 3x to 1920x1080 with nearest-neighbor.")
    md.append("- Font: default bitmap (placeholder). When a custom font is introduced later, keep the same sizes and spacing rules.")
    md.append("- Text rules: short labels, avoid long paragraphs; use tooltips for explanations.\n")
    md.append("## Spacing + Layout\n")
    md.append("- Grid step: 2px (base). Padding common: 6px (base) inside panels.")
    md.append("- Safe margins: 12px (base) from screen edge for primary containers.")
    md.append("- Focus: always visible outline + subtle glow fill; never rely on color alone for selection.\n")
    md.append("## Component Contract\n")
    md.append("- Window/Panel: titlebar band, 1px outline, dither fill, optional drop shadow.")
    md.append("- Button states: default, hover/focus, pressed, disabled, danger.")
    md.append("- List: single selection, always shows cursor marker, selection outline, scroll hints when needed.")
    md.append("- Toggle: OFF/ON segmented control.")
    md.append("- Slider: thick track + chunky knob.")
    md.append("- Entry: outlined field with readable contrast.")
    md.append("- Dropdown: single-line select with chevron.")
    md.append("- Tooltip: anchored, never overlaps cursor, single responsibility: explain focused item.")
    md.append("- Meter: labeled bar, color-coded by semantics (ok/accent/danger).\n")
    md.append("## Do-Not\n")
    md.append("- No soft gradients; no blurry shadows; no tiny hit targets.")
    md.append("- No inconsistent paddings per screen; no ad-hoc colors outside tokens.")

    out_path.write_text("\n".join(md), encoding="utf-8")

def write_variant_md(theme: Theme, variant: Variant, out_path: Path) -> None:
    md: list[str] = []
    md.append(f"# {theme.name} / {variant.name}\n")
    md.append("\n")
    md.append("## Intent\n")
    md.append("- Same PS1/PS2-era minimal UI direction, but with a distinct layout/framing recipe.\n")
    md.append("## Variant Parameters\n")
    md.append(f"- margin: `{variant.margin}px` (base 640x360)\n")
    md.append(f"- pad: `{variant.pad}px` (base 640x360)\n")
    md.append(f"- outline width: `{variant.outline_w}px`\n")
    md.append(f"- shadow offset: `{variant.shadow_off}px`\n")
    md.append(f"- bevel: `{variant.bevel}`\n")
    md.append("\n")
    md.append("## Tokens (Core)\n")
    md.append(f"- outline: `{_hex(theme.outline)}`\n")
    md.append(f"- text: `{_hex(theme.text)}`\n")
    md.append(f"- accent: `{_hex(theme.accent)}`\n")
    md.append("\n")
    md.append("## Rules\n")
    md.append("- Buttons must always fit inside their parent panel; layout adapts (4-wide or 2x2) based on available width.\n")
    md.append("- Padding/margins are part of the style and must not vary per-screen.\n")
    out_path.write_text("".join(md), encoding="utf-8")


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    out_dir = repo / "ui-passports" / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    out_w, out_h = 1920, 1080  # default verification target (16:9, 3x of 640x360)

    for th in THEMES:
        base = draw_kit(th, base_w=640, base_h=360)
        final = base.resize((out_w, out_h), resample=Image.Resampling.NEAREST)
        png_path = out_dir / f"kit_{th.key}.png"
        final.save(png_path)

        md_path = repo / "ui-passports" / f"{th.key}.md"
        write_passport_md(th, md_path)

    # Additional style variants: same themes, different layout/framing recipes.
    # We render the variants using the PS2-ish theme by default (neutral baseline).
    base_theme = next((t for t in THEMES if t.key == "ps2_cyan"), THEMES[0])
    for v in VARIANTS:
        base = draw_kit_variant(base_theme, v, base_w=640, base_h=360)
        final = base.resize((out_w, out_h), resample=Image.Resampling.NEAREST)
        png_path = out_dir / f"kit_{base_theme.key}_{v.key}.png"
        final.save(png_path)

        md_path = repo / "ui-passports" / f"{base_theme.key}_{v.key}.md"
        write_variant_md(base_theme, v, md_path)


if __name__ == "__main__":
    main()
