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
    pad: float = 0.07
    gap: float = 0.040
    outline_w: float = 0.008
    header_h: float = 0.085

    # Typography (DirectGUI `text_scale` in aspect2d units)
    title_scale: float = 0.052
    label_scale: float = 0.040
    small_scale: float = 0.032

    # Palette (retro industrial baseline: dark panels + warm orange accent)
    bg: Color = (0.06, 0.055, 0.050, 1.0)
    panel: Color = (0.15, 0.14, 0.13, 0.98)
    panel2: Color = (0.21, 0.20, 0.19, 0.98)
    outline: Color = (0.62, 0.60, 0.58, 1.0)
    # Slightly desaturated "burnt orange" so it reads more PS2/industrial than neon.
    header: Color = (0.88, 0.44, 0.12, 1.0)  # orange accent
    text: Color = (0.93, 0.92, 0.89, 1.0)
    text_muted: Color = (0.68, 0.66, 0.60, 1.0)
    ink: Color = (0.07, 0.06, 0.05, 1.0)
    danger: Color = (255 / 255, 86 / 255, 120 / 255, 1.0)

    # Retro depth cues (procedural, no textures required)
    shadow: Color = (0.0, 0.0, 0.0, 0.55)
    shadow_off_x: float = 0.02
    shadow_off_y: float = -0.02

    def with_overrides(self, **kwargs) -> "Theme":
        """Return a copy with overridden fields (simple project-side customization hook)."""
        return replace(self, **kwargs)

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
