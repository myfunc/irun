from __future__ import annotations

from dataclasses import dataclass

from irun_ui_kit.layout import Rect
from irun_ui_kit.theme import Theme


@dataclass(frozen=True)
class EditorRects:
    left: Rect
    viewport: Rect
    right: Rect


def compute_editor_rects(
    *,
    bounds: Rect,
    theme: Theme,
    left_frac: float = 0.23,
    right_frac: float = 0.27,
    min_viewport_w: float = 0.85,
    outer_pad: float | None = None,
) -> EditorRects:
    """
    Compute Baker editor chrome rectangles in a local coordinate space.

    Rects are bottom-left anchored: (x0, y0) .. (x1, y1).
    """

    pad = float(theme.pad if outer_pad is None else outer_pad)
    gap = float(theme.gap)

    x0 = float(bounds.x0) + pad
    x1 = float(bounds.x1) - pad
    y0 = float(bounds.y0) + pad
    y1 = float(bounds.y1) - pad
    total_w = max(0.01, float(x1 - x0))
    total_h = max(0.01, float(y1 - y0))

    left_w = max(0.55, total_w * float(left_frac))
    right_w = max(0.65, total_w * float(right_frac))

    # Ensure the viewport stays usable; if not, shrink side panels proportionally.
    viewport_w = total_w - left_w - right_w - gap * 2.0
    if viewport_w < float(min_viewport_w):
        need = float(min_viewport_w) - viewport_w
        # Take the shrink from the larger panel first, but keep minimums.
        lmin = 0.45
        rmin = 0.50
        take_r = min(need, max(0.0, right_w - rmin))
        right_w -= take_r
        need -= take_r
        take_l = min(need, max(0.0, left_w - lmin))
        left_w -= take_l

    left = Rect(x0=x0, y0=y0, x1=x0 + left_w, y1=y0 + total_h)
    right = Rect(x0=x1 - right_w, y0=y0, x1=x1, y1=y0 + total_h)
    viewport = Rect(
        x0=left.x1 + gap,
        y0=y0,
        x1=right.x0 - gap,
        y1=y0 + total_h,
    )
    return EditorRects(left=left, viewport=viewport, right=right)


def point_in_rect(*, x: float, y: float, r: Rect) -> bool:
    return (float(r.x0) <= float(x) <= float(r.x1)) and (float(r.y0) <= float(y) <= float(r.y1))
