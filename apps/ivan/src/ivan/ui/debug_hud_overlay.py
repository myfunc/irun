"""Compact F12-driven runtime debug overlay with multiple modes + mini frametime graph."""

from __future__ import annotations

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame, DirectLabel
from direct.showbase import ShowBaseGlobal
from panda3d.core import LineSegs, TextNode

from irun_ui_kit.theme import Theme


DEBUG_HUD_MODES = ("minimal", "render", "streaming", "graph")
MODE_LABELS = {
    "minimal": "min",
    "render": "render",
    "streaming": "stream",
    "graph": "graph",
}


class DebugHudOverlay:
    """Compact debug overlay: F12 cycles minimal | render | streaming | graph."""

    def __init__(self, *, aspect2d, theme: Theme) -> None:
        aspect_ratio = 16.0 / 9.0
        if getattr(ShowBaseGlobal, "base", None) is not None:
            try:
                aspect_ratio = float(ShowBaseGlobal.base.getAspectRatio())
            except Exception:
                pass

        self._theme = theme
        self._mode_index = 0
        self._enabled = False

        # Compact box: top-right, below speed chip; avoid overlap with speed/health HUD.
        pad = 0.04
        w = 0.32
        h = 0.18
        x = aspect_ratio - pad - w
        y = 0.80

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
            frameColor=(theme.panel[0], theme.panel[1], theme.panel[2], 0.90),
            relief=DGG.FLAT,
            frameSize=(theme.outline_w, w - theme.outline_w, theme.outline_w, h - theme.outline_w),
        )["state"] = DGG.DISABLED

        self._label = DirectLabel(
            parent=self._root,
            text="",
            text_scale=0.028,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(theme.outline_w + theme.pad * 0.5, 0.0, h - theme.outline_w - theme.pad - 0.022),
            text_wordwrap=45,
        )

        # Graph area: below the header line, thin strip for frametime bars.
        graph_h = 0.055
        graph_y = theme.outline_w + theme.pad * 0.3
        graph_w = w - theme.outline_w * 2 - theme.pad
        graph_x = theme.outline_w + theme.pad * 0.5

        self._graph_root = DirectFrame(
            parent=self._root,
            frameColor=(0.15, 0.15, 0.18, 0.95),
            relief=DGG.FLAT,
            frameSize=(0.0, graph_w, 0.0, graph_h),
            pos=(graph_x, 0.0, graph_y),
        )
        self._graph_root["state"] = DGG.DISABLED
        self._graph_root.hide()

        self._graph_w = graph_w
        self._graph_h = graph_h
        self._root.hide()

    def cycle_mode(self) -> None:
        """F12: cycle off -> minimal -> render -> streaming -> graph -> off."""
        if not self._enabled:
            self._enabled = True
            self._mode_index = 0
            self._root.show()
            self._graph_root.hide()
            return
        self._mode_index += 1
        if self._mode_index >= len(DEBUG_HUD_MODES):
            self._enabled = False
            self._mode_index = 0
            self._root.hide()
            self._graph_root.hide()
            return
        mode = DEBUG_HUD_MODES[self._mode_index]
        if mode == "graph":
            self._graph_root.show()
        else:
            self._graph_root.hide()

    def mode(self) -> str:
        return DEBUG_HUD_MODES[self._mode_index]

    def is_visible(self) -> bool:
        return self._enabled

    def update(
        self,
        *,
        fps: float,
        frame_dt_ms: float,
        frame_p95_ms: float,
        sim_steps: int,
        sim_hz: int,
        net_connected: bool,
        net_perf_text: str,
        frame_ms_history: list[float],
        frame_spike_threshold_ms: float,
    ) -> None:
        """Update overlay content based on current mode."""
        if not self._enabled:
            return

        mode = DEBUG_HUD_MODES[self._mode_index]
        mode_tag = f"[{MODE_LABELS[mode]}]"

        if mode == "minimal":
            self._graph_root.hide()
            self._label["text"] = f"{mode_tag} F12\n{fps:.1f} fps | {frame_dt_ms:.2f}ms"
            return

        if mode == "render":
            self._graph_root.hide()
            self._label["text"] = (
                f"{mode_tag} F12\n"
                f"{fps:.1f} fps | {frame_dt_ms:.2f}ms | p95={frame_p95_ms:.2f}ms\n"
                f"sim={sim_hz}hz steps={sim_steps}"
            )
            return

        if mode == "streaming":
            self._graph_root.hide()
            net_line = net_perf_text if net_connected else "offline"
            self._label["text"] = (
                f"{mode_tag} F12\n"
                f"{fps:.1f} fps | p95={frame_p95_ms:.2f}ms\n"
                f"net: {net_line[:50]}"
            )
            return

        # graph mode
        self._graph_root.show()
        spike_count = sum(1 for ms in frame_ms_history if ms >= frame_spike_threshold_ms)
        self._label["text"] = (
            f"{mode_tag} F12 | {fps:.1f} fps | spikes={spike_count}\n"
        )
        self._redraw_graph(
            frame_ms_history=frame_ms_history,
            spike_threshold_ms=frame_spike_threshold_ms,
        )

    def _redraw_graph(
        self,
        *,
        frame_ms_history: list[float],
        spike_threshold_ms: float,
    ) -> None:
        """Draw mini frametime graph with spike markers."""
        if not frame_ms_history:
            return

        # Remove old graph node.
        for child in self._graph_root.getChildren():
            child.removeNode()

        graph_w = self._graph_w
        graph_h = self._graph_h
        n = min(128, len(frame_ms_history))
        vals = list(frame_ms_history)[-n:]
        max_ms = max(max(vals, default=1.0), spike_threshold_ms * 1.2, 20.0)
        dx = graph_w / max(1, n - 1)

        ls = LineSegs("frametime-graph")
        ls.setThickness(1.5)

        for i, ms in enumerate(vals):
            x = i * dx
            bar_h = min(1.0, ms / max_ms) * graph_h
            is_spike = ms >= spike_threshold_ms
            if is_spike:
                ls.setColor(1.0, 0.35, 0.25, 1.0)
            else:
                ls.setColor(0.4, 0.75, 0.5, 0.95)
            ls.moveTo(x, 0, 0)
            ls.drawTo(x, 0, bar_h)

        np = self._graph_root.attachNewNode(ls.create())
        np.setScale(1.0)

    def show(self) -> None:
        self._enabled = True
        self._root.show()
        if self.mode() == "graph":
            self._graph_root.show()

    def hide(self) -> None:
        self._enabled = False
        self._root.hide()
        self._graph_root.hide()
