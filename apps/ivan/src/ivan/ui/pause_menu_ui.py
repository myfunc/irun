from __future__ import annotations

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, DirectLabel
from direct.showbase import ShowBaseGlobal
from panda3d.core import TextNode


class PauseMenuUI:
    """
    Lightweight in-game system panel shown alongside the debug menu when the cursor is unlocked.
    """

    def __init__(self, *, aspect2d, on_resume, on_back_to_menu, on_quit) -> None:
        aspect_ratio = 16.0 / 9.0
        if getattr(ShowBaseGlobal, "base", None) is not None:
            aspect_ratio = float(ShowBaseGlobal.base.getAspectRatio())

        panel_top = 0.95
        panel_bottom = -0.25
        panel_width = 0.62
        right = aspect_ratio - 0.04
        left = right - panel_width

        self.root = DirectFrame(
            parent=aspect2d,
            frameColor=(0.06, 0.06, 0.06, 0.88),
            frameSize=(left, right, panel_bottom, panel_top),
            relief=DGG.FLAT,
            pos=(0, 0, 0),
        )

        DirectLabel(
            parent=self.root,
            text="System",
            text_scale=0.060,
            text_align=TextNode.ALeft,
            text_fg=(1.0, 0.92, 0.65, 1.0),
            frameColor=(0, 0, 0, 0),
            pos=(left + 0.06, 0, panel_top - 0.12),
        )

        hint = "Esc: resume"
        DirectLabel(
            parent=self.root,
            text=hint,
            text_scale=0.040,
            text_align=TextNode.ALeft,
            text_fg=(0.85, 0.85, 0.85, 1.0),
            frameColor=(0, 0, 0, 0),
            pos=(left + 0.06, 0, panel_top - 0.20),
        )

        btn_w = (right - left) - 0.12
        btn_x = left + 0.06 + (btn_w / 2.0)
        btn_scale = 0.065
        btn_frame = (-btn_w / 2.0, btn_w / 2.0, -0.58, 0.58)

        def _btn(*, label: str, y: float, command):
            return DirectButton(
                parent=self.root,
                text=(label, label, label, label),
                text_scale=0.60,
                text_fg=(0.95, 0.95, 0.95, 1),
                frameColor=(0.18, 0.18, 0.18, 0.95),
                relief=DGG.FLAT,
                command=command,
                scale=btn_scale,
                frameSize=btn_frame,
                pos=(btn_x, 0, y),
            )

        _btn(label="Resume", y=panel_top - 0.38, command=on_resume)
        _btn(label="Back to Menu", y=panel_top - 0.55, command=on_back_to_menu)
        _btn(label="Quit", y=panel_top - 0.72, command=on_quit)

        self.root.hide()

    def show(self) -> None:
        self.root.show()

    def hide(self) -> None:
        self.root.hide()

    def destroy(self) -> None:
        self.root.destroy()

