from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def w(self) -> float:
        return self.x1 - self.x0

    @property
    def h(self) -> float:
        return self.y1 - self.y0


@dataclass(frozen=True)
class GridSpec:
    cols: int
    rows: int
    gap: float

    def cell(self, bounds: Rect, *, col: int, row: int) -> Rect:
        if self.cols <= 0 or self.rows <= 0:
            raise ValueError("GridSpec must have positive cols/rows.")
        if not (0 <= col < self.cols) or not (0 <= row < self.rows):
            raise IndexError("Grid cell out of range.")

        total_gap_x = self.gap * (self.cols - 1)
        total_gap_y = self.gap * (self.rows - 1)
        cell_w = (bounds.w - total_gap_x) / self.cols
        cell_h = (bounds.h - total_gap_y) / self.rows

        x0 = bounds.x0 + col * (cell_w + self.gap)
        y0 = bounds.y0 + row * (cell_h + self.gap)
        return Rect(x0=x0, y0=y0, x1=x0 + cell_w, y1=y0 + cell_h)

