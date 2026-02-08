from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

from direct.showbase.ShowBase import ShowBase
from direct.gui import DirectGuiGlobals as DGG
from panda3d.core import CardMaker, Texture, TextureStage, PNMImage, SamplerState
from panda3d.core import TextNode

from irun_ui_kit.theme import Theme
from irun_ui_kit.widgets.window import Window


@dataclass
class UIRenderer:
    base: ShowBase
    theme: Theme

    def set_background(self) -> None:
        self._apply_theme_defaults()
        self.base.setBackgroundColor(*self.theme.bg)
        self._ensure_background_card()

    def _compute_ui_scale(self) -> float:
        """
        Best-effort DPI scale factor.

        On macOS Retina the framebuffer size can be larger than the window size.
        If both APIs are available, use fb/window ratio.
        """

        win = getattr(self.base, "win", None)
        if win is None:
            return 1.0

        def _safe_call(obj, name: str) -> int | None:
            if not hasattr(obj, name):
                return None
            try:
                v = int(getattr(obj, name)())
                return v if v > 0 else None
            except Exception:
                return None

        x = _safe_call(win, "getXSize")
        y = _safe_call(win, "getYSize")
        fx = _safe_call(win, "getFbXSize")
        fy = _safe_call(win, "getFbYSize")
        if x and y and fx and fy:
            return max(1.0, float(fx) / float(x), float(fy) / float(y))
        return 1.0

    def _apply_theme_defaults(self) -> None:
        if getattr(self, "_theme_applied", False):
            return
        self._theme_applied = True

        dpi = self._compute_ui_scale()
        self._ui_scale = dpi
        self.theme = self.theme.with_dpi(dpi)

        def _try_font(name: str) -> bool:
            try:
                font = self.base.loader.loadFont(
                    name,
                    pixelsPerUnit=int(192 * dpi),
                    scaleFactor=2.0,
                    textureMargin=4,
                    minFilter=SamplerState.FTNearest,
                    magFilter=SamplerState.FTNearest,
                )
                if font is None:
                    return False
                TextNode.setDefaultFont(font)
                DGG.setDefaultFont(font)
                return True
            except Exception:
                return False

        # Prefer a bold, low-res readable console font on macOS.
        candidates: list[str] = []
        if self.theme.font:
            candidates.append(self.theme.font)

        if sys.platform == "darwin":
            candidates.extend(
                [
                    # Prefer classic console-style monos for low-res readability.
                    "/System/Library/Fonts/Monaco.ttf",
                    "/System/Library/Fonts/Menlo.ttc",
                    "/System/Library/Fonts/SFNSMono.ttf",
                    "/System/Library/Fonts/Supplemental/Andale Mono.ttf",
                    "/System/Library/Fonts/Supplemental/Courier New Bold.ttf",
                    "/System/Library/Fonts/Supplemental/Courier New.ttf",
                ]
            )

        # Panda3D bundled fallbacks.
        candidates.extend(["cmtt12.egg", "cmss12.egg", "cmr12.egg"])

        for c in candidates:
            # If it's a filesystem path, skip missing.
            if c.startswith("/") and not Path(c).exists():
                continue
            if _try_font(c):
                break

    def _ensure_background_card(self) -> None:
        # Procedural background pattern (subtle), kept as a single card in render2d.
        if hasattr(self, "_bg_card"):
            return

        cm = CardMaker("ui-kit-bg")
        cm.setFrame(-1, 1, -1, 1)
        card = self.base.render2d.attachNewNode(cm.generate())
        card.setBin("background", 0)
        card.setDepthWrite(False)
        card.setDepthTest(False)
        card.setTransparency(True)

        # Build a tiny dither/scanline-ish texture.
        size = 96
        img = PNMImage(size, size, 4)
        for y in range(size):
            scan = 0.014 if (y % 2 == 0) else 0.0
            for x in range(size):
                # cheap ordered-dither style speckle
                speck = 0.008 if ((x * 3 + y * 5) % 17 == 0) else 0.0
                v = min(1.0, scan + speck)
                img.setXelA(x, y, v, v, v, 0.08 if v > 0 else 0.0)

        tex = Texture("ui-kit-bg-tex")
        tex.load(img)
        tex.setWrapU(SamplerState.WM_repeat)
        tex.setWrapV(SamplerState.WM_repeat)
        card.setTexture(tex, 1)
        card.setTexScale(TextureStage.getDefault(), 10.0, 10.0)
        card.setColorScale(1, 1, 1, 1)

        self._bg_card = card

    def create_window(self, *, title: str, x: float, y: float, w: float, h: float) -> Window:
        win = Window(
            aspect2d=self.base.aspect2d,
            theme=self.theme,
            title=title,
            x=x,
            y=y,
            w=w,
            h=h,
        )
        return win
