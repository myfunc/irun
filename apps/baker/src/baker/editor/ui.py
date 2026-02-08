from __future__ import annotations

from dataclasses import dataclass

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame, DirectLabel
from panda3d.core import LVector3f, TextNode

from irun_ui_kit.theme import Theme
from irun_ui_kit.widgets.button import Button
from irun_ui_kit.widgets.numeric_control import NumericControl
from irun_ui_kit.widgets.panel import Panel
from irun_ui_kit.widgets.scrolled import Scrolled
from irun_ui_kit.widgets.tabs import Tabs

from baker.editor.layout import EditorRects
from baker.editor.scene_objects import EditorObject, update_point_light_preview


@dataclass
class _InspectorWidgets:
    title: DirectLabel | None = None
    pos_x: NumericControl | None = None
    pos_y: NumericControl | None = None
    pos_z: NumericControl | None = None
    intensity: NumericControl | None = None
    col_r: NumericControl | None = None
    col_g: NumericControl | None = None
    col_b: NumericControl | None = None
    radius: NumericControl | None = None


class BakerEditorUI:
    def __init__(
        self,
        *,
        parent,
        theme: Theme,
        rects: EditorRects,
        on_add_light,
        on_delete_selected,
        on_select_object_id,
    ) -> None:
        self._parent = parent
        self.theme = theme
        self.rects = rects
        self._on_add_light = on_add_light
        self._on_delete_selected = on_delete_selected
        self._on_select_object_id = on_select_object_id

        self._left_panel: Panel | None = None
        self._right_panel: Panel | None = None
        self._viewport_outline: list[DirectFrame] = []

        self._objects_scrolled: Scrolled | None = None
        self._object_rows: list[Button] = []

        self._ins_scrolled: Scrolled | None = None
        self._ins_canvas_root: DirectFrame | None = None
        self._ins_widgets = _InspectorWidgets()
        self._selected: EditorObject | None = None
        self._world_root = None

        self._build()

    def destroy(self) -> None:
        try:
            for b in self._object_rows:
                b.node.destroy()
        except Exception:
            pass
        self._object_rows.clear()

        try:
            if self._objects_scrolled is not None:
                self._objects_scrolled.frame.destroy()
        except Exception:
            pass
        self._objects_scrolled = None

        self._destroy_inspector_widgets()
        try:
            if self._ins_scrolled is not None:
                self._ins_scrolled.frame.destroy()
        except Exception:
            pass
        self._ins_scrolled = None

        try:
            for f in self._viewport_outline:
                f.destroy()
        except Exception:
            pass
        self._viewport_outline.clear()

        try:
            if self._left_panel is not None:
                self._left_panel.node.destroy()
        except Exception:
            pass
        self._left_panel = None

        try:
            if self._right_panel is not None:
                self._right_panel.node.destroy()
        except Exception:
            pass
        self._right_panel = None

    def relayout(self, *, rects: EditorRects) -> None:
        # For now: rebuild (keeps logic simple; UI is small).
        self.rects = rects
        sel = self._selected
        self.destroy()
        self._build()
        if sel is not None:
            self.set_selected(sel)

    def _build(self) -> None:
        t = self.theme

        self._left_panel = Panel.build(
            parent=self._parent,
            theme=t,
            x=self.rects.left.x0,
            y=self.rects.left.y0,
            w=self.rects.left.w,
            h=self.rects.left.h,
            title="Tools",
            header=True,
        )

        self._right_panel = Panel.build(
            parent=self._parent,
            theme=t,
            x=self.rects.right.x0,
            y=self.rects.right.y0,
            w=self.rects.right.w,
            h=self.rects.right.h,
            title="Inspector",
            header=True,
        )

        # Viewport outline only (no fill, to avoid covering the 3D view).
        self._build_viewport_outline()

        self._build_left()
        self._build_right()

    def _build_viewport_outline(self) -> None:
        t = self.theme
        r = self.rects.viewport
        w = max(0.004, float(t.outline_w))

        def _mk(x0: float, x1: float, y0: float, y1: float) -> DirectFrame:
            f = DirectFrame(
                parent=self._parent,
                frameColor=t.outline,
                relief=DGG.FLAT,
                frameSize=(float(x0), float(x1), float(y0), float(y1)),
            )
            f["state"] = DGG.DISABLED
            return f

        # Top, bottom, left, right strips.
        self._viewport_outline = [
            _mk(r.x0, r.x1, r.y1 - w, r.y1),
            _mk(r.x0, r.x1, r.y0, r.y0 + w),
            _mk(r.x0, r.x0 + w, r.y0, r.y1),
            _mk(r.x1 - w, r.x1, r.y0, r.y1),
        ]

    def _panel_content_frame(self, *, panel: Panel) -> DirectFrame:
        t = self.theme
        header_total_h = t.header_h + (t.outline_w * 2)
        content_w = float(panel.w - t.pad * 2)
        content_h = float((panel.h - header_total_h) - t.pad * 2)
        return DirectFrame(
            parent=panel.content,
            frameColor=(0, 0, 0, 0),
            relief=DGG.FLAT,
            frameSize=(0.0, content_w, 0.0, max(0.01, content_h)),
            pos=(t.pad, 0.0, t.pad),
        )

    def _build_left(self) -> None:
        assert self._left_panel is not None
        t = self.theme
        content = self._panel_content_frame(panel=self._left_panel)
        w = float(content["frameSize"][1])
        h = float(content["frameSize"][3])

        # Tabs: Tools vs Objects
        tab_h = max(0.10, t.header_h * 0.90)
        page_h = max(0.2, h - tab_h)
        tabs = Tabs.build(
            parent=content,
            theme=t,
            x=0.0,
            y=0.0,
            w=w,
            tab_h=tab_h,
            page_h=page_h,
            labels=["Tools", "Objects"],
            active=0,
        )

        # Tools page.
        tools = tabs.page(0)
        btn_w = min(1.10, w)
        btn_h = 0.12
        y = page_h - btn_h * 0.65
        Button.build(
            parent=tools,
            theme=t,
            x=btn_w / 2.0,
            y=y,
            w=btn_w,
            h=btn_h,
            label="+ Add Point Light",
            on_click=self._on_add_light,
        )
        y -= btn_h + t.gap
        Button.build(
            parent=tools,
            theme=t,
            x=btn_w / 2.0,
            y=y,
            w=btn_w,
            h=btn_h,
            label="Delete Selection",
            on_click=self._on_delete_selected,
        )

        hint = DirectLabel(
            parent=tools,
            text=(
                "Viewport:\n"
                "  RMB drag: orbit\n"
                "  MMB drag: pan\n"
                "  wheel: zoom\n"
                "Trackpad:\n"
                "  Alt+LMB: orbit\n"
                "  Alt+Shift+LMB: pan\n"
                "  Alt+Ctrl+LMB: zoom"
            ),
            text_scale=t.small_scale,
            text_align=TextNode.ALeft,
            text_fg=t.text_muted,
            frameColor=(0, 0, 0, 0),
            pos=(0.0, 0, max(0.02, y - 0.22)),
        )

        # Objects page.
        objs = tabs.page(1)
        # Scrolled list.
        canvas_h = max(0.6, page_h * 2.2)
        self._objects_scrolled = Scrolled.build(
            parent=objs,
            theme=t,
            x=0.0,
            y=0.0,
            w=w,
            h=page_h,
            canvas_h=canvas_h,
        )

    def _build_right(self) -> None:
        assert self._right_panel is not None
        t = self.theme
        content = self._panel_content_frame(panel=self._right_panel)
        w = float(content["frameSize"][1])
        h = float(content["frameSize"][3])

        # Scrollable inspector.
        canvas_h = max(0.6, h * 2.0)
        self._ins_scrolled = Scrolled.build(
            parent=content,
            theme=t,
            x=0.0,
            y=0.0,
            w=w,
            h=h,
            canvas_h=canvas_h,
        )
        self._ins_canvas_root = DirectFrame(
            parent=self._ins_scrolled.canvas,
            frameColor=(0, 0, 0, 0),
            relief=DGG.FLAT,
            frameSize=(0.0, self._ins_scrolled.content_w(), 0.0, canvas_h),
        )

        self._build_inspector_for(None)

    def set_objects(self, objects: list[EditorObject], *, selected_id: int | None) -> None:
        if self._objects_scrolled is None:
            return
        t = self.theme
        canvas = self._objects_scrolled.canvas
        try:
            for b in self._object_rows:
                b.node.destroy()
        except Exception:
            pass
        self._object_rows.clear()

        row_h = 0.115
        w = self._objects_scrolled.content_w()
        y = float(self._objects_scrolled.canvas_h) - row_h * 0.6
        for obj in objects:
            label = obj.name
            if selected_id is not None and int(obj.id) == int(selected_id):
                label = "> " + label
            b = Button.build(
                parent=canvas,
                theme=t,
                x=w / 2.0,
                y=y,
                w=w,
                h=row_h,
                label=label,
                on_click=lambda oid=int(obj.id): self._on_select_object_id(oid),
            )
            self._object_rows.append(b)
            y -= row_h + t.gap * 0.6

    def _destroy_inspector_widgets(self) -> None:
        ws = self._ins_widgets
        for w in (
            ws.title,
            getattr(ws.pos_x, "root", None),
            getattr(ws.pos_y, "root", None),
            getattr(ws.pos_z, "root", None),
            getattr(ws.intensity, "root", None),
            getattr(ws.col_r, "root", None),
            getattr(ws.col_g, "root", None),
            getattr(ws.col_b, "root", None),
            getattr(ws.radius, "root", None),
        ):
            if w is None:
                continue
            try:
                w.destroy()
            except Exception:
                pass
        self._ins_widgets = _InspectorWidgets()

    def _build_inspector_for(self, obj: EditorObject | None) -> None:
        if self._ins_canvas_root is None:
            return
        self._destroy_inspector_widgets()

        t = self.theme
        root = self._ins_canvas_root
        w = float(root["frameSize"][1])
        y = float(root["frameSize"][3]) - t.small_scale * 1.4

        title = "(none)" if obj is None else f"{obj.name} ({obj.kind})"
        self._ins_widgets.title = DirectLabel(
            parent=root,
            text=title,
            text_scale=t.label_scale,
            text_align=TextNode.ALeft,
            text_fg=t.text,
            frameColor=(0, 0, 0, 0),
            pos=(0.0, 0, y),
        )
        y -= 0.16

        if obj is None:
            DirectLabel(
                parent=root,
                text="Click an object in the viewport or from the Objects tab.",
                text_scale=t.small_scale,
                text_align=TextNode.ALeft,
                text_fg=t.text_muted,
                frameColor=(0, 0, 0, 0),
                pos=(0.0, 0, y),
            )
            return

        # Common: position.
        def _mk_pos_setter(axis: int):
            def _set(v: float) -> None:
                if self._world_root is None:
                    return
                p = obj.pos(rel_to=self._world_root)
                pp = LVector3f(p)
                if axis == 0:
                    pp.x = float(v)
                elif axis == 1:
                    pp.y = float(v)
                else:
                    pp.z = float(v)
                obj.set_pos(rel_to=self._world_root, pos=pp)

            return _set

        # Defaults; will be immediately set by set_selected().
        self._ins_widgets.pos_x = NumericControl.build(
            parent=root,
            theme=t,
            x=0.0,
            y=y,
            w=w,
            label="Position X",
            value=0.0,
            minimum=-100000.0,
            maximum=100000.0,
            on_change=_mk_pos_setter(0),
            normalized_slider=False,
            normalized_entry=False,
            precision=3,
        )
        y -= 0.125
        self._ins_widgets.pos_y = NumericControl.build(
            parent=root,
            theme=t,
            x=0.0,
            y=y,
            w=w,
            label="Position Y",
            value=0.0,
            minimum=-100000.0,
            maximum=100000.0,
            on_change=_mk_pos_setter(1),
            normalized_slider=False,
            normalized_entry=False,
            precision=3,
        )
        y -= 0.125
        self._ins_widgets.pos_z = NumericControl.build(
            parent=root,
            theme=t,
            x=0.0,
            y=y,
            w=w,
            label="Position Z",
            value=0.0,
            minimum=-100000.0,
            maximum=100000.0,
            on_change=_mk_pos_setter(2),
            normalized_slider=False,
            normalized_entry=False,
            precision=3,
        )
        y -= 0.16

        if obj.kind == "point_light":
            def _set_intensity(v: float) -> None:
                obj.intensity = float(v)
                update_point_light_preview(obj)

            def _set_r(v: float) -> None:
                obj.color = (float(v), float(obj.color[1]), float(obj.color[2]))
                update_point_light_preview(obj)

            def _set_g(v: float) -> None:
                obj.color = (float(obj.color[0]), float(v), float(obj.color[2]))
                update_point_light_preview(obj)

            def _set_b(v: float) -> None:
                obj.color = (float(obj.color[0]), float(obj.color[1]), float(v))
                update_point_light_preview(obj)

            def _set_radius(v: float) -> None:
                obj.radius = float(v)

            self._ins_widgets.intensity = NumericControl.build(
                parent=root,
                theme=t,
                x=0.0,
                y=y,
                w=w,
                label="Intensity",
                value=float(obj.intensity),
                minimum=0.0,
                maximum=20.0,
                on_change=_set_intensity,
                normalized_slider=True,
                normalized_entry=False,
                precision=2,
            )
            y -= 0.125
            self._ins_widgets.col_r = NumericControl.build(
                parent=root,
                theme=t,
                x=0.0,
                y=y,
                w=w,
                label="Color R",
                value=float(obj.color[0]),
                minimum=0.0,
                maximum=1.0,
                on_change=_set_r,
                normalized_slider=True,
                normalized_entry=False,
                precision=3,
            )
            y -= 0.125
            self._ins_widgets.col_g = NumericControl.build(
                parent=root,
                theme=t,
                x=0.0,
                y=y,
                w=w,
                label="Color G",
                value=float(obj.color[1]),
                minimum=0.0,
                maximum=1.0,
                on_change=_set_g,
                normalized_slider=True,
                normalized_entry=False,
                precision=3,
            )
            y -= 0.125
            self._ins_widgets.col_b = NumericControl.build(
                parent=root,
                theme=t,
                x=0.0,
                y=y,
                w=w,
                label="Color B",
                value=float(obj.color[2]),
                minimum=0.0,
                maximum=1.0,
                on_change=_set_b,
                normalized_slider=True,
                normalized_entry=False,
                precision=3,
            )
            y -= 0.125
            self._ins_widgets.radius = NumericControl.build(
                parent=root,
                theme=t,
                x=0.0,
                y=y,
                w=w,
                label="Bake Radius (meta)",
                value=float(obj.radius),
                minimum=0.0,
                maximum=200.0,
                on_change=_set_radius,
                normalized_slider=True,
                normalized_entry=False,
                precision=2,
            )

    def set_selected(self, obj: EditorObject | None, *, world_root=None) -> None:
        self._selected = obj
        if world_root is not None:
            self._world_root = world_root
        self._build_inspector_for(obj)
        if obj is None:
            return
        if self._world_root is None:
            return
        p = obj.pos(rel_to=self._world_root)
        ws = self._ins_widgets
        if ws.pos_x:
            ws.pos_x.set_value(float(p.x), emit=False)
        if ws.pos_y:
            ws.pos_y.set_value(float(p.y), emit=False)
        if ws.pos_z:
            ws.pos_z.set_value(float(p.z), emit=False)
