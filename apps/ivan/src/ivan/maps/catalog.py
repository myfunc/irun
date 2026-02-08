from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ivan.ui.map_select_ui import MapEntry
from ivan.maps.bundle_io import PACKED_BUNDLE_EXT


@dataclass(frozen=True)
class MapBundle:
    """
    A runnable IVAN map bundle.

    Note: A bundle is identified by a map JSON file. Historically this was a
    `<bundle-dir>/map.json`, but we also allow standalone `*_map.json` files.
    """

    label: str
    map_json: str


def _is_under(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except Exception:
        return False


def _label_for_map_json(*, app_root: Path, map_json_path: Path) -> str:
    assets = app_root / "assets"
    p = map_json_path
    if _is_under(p, assets):
        rel = p.resolve().relative_to(assets.resolve())
        # Prefer directory label for `<dir>/map.json`; otherwise use file stem.
        if rel.name == "map.json" and rel.parent != Path("."):
            return rel.parent.as_posix()
        return rel.with_suffix("").as_posix()
    if p.name == "map.json":
        return p.parent.name
    return p.stem


def find_runnable_bundles(*, app_root: Path) -> list[MapBundle]:
    """
    Discover runnable map bundles shipped with the repo under `apps/ivan/assets/`.

    Sources:
    - `assets/imported/**/map.json` (GoldSrc/Xash3D imports)
    - `assets/imported/**/*.irunmap` (packed imports)
    - `assets/maps/**/map.json` (hand-authored bundles)
    - `assets/maps/**/*.irunmap` (packed bundles)
    - `assets/generated/*_map.json` (single-file generated bundles)
    """

    assets = app_root / "assets"
    candidates: list[Path] = []
    candidates.extend((assets / "imported").glob("**/map.json"))
    candidates.extend((assets / "imported").glob(f"**/*{PACKED_BUNDLE_EXT}"))
    candidates.extend((assets / "maps").glob("**/map.json"))
    candidates.extend((assets / "maps").glob(f"**/*{PACKED_BUNDLE_EXT}"))
    candidates.extend((assets / "generated").glob("*_map.json"))

    out: list[MapBundle] = []
    for p in candidates:
        if not p.is_file():
            continue
        out.append(
            MapBundle(
                label=_label_for_map_json(app_root=app_root, map_json_path=p),
                map_json=str(p),
            )
        )
    out.sort(key=lambda b: b.label.lower())
    return out


def detect_goldsrc_like_mods(*, game_root: Path) -> list[str]:
    """
    Detect mod folders within a GoldSrc/Xash3D-style game install root.

    A "mod" is any direct subfolder that contains `maps/*.bsp`.
    """

    root = resolve_goldsrc_install_root(game_root)
    if root is None:
        return []
    mods: list[str] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        maps_dir = child / "maps"
        if maps_dir.is_dir() and any(maps_dir.glob("*.bsp")):
            mods.append(child.name)
    return mods


def list_goldsrc_like_maps(*, game_root: Path, mod: str) -> list[MapEntry]:
    root = resolve_goldsrc_install_root(game_root)
    if root is None:
        return []
    maps_dir = root / mod / "maps"
    if not maps_dir.exists():
        return []
    out: list[MapEntry] = []
    for p in sorted(maps_dir.glob("*.bsp")):
        out.append(MapEntry(label=p.stem, bsp_path=str(p)))
    return out


def resolve_goldsrc_install_root(game_root: Path) -> Path | None:
    """
    Best-effort resolver for GoldSrc/Xash3D install roots.

    Users may point at:
    - a standard install root: `<root>/<mod>/maps/*.bsp` (Windows/Linux common)
    - a macOS app bundle: `<root>/*.app` or `<root>/<Game>.app/Contents/Resources/<mod>/maps/*.bsp`

    The importer expects `--game-root` to be a directory that directly contains mod folders.
    """

    root = Path(game_root)
    if not root.exists():
        return None

    def has_any_mods(cand: Path) -> bool:
        try:
            if not cand.exists() or not cand.is_dir():
                return False
            for child in cand.iterdir():
                if not child.is_dir():
                    continue
                maps_dir = child / "maps"
                if maps_dir.is_dir() and any(maps_dir.glob("*.bsp")):
                    return True
            return False
        except Exception:
            return False

    # 1) Direct root.
    if has_any_mods(root):
        return root

    # 2) User picked the .app itself.
    if root.suffix.lower() == ".app":
        resources = root / "Contents" / "Resources"
        if has_any_mods(resources):
            return resources

    # 3) User picked a folder that contains the .app (typical Steam "common/<Game>" on macOS).
    try:
        for app in sorted(root.glob("*.app")):
            resources = app / "Contents" / "Resources"
            if has_any_mods(resources):
                return resources
    except Exception:
        pass

    # Fall back to the provided root (even if it has no mods); callers may show a better error.
    return root
