"""Valve 220 .map file parser (TrenchBroom / Quake family).

Parses the text-based ``.map`` format used by TrenchBroom, J.A.C.K., and other
Quake-family level editors.  The parser targets the **Valve 220** texture-axis
variant (``[ ux uy uz offset ]``) and will degrade gracefully when encountering
the older Standard format (three-float texture fields without brackets).

References
----------
- Quake Map Format Spec (various community docs)
- TrenchBroom documentation: https://trenchbroom.github.io/

Usage::

    from ivan.maps.map_parser import parse_map, MapEntity

    with open("mymap.map", encoding="utf-8", errors="replace") as fh:
        entities = parse_map(fh.read())

    for ent in entities:
        print(ent.properties.get("classname", "<no classname>"))
        print(f"  {len(ent.brushes)} brush(es)")
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterator


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Vec3:
    """Three-component vector / point."""

    x: float
    y: float
    z: float


@dataclass
class BrushFace:
    """A single half-plane of a convex brush.

    Valve 220 texture projection stores explicit U/V axis vectors and offsets
    rather than the simpler rotation-based Standard format.
    """

    plane_points: tuple[Vec3, Vec3, Vec3]
    texture: str
    u_axis: Vec3
    u_offset: float
    v_axis: Vec3
    v_offset: float
    rotation: float
    scale_x: float
    scale_y: float


@dataclass
class Brush:
    """A convex solid defined by a set of half-planes (faces)."""

    faces: list[BrushFace] = field(default_factory=list)


@dataclass
class MapEntity:
    """One entity block from a ``.map`` file.

    ``properties`` holds the key/value pairs (e.g. ``classname``, ``origin``).
    ``brushes`` holds the solid geometry owned by this entity (may be empty
    for point entities).
    """

    properties: dict[str, str] = field(default_factory=dict)
    brushes: list[Brush] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Tokeniser helpers
# ---------------------------------------------------------------------------

# Matches a Valve-220 face line.  Captured groups:
#   1-9   : three plane points  (x1 y1 z1  x2 y2 z2  x3 y3 z3)
#   10    : texture name
#   11-14 : u_axis (ux uy uz) + offset
#   15-18 : v_axis (vx vy vz) + offset
#   19    : rotation
#   20    : scale_x
#   21    : scale_y
_FLOAT = r"([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)"
_POINT = rf"\(\s*{_FLOAT}\s+{_FLOAT}\s+{_FLOAT}\s*\)"
_TEX = r"(\S+)"
_AXIS = rf"\[\s*{_FLOAT}\s+{_FLOAT}\s+{_FLOAT}\s+{_FLOAT}\s*\]"

_VALVE_FACE_RE = re.compile(
    rf"\s*{_POINT}\s+{_POINT}\s+{_POINT}"            # 3 plane points (groups 1-9)
    rf"\s+{_TEX}"                                      # texture name  (group 10)
    rf"\s+{_AXIS}"                                     # U axis+offset (groups 11-14)
    rf"\s+{_AXIS}"                                     # V axis+offset (groups 15-18)
    rf"\s+{_FLOAT}"                                    # rotation      (group 19)
    rf"\s+{_FLOAT}"                                    # scale_x       (group 20)
    rf"\s+{_FLOAT}"                                    # scale_y       (group 21)
)

# Standard (non-Valve) face line: tex offsetX offsetY rotation scaleX scaleY
_STD_FACE_RE = re.compile(
    rf"\s*{_POINT}\s+{_POINT}\s+{_POINT}"
    rf"\s+{_TEX}"
    rf"\s+{_FLOAT}\s+{_FLOAT}\s+{_FLOAT}\s+{_FLOAT}\s+{_FLOAT}"
)


def _parse_valve_face(m: re.Match[str]) -> BrushFace:
    """Build a :class:`BrushFace` from a Valve 220 regex match."""

    g = [m.group(i) for i in range(1, 22)]
    f = [float(v) for v in g[:9]]  # plane points
    texture = g[9]
    uv = [float(v) for v in g[10:]]

    return BrushFace(
        plane_points=(
            Vec3(f[0], f[1], f[2]),
            Vec3(f[3], f[4], f[5]),
            Vec3(f[6], f[7], f[8]),
        ),
        texture=texture,
        u_axis=Vec3(uv[0], uv[1], uv[2]),
        u_offset=uv[3],
        v_axis=Vec3(uv[4], uv[5], uv[6]),
        v_offset=uv[7],
        rotation=uv[8],
        scale_x=uv[9],
        scale_y=uv[10],
    )


def _parse_standard_face(m: re.Match[str]) -> BrushFace:
    """Build a :class:`BrushFace` from a Standard-format regex match.

    The Standard format does not carry explicit UV axes; we synthesise
    trivial axes from the face normal so that downstream code can still
    produce *some* UVs (they will look wrong for non-axis-aligned faces,
    but this keeps the pipeline running).
    """

    g = [m.group(i) for i in range(1, 15)]
    f = [float(v) for v in g[:9]]
    texture = g[9]
    rest = [float(v) for v in g[10:]]

    # rest: offsetX offsetY rotation scaleX scaleY
    off_x, off_y, rotation, sx, sy = rest

    # Derive a crude U/V basis from the plane normal.
    p0 = Vec3(f[0], f[1], f[2])
    p1 = Vec3(f[3], f[4], f[5])
    p2 = Vec3(f[6], f[7], f[8])
    normal = _cross(
        Vec3(p1.x - p0.x, p1.y - p0.y, p1.z - p0.z),
        Vec3(p2.x - p0.x, p2.y - p0.y, p2.z - p0.z),
    )
    u_axis, v_axis = _basis_from_normal(normal)

    return BrushFace(
        plane_points=(p0, p1, p2),
        texture=texture,
        u_axis=u_axis,
        u_offset=off_x,
        v_axis=v_axis,
        v_offset=off_y,
        rotation=rotation,
        scale_x=sx if sx != 0 else 1.0,
        scale_y=sy if sy != 0 else 1.0,
    )


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return Vec3(
        a.y * b.z - a.z * b.y,
        a.z * b.x - a.x * b.z,
        a.x * b.y - a.y * b.x,
    )


def _basis_from_normal(n: Vec3) -> tuple[Vec3, Vec3]:
    """Return a rough tangent/bitangent pair for a face normal.

    Chooses the closest world axis to avoid degenerate cross products.
    """

    ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
    if az >= ax and az >= ay:
        # Mostly Z-facing -> use X as U.
        up = Vec3(0.0, 1.0, 0.0)
    elif ay >= ax:
        # Mostly Y-facing -> use X as U.
        up = Vec3(0.0, 0.0, 1.0)
    else:
        # Mostly X-facing -> use Y as U.
        up = Vec3(0.0, 0.0, 1.0)

    u = _cross(n, up)
    v = _cross(n, u)
    return u, v


# ---------------------------------------------------------------------------
# Key / value pair parser
# ---------------------------------------------------------------------------

_KV_RE = re.compile(r'"([^"]*?)"\s+"([^"]*?)"')


# ---------------------------------------------------------------------------
# Line iteration helpers
# ---------------------------------------------------------------------------

def _strip_comments(text: str) -> Iterator[str]:
    """Yield non-empty, non-comment lines from *text*."""

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("//"):
            continue
        # Inline comments (rare but possible).
        idx = line.find("//")
        if idx != -1:
            # Only strip if "//" is not inside a quoted string.  A rough
            # heuristic: count quotes before idx.
            if line[:idx].count('"') % 2 == 0:
                line = line[:idx].rstrip()
        if line:
            yield line


# ---------------------------------------------------------------------------
# Public parser
# ---------------------------------------------------------------------------

def parse_map(text: str) -> list[MapEntity]:
    """Parse a Valve 220 / Standard ``.map`` file and return entities.

    Parameters
    ----------
    text:
        The full text content of the ``.map`` file.

    Returns
    -------
    list[MapEntity]
        A flat list of parsed entities, each with its properties and brushes.
        The first entity is typically ``worldspawn``.
    """

    entities: list[MapEntity] = []
    lines = list(_strip_comments(text))
    pos = 0
    total = len(lines)

    while pos < total:
        line = lines[pos]

        if line == "{":
            entity, pos = _parse_entity(lines, pos + 1)
            entities.append(entity)
        else:
            # Skip unexpected tokens outside entity blocks.
            pos += 1

    return entities


def _parse_entity(lines: list[str], pos: int) -> tuple[MapEntity, int]:
    """Parse a single entity block (already past the opening ``{``).

    Returns the entity and the index of the line *after* the closing ``}``.
    """

    ent = MapEntity()
    total = len(lines)

    while pos < total:
        line = lines[pos]

        if line == "}":
            return ent, pos + 1

        if line == "{":
            # Start of a brush definition.
            brush, pos = _parse_brush(lines, pos + 1)
            ent.brushes.append(brush)
            continue

        # Try key-value pair.
        kv = _KV_RE.match(line)
        if kv:
            ent.properties[kv.group(1)] = kv.group(2)
            pos += 1
            continue

        # Unknown line inside entity – skip.
        pos += 1

    return ent, pos


def _parse_brush(lines: list[str], pos: int) -> tuple[Brush, int]:
    """Parse a single brush block (already past the opening ``{``).

    Returns the brush and the index of the line *after* the closing ``}``.
    """

    brush = Brush()
    total = len(lines)

    while pos < total:
        line = lines[pos]

        if line == "}":
            return brush, pos + 1

        # Try Valve 220 format first (most common with TrenchBroom).
        m = _VALVE_FACE_RE.match(line)
        if m:
            brush.faces.append(_parse_valve_face(m))
            pos += 1
            continue

        # Fall back to Standard format.
        m = _STD_FACE_RE.match(line)
        if m:
            brush.faces.append(_parse_standard_face(m))
            pos += 1
            continue

        # Unrecognised face line – skip gracefully.
        pos += 1

    return brush, pos
