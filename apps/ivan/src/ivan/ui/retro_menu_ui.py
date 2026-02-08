from __future__ import annotations

import math
from dataclasses import dataclass

from direct.gui.OnscreenText import OnscreenText
from panda3d.core import (
    CardMaker,
    NodePath,
    PNMImage,
    SamplerState,
    TextNode,
    Texture,
    TransparencyAttrib,
)


@dataclass(frozen=True)
class RetroMenuItem:
    label: str
    enabled: bool = True


class RetroMenuUI:
    """
    Minimal retro-styled menu.

    Implementation notes:
    - Uses procedural textures (PNMImage -> Texture) so we don't need to ship fonts or images.
    - Keeps layout stable: fixed row positions, with a compact status/footer bar.
    """

    def __init__(self, *, aspect2d, title: str, hint: str) -> None:
        self._aspect2d = aspect2d

        self._root = aspect2d.attachNewNode("retro-menu-root")
        self._bg = self._root.attachNewNode("retro-menu-bg")
        self._build_background()

        self._title = OnscreenText(
            text=title,
            parent=self._root,
            align=TextNode.ALeft,
            pos=(-1.30, 0.92),
            scale=0.075,
            fg=(1.0, 0.92, 0.65, 1.0),
            shadow=(0, 0, 0, 1),
        )
        self._hint = OnscreenText(
            text=hint,
            parent=self._root,
            align=TextNode.ALeft,
            pos=(-1.30, 0.84),
            scale=0.045,
            fg=(0.85, 0.85, 0.85, 1.0),
            shadow=(0, 0, 0, 1),
        )
        self._status = OnscreenText(
            text="",
            parent=self._root,
            align=TextNode.ALeft,
            pos=(-1.30, -0.92),
            scale=0.045,
            fg=(0.9, 0.9, 0.9, 1.0),
            shadow=(0, 0, 0, 1),
        )

        self._rows: list[OnscreenText] = []
        self._visible_rows = 18
        for i in range(self._visible_rows):
            y = 0.70 - i * 0.075
            self._rows.append(
                OnscreenText(
                    text="",
                    parent=self._root,
                    align=TextNode.ALeft,
                    pos=(-1.20, y),
                    scale=0.052,
                    fg=(0.8, 0.8, 0.8, 1.0),
                    shadow=(0, 0, 0, 1),
                )
            )

        self._items: list[RetroMenuItem] = []
        self._selected: int = 0
        self._loader_base_status: str | None = None
        self._loader_started_at: float = 0.0

    def destroy(self) -> None:
        for r in self._rows:
            r.removeNode()
        self._rows.clear()
        self._title.removeNode()
        self._hint.removeNode()
        self._status.removeNode()
        self._root.removeNode()

    def set_title(self, title: str) -> None:
        self._title.setText(title)

    def set_hint(self, hint: str) -> None:
        self._hint.setText(hint)

    def set_items(self, items: list[RetroMenuItem], *, selected: int = 0) -> None:
        self._items = items
        self._selected = 0 if not items else max(0, min(len(items) - 1, selected))
        self._redraw()

    def move(self, delta: int) -> None:
        if not self._items:
            return
        self._selected = max(0, min(len(self._items) - 1, self._selected + delta))
        self._redraw()

    def selected_index(self) -> int | None:
        if not self._items:
            return None
        return self._selected

    def set_status(self, text: str) -> None:
        self._loader_base_status = None
        self._status.setText(text)

    def set_loading_status(self, text: str, *, started_at: float) -> None:
        self._loader_base_status = text
        self._loader_started_at = float(started_at)
        self._status.setText(text)

    def tick(self, now: float) -> None:
        if not self._loader_base_status:
            return
        # Animate with a simple dot cycle. Keep it stable under low FPS.
        t = max(0.0, float(now) - self._loader_started_at)
        dots = int(t * 2.5) % 4
        self._status.setText(self._loader_base_status + ("." * dots))

    def _redraw(self) -> None:
        if not self._items:
            for r in self._rows:
                r.setText("")
            self._status.setText("No entries.")
            return

        half = self._visible_rows // 2
        start = max(0, min(len(self._items) - self._visible_rows, self._selected - half))
        window = self._items[start : start + self._visible_rows]

        for i, r in enumerate(self._rows):
            if i >= len(window):
                r.setText("")
                continue
            idx = start + i
            item = window[i]
            prefix = "> " if idx == self._selected else "  "
            label = item.label
            if not item.enabled:
                label = f"{label} [missing]"
            r.setText(prefix + label)

            if idx == self._selected:
                r.setFg((1.0, 0.92, 0.65, 1.0) if item.enabled else (0.7, 0.7, 0.7, 1.0))
            else:
                r.setFg((0.82, 0.82, 0.82, 1.0) if item.enabled else (0.55, 0.55, 0.55, 1.0))

    def _build_background(self) -> None:
        # Two-layer background:
        # - base: gradient + subtle noise (opaque)
        # - overlay: scanlines + vignette (alpha)
        cm = CardMaker("retro-menu-card")
        cm.setFrame(-1.6, 1.6, -1.0, 1.0)
        base = NodePath(cm.generate())
        base.reparentTo(self._bg)
        base.setBin("background", 0)
        base.setDepthWrite(False)
        base.setDepthTest(False)

        overlay = NodePath(cm.generate())
        overlay.reparentTo(self._bg)
        overlay.setBin("background", 1)
        overlay.setDepthWrite(False)
        overlay.setDepthTest(False)
        overlay.setTransparency(TransparencyAttrib.M_alpha)

        base_tex = _make_base_texture(512, 512)
        scan_tex = _make_scanline_texture(512, 512)
        vign_tex = _make_vignette_texture(512, 512)

        base.setTexture(base_tex, 1)
        overlay.setTexture(scan_tex, 1)

        # Vignette as a second overlay card.
        vign = NodePath(cm.generate())
        vign.reparentTo(self._bg)
        vign.setBin("background", 2)
        vign.setDepthWrite(False)
        vign.setDepthTest(False)
        vign.setTransparency(TransparencyAttrib.M_alpha)
        vign.setTexture(vign_tex, 1)


