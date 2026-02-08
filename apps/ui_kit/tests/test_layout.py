from __future__ import annotations

from irun_ui_kit.layout import GridSpec, Rect


def test_grid_cells_do_not_overlap() -> None:
    bounds = Rect(0.0, 0.0, 10.0, 10.0)
    g = GridSpec(cols=2, rows=2, gap=1.0)
    c00 = g.cell(bounds, col=0, row=0)
    c10 = g.cell(bounds, col=1, row=0)
    c01 = g.cell(bounds, col=0, row=1)
    c11 = g.cell(bounds, col=1, row=1)

    assert c00.x1 <= c10.x0
    assert c01.x1 <= c11.x0
    assert c00.y1 <= c01.y0
    assert c10.y1 <= c11.y0

