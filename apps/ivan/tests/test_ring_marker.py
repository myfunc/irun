"""Tests for shared ring marker rendering helper."""

from __future__ import annotations

from panda3d.core import LVector3f, NodePath

from ivan.game.ring_marker import build_ring


def test_build_ring_creates_child_node() -> None:
    """build_ring attaches a LineSegs-based node to parent."""
    parent = NodePath("ring-marker-test-parent")
    assert parent.getNumChildren() == 0

    build_ring(
        parent,
        name="test-ring",
        center=LVector3f(0.0, 0.0, 1.0),
        radius=2.0,
        half_z=1.5,
        color=(1.0, 0.5, 0.0, 0.8),
        thickness=3.0,
        segs=48,
        ribs=12,
    )

    assert parent.getNumChildren() == 1
    child = parent.getChild(0)
    assert not child.isEmpty()
