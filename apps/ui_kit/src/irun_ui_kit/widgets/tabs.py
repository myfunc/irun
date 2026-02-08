from __future__ import annotations

from dataclasses import dataclass

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame
from panda3d.core import NodePath, TextNode

from irun_ui_kit.theme import Theme, Color


@dataclass
class Tabs:
    """
    Simple tab bar + page container.

    - Creates one tab button per label.
    - Each tab has a page NodePath; only the active page is shown.
    - Intended for hiding/showing groups of controls in a panel.
    """

    root: NodePath
    bar: DirectFrame
    pages_root: DirectFrame
    buttons: list[DirectButton]
    accents: list[DirectFrame]
    pages: list[NodePath]
    active: int

    @staticmethod
    def _fit_label(label: str, *, tab_w: float, scale: float, pad: float) -> str:
        """
        Best-effort label fitting without font metrics.

        We keep it ASCII-only (use "..." not ellipsis).
        """

        # Approx: for typical bitmap-ish UI fonts, average glyph width ~0.55-0.65 of height.
        est_glyph_w = scale * 0.60
        avail = max(0.01, tab_w - (pad * 2))
        max_chars = int(avail / max(0.001, est_glyph_w))
        max_chars = max(4, max_chars)
        if len(label) <= max_chars:
            return label
        if max_chars <= 3:
            return label[:max_chars]
        return label[: max_chars - 3] + "..."

    @staticmethod
    def build(
        *,
        parent,
        theme: Theme,
        x: float,
        y: float,
        w: float,
        tab_h: float,
        page_h: float,
        labels: list[str],
        active: int = 0,
        active_color: Color | None = None,
        inactive_color: Color | None = None,
        on_change=None,
    ) -> "Tabs":
        if not labels:
            raise ValueError("Tabs requires at least one label.")
        if not (0 <= active < len(labels)):
            raise IndexError("Tabs active index out of range.")

        root = DirectFrame(
            parent=parent,
            frameColor=(0, 0, 0, 0),
            relief=DGG.FLAT,
            frameSize=(0.0, w, 0.0, tab_h + page_h),
            pos=(x, 0, y),
        )
        bar = DirectFrame(
            parent=root,
            frameColor=(0, 0, 0, 0),
            relief=DGG.FLAT,
            frameSize=(0.0, w, 0.0, tab_h),
            pos=(0, 0, page_h),
        )
        pages_root = DirectFrame(
            parent=root,
            frameColor=(0, 0, 0, 0),
            relief=DGG.FLAT,
            frameSize=(0.0, w, 0.0, page_h),
        )

        ac = active_color or theme.panel2
        ic = inactive_color or theme.panel
        # CLI-style: keep text readable, use accent only as a thin underline.
        at = theme.text
        it = theme.text_muted

        btns: list[DirectButton] = []
        accents: list[DirectFrame] = []
        pages: list[NodePath] = []
        tab_w = w / float(len(labels))

        # Build buttons left-to-right. Position is bottom-left anchored.
        for i, label in enumerate(labels):
            bx = i * tab_w
            label_caps = str(label).upper()
            disp = Tabs._fit_label(label_caps, tab_w=tab_w, scale=theme.small_scale, pad=theme.pad * 0.40)
            base_color = ac if i == active else ic
            frame_colors = (
                base_color,
                (base_color[0] * 0.82, base_color[1] * 0.82, base_color[2] * 0.82, base_color[3]),
                (min(1.0, base_color[0] * 1.06), min(1.0, base_color[1] * 1.06), min(1.0, base_color[2] * 1.06), base_color[3]),
                (base_color[0] * 0.60, base_color[1] * 0.60, base_color[2] * 0.60, base_color[3]),
            )
            b = DirectButton(
                parent=bar,
                text=(disp, disp, disp, disp),
                text_scale=theme.small_scale,
                text_align=TextNode.ACenter,
                # DirectGUI baseline tends to sit low; keep a bit higher to avoid clipping.
                text_pos=(0.0, -theme.small_scale * 0.10),
                text_fg=at if i == active else it,
                frameColor=frame_colors,
                relief=DGG.FLAT,
                frameSize=(-tab_w / 2, tab_w / 2, -tab_h / 2, tab_h / 2),
                pos=(bx + (tab_w / 2), 0, tab_h / 2),
                command=lambda ii=i: None,
                pressEffect=0,
            )
            btns.append(b)

            acc = DirectFrame(
                parent=bar,
                frameColor=theme.header,
                relief=DGG.FLAT,
                frameSize=(0.0, tab_w, 0.0, theme.accent_h),
                pos=(bx, 0, tab_h - theme.accent_h),
            )
            if i != active:
                acc.hide()
            accents.append(acc)

            page = DirectFrame(
                parent=pages_root,
                frameColor=(0, 0, 0, 0),
                relief=DGG.FLAT,
                frameSize=(0.0, w, 0.0, page_h),
            )
            if i != active:
                page.hide()
            pages.append(page)

        out = Tabs(
            root=root,
            bar=bar,
            pages_root=pages_root,
            buttons=btns,
            accents=accents,
            pages=pages,
            active=active,
        )

        def _select(ii: int) -> None:
            out.select(ii, active_color=ac, inactive_color=ic, active_text_fg=at, inactive_text_fg=it)
            if on_change is not None:
                on_change(ii)

        for i, b in enumerate(out.buttons):
            b["command"] = lambda ii=i: _select(ii)

        return out

    def select(
        self,
        idx: int,
        *,
        active_color: Color,
        inactive_color: Color,
        active_text_fg: Color,
        inactive_text_fg: Color,
    ) -> None:
        if not (0 <= idx < len(self.pages)):
            return
        if idx == self.active:
            return
        for i, page in enumerate(self.pages):
            if i == idx:
                page.show()
            else:
                page.hide()
        for i, b in enumerate(self.buttons):
            base = active_color if i == idx else inactive_color
            frame_colors = (
                base,
                (base[0] * 0.82, base[1] * 0.82, base[2] * 0.82, base[3]),
                (min(1.0, base[0] * 1.06), min(1.0, base[1] * 1.06), min(1.0, base[2] * 1.06), base[3]),
                (base[0] * 0.60, base[1] * 0.60, base[2] * 0.60, base[3]),
            )
            b["frameColor"] = frame_colors
            b["text_fg"] = active_text_fg if i == idx else inactive_text_fg
        for i, a in enumerate(self.accents):
            if i == idx:
                a.show()
            else:
                a.hide()
        self.active = idx

    def page(self, idx: int) -> NodePath:
        return self.pages[idx]

    def destroy(self) -> None:
        try:
            self.root.destroy()
        except Exception:
            pass
