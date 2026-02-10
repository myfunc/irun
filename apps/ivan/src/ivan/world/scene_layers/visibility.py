from __future__ import annotations

from pathlib import Path

from panda3d.core import Filename, LVector3f, Texture

from ivan.app_config import MAP_PROFILE_DEV_FAST
from ivan.world.goldsrc_visibility import load_or_build_visibility_cache
from ivan.world.scene_layers.contracts import SceneLayerContract


def tick_visibility(scene: SceneLayerContract) -> None:
    """Update visible face set from current camera leaf."""
    if scene._vis_goldsrc is None:
        return
    if scene._world_root_np is None or scene._camera_np is None:
        return
    if not scene._vis_face_nodes:
        return

    try:
        pos = scene._camera_np.getPos(scene._world_root_np)
        leaf = best_effort_visibility_leaf(scene, pos=pos)
    except Exception:
        return
    if leaf is None:
        return

    if scene._vis_current_leaf is not None and int(leaf) == int(scene._vis_current_leaf):
        return
    scene._vis_current_leaf = int(leaf)

    # World-model faces are controlled by PVS; brush submodels remain always visible.
    flags = scene._vis_goldsrc.visible_world_face_flags_for_leaf(int(leaf))
    w0 = int(scene._vis_goldsrc.world_first_face)
    w1 = int(scene._vis_goldsrc.world_face_end)
    for face_idx, nodes in scene._vis_face_nodes.items():
        show = True
        if int(w0) <= int(face_idx) < int(w1):
            show = bool(flags[int(face_idx - w0)])
        for np in nodes:
            try:
                if show:
                    np.show()
                else:
                    np.hide()
            except Exception:
                pass

        if show and int(w0) <= int(face_idx) < int(w1):
            ensure_deferred_lightmaps_loaded(scene, face_idx=int(face_idx))


def best_effort_visibility_leaf(scene: SceneLayerContract, *, pos: LVector3f) -> int | None:
    """
    Find a stable BSP leaf index for PVS culling.
    """
    if scene._vis_goldsrc is None:
        return None
    if scene._world_root_np is None or scene._camera_np is None:
        return None

    scale = float(scene._map_scale) if float(scene._map_scale) > 0.0 else 1.0
    bsp_pos = LVector3f(float(pos[0]) / scale, -float(pos[1]) / scale, float(pos[2]) / scale)

    try:
        leaf0 = int(scene._vis_goldsrc.point_leaf(x=float(bsp_pos[0]), y=float(bsp_pos[1]), z=float(bsp_pos[2])))
    except Exception:
        return None

    try:
        vis_offset = int(scene._vis_goldsrc.leaves[int(leaf0)][0])
    except Exception:
        vis_offset = -1
    if vis_offset >= 0:
        return int(leaf0)

    if scene._vis_current_leaf is not None:
        try:
            prev_ofs = int(scene._vis_goldsrc.leaves[int(scene._vis_current_leaf)][0])
        except Exception:
            prev_ofs = -1
        if prev_ofs >= 0:
            return int(scene._vis_current_leaf)
    return int(leaf0)


def ensure_deferred_lightmaps_loaded(scene: SceneLayerContract, *, face_idx: int) -> None:
    """
    Load and bind per-face lightmap textures for a face that was previously deferred.
    """
    ent = scene._vis_deferred_lightmaps.get(int(face_idx))
    if not isinstance(ent, dict):
        return
    paths = ent.get("paths")
    nps = ent.get("nodepaths")
    if not (isinstance(paths, list) and len(paths) == 4):
        scene._vis_deferred_lightmaps.pop(int(face_idx), None)
        return
    if not isinstance(nps, list) or not nps:
        scene._vis_deferred_lightmaps.pop(int(face_idx), None)
        return
    loader = ent.get("loader")
    if loader is None:
        scene._vis_deferred_lightmaps.pop(int(face_idx), None)
        return

    lm_texs: list[Texture | None] = [None, None, None, None]
    for i in range(4):
        p = paths[i]
        if isinstance(p, Path) and p.exists():
            try:
                t = loader.loadTexture(Filename.fromOsSpecific(str(p)))
            except Exception:
                t = None
            if t is not None:
                t.setWrapU(Texture.WM_clamp)
                t.setWrapV(Texture.WM_clamp)
                t.setMinfilter(Texture.FT_linear)
                t.setMagfilter(Texture.FT_linear)
                lm_texs[i] = t

    for np in nps:
        try:
            if lm_texs[0] is not None:
                np.setShaderInput("lm_tex0", lm_texs[0])
            if lm_texs[1] is not None:
                np.setShaderInput("lm_tex1", lm_texs[1])
            if lm_texs[2] is not None:
                np.setShaderInput("lm_tex2", lm_texs[2])
            if lm_texs[3] is not None:
                np.setShaderInput("lm_tex3", lm_texs[3])
        except Exception:
            pass

    scene._vis_deferred_lightmaps.pop(int(face_idx), None)


def resolve_visibility(scene: SceneLayerContract, *, cfg, map_json: Path, payload: dict):
    """
    Best-effort visibility (occlusion) culling configuration and cache resolve.
    """
    vis_cfg = getattr(cfg, "visibility", None)
    enabled = False
    mode = "auto"  # auto | goldsrc_pvs
    build_cache = True
    if isinstance(vis_cfg, dict):
        if isinstance(vis_cfg.get("enabled"), bool):
            enabled = bool(vis_cfg.get("enabled"))
        m = vis_cfg.get("mode")
        if isinstance(m, str) and m.strip():
            mode = m.strip()
        if isinstance(vis_cfg.get("build_cache"), bool):
            build_cache = bool(vis_cfg.get("build_cache"))

    profile = getattr(cfg, "map_profile", "") or "prod-baked"
    if profile == MAP_PROFILE_DEV_FAST:
        enabled = False
    if not enabled:
        return None

    lm = payload.get("lightmaps")
    lm_encoding = lm.get("encoding") if isinstance(lm, dict) else None
    is_goldsrc = isinstance(lm_encoding, str) and lm_encoding.strip() == "goldsrc_rgb"

    if mode == "auto" and not is_goldsrc:
        return None
    if mode not in ("auto", "goldsrc_pvs"):
        return None

    cache_path = map_json.parent / "visibility.goldsrc.json"
    source_bsp = payload.get("source_bsp")
    source_bsp_path = Path(str(source_bsp)) if isinstance(source_bsp, str) and source_bsp.strip() else None
    if not build_cache:
        source_bsp_path = None
    try:
        return load_or_build_visibility_cache(cache_path=cache_path, source_bsp_path=source_bsp_path)
    except Exception:
        return None

