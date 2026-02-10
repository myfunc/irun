from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

# Fields recognised in a .material.json file and the corresponding
# MaterialDef attribute they map to.  Texture map fields point to image
# files that are resolved relative to the material directory.
_TEXTURE_FIELDS: dict[str, str] = {
    "albedo": "albedo_path",
    "normal": "normal_path",
    "roughness": "roughness_path",
    "metallic": "metallic_path",
    "emission": "emission_path",
}

_VALID_ALPHA_MODES: frozenset[str] = frozenset({"opaque", "binary", "blend"})


@dataclass(frozen=True)
class MaterialDef:
    """Material definition for a single texture.

    All texture paths are resolved to absolute :class:`~pathlib.Path` objects
    (or ``None`` when a particular map is not present in the definition).

    Scalar fallback values (``roughness_value``, ``metallic_value``) are used
    by the renderer when the corresponding texture map is absent.
    """

    name: str  # texture name (e.g. "brick")

    # -- texture maps (absolute paths or None) --
    albedo_path: Path | None = None
    normal_path: Path | None = None
    roughness_path: Path | None = None
    metallic_path: Path | None = None
    emission_path: Path | None = None

    # -- rendering properties --
    alpha_mode: str = "opaque"  # "opaque" | "binary" | "blend"
    double_sided: bool = False
    roughness_value: float = 0.8  # fallback roughness (when no map)
    metallic_value: float = 0.0  # fallback metallic (when no map)


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------


