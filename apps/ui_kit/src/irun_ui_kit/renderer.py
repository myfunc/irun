from __future__ import annotations

from dataclasses import dataclass

from direct.showbase.ShowBase import ShowBase
from panda3d.core import CardMaker, Texture, TextureStage, PNMImage, SamplerState

from irun_ui_kit.theme import Theme
from irun_ui_kit.widgets.window import Window


@dataclass
class UIRenderer:
    base: ShowBase
    theme: Theme

    def set_background(self) -> None:
        self.base.setBackgroundColor(*self.theme.bg)
        self._ensure_background_card()

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
            scan = 0.018 if (y % 2 == 0) else 0.0
            for x in range(size):
                # cheap ordered-dither style speckle
                speck = 0.010 if ((x * 3 + y * 5) % 17 == 0) else 0.0
                v = min(1.0, scan + speck)
                img.setXelA(x, y, v, v, v, 0.12 if v > 0 else 0.0)

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
