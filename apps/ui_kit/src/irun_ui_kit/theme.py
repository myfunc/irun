from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path


Color = tuple[float, float, float, float]


@dataclass(frozen=True)
class Theme:
    """
    UI theme tokens.

    Values are normalized floats (0..1), compatible with Panda3D color tuples.
    """

    # Layout
    # Smaller default padding to reduce "air" in the kit.
    pad: float = 0.045
    gap: float = 0.028
    outline_w: float = 0.008
    header_h: float = 0.085
    # Thin accent thickness (used for underlines/indicators).
    accent_h: float = 0.010

    # Typography (DirectGUI `text_scale` in aspect2d units)
    title_scale: float = 0.056
    label_scale: float = 0.044
    small_scale: float = 0.038

    # Optional font preference. When None, the renderer picks a console-friendly default
    # (and falls back to Panda3D's bundled fonts).
    font: str | None = None

    # Palette (darker retro industrial baseline + subtle warm orange notes)
    bg: Color = (0.035, 0.033, 0.030, 1.0)
    panel: Color = (0.105, 0.100, 0.092, 0.98)
    panel2: Color = (0.145, 0.138, 0.128, 0.98)
    outline: Color = (0.50, 0.48, 0.46, 1.0)
    header: Color = (0.78, 0.34, 0.10, 1.0)  # accent (subtle)
    text: Color = (0.92, 0.91, 0.88, 1.0)
    text_muted: Color = (0.62, 0.60, 0.56, 1.0)
    ink: Color = (0.055, 0.050, 0.045, 1.0)
    danger: Color = (255 / 255, 86 / 255, 120 / 255, 1.0)

    # Retro depth cues (procedural, no textures required)
    shadow: Color = (0.0, 0.0, 0.0, 0.55)
    shadow_off_x: float = 0.02
    shadow_off_y: float = -0.02

    def with_overrides(self, **kwargs) -> "Theme":
        """Return a copy with overridden fields (simple project-side customization hook)."""
        return replace(self, **kwargs)

    def with_dpi(self, dpi_scale: float) -> "Theme":
        """
        Return a copy adjusted for high-DPI displays.

        We scale typography aggressively (to preserve physical size) and layout
        more conservatively (to avoid the UI ballooning).
        """

        s = float(dpi_scale)
        if s <= 1.0:
            return self

        # Conservative layout scaling.
        layout_s = 1.0 + (s - 1.0) * 0.35
        layout_s = max(1.0, min(1.5, layout_s))

        return replace(
            self,
            pad=self.pad * layout_s,
            gap=self.gap * layout_s,
            outline_w=self.outline_w * layout_s,
            header_h=self.header_h * layout_s,
            accent_h=self.accent_h * layout_s,
            title_scale=self.title_scale * s,
            label_scale=self.label_scale * s,
            small_scale=self.small_scale * s,
            shadow_off_x=self.shadow_off_x * layout_s,
            shadow_off_y=self.shadow_off_y * layout_s,
        )

    @staticmethod
    def from_json(path: str | Path) -> "Theme":
        """
        Load a theme override JSON.

        JSON keys must match Theme field names. Colors can be:
        - 4-tuple floats (0..1), or
        - 4-tuple ints (0..255) (will be normalized)
        """

        p = Path(path)
        data = json.loads(p.read_text(encoding="utf-8"))
        kwargs = {}
        for k, v in dict(data).items():
            if k in {
                "bg",
                "panel",
                "panel2",
                "outline",
                "header",
                "text",
                "text_muted",
                "ink",
                "danger",
                "shadow",
            }:
                if not (isinstance(v, (list, tuple)) and len(v) == 4):
                    raise ValueError(f"Theme color '{k}' must be a 4-item array.")
                if all(isinstance(x, int) for x in v):
                    vv = tuple(float(int(x)) / 255.0 for x in v)  # type: ignore[assignment]
                else:
                    vv = tuple(float(x) for x in v)  # type: ignore[assignment]
                kwargs[k] = vv
            else:
                kwargs[k] = v
        return Theme().with_overrides(**kwargs)
