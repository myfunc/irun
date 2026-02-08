from __future__ import annotations

from dataclasses import dataclass

from direct.showbase.ShowBase import ShowBase

from irun_ui_kit.theme import Theme
from irun_ui_kit.widgets.window import Window


@dataclass
class UIRenderer:
    base: ShowBase
    theme: Theme

    def set_background(self) -> None:
        self.base.setBackgroundColor(*self.theme.bg)

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

