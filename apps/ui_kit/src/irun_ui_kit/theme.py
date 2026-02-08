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

    # Palette (ps2_cyan-ish baseline)
    bg: Color = (0.06, 0.06, 0.07, 1.0)
    panel: Color = (0.16, 0.16, 0.18, 0.98)
    panel2: Color = (0.22, 0.22, 0.25, 0.98)
    outline: Color = (0.55, 0.56, 0.59, 1.0)
    header: Color = (0.00, 0.90, 0.92, 1.0)
    text: Color = (236 / 255, 238 / 255, 244 / 255, 1.0)
    text_muted: Color = (170 / 255, 175 / 255, 188 / 255, 1.0)
    ink: Color = (0.06, 0.06, 0.08, 1.0)
    danger: Color = (255 / 255, 86 / 255, 120 / 255, 1.0)

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
            if k in {"bg", "panel", "panel2", "outline", "header", "text", "text_muted", "ink", "danger"}:
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

