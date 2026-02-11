"""Sync TrenchBroom profile from resource-pack manifests.

Reads pack manifests (derived from assets, maps, WADs) and generates
editor-consumable outputs under apps/ivan/trenchbroom/generated/.

Usage::

    python tools/sync_trenchbroom_profile.py [--assets path] [--output path] [--dry-run]

Outputs:
- trenchbroom/generated/manifest.json: textures, entities, wad paths
- trenchbroom/generated/editor_paths.json: paths for GameConfig / game path
- trenchbroom/generated/textures/: direct-folder PNG copies (no WAD generation)
- assets/textures_tb/: TrenchBroom materials folder consumed by GameConfig.cfg

Direct-folder texture mode: textures are available as loose PNGs in generated/
for tooling and mirrored to assets/textures_tb for TrenchBroom.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Project imports
# ---------------------------------------------------------------------------

_TOOLS_DIR = Path(__file__).resolve().parent
_APPS_SRC = _TOOLS_DIR.parent / "src"
if str(_APPS_SRC) not in sys.path:
    sys.path.insert(0, str(_APPS_SRC))

from ivan.maps.map_parser import parse_map
from ivan.paths import app_root

_GOLDSRC_DIR = _TOOLS_DIR / "importers" / "goldsrc"
if str(_GOLDSRC_DIR) not in sys.path:
    sys.path.insert(0, str(_GOLDSRC_DIR))

try:
    from goldsrc_wad import Wad3
except ImportError:
    Wad3 = None  # type: ignore[assignment,misc]

try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Manifest building
# ---------------------------------------------------------------------------


def _collect_texture_names_from_map(map_text: str) -> set[str]:
    """Gather texture names referenced by brush faces in a .map file."""
    names: set[str] = set()
    for ent in parse_map(map_text):
        for brush in ent.brushes:
            for face in brush.faces:
                if face.texture:
                    names.add(face.texture)
    return names


def _collect_entity_classnames_from_map(map_text: str) -> set[str]:
    """Gather entity classnames from a .map file."""
    names: set[str] = set()
    for ent in parse_map(map_text):
        cn = ent.properties.get("classname", "").strip()
        if cn:
            names.add(cn)
    return names


def _collect_textures_from_wad(wad_path: Path) -> set[str]:
    """List texture names inside a WAD file."""
    if Wad3 is None:
        return set()
    try:
        wad = Wad3.load(wad_path)
        return {tex.name for tex in wad.iter_textures()}
    except Exception:
        return set()


def _collect_png_textures(assets_root: Path) -> dict[str, Path]:
    """Scan assets/raw for PNG textures; return {basename_stem: path}."""
    result: dict[str, Path] = {}
    raw_dir = assets_root / "raw"
    if not raw_dir.is_dir():
        return result
    for p in raw_dir.rglob("*.png"):
        stem = p.stem
        if stem and stem not in result:
            result[stem] = p
    return result


def _discover_maps(assets_root: Path) -> list[Path]:
    """Find all .map files under assets/maps (excludes autosave)."""
    maps_dir = assets_root / "maps"
    if not maps_dir.is_dir():
        return []
    return sorted(
        p for p in maps_dir.rglob("*.map")
        if "autosave" not in p.parts
    )


def _discover_wads(assets_root: Path) -> list[Path]:
    """Find all .wad files under assets/textures."""
    tex_dir = assets_root / "textures"
    if not tex_dir.is_dir():
        return []
    return sorted(tex_dir.glob("*.wad"))


def build_manifest(
    *,
    assets_root: Path,
    maps: list[Path] | None = None,
    wads: list[Path] | None = None,
) -> dict:
    """Build a pack manifest from assets, maps, and WADs."""
    maps = maps or _discover_maps(assets_root)
    wads = wads or _discover_wads(assets_root)

    texture_names: set[str] = set()
    entity_classnames: set[str] = set()
    wad_textures: dict[str, list[str]] = {}
    map_sources: list[dict] = []

    for wad_path in wads:
        tex_set = _collect_textures_from_wad(wad_path)
        wad_textures[str(wad_path)] = sorted(tex_set)
        texture_names.update(tex_set)

    for map_path in maps:
        try:
            text = map_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        tex = _collect_texture_names_from_map(text)
        ent = _collect_entity_classnames_from_map(text)
        texture_names.update(tex)
        entity_classnames.update(ent)
        map_sources.append({
            "path": str(map_path),
            "textures": len(tex),
            "entities": len(ent),
        })

    png_textures = _collect_png_textures(assets_root)
    texture_names.update(png_textures.keys())

    return {
        "version": 1,
        "textures": {
            "names": sorted(texture_names),
            "count": len(texture_names),
            "wads": {k: v for k, v in wad_textures.items()},
            "png_sources": {k: str(v) for k, v in png_textures.items()},
        },
        "entities": {
            "classnames": sorted(entity_classnames),
            "count": len(entity_classnames),
        },
        "maps": map_sources,
        "sources": {
            "assets_root": str(assets_root),
            "maps_count": len(maps),
            "wads_count": len(wads),
        },
    }


def extract_wad_textures_to_folder(
    wad_paths: list[Path],
    out_dir: Path,
    texture_names: set[str] | None = None,
) -> int:
    """Extract textures from WAD files to out_dir as PNG. Returns count extracted."""
    if Wad3 is None or Image is None:
        return 0
    extracted = 0
    used_cf = {n.casefold() for n in (texture_names or set())} if texture_names else None
    for wad_path in wad_paths:
        try:
            wad = Wad3.load(wad_path)
        except Exception:
            continue
        for tex in wad.iter_textures():
            if used_cf is not None and tex.name.casefold() not in used_cf:
                continue
            dst = out_dir / f"{tex.name}.png"
            if dst.exists():
                continue
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                img = Image.frombytes("RGBA", (tex.width, tex.height), tex.rgba)
                img.save(dst)
                extracted += 1
            except Exception:
                pass
    return extracted


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def generate(
    *,
    assets_root: Path,
    output_dir: Path,
    extract_textures: bool = True,
    dry_run: bool = False,
) -> dict:
    """Generate trenchbroom profile outputs. Returns generation report."""
    manifest = build_manifest(assets_root=assets_root)
    texture_names = set(manifest["textures"]["names"])
    wad_paths = [Path(p) for p in manifest["textures"]["wads"].keys() if Path(p).exists()]
    editor_materials_dir = assets_root / "textures_tb"

    report: dict = {
        "manifest": manifest,
        "extracted": 0,
        "files_written": [],
    }

    if dry_run:
        report["dry_run"] = True
        return report

    output_dir.mkdir(parents=True, exist_ok=True)
    textures_dir = output_dir / "textures"
    # Keep materials root stable for TrenchBroom even when there are
    # no extracted/copied textures in the current run.
    textures_dir.mkdir(parents=True, exist_ok=True)
    editor_materials_dir.mkdir(parents=True, exist_ok=True)
    if extract_textures and wad_paths:
        report["extracted"] = extract_wad_textures_to_folder(
            wad_paths, textures_dir, texture_names
        )
        report["extracted"] += extract_wad_textures_to_folder(
            wad_paths, editor_materials_dir, texture_names
        )

    # Copy PNG sources into generated/textures for direct-folder mode
    png_sources = manifest["textures"].get("png_sources", {})
    for name, src_path in png_sources.items():
        src = Path(src_path)
        if src.exists():
            dst = textures_dir / f"{name}.png"
            editor_dst = editor_materials_dir / f"{name}.png"
            if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
                textures_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                report["extracted"] += 1
                report["files_written"].append(str(dst))
            if not editor_dst.exists() or editor_dst.stat().st_mtime < src.stat().st_mtime:
                editor_materials_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, editor_dst)
                report["extracted"] += 1
                report["files_written"].append(str(editor_dst))

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    report["files_written"].append(str(manifest_path))

    assets_abs = assets_root.resolve()
    editor_paths = {
        "game_path": str(assets_abs),
        "generated_root": str(output_dir.resolve()),
        "textures_dir": str(editor_materials_dir.resolve()) if editor_materials_dir.exists() else None,
        "generated_textures_dir": str(textures_dir.resolve()) if textures_dir.exists() else None,
        "wad_paths": [str(p.resolve()) for p in wad_paths if p.exists()],
        "fgd_path": str(output_dir.parent / "ivan.fgd"),
    }
    editor_paths_path = output_dir / "editor_paths.json"
    editor_paths_path.write_text(
        json.dumps(editor_paths, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    report["files_written"].append(str(editor_paths_path))

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sync TrenchBroom profile from resource-pack manifests.",
    )
    parser.add_argument(
        "--assets",
        type=Path,
        default=None,
        help="Assets root (default: apps/ivan/assets).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output directory (default: trenchbroom/generated).",
    )
    parser.add_argument(
        "--no-extract",
        action="store_true",
        help="Skip WAD texture extraction (manifest only).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build manifest only, do not write files.",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    assets_root = args.assets or (app_root() / "assets")
    output_dir = args.output or (app_root() / "trenchbroom" / "generated")

    if not assets_root.is_dir():
        print(f"[sync] ERROR: assets root not found: {assets_root}")
        sys.exit(1)

    print(f"[sync] Assets  : {assets_root}")
    print(f"[sync] Output  : {output_dir}")
    print(f"[sync] Dry run : {args.dry_run}")

    report = generate(
        assets_root=assets_root,
        output_dir=output_dir,
        extract_textures=not args.no_extract,
        dry_run=args.dry_run,
    )

    m = report["manifest"]
    print(f"\n[sync] Manifest: {m['textures']['count']} textures, {m['entities']['count']} entities")
    print(f"[sync] Maps    : {len(m['maps'])}")
    if not args.dry_run:
        print(f"[sync] Extracted: {report['extracted']} textures")
        print(f"[sync] Written : {len(report['files_written'])} files")
        print(f"[sync] Done: {output_dir}")


if __name__ == "__main__":
    main()
