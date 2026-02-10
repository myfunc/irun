"""Layer helpers for `ivan.world.scene`.

The runtime `WorldScene` class stays the high-level facade, while this package
contains reusable lower-level logic (path resolution, lightstyle handling,
shader/texture primitives) so callers do not need to navigate one giant file.
"""

# Shared typing contract for layer entry points.
from ivan.world.scene_layers.contracts import SceneLayerContract

__all__ = ["SceneLayerContract"]

