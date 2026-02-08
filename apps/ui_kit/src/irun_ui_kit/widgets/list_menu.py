from __future__ import annotations

from dataclasses import dataclass

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame, DirectLabel
from direct.showbase import ShowBaseGlobal
from panda3d.core import TextNode

from irun_ui_kit.theme import Theme
from irun_ui_kit.widgets.panel import Panel
from irun_ui_kit.widgets.text_input import TextInput


@dataclass(frozen=True)
class ListMenuItem:
    label: str
    enabled: bool = True


class ListMenu:
    """
    Keyboard-friendly list menu (title + hint + rows + status) with optional search.

    This is a generic replacement for game-specific "retro menu" screens.
    """

    def __init__(self, *, aspect2d, theme: Theme, title: str, hint: str) -> None:
        self._aspect2d = aspect2d
        self._theme = theme

        aspect_ratio = 16.0 / 9.0
        if getattr(ShowBaseGlobal, "base", None) is not None:
            try:
                aspect_ratio = float(ShowBaseGlobal.base.getAspectRatio())
            except Exception:
                pass

        # Centered panel (avoid full-width "spreadsheet" look).
        w = min((aspect_ratio * 2.0) - 0.18, 2.55)
        h = min(1.80, 2.0 - 0.14)
        x = -w / 2.0
        y = -h / 2.0

        self._panel = Panel.build(parent=aspect2d, theme=theme, x=x, y=y, w=w, h=h, title=title, header=True)
        self._root = self._panel.node
        self._w = float(w)
        self._h = float(h)

        header_total_h = theme.header_h + (theme.outline_w * 2)
        self._content = DirectFrame(
            parent=self._panel.content,
            frameColor=(0, 0, 0, 0),
            relief=DGG.FLAT,
            frameSize=(theme.pad, w - theme.pad, theme.pad, h - header_total_h),
        )

        self._content_w = float(w - theme.pad * 2)
        content_h = float((h - header_total_h) - theme.pad * 2)
        self._content_h = content_h
        self._hint = DirectLabel(
            parent=self._content,
            text=hint,
            text_scale=theme.small_scale,
            text_align=TextNode.ALeft,
            text_fg=theme.text_muted,
            frameColor=(0, 0, 0, 0),
            pos=(0.0, 0, content_h - theme.small_scale * 1.30),
        )
        self._status = DirectLabel(
            parent=self._content,
            text="",
            text_scale=theme.small_scale,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(0.0, 0, 0.0),
        )

        self._search_label: DirectLabel | None = None
        self._search_input: TextInput | None = None
        self._search_last_text: str = ""

        self._sel_bg: DirectFrame | None = None

        # Rows.
        self._items: list[ListMenuItem] = []
        self._selected: int = 0

        # Reserve top for hint/search and bottom for status.
        rows_top = content_h - theme.small_scale * 2.40
        rows_bottom = theme.small_scale * 1.60
        rows_h = max(0.2, rows_top - rows_bottom)
        row_h = theme.label_scale * 1.50
        self._visible_rows = max(10, int(rows_h / max(0.01, row_h)))
        self._row_h = float(row_h)
        self._rows_top = float(rows_top)

        # Selection highlight (a soft bar behind the selected row).
        self._sel_bg = DirectFrame(
            parent=self._content,
            frameColor=(theme.panel2[0], theme.panel2[1], theme.panel2[2], 0.70),
            relief=DGG.FLAT,
            frameSize=(-0.01, self._content_w + 0.01, -row_h * 0.55, row_h * 0.55),
            pos=(0.0, 0.0, rows_top),
        )

        self._row_nodes: list[DirectLabel] = []
        for i in range(self._visible_rows):
            yy = rows_top - i * row_h
            self._row_nodes.append(
                DirectLabel(
                    parent=self._content,
                    text="",
                    text_scale=theme.label_scale,
                    text_align=TextNode.ALeft,
                    text_fg=theme.text_muted,
                    frameColor=(0, 0, 0, 0),
                    pos=(0.0, 0, yy),
                )
            )

        self._loader_base_status: str | None = None
        self._loader_started_at: float = 0.0

    def destroy(self) -> None:
        self.hide_search()
        try:
            if self._sel_bg is not None:
                self._sel_bg.destroy()
            for r in self._row_nodes:
                r.destroy()
        except Exception:
            pass
        self._row_nodes.clear()
        try:
            self._root.destroy()
        except Exception:
            pass

    def set_title(self, title: str) -> None:
        try:
            if getattr(self._panel, "title", None) is not None:
                self._panel.title["text"] = str(title).upper()
        except Exception:
            pass

    def set_hint(self, hint: str) -> None:
        self._hint["text"] = str(hint)

    def set_items(self, items: list[ListMenuItem], *, selected: int = 0) -> None:
        self._items = list(items or [])
        self._selected = 0 if not self._items else max(0, min(len(self._items) - 1, int(selected)))
        self._redraw()

    def move(self, delta: int) -> None:
        if not self._items:
            return
        self._selected = max(0, min(len(self._items) - 1, self._selected + int(delta)))
        self._redraw()

    def selected_index(self) -> int | None:
        if not self._items:
            return None
        return self._selected

    def set_status(self, text: str) -> None:
        self._loader_base_status = None
        self._status["text"] = str(text)

    def set_loading_status(self, text: str, *, started_at: float) -> None:
        self._loader_base_status = str(text)
        self._loader_started_at = float(started_at)
        self._status["text"] = str(text)

    def tick(self, now: float) -> None:
        if self._loader_base_status:
            t = max(0.0, float(now) - self._loader_started_at)
            dots = int(t * 2.5) % 4
            self._status["text"] = self._loader_base_status + ("." * dots)

        if self._search_input is not None:
            try:
                text = str(self._search_input.entry.get())
            except Exception:
                text = ""
            if text != self._search_last_text:
                self._search_last_text = text
                self._apply_search(text)

    def is_search_active(self) -> bool:
        return self._search_input is not None

    def toggle_search(self) -> None:
        if self._search_input is not None:
            self.hide_search()
            return

        self._search_last_text = ""
        search_y = self._content_h - self._theme.small_scale * 2.70
        self._search_label = DirectLabel(
            parent=self._content,
            text="Search:",
            text_scale=self._theme.small_scale,
            text_align=TextNode.ALeft,
            text_fg=self._theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(0.0, 0, search_y),
        )
        label_w = 0.34
        input_w = min(1.35, max(0.70, self._content_w - label_w - self._theme.gap))
        self._search_input = TextInput.build(
            parent=self._content,
            theme=self._theme,
            x=label_w + self._theme.gap + input_w / 2.0,
            y=search_y - self._theme.small_scale * 0.25,
            w=input_w,
            h=0.10,
            initial="",
            on_submit=lambda _text: self.hide_search(),
            frame_color=self._theme.panel2,
            text_fg=self._theme.text,
        )
        try:
            self._search_input.entry["focus"] = 1
        except Exception:
            pass

    def hide_search(self) -> None:
        try:
            if self._search_input is not None:
                self._search_input.frame.destroy()
        except Exception:
            pass
        try:
            if self._search_label is not None:
                self._search_label.destroy()
        except Exception:
            pass
        self._search_input = None
        self._search_label = None
        self._search_last_text = ""

    def _apply_search(self, text: str) -> None:
        q = (text or "").strip().casefold()
        if not q or not self._items:
            return

        best: int | None = None
        for i, it in enumerate(self._items):
            if it.label.casefold().startswith(q):
                best = i
                break
        if best is None:
            for i, it in enumerate(self._items):
                if q in it.label.casefold():
                    best = i
                    break
        if best is None:
            return
        if best != self._selected:
            self._selected = best
            self._redraw()

    def _redraw(self) -> None:
        if not self._items:
            if self._sel_bg is not None:
                self._sel_bg.hide()
            for r in self._row_nodes:
                r["text"] = ""
            self._status["text"] = "No entries."
            return

        if self._sel_bg is not None:
            self._sel_bg.show()
        half = self._visible_rows // 2
        start = max(0, min(len(self._items) - self._visible_rows, self._selected - half))
        window = self._items[start : start + self._visible_rows]

        for i, r in enumerate(self._row_nodes):
            if i >= len(window):
                r["text"] = ""
                continue
            idx = start + i
            item = window[i]
            prefix = "> " if idx == self._selected else "  "
            label = item.label
            if not item.enabled:
                label = f"{label} [missing]"
            r["text"] = prefix + label

            if idx == self._selected:
                r["text_fg"] = self._theme.text if item.enabled else self._theme.text_muted
                # Move selection highlight behind this row.
                rpos = r.getPos()
                if self._sel_bg is not None:
                    self._sel_bg.setPos(0.0, 0.0, float(rpos.z))
            else:
                r["text_fg"] = self._theme.text_muted if item.enabled else (
                    self._theme.text_muted[0] * 0.75,
                    self._theme.text_muted[1] * 0.75,
                    self._theme.text_muted[2] * 0.75,
                    self._theme.text_muted[3],
                )
