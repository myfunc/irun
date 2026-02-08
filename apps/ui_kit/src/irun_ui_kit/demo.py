from __future__ import annotations

import argparse
from pathlib import Path

from direct.showbase.ShowBase import ShowBase
from panda3d.core import loadPrcFileData

from irun_ui_kit.renderer import UIRenderer
from irun_ui_kit.theme import Theme
from irun_ui_kit.widgets.button import Button
from irun_ui_kit.widgets.text_input import TextInput


class DemoApp(ShowBase):
    def __init__(self, *, smoke_screenshot: str | None) -> None:
        loadPrcFileData("", "win-size 1280 720")
        loadPrcFileData("", "window-title IRUN UI Kit Demo")
        loadPrcFileData("", "sync-video 1")
        loadPrcFileData("", "show-frame-rate-meter 0")
        super().__init__()
        self.disableMouse()

        theme = Theme()
        self.ui = UIRenderer(base=self, theme=theme)
        self.ui.set_background()

        aspect = float(self.getAspectRatio())
        win = self.ui.create_window(title="UI KIT DEMO", x=-aspect + 0.10, y=-0.80, w=1.30, h=1.70)

        # Controls inside the window.
        Button.build(
            parent=win.content,
            theme=theme,
            x=0.65,
            y=1.30,
            w=1.18,
            h=0.12,
            label="Primary Button",
            frame_color=theme.panel2,
            on_click=lambda: None,
        )
        Button.build(
            parent=win.content,
            theme=theme,
            x=0.65,
            y=1.12,
            w=1.18,
            h=0.12,
            label="Danger Button",
            frame_color=theme.danger,
            on_click=lambda: None,
        )
        TextInput.build(
            parent=win.content,
            theme=theme,
            x=0.65,
            y=0.92,
            w=1.18,
            h=0.11,
            initial="Search...",
            on_submit=lambda text: None,
        )

        self.accept("escape", self.userExit)
        self.accept("q", self.userExit)

        if smoke_screenshot:
            out = Path(smoke_screenshot).expanduser()
            self.taskMgr.doMethodLater(0.2, self._smoke, "smoke", extraArgs=[out], appendTask=True)

    def _smoke(self, out: Path, task):
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        try:
            self.graphicsEngine.renderFrame()
            self.graphicsEngine.renderFrame()
            self.win.saveScreenshot(str(out))
        finally:
            self.userExit()
        return task.done


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke-screenshot", default=None)
    args = ap.parse_args()
    DemoApp(smoke_screenshot=args.smoke_screenshot).run()


if __name__ == "__main__":
    main()

