from __future__ import annotations

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame, DirectLabel
from direct.showbase import ShowBaseGlobal
from panda3d.core import TextNode

from ivan.common.error_log import ErrorLog
from irun_ui_kit.theme import Theme


class ErrorConsoleUI:
    """
    Bottom-screen error console with a small feed.

    Behavior:
    - hidden when there are no errors
    - collapsed view shows the latest error (one-ish line)
    - expanded view (toggle) shows the last few errors as a feed
    """

    def __init__(self, *, aspect2d, theme: Theme, error_log: ErrorLog) -> None:
        self._log = error_log
        self._theme = theme
        # 0=hidden, 1=collapsed, 2=expanded
        self._mode = 0

        aspect_ratio = 16.0 / 9.0
        if getattr(ShowBaseGlobal, "base", None) is not None:
            try:
                aspect_ratio = float(ShowBaseGlobal.base.getAspectRatio())
            except Exception:
                pass

        pad = 0.06
        w = min(1.80, (aspect_ratio * 2.0) - (pad * 2.0))
        h = 0.13
        x = -aspect_ratio + pad
        # Sit above the bottom status bar.
        y = -0.82

        self._root = DirectFrame(
            parent=aspect2d,
            frameColor=theme.outline,
            relief=DGG.FLAT,
            frameSize=(0.0, w, 0.0, h),
            pos=(x, 0.0, y),
        )
        self._root["state"] = DGG.DISABLED
        DirectFrame(
            parent=self._root,
            frameColor=(theme.panel2[0], theme.panel2[1], theme.panel2[2], 0.90),
            relief=DGG.FLAT,
            frameSize=(theme.outline_w, w - theme.outline_w, theme.outline_w, h - theme.outline_w),
        )["state"] = DGG.DISABLED

        self._label = DirectLabel(
            parent=self._root,
            text="",
            text_scale=0.034,
            text_align=TextNode.ALeft,
            text_fg=theme.danger,
            frameColor=(0, 0, 0, 0),
            pos=(theme.outline_w + theme.pad * 0.50, 0.0, h * 0.35),
            text_wordwrap=86,
        )
        self._root.hide()

    def destroy(self) -> None:
        try:
            self._root.destroy()
        except Exception:
            pass

    def toggle(self) -> None:
        # Cycle: hidden -> collapsed -> expanded -> hidden
        self._mode = (self._mode + 1) % 3
        self.refresh(auto_reveal=False)

    def hide(self) -> None:
        self._mode = 0
        self.refresh(auto_reveal=False)

    def refresh(self, *, auto_reveal: bool) -> None:
        items = self._log.items()
        if not items:
            self._label["text"] = ""
            self._root.hide()
            return

        if auto_reveal and self._mode == 0:
            self._mode = 1

        if self._mode == 0:
            self._label["text"] = ""
            self._root.hide()
            return

        if self._mode == 2:
            tail = items[-6:]
            lines = ["Errors (F3 to collapse):"]
            for it in tail:
                lines.append(f"- {it.summary_line()}")
            self._label["text"] = "\n".join(lines)
        else:
            last = items[-1]
            self._label["text"] = f"ERROR: {last.summary_line()}  [F3 more]"
        self._root.show()
