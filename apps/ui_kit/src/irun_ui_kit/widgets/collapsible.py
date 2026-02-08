from __future__ import annotations

from dataclasses import dataclass

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, DirectLabel
from panda3d.core import NodePath, TextNode

from irun_ui_kit.theme import Theme


@dataclass
class CollapsiblePanel:
    """
    Collapsible panel section with a clickable header.

    - When collapsed, the widget shrinks to header-only height.
    - Optional `on_toggle` lets callers relayout neighboring panels.
    """

    root: DirectFrame
    shadow: DirectFrame
    outline: DirectFrame
    inner: DirectFrame
    header: DirectFrame
    title: DirectLabel
    chevron: DirectLabel
    header_hit: DirectButton
    content: NodePath
    theme: Theme
    x: float
    y: float
    w: float
    expanded_h: float
    expanded: bool
    on_toggle: callable | None

    @staticmethod
    def build(
        *,
        parent,
        theme: Theme,
        x: float,
        y: float,
        w: float,
        expanded_h: float,
        title: str,
        expanded: bool = True,
        on_toggle=None,
    ) -> "CollapsiblePanel":
        # Root is a transparent container; everything is positioned relative to it.
        root = DirectFrame(
            parent=parent,
            frameColor=(0, 0, 0, 0),
            relief=DGG.FLAT,
            frameSize=(0.0, w, 0.0, expanded_h),
            pos=(x, 0, y),
        )

        shadow = DirectFrame(
            parent=root,
            frameColor=theme.shadow,
            relief=DGG.FLAT,
            frameSize=(0.0, w, 0.0, expanded_h),
            pos=(theme.shadow_off_x, 0, theme.shadow_off_y),
        )
        shadow["state"] = DGG.DISABLED

        outline = DirectFrame(
            parent=root,
            frameColor=theme.outline,
            relief=DGG.FLAT,
            frameSize=(0.0, w, 0.0, expanded_h),
        )
        inner = DirectFrame(
            parent=outline,
            frameColor=theme.panel,
            relief=DGG.FLAT,
            frameSize=(theme.outline_w, w - theme.outline_w, theme.outline_w, expanded_h - theme.outline_w),
        )

        header = DirectFrame(
            parent=inner,
            frameColor=theme.panel2,
            relief=DGG.FLAT,
            frameSize=(
                theme.outline_w,
                w - theme.outline_w,
                expanded_h - theme.outline_w - theme.header_h,
                expanded_h - theme.outline_w,
            ),
        )
        title_lbl = DirectLabel(
            parent=inner,
            text=str(title).upper(),
            text_scale=theme.title_scale,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(theme.outline_w + theme.pad, 0, expanded_h - theme.outline_w - (theme.header_h * 0.70)),
        )
        chevron = DirectLabel(
            parent=inner,
            text="v" if expanded else ">",
            text_scale=theme.small_scale,
            text_align=TextNode.ALeft,
            text_fg=theme.text_muted,
            frameColor=(0, 0, 0, 0),
            pos=(theme.outline_w + theme.pad * 0.35, 0, expanded_h - theme.outline_w - (theme.header_h * 0.70)),
        )
        # Click target over header strip.
        hit = DirectButton(
            parent=inner,
            text="",
            frameColor=(0, 0, 0, 0),
            relief=DGG.FLAT,
            frameSize=(
                theme.outline_w,
                w - theme.outline_w,
                expanded_h - theme.outline_w - theme.header_h,
                expanded_h - theme.outline_w,
            ),
            command=lambda: None,
            pressEffect=0,
        )

        header_total_h = theme.header_h + (theme.outline_w * 2)
        content = DirectFrame(
            parent=inner,
            frameColor=(0, 0, 0, 0),
            relief=DGG.FLAT,
            frameSize=(theme.pad, w - theme.pad, theme.pad, expanded_h - header_total_h),
        )

        out = CollapsiblePanel(
            root=root,
            shadow=shadow,
            outline=outline,
            inner=inner,
            header=header,
            title=title_lbl,
            chevron=chevron,
            header_hit=hit,
            content=content,
            theme=theme,
            x=float(x),
            y=float(y),
            w=float(w),
            expanded_h=float(expanded_h),
            expanded=bool(expanded),
            on_toggle=on_toggle,
        )

        def _toggle() -> None:
            out.set_expanded(not out.expanded)
            if out.on_toggle is not None:
                out.on_toggle()

        out.header_hit["command"] = _toggle
        out.header_hit.bind(DGG.ENTER, lambda _evt: out.chevron.__setitem__("text_fg", theme.text))
        out.header_hit.bind(DGG.EXIT, lambda _evt: out.chevron.__setitem__("text_fg", theme.text_muted))

        out.set_expanded(out.expanded)
        return out

    def collapsed_h(self) -> float:
        # Header-only: header strip + outline.
        return (self.theme.header_h + (self.theme.outline_w * 2))

    def current_h(self) -> float:
        return self.expanded_h if self.expanded else self.collapsed_h()

    def set_pos(self, *, y: float) -> None:
        self.y = float(y)
        self.root.setPos(self.x, 0, self.y)

    def set_expanded(self, expanded: bool) -> None:
        self.expanded = bool(expanded)
        h = self.current_h()

        # Resize root and layers.
        self.root["frameSize"] = (0.0, self.w, 0.0, h)
        self.shadow["frameSize"] = (0.0, self.w, 0.0, h)
        self.outline["frameSize"] = (0.0, self.w, 0.0, h)
        self.inner["frameSize"] = (self.theme.outline_w, self.w - self.theme.outline_w, self.theme.outline_w, h - self.theme.outline_w)

        # Header always stays at the top.
        self.header["frameSize"] = (
            self.theme.outline_w,
            self.w - self.theme.outline_w,
            h - self.theme.outline_w - self.theme.header_h,
            h - self.theme.outline_w,
        )
        z = h - self.theme.outline_w - (self.theme.header_h * 0.70)
        self.title.setPos(self.theme.outline_w + self.theme.pad, 0, z)
        self.chevron.setPos(self.theme.outline_w + self.theme.pad * 0.35, 0, z)
        self.header_hit["frameSize"] = (
            self.theme.outline_w,
            self.w - self.theme.outline_w,
            h - self.theme.outline_w - self.theme.header_h,
            h - self.theme.outline_w,
        )

        # Content region.
        header_total_h = self.theme.header_h + (self.theme.outline_w * 2)
        if self.expanded:
            self.content.show()
            self.content["frameSize"] = (self.theme.pad, self.w - self.theme.pad, self.theme.pad, h - header_total_h)
            self.chevron["text"] = "v"
        else:
            self.content.hide()
            self.chevron["text"] = ">"

    def destroy(self) -> None:
        try:
            self.root.destroy()
        except Exception:
            pass