def _set_common_sampler(tex: Texture) -> None:
    tex.setWrapU(SamplerState.WM_repeat)
    tex.setWrapV(SamplerState.WM_repeat)
    tex.setMinfilter(SamplerState.FT_linear)
    tex.setMagfilter(SamplerState.FT_linear)


def _make_base_texture(w: int, h: int) -> Texture:
    img = PNMImage(w, h, 3)
    # Warm-to-cool gradient with subtle noise.
    top = (0.08, 0.10, 0.12)
    bot = (0.03, 0.04, 0.05)
    for y in range(h):
        t = y / max(1, h - 1)
        r = bot[0] * (1.0 - t) + top[0] * t
        g = bot[1] * (1.0 - t) + top[1] * t
        b = bot[2] * (1.0 - t) + top[2] * t
        for x in range(w):
            # Deterministic pseudo-noise: cheap hash (no RNG state).
            n = ((x * 1973 + y * 9277 + 89173) ^ (x * 7919)) & 0xFFFF
            nf = (n / 65535.0 - 0.5) * 0.035
            img.setXel(x, y, max(0.0, min(1.0, r + nf)), max(0.0, min(1.0, g + nf)), max(0.0, min(1.0, b + nf)))
    tex = Texture("retro-menu-base")
    tex.load(img)
    _set_common_sampler(tex)
    return tex


def _make_scanline_texture(w: int, h: int) -> Texture:
    img = PNMImage(w, h, 4)
    for y in range(h):
        # Scanline intensity: every other line darker.
        is_dark = (y % 2) == 0
        a = 0.10 if is_dark else 0.03
        # Slight horizontal modulation to avoid a too-perfect pattern.
        for x in range(w):
            wobble = 0.02 * math.sin((x / w) * math.tau * 6.0 + (y / h) * math.tau * 2.0)
            img.setXelA(x, y, 0.0, 0.0, 0.0, max(0.0, min(1.0, a + wobble)))
    tex = Texture("retro-menu-scanlines")
    tex.load(img)
    _set_common_sampler(tex)
    return tex


def _make_vignette_texture(w: int, h: int) -> Texture:
    img = PNMImage(w, h, 4)
    cx = (w - 1) * 0.5
    cy = (h - 1) * 0.5
    max_r = math.sqrt(cx * cx + cy * cy)
    for y in range(h):
        for x in range(w):
            dx = x - cx
            dy = y - cy
            r = math.sqrt(dx * dx + dy * dy) / max_r
            # Black vignette: alpha ramps up near edges.
            a = max(0.0, min(1.0, (r - 0.45) / 0.55))
            a = a * a * 0.55
            img.setXelA(x, y, 0.0, 0.0, 0.0, a)
    tex = Texture("retro-menu-vignette")
    tex.load(img)
    _set_common_sampler(tex)
    return tex

