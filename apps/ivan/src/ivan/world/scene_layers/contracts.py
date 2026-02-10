from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from panda3d.core import GeomVertexFormat, LVector3f, Shader, Texture


class SceneLayerContract(Protocol):
    """
    Minimal contract used by scene layer helpers.

    The concrete implementation is `WorldScene`, but typing against this protocol
    keeps layer modules decoupled from the full class definition.
    """

    # Shared runtime state (read/write).
    _map_id: str
    _course: dict | None
    _map_scale: float
    _map_json_path: Path | None
    _map_payload: dict | None
    _material_texture_index: dict[str, Path] | None
    _material_texture_root: Path | None
    _materials_meta: dict[str, dict] | None
    _lightmap_faces: dict[int, dict] | None
    _lightstyles: dict[int, str]
    _lightstyle_mode: str
    _lightstyle_last_frame: int | None
    _lightstyle_animated_styles: set[int]
    _lightmap_nodes: list[tuple[Any, list[int | None]]]
    _vis_goldsrc: Any
    _vis_face_nodes: dict[int, list[Any]]
    _vis_current_leaf: int | None
    _vis_enabled: bool
    _vis_deferred_lightmaps: dict[int, dict]
    _vis_initial_world_face_flags: bytearray | None
    _ambient_np: Any
    _sun_np: Any
    _skybox_np: Any

    spawn_point: LVector3f
    spawn_yaw: float
    kill_z: float
    triangles: list[list[float]] | None
    triangle_collision_mode: bool

    # Methods called by layers.
    def _resolve_map_bundle_path(self, map_json: Path) -> Path | None: ...
    def _try_load_map_file(self, *, cfg, map_file: Path, loader, render, camera) -> bool: ...
    def _resolve_material_root(self, *, map_json: Path, payload: dict) -> Path | None: ...
    def _resolve_lightmaps(self, *, map_json: Path, payload: dict) -> dict[int, dict] | None: ...
    def _lights_from_payload(self, *, payload: dict) -> list: ...
    def _resolve_lightstyles(self, *, payload: dict, cfg: dict | None) -> tuple[dict[int, str], str]: ...
    def _resolve_visibility(self, *, cfg, map_json: Path, payload: dict): ...
    def _attach_triangle_map_geometry(self, *, render, triangles: list[list[float]]) -> None: ...
    def _attach_triangle_map_geometry_v2(self, *, loader, render, triangles: list[dict]) -> None: ...
    def _attach_triangle_map_geometry_v2_unlit(self, *, loader, render, triangles: list[dict]) -> None: ...
    def _enhance_map_file_lighting(self, render, lights) -> None: ...
    def _setup_skybox(self, *, loader, camera, skyname: str) -> None: ...
    def _build_material_texture_index(self, root: Path) -> dict[str, Path]: ...
    def _resolve_material_texture_path(self, *, material_name: str) -> Path | None: ...
    def _make_debug_checker_texture(self) -> Texture: ...
    def _make_solid_texture(self, *, name: str, rgba: tuple[float, float, float, float]) -> Texture: ...
    def _lightmap_shader(self) -> Shader: ...
    def _vformat_v3n3c4t2t2(self) -> GeomVertexFormat: ...

