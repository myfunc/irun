from __future__ import annotations

from dataclasses import dataclass
import subprocess
import sys

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectEntry
from direct.showbase import ShowBaseGlobal
from panda3d.core import TextNode

from irun_ui_kit.theme import Theme, Color


@dataclass
class TextInput:
    # We keep both: a frame button (for consistent sizing) and the entry itself.
    frame: DirectButton
    entry: DirectEntry

    def _has_focus(self) -> bool:
        if bool(getattr(self, "_focused", False)):
            return True
        try:
            return bool(self.entry["focus"])
        except Exception:
            pass
        try:
            return bool(self.entry.guiItem.getFocus())
        except Exception:
            return False

    def _clipboard_get(self) -> str | None:
        if sys.platform != "darwin":
            return None
        try:
            p = subprocess.run(["pbpaste"], check=False, capture_output=True, text=True)
            return p.stdout
        except Exception:
            return None

    def _clipboard_set(self, text: str) -> None:
        if sys.platform != "darwin":
            return
        try:
            subprocess.run(["pbcopy"], input=text, check=False, text=True)
        except Exception:
            return

    def _set_text(self, text: str) -> None:
        try:
            self.entry.enterText(text)
        except Exception:
            self.entry["initialText"] = text

    def _insert_text(self, insert: str) -> None:
        try:
            cur = int(self.entry.getCursorPosition())
        except Exception:
            cur = len(self.entry.get())
        s = str(self.entry.get())
        cur = max(0, min(len(s), cur))
        out = s[:cur] + insert + s[cur:]
        self._set_text(out)
        try:
            self.entry.setCursorPosition(cur + len(insert))
        except Exception:
            pass

    @staticmethod
    def build(
        *,
        parent,
        theme: Theme,
        x: float,
        y: float,
        w: float,
        h: float,
        initial: str,
        on_submit,
        frame_color: Color | None = None,
        text_fg: Color | None = None,
    ) -> "TextInput":
        # Frame provides predictable box sizing and keeps the entry visually anchored.
        frame = DirectButton(
            parent=parent,
            text="",
            frameColor=frame_color or theme.panel2,
            relief=DGG.FLAT,
            frameSize=(-w / 2, w / 2, -h / 2, h / 2),
            pos=(x, 0, y),
            command=lambda: None,
        )
        entry = DirectEntry(
            parent=frame,
            initialText=initial,
            numLines=1,
            focus=0,
            width=22,  # approx; refined in runtime later
            text_scale=theme.small_scale,
            text_align=TextNode.ALeft,
            text_fg=text_fg or theme.text,
            frameColor=(0, 0, 0, 0),
            relief=DGG.FLAT,
            pos=(-w / 2 + (theme.pad * 0.55), 0, -theme.small_scale * 0.40),
            command=on_submit,
            suppressMouse=False,
        )
        out = TextInput(frame=frame, entry=entry)
        out._focused = False  # set via focus in/out commands below

        def _focus_in() -> None:
            out._focused = True

        def _focus_out() -> None:
            out._focused = False

        # Track focus explicitly; this is more reliable than polling.
        try:
            entry["focusInCommand"] = _focus_in
            entry["focusOutCommand"] = _focus_out
        except Exception:
            pass

        # Text editing micro-features (best-effort, cross-platform):
        # - Clear all: Ctrl+U, Ctrl+Backspace, Cmd+Backspace
        # - Copy/Paste/Cut: Ctrl/Cmd + C/V/X (macOS uses pbcopy/pbpaste)
        # - Select all: Ctrl/Cmd + A (moves cursor to end; full selection is not exposed in PGEntry)
        base = getattr(ShowBaseGlobal, "base", None)

        def _clear_all() -> None:
            if out._has_focus():
                out._set_text("")

        def _cursor_end() -> None:
            if out._has_focus():
                try:
                    entry.setCursorPosition(-1)
                except Exception:
                    pass

        def _copy() -> None:
            if out._has_focus():
                out._clipboard_set(str(entry.get()))

        def _cut() -> None:
            if out._has_focus():
                out._clipboard_set(str(entry.get()))
                out._set_text("")

        def _paste() -> None:
            if not out._has_focus():
                return
            clip = out._clipboard_get()
            if not clip:
                return
            # Keep it single-line.
            clip = clip.replace("\r\n", "\n").replace("\r", "\n").split("\n", 1)[0]
            out._insert_text(clip)

        # Key names vary a bit across platforms/builds, so we listen to multiple.
        keymap: dict[str, callable] = {
            "control-u": _clear_all,
            "control-backspace": _clear_all,
            "meta-backspace": _clear_all,
            "command-backspace": _clear_all,
            "control-a": _cursor_end,
            "meta-a": _cursor_end,
            "command-a": _cursor_end,
            "control-c": _copy,
            "meta-c": _copy,
            "command-c": _copy,
            "control-x": _cut,
            "meta-x": _cut,
            "command-x": _cut,
            "control-v": _paste,
            "meta-v": _paste,
            "command-v": _paste,
        }

        if base is not None:
            for k, fn in keymap.items():
                try:
                    base.accept(k, fn)
                except Exception:
                    pass
        else:
            for k, fn in keymap.items():
                try:
                    entry.accept(k, fn)
                except Exception:
                    pass

        # Allow clicking the frame to focus the entry.
        frame["command"] = lambda: entry.__setitem__("focus", 1)

        # Make the cursor a bit more obvious in darker themes.
        try:
            entry.guiItem.setCursorColor(1, 1, 1, 0.85)
        except Exception:
            pass

        return out
