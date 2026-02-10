from __future__ import annotations

from pathlib import Path

from ivan.maps.bundle_io import PACKED_BUNDLE_EXT, MapFileHandle, resolve_bundle_handle_path
from ivan.paths import app_root as ivan_app_root


def resolve_map_bundle_path(map_ref: Path) -> Path | None:
    """
    Resolve map inputs to a concrete runtime map path.

    Supported inputs:
    - absolute/relative `map.json`
    - absolute/relative packed bundle (`.irunmap`)
    - absolute/relative `.map`
    - directory alias that contains `map.json`
    """
    candidates: list[Path] = []
    if map_ref.is_absolute():
        candidates.append(map_ref)
    else:
        candidates.append((Path.cwd() / map_ref).resolve())
        candidates.append((ivan_app_root() / "assets" / map_ref).resolve())

    expanded: list[Path] = []
    for c in candidates:
        expanded.append(c)
        suf = c.suffix.lower()
        if suf not in (".json", PACKED_BUNDLE_EXT, ".map"):
            expanded.append(c / "map.json")
            try:
                expanded.append(c.with_suffix(PACKED_BUNDLE_EXT))
            except Exception:
                pass

    for c in expanded:
        if not c.exists():
            continue
        if c.is_file() and c.suffix.lower() == ".map":
            return c
        if c.is_dir():
            h = resolve_bundle_handle_path(c)
            if h is None:
                continue
            if isinstance(h, MapFileHandle):
                return h.map_file
            return h.map_json
        if c.is_file():
            h = resolve_bundle_handle_path(c)
            if h is None:
                continue
            if isinstance(h, MapFileHandle):
                return h.map_file
            return h.map_json
    return None


def resolve_material_root(*, map_json: Path, payload: dict) -> Path | None:
    materials = payload.get("materials")
    if not isinstance(materials, dict):
        return None
    converted_root = materials.get("converted_root")
    if not isinstance(converted_root, str) or not converted_root.strip():
        return None

    raw = Path(converted_root)
    if not raw.is_absolute():
        cand = (map_json.parent / raw).resolve()
        if cand.exists():
            return cand
    app_root = ivan_app_root()
    cand = (app_root / raw).resolve()
    if cand.exists():
        return cand
    cand = (Path.cwd() / raw).resolve()
    if cand.exists():
        return cand
    return None


def resolve_lightmaps(*, map_json: Path, payload: dict) -> dict[int, dict] | None:
    lm = payload.get("lightmaps")
    if not isinstance(lm, dict):
        return None
    faces = lm.get("faces")
    if not isinstance(faces, dict) or not faces:
        return None

    def resolve_path(v: str) -> Path | None:
        raw = Path(v)
        if raw.is_absolute() and raw.exists():
            return raw
        cand = (map_json.parent / raw).resolve()
        if cand.exists():
            return cand
        app_root = ivan_app_root()
        cand = (app_root / raw).resolve()
        if cand.exists():
            return cand
        cand = (Path.cwd() / raw).resolve()
        if cand.exists():
            return cand
        return None

    out: dict[int, dict] = {}
    for k, v in faces.items():
        try:
            idx = int(k)
        except Exception:
            continue
        if isinstance(v, str) and v.strip():
            p = resolve_path(v.strip())
            if p:
                out[idx] = {"paths": [p, None, None, None], "styles": [0, None, None, None]}
            continue
        if isinstance(v, dict):
            paths = v.get("paths")
            styles = v.get("styles")
            if not (isinstance(paths, list) and len(paths) == 4):
                continue
            if not (isinstance(styles, list) and len(styles) == 4):
                styles = [0, None, None, None]
            resolved: list[Path | None] = [None, None, None, None]
            for i in range(4):
                pv = paths[i]
                if isinstance(pv, str) and pv.strip():
                    resolved[i] = resolve_path(pv.strip())
            if not any(isinstance(p, Path) for p in resolved):
                continue
            out[idx] = {"paths": resolved, "styles": list(styles)}
    return out or None


def build_material_texture_index(root: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    if not root.exists():
        return index
    for p in root.rglob("*.png"):
        rel = p.relative_to(root)
        key = str(rel.with_suffix("")).replace("\\", "/").casefold()
        index[key] = p
    return index


def resolve_material_texture_path(
    *,
    material_name: str,
    materials_meta: dict[str, dict] | None,
    material_texture_index: dict[str, Path],
) -> Path | None:
    keys: list[str] = []
    base = None
    if materials_meta and isinstance(materials_meta.get(material_name), dict):
        base = materials_meta.get(material_name, {}).get("base_texture")
    if isinstance(base, str) and base.strip():
        keys.append(base.replace("\\", "/").casefold())
    keys.append(material_name.replace("\\", "/").casefold())

    extra: list[str] = []
    for k in keys:
        parts = [p for p in k.split("/") if p]
        if len(parts) >= 3 and parts[0] == "maps":
            stripped = "/".join(parts[2:])
            extra.append(stripped)
            extra.append(_strip_source_map_suffix(stripped))
        extra.append(_strip_source_map_suffix(k))
    for k in extra:
        if k and k not in keys:
            keys.append(k)

    for key in keys:
        p = material_texture_index.get(key)
        if p is not None:
            return p
    return None


def _strip_source_map_suffix(key: str) -> str:
    import re

    return re.sub(r"_-?\d+_-?\d+_-?\d+$", "", key)

