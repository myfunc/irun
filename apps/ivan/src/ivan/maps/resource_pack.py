"""Shared resource pack (.irunres) support for map runtime loading.

Schema: .irunres is a zip archive with manifest.json at root.
Cache: ~/.irun/ivan/cache/resource_packs/<pack_hash>/
"""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

from ivan.state import state_dir


PACKED_RESOURCE_EXT = ".irunres"
_MANIFEST_FILENAME = "manifest.json"
_SCHEMA_VERSION = "ivan.resource_pack.v1"
_CACHE_VERSION = 1


class MissingResourcePackAssetError(Exception):
    """Raised when a map references an asset_id that is not in any loaded pack."""

    def __init__(self, asset_id: str, missing_materials: list[str]) -> None:
        self.asset_id = asset_id
        self.missing_materials = missing_materials
        msg = (
            f"Resource pack asset missing: asset_id={asset_id!r} "
            f"(materials: {missing_materials[:5]}{'...' if len(missing_materials) > 5 else ''}). "
            "Ensure all resource packs are available and map asset_bindings are correct."
        )
        super().__init__(msg)


@dataclass(frozen=True)
class ResourcePackManifest:
    """Parsed manifest from a .irunres pack."""

    schema: str
    pack_hash: str
    assets: dict[str, str]  # asset_id -> path-in-archive (e.g. "brick" -> "textures/brick.png")


def _resource_pack_cache_root() -> Path:
    return state_dir() / "cache" / "resource_packs"


def _compute_pack_hash(pack_path: Path) -> str:
    """Content-addressable hash for a resource pack archive."""
    h = hashlib.sha256()
    with open(pack_path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    h.update(str(_CACHE_VERSION).encode("ascii"))
    return h.hexdigest()


def _validate_manifest(manifest: dict) -> ResourcePackManifest | None:
    """Parse and validate manifest; return None if invalid."""
    schema = manifest.get("schema")
    if not isinstance(schema, str) or schema != _SCHEMA_VERSION:
        return None
    pack_hash = manifest.get("pack_hash")
    if not isinstance(pack_hash, str) or not pack_hash.strip():
        return None
    assets_raw = manifest.get("assets")
    if not isinstance(assets_raw, dict):
        return None
    assets: dict[str, str] = {}
    for k, v in assets_raw.items():
        if isinstance(k, str) and isinstance(v, str) and k.strip() and v.strip():
            assets[k.strip()] = v.strip()
    return ResourcePackManifest(schema=schema, pack_hash=pack_hash.strip(), assets=assets)


def ensure_pack_extracted(pack_ref: Path) -> Path:
    """
    Extract a .irunres pack to cache and return the cache root.

    Uses pack content hash for cache key. Reuses existing extraction when valid.
    """
    pack_ref = Path(pack_ref).resolve()
    if not pack_ref.exists() or not pack_ref.is_file():
        raise FileNotFoundError(f"Resource pack not found: {pack_ref}")
    if pack_ref.suffix.lower() != PACKED_RESOURCE_EXT:
        raise ValueError(f"Not a resource pack (expected {PACKED_RESOURCE_EXT}): {pack_ref}")

    content_hash = _compute_pack_hash(pack_ref)
    cache_root = _resource_pack_cache_root() / content_hash
    marker_path = cache_root / ".cache_hash"

    if marker_path.exists():
        try:
            if marker_path.read_text(encoding="utf-8").strip() == content_hash:
                return cache_root
        except Exception:
            pass
        shutil.rmtree(cache_root, ignore_errors=True)

    cache_root.parent.mkdir(parents=True, exist_ok=True)
    cache_root.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(pack_ref, "r") as zf:
        namelist = zf.namelist()
        manifest_data = None
        for name in namelist:
            if name.rstrip("/") == _MANIFEST_FILENAME:
                manifest_data = zf.read(name).decode("utf-8")
                break
        if not manifest_data:
            raise ValueError(f"Resource pack missing {_MANIFEST_FILENAME}: {pack_ref}")

        parsed = json.loads(manifest_data)
        if not isinstance(parsed, dict):
            raise ValueError(f"Invalid manifest in {pack_ref}")
        manifest = _validate_manifest(parsed)
        if manifest is None:
            raise ValueError(f"Invalid manifest schema in {pack_ref}")

        for info in zf.infolist():
            name = info.filename
            if not name or name.endswith("/"):
                continue
            rel = Path(name)
            if rel.is_absolute() or ".." in rel.parts:
                continue
            dst = (cache_root / rel).resolve()
            try:
                dst.relative_to(cache_root.resolve())
            except ValueError:
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info, "r") as src, open(dst, "wb") as f:
                shutil.copyfileobj(src, f)

    try:
        (cache_root / ".cache_hash").write_text(content_hash + "\n", encoding="utf-8")
    except Exception:
        pass

    return cache_root


def resolve_asset_from_pack(cache_root: Path, asset_id: str) -> Path | None:
    """Return path to asset file in extracted pack, or None if not found."""
    manifest_path = cache_root / _MANIFEST_FILENAME
    if not manifest_path.exists():
        return None
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = _validate_manifest(raw) if isinstance(raw, dict) else None
        if manifest is None:
            return None
        rel = manifest.assets.get(asset_id)
        if not rel:
            return None
        p = (cache_root / rel).resolve()
        if p.exists() and p.is_file():
            return p
    except Exception:
        pass
    return None


def resolve_materials_from_resource_packs(
    *,
    resource_packs: list[str],
    asset_bindings: dict[str, str],
    map_json: Path,
) -> dict[str, Path]:
    """
    Resolve material_name -> Path for all materials using resource packs.

    resource_packs: list of paths or pack identifiers (paths to .irunres).
    asset_bindings: material_name -> asset_id.

    Raises MissingResourcePackAssetError if any material's asset is not found.
    """
    pack_roots: list[Path] = []
    for ref in resource_packs:
        if not isinstance(ref, str) or not ref.strip():
            continue
        p = Path(ref.strip())
        if not p.is_absolute():
            candidates = [
                map_json.parent / p,
                (map_json.parent / p).resolve(),
            ]
            for c in candidates:
                if c.exists() and c.is_file():
                    p = c
                    break
        try:
            root = ensure_pack_extracted(p)
            pack_roots.append(root)
        except Exception as e:
            raise MissingResourcePackAssetError(
                asset_id="", missing_materials=[f"Failed to load pack {ref!r}: {e}"]
            ) from e

    index: dict[str, Path] = {}
    missing: list[tuple[str, str]] = []  # (material_name, asset_id)

    for mat_name, asset_id in asset_bindings.items():
        if not isinstance(mat_name, str) or not isinstance(asset_id, str):
            continue
        mat_key = mat_name.replace("\\", "/").casefold()
        if mat_key in index:
            continue
        for root in pack_roots:
            path = resolve_asset_from_pack(root, asset_id)
            if path is not None:
                index[mat_key] = path
                break
        else:
            missing.append((mat_name, asset_id))

    if missing:
        by_asset: dict[str, list[str]] = {}
        for mn, aid in missing:
            by_asset.setdefault(aid, []).append(mn)
        first = next(iter(by_asset.items()))
        raise MissingResourcePackAssetError(asset_id=first[0], missing_materials=first[1])

    return index
