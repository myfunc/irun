from __future__ import annotations

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame, DirectLabel
from direct.showbase import ShowBaseGlobal
from panda3d.core import TextNode


class RaceUiFeedback:
    def __init__(self, *, aspect2d) -> None:
        aspect_ratio = 16.0 / 9.0
        if getattr(ShowBaseGlobal, "base", None) is not None:
            try:
                aspect_ratio = float(ShowBaseGlobal.base.getAspectRatio())
            except Exception:
                pass
        self._flash = DirectFrame(
            parent=aspect2d,
            frameColor=(0.0, 0.0, 0.0, 0.0),
            frameSize=(-aspect_ratio, aspect_ratio, -1.0, 1.0),
            relief=DGG.FLAT,
        )
        self._flash.hide()
        self._flash_until = 0.0
        self._flash_start = 0.0
        self._flash_color = (0.0, 0.0, 0.0, 0.0)

        self._notice = DirectLabel(
            parent=aspect2d,
            text="",
            text_scale=0.062,
            text_align=TextNode.ACenter,
            text_fg=(1.0, 1.0, 1.0, 0.0),
            frameColor=(0.0, 0.0, 0.0, 0.0),
            pos=(0.0, 0.0, 0.78),
        )
        self._notice.hide()
        self._notice_until = 0.0

    def destroy(self) -> None:
        try:
            self._flash.destroy()
        except Exception:
            pass
        try:
            self._notice.destroy()
        except Exception:
            pass

    def flash(self, *, color: tuple[float, float, float, float], now: float, duration: float = 0.18) -> None:
        dur = max(0.05, float(duration))
        self._flash_start = float(now)
        self._flash_until = float(now) + dur
        self._flash_color = (
            float(color[0]),
            float(color[1]),
            float(color[2]),
            max(0.0, min(1.0, float(color[3]))),
        )
        self._flash.show()

    def notice(
        self,
        *,
        text: str,
        color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 0.96),
        now: float,
        duration: float = 1.3,
    ) -> None:
        self._notice["text"] = str(text)
        self._notice["text_fg"] = (
            float(color[0]),
            float(color[1]),
            float(color[2]),
            max(0.0, min(1.0, float(color[3]))),
        )
        self._notice_until = float(now) + max(0.2, float(duration))
        self._notice.show()

    def tick(self, *, now: float) -> None:
        now_f = float(now)
        if now_f >= float(self._flash_until):
            self._flash.hide()
        else:
            span = max(1e-6, float(self._flash_until) - float(self._flash_start))
            t = max(0.0, min(1.0, (now_f - float(self._flash_start)) / span))
            alpha = float(self._flash_color[3]) * (1.0 - t)
            self._flash["frameColor"] = (
                float(self._flash_color[0]),
                float(self._flash_color[1]),
                float(self._flash_color[2]),
                float(alpha),
            )
            self._flash.show()

        if now_f >= float(self._notice_until):
            self._notice.hide()

