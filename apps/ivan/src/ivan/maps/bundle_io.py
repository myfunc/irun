from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

from ivan.state import resolve_map_json as _resolve_map_json
from ivan.state import state_dir


PACKED_BUNDLE_EXT = ".irunmap"
_CACHE_VERSION = 1


@dataclass(frozen=True)
class BundleHandle:
    """
    Resolved view of a runnable map bundle.

    - For directory bundles: `bundle_ref` is the directory root.
    - For packed bundles (.irunmap): `bundle_ref` is the .irunmap file and `map_json`
      points to an extracted-on-disk cache location.
    """

    bundle_ref: Path
    map_json: Path
    extracted_root: Path | None = None


def is_packed_bundle_path(p: Path) -> bool:
    return p.is_file() and p.suffix.lower() == PACKED_BUNDLE_EXT


def run_json_path_for_bundle_ref(bundle_ref: Path) -> Path:
    """
    Return the path where run metadata should be stored for a given bundle reference.

    - Directory bundle: <bundle>/run.json
    - Packed bundle (.irunmap): <bundle>.run.json (sidecar)
    - Single-file map json: <map-json-parent>/run.json
    """

    if bundle_ref.is_file() and bundle_ref.suffix.lower() == PACKED_BUNDLE_EXT:
        # Unambiguous sidecar filename that preserves the original archive name.
        return bundle_ref.with_name(bundle_ref.name + ".run.json")
    if bundle_ref.is_dir():
        return bundle_ref / "run.json"
    # e.g. assets/generated/*_map.json
    return bundle_ref.parent / "run.json"


def resolve_bundle_handle(map_json: str) -> BundleHandle | None:
    """
    Resolve a user-facing map selection (path/alias) into a runnable on-disk map.json.
    """

    p = _resolve_map_json(map_json)
    if p is None:
        return None
    return resolve_bundle_handle_path(p)


def resolve_bundle_handle_path(p: Path) -> BundleHandle | None:
    """
    Resolve a path into a runnable bundle handle.

    Supported inputs:
    - <bundle-dir> (implies <bundle-dir>/map.json)
    - <bundle-dir>/map.json
    - <bundle>.irunmap (packed bundle)
    - <something>_map.json (single-file generated bundle)
    """

    if p.exists() and p.is_dir():
        mj = p / "map.json"
        if mj.exists() and mj.is_file():
            return BundleHandle(bundle_ref=p, map_json=mj, extracted_root=None)
        return None

    if is_packed_bundle_path(p):
        root = _ensure_extracted_cache(p)
        mj = root / "map.json"
        if not mj.exists() or not mj.is_file():
            return None
        return BundleHandle(bundle_ref=p, map_json=mj, extracted_root=root)

    if p.exists() and p.is_file():
        # Treat any json file as a map manifest (historical: map.json, generated: *_map.json).
        if p.suffix.lower() == ".json":
            return BundleHandle(bundle_ref=p.parent, map_json=p, extracted_root=None)
    return None


def pack_bundle_dir_to_irunmap(*, bundle_dir: Path, out_path: Path, compresslevel: int = 1) -> None:
    """
    Pack a directory bundle into a single .irunmap zip archive.
    """

    bundle_dir = Path(bundle_dir)
    out_path = Path(out_path)
    if not bundle_dir.exists() or not bundle_dir.is_dir():
        raise ValueError(f"bundle_dir must be a directory: {bundle_dir}")
    map_json = bundle_dir / "map.json"
    if not map_json.exists() or not map_json.is_file():
        raise ValueError(f"bundle_dir missing map.json: {map_json}")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Write to a temp file first to avoid leaving partial archives on failures.
    tmp = out_path.with_name(out_path.name + ".tmp")
    if tmp.exists():
        try:
            tmp.unlink()
        except Exception:
            pass

    with zipfile.ZipFile(
        tmp,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=int(compresslevel),
    ) as zf:
        files = sorted([p for p in bundle_dir.rglob("*") if p.is_file()])
        for p in files:
            rel = p.relative_to(bundle_dir)
            zf.write(p, arcname=rel.as_posix())

    tmp.replace(out_path)


def _cache_root() -> Path:
    return state_dir() / "cache" / "bundles"


def _cache_key_for_packed_bundle(packed: Path) -> str:
    st = packed.stat()
    h = hashlib.sha256()
    # Path is included so two different archives with identical mtimes/sizes don't collide.
    h.update(str(packed.resolve()).encode("utf-8", errors="ignore"))
    h.update(b"\0")
    h.update(str(int(st.st_size)).encode("ascii"))
    h.update(b"\0")
    h.update(str(int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)))).encode("ascii"))
    h.update(b"\0")
    h.update(str(int(_CACHE_VERSION)).encode("ascii"))
    return h.hexdigest()


def _ensure_extracted_cache(packed: Path) -> Path:
    packed = Path(packed)
    if not zipfile.is_zipfile(packed):
        raise ValueError(f"Not a zip archive: {packed}")
    key = _cache_key_for_packed_bundle(packed)
    root = _cache_root() / key
    mj = root / "map.json"
    if mj.exists() and mj.is_file():
        return root

    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    root.parent.mkdir(parents=True, exist_ok=True)
    root.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(packed, "r") as zf:
        for info in zf.infolist():
            name = info.filename
            if not name or name.endswith("/"):
                continue
            # Basic zip-slip protection.
            rel = Path(name)
            if rel.is_absolute() or ".." in rel.parts:
                continue
            dst = (root / rel).resolve()
            try:
                dst.relative_to(root.resolve())
            except Exception:
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info, "r") as src, open(dst, "wb") as f:
                shutil.copyfileobj(src, f)

    # Marker for debugging/support.
    try:
        st = packed.stat()
        meta = {
            "source": str(packed),
            "size": int(st.st_size),
            "mtime_ns": int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9))),
            "cache_version": int(_CACHE_VERSION),
        }
        (root / ".irunmap-extracted.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception:
        pass

    return root