class MaterialResolver:
    """Resolve material definitions from one or more material directories.

    The resolver scans for ``<texture_name>.material.json`` files in the
    configured directories and builds :class:`MaterialDef` instances with
    fully-resolved absolute paths.  Results are cached so each texture name
    is only parsed once.

    Typical usage::

        resolver = MaterialResolver([game_materials_dir, bundle_materials_dir])
        mat = resolver.resolve("brick", albedo_path=wad_albedo)
    """

    def __init__(self, materials_dirs: list[Path]) -> None:
        """
        Args:
            materials_dirs: Directories to search for ``.material.json`` files
                and texture images.  Searched in order; the first matching
                definition wins.
        """
        # Normalise to resolved Path objects so later comparisons are stable.
        self._dirs: list[Path] = [Path(d).resolve() for d in materials_dirs]

        # Cache: texture name (casefolded) -> MaterialDef | None
        # A value of None means "we looked and found nothing" (negative cache).
        self._cache: dict[str, MaterialDef | None] = {}

        # Pre-build a case-insensitive index of .material.json files so that
        # every resolve() call doesn't need to re-scan the filesystem.
        # key: casefolded stem  ->  value: absolute path to the json file
        self._json_index: dict[str, Path] = self._build_json_index()

    # -- public API ---------------------------------------------------------

    def resolve(
        self,
        texture_name: str,
        *,
        albedo_path: Path | None = None,
    ) -> MaterialDef:
        """Resolve a material definition for *texture_name*.

        Args:
            texture_name: The texture name from the ``.map`` file (e.g.
                ``"brick"``).
            albedo_path: Pre-resolved albedo texture path (e.g. extracted
                from a WAD file).  Used as the albedo when a
                ``.material.json`` does not specify one.

        Returns:
            A :class:`MaterialDef` with all available paths resolved.
            If no ``.material.json`` exists a basic ``MaterialDef`` with
            only the albedo is returned.
        """
        key = texture_name.casefold()

        if key in self._cache:
            cached = self._cache[key]
            if cached is not None:
                # If the caller provides an albedo and the cached def has none,
                # patch it in (common when WAD extraction happens after the
                # first resolve call).
                if albedo_path is not None and cached.albedo_path is None:
                    cached = MaterialDef(
                        name=cached.name,
                        albedo_path=albedo_path,
                        normal_path=cached.normal_path,
                        roughness_path=cached.roughness_path,
                        metallic_path=cached.metallic_path,
                        emission_path=cached.emission_path,
                        alpha_mode=cached.alpha_mode,
                        double_sided=cached.double_sided,
                        roughness_value=cached.roughness_value,
                        metallic_value=cached.metallic_value,
                    )
                    self._cache[key] = cached
                return cached
            # Negative cache hit – no .material.json found earlier.
            return MaterialDef(name=texture_name, albedo_path=albedo_path)

        # Try to locate and load a .material.json.
        json_path = self._find_material_json(texture_name)
        if json_path is not None:
            mat = self._load_material_json(json_path, texture_name, albedo_path=albedo_path)
            self._cache[key] = mat
            return mat

        # No definition found – negative cache.
        self._cache[key] = None
        return MaterialDef(name=texture_name, albedo_path=albedo_path)

    # -- private helpers ----------------------------------------------------

    def _build_json_index(self) -> dict[str, Path]:
        """Scan all material directories for .material.json files.

        Returns a dict mapping *casefolded* texture names to their
        ``.material.json`` paths.  The first directory in the search
        list takes priority (earlier entry wins).
        """
        index: dict[str, Path] = {}
        for d in self._dirs:
            if not d.is_dir():
                continue
            for p in d.iterdir():
                if not p.is_file():
                    continue
                # Expected pattern: <name>.material.json
                lname = p.name.lower()
                if not lname.endswith(".material.json"):
                    continue
                # Strip the compound suffix to get the texture stem.
                stem = p.name[: -len(".material.json")]
                cf = stem.casefold()
                # First directory wins – skip if already present.
                if cf not in index:
                    index[cf] = p.resolve()
        return index

    def _find_material_json(self, texture_name: str) -> Path | None:
        """Find a ``.material.json`` file for *texture_name* (case-insensitive).

        Uses the pre-built index for O(1) lookup.
        """
        return self._json_index.get(texture_name.casefold())

    def _load_material_json(
        self,
        json_path: Path,
        texture_name: str,
        *,
        albedo_path: Path | None = None,
    ) -> MaterialDef:
        """Parse a ``.material.json`` file into a :class:`MaterialDef`.

        On any parse error the method logs a warning and returns a
        default ``MaterialDef`` with just the albedo.
        """
        try:
            raw = json_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if not isinstance(data, dict):
                logger.warning(
                    "material_defs: %s – expected JSON object, got %s; using defaults",
                    json_path,
                    type(data).__name__,
                )
                return MaterialDef(name=texture_name, albedo_path=albedo_path)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(
                "material_defs: failed to read %s: %s; using defaults",
                json_path,
                exc,
            )
            return MaterialDef(name=texture_name, albedo_path=albedo_path)

        # The directory that contains the .material.json is the reference
        # root for resolving relative texture paths.
        base_dir = json_path.parent

        # -- resolve texture paths ------------------------------------------
        resolved_paths: dict[str, Path | None] = {}
        for json_key, attr_name in _TEXTURE_FIELDS.items():
            rel = data.get(json_key)
            if rel is None:
                resolved_paths[attr_name] = None
                continue
            if not isinstance(rel, str) or not rel.strip():
                resolved_paths[attr_name] = None
                continue
            # Normalise path separators and resolve relative to base_dir.
            tex_path = (base_dir / Path(rel.replace("\\", "/"))).resolve()
            resolved_paths[attr_name] = tex_path

        # If the json didn't provide an albedo, fall back to the caller-
        # provided path (typically extracted from a WAD).
        if resolved_paths.get("albedo_path") is None:
            resolved_paths["albedo_path"] = albedo_path

        # -- alpha mode -----------------------------------------------------
        alpha_mode_raw = data.get("alpha_mode", "opaque")
        if not isinstance(alpha_mode_raw, str) or alpha_mode_raw not in _VALID_ALPHA_MODES:
            logger.warning(
                "material_defs: %s – invalid alpha_mode %r; defaulting to 'opaque'",
                json_path,
                alpha_mode_raw,
            )
            alpha_mode_raw = "opaque"

        # -- boolean / scalar properties ------------------------------------
        double_sided = bool(data.get("double_sided", False))

        roughness_value = _clamp_float(data.get("roughness_value", 0.8), 0.0, 1.0)
        metallic_value = _clamp_float(data.get("metallic_value", 0.0), 0.0, 1.0)

        return MaterialDef(
            name=texture_name,
            albedo_path=resolved_paths.get("albedo_path"),
            normal_path=resolved_paths.get("normal_path"),
            roughness_path=resolved_paths.get("roughness_path"),
            metallic_path=resolved_paths.get("metallic_path"),
            emission_path=resolved_paths.get("emission_path"),
            alpha_mode=alpha_mode_raw,
            double_sided=double_sided,
            roughness_value=roughness_value,
            metallic_value=metallic_value,
        )


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _clamp_float(value: object, lo: float, hi: float) -> float:
    """Coerce *value* to a float clamped to [*lo*, *hi*].

    Non-numeric values silently fall back to *lo*.
    """
    try:
        f = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return lo
    return max(lo, min(hi, f))
