from __future__ import annotations

from direct.gui.OnscreenText import OnscreenText
from panda3d.core import TextNode

from ivan.common.error_log import ErrorLog


class ErrorConsoleUI:
    """
    Bottom-screen error console with a small feed.

    Behavior:
    - hidden when there are no errors
    - collapsed view shows the latest error (one-ish line)
    - expanded view (toggle) shows the last few errors as a feed
    """

    def __init__(self, *, aspect2d, error_log: ErrorLog) -> None:
        self._log = error_log
        # 0=hidden, 1=collapsed, 2=expanded
        self._mode = 0

        # Place slightly above the gameplay status line.
        self._text = OnscreenText(
            text="",
            parent=aspect2d,
            align=TextNode.ALeft,
            pos=(-1.30, -0.78),
            scale=0.038,
            fg=(1.0, 0.55, 0.55, 0.98),
            shadow=(0, 0, 0, 1),
            mayChange=True,
        )
        self._text.hide()

    def destroy(self) -> None:
        self._text.removeNode()

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
            self._text.setText("")
            self._text.hide()
            return

        if auto_reveal and self._mode == 0:
            self._mode = 1

        if self._mode == 0:
            self._text.setText("")
            self._text.hide()
            return

        if self._mode == 2:
            tail = items[-6:]
            lines = ["Errors (F3 to collapse):"]
            for it in tail:
                lines.append(f"- {it.summary_line()}")
            self._text.setText("\n".join(lines))
        else:
            last = items[-1]
            self._text.setText(f"ERROR: {last.summary_line()}  [F3 more]")
        self._text.show()
