from __future__ import annotations

from dataclasses import dataclass

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame

from irun_ui_kit.theme import Theme
from irun_ui_kit.widgets.button import Button


@dataclass
class Dropdown:
    """
    Small dropdown/select widget.

    - Renders a button showing the active item.
    - Clicking toggles a popup list of items (fixed visible rows, scrollable via wheel).
    """

    root: DirectFrame
    button: Button
    popup: DirectFrame
    rows: list[Button]
    theme: Theme
    w: float
    row_h: float
    visible: int
    open: bool
    items: list[str]
    active: str
    offset: int
    prefix: str
    on_select: callable

    @staticmethod
    def build(
        *,
        parent,
        theme: Theme,
        x: float,
        y: float,
        w: float,
        h: float,
        visible: int = 6,
        prefix: str = "",
        on_select=None,
    ) -> "Dropdown":
        visible = int(max(1, visible))

        root = DirectFrame(
            parent=parent,
            frameColor=(0, 0, 0, 0),
            relief=DGG.FLAT,
            frameSize=(0.0, w, 0.0, h),
            pos=(x, 0, y),
        )

        # Main button is centered; Button expects center-pos.
        btn = Button.build(
            parent=root,
            theme=theme,
            x=w / 2.0,
            y=h / 2.0,
            w=w,
            h=h,
            label="(none)",
            on_click=lambda: None,
        )

        # Popup list opens downward (smaller y).
        row_h = max(h, theme.header_h * 0.85)
        popup_h = row_h * visible + theme.outline_w * 2

        popup_outline = DirectFrame(
            parent=root,
            frameColor=theme.outline,
            relief=DGG.FLAT,
            frameSize=(0.0, w, -popup_h, 0.0),
            pos=(0.0, 0.0, -theme.gap),
        )
        # Ensure the popup draws above other UI (e.g. scrolled frames) and receives clicks.
        popup_outline.setBin("gui-popup", 60)
        popup_outline.setDepthTest(False)
        popup_outline.setDepthWrite(False)
        popup = DirectFrame(
            parent=popup_outline,
            frameColor=theme.panel,
            relief=DGG.FLAT,
            frameSize=(theme.outline_w, w - theme.outline_w, -popup_h + theme.outline_w, -theme.outline_w),
        )
        popup.setBin("gui-popup", 61)
        popup.setDepthTest(False)
        popup.setDepthWrite(False)

        # Prevent popup from intercepting clicks when hidden.
        popup_outline.hide()

        rows: list[Button] = []
        for i in range(visible):
            cy = -theme.outline_w - (row_h * i) - (row_h / 2.0)
            b = Button.build(
                parent=popup,
                theme=theme,
                x=w / 2.0,
                y=cy,
                w=w - theme.outline_w * 2,
                h=row_h,
                label="-",
                on_click=lambda: None,
            )
            # Row buttons must be above everything else to be clickable.
            b.node.setBin("gui-popup", 62)
            b.node.setDepthTest(False)
            b.node.setDepthWrite(False)
            rows.append(b)

        out = Dropdown(
            root=root,
            button=btn,
            popup=popup_outline,
            rows=rows,
            theme=theme,
            w=float(w),
            row_h=float(row_h),
            visible=int(visible),
            open=False,
            items=[],
            active="",
            offset=0,
            prefix=str(prefix or ""),
            on_select=on_select or (lambda _name: None),
        )

        def _toggle() -> None:
            out.set_open(not out.open)

        out.button.node["command"] = _toggle
        out.root.bind("wheel_up", lambda _evt: out.scroll_wheel(+1))
        out.root.bind("wheel_down", lambda _evt: out.scroll_wheel(-1))
        return out

    def set_items(self, items: list[str], *, active: str) -> None:
        self.items = [str(x) for x in (items or [])]
        self.active = str(active or "")
        if self.active and self.active in self.items:
            idx = self.items.index(self.active)
            if idx < self.offset:
                self.offset = idx
            if idx >= self.offset + self.visible:
                self.offset = max(0, idx - self.visible + 1)
        self.offset = max(0, min(self.offset, max(0, len(self.items) - self.visible)))
        self._refresh()

    def set_open(self, open_: bool) -> None:
        self.open = bool(open_)
        if self.open and self.items:
            self.popup.show()
        else:
            self.popup.hide()

    def scroll_wheel(self, direction: int) -> None:
        if not self.open:
            return
        if len(self.items) <= self.visible:
            return
        d = 1 if int(direction) > 0 else -1
        self.offset -= d
        self.offset = max(0, min(max(0, len(self.items) - self.visible), self.offset))
        self._refresh()

    def _refresh(self) -> None:
        shown = self.active if self.active else "(none)"
        if self.prefix:
            header = f"{self.prefix}: {shown}"
        else:
            header = shown
        self.button.node["text"] = (header,) * 4

        total = len(self.items)
        if total <= 0:
            for r in self.rows:
                r.node.hide()
            self.set_open(False)
            return

        for i, r in enumerate(self.rows):
            idx = self.offset + i
            if idx >= total:
                r.node.hide()
                continue
            name = self.items[idx]
            prefix = "> " if name == self.active else "  "
            label = prefix + name
            r.node["text"] = (label, label, label, label)
            r.node.show()

            def _mk(ii: int) -> callable:
                return lambda: self._select(ii)

            r.node["command"] = _mk(idx)

    def _select(self, idx: int) -> None:
        if idx < 0 or idx >= len(self.items):
            return
        self.active = self.items[idx]
        self.on_select(self.active)
        self.set_open(False)
        self._refresh()

    def destroy(self) -> None:
        try:
            self.root.destroy()
        except Exception:
            pass
