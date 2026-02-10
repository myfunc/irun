"""Brush-to-triangle mesh conversion (CSG half-plane clipping).

Converts :class:`~ivan.maps.map_parser.Brush` definitions into renderable
triangle meshes suitable for Panda3D.  The algorithm:

1. Derive a plane equation (normal + distance) from the three points on each
   brush face.
2. Create a large initial polygon lying on that plane.
3. Clip the polygon against every *other* plane in the brush using
   Sutherland-Hodgman clipping.  The result is the visible winding for that
   face.
4. Fan-triangulate each convex polygon.
5. Compute Valve-220 UVs from the face texture-axis data.
6. Optionally apply Phong smooth normals across shared vertices.

No external dependencies – pure ``math`` module arithmetic.

Coordinate system
-----------------
Panda3D default: X right, Y forward, Z up.  The ``.map`` format uses the
same axes, so no coordinate-system conversion is needed.  A uniform
``scale`` factor (default ``0.03``) converts GoldSrc map units to game
units.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

from ivan.maps.map_parser import Brush, BrushFace, Vec3


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Textures that should be excluded from render output.  These are tool
#: textures used by the editor for triggers, hints, and other non-visible
#: geometry.
SKIP_RENDER_TEXTURES: frozenset[str] = frozenset({
    "trigger",
    "skip",
    "hint",
    "origin",
    "null",
    "aaatrigger",
    "clip",
    "nodraw",
})

#: Textures that should still produce collision geometry even though they
#: are invisible.
COLLISION_ONLY_TEXTURES: frozenset[str] = frozenset({
    "clip",
})

#: Epsilon for floating-point comparisons.
_EPS = 1e-6

#: Half-size of the large initial polygon used for clipping (in map units).
_HUGE = 65536.0


# ---------------------------------------------------------------------------
# Output data structures
# ---------------------------------------------------------------------------

@dataclass
class Triangle:
    """A single output triangle with positions, normals, UVs, and material."""

    positions: list[float]   # 9 floats: v0xyz v1xyz v2xyz
    normals: list[float]     # 9 floats: n0xyz n1xyz n2xyz
    uvs: list[float]         # 6 floats: uv0 uv1 uv2
    material: str            # texture / material name


@dataclass
class ConvertedBrushResult:
    """Aggregated output for a brush or set of brushes."""

    triangles: list[Triangle] = field(default_factory=list)
    collision_triangles: list[list[float]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Vector math helpers (pure Python, no deps)
# ---------------------------------------------------------------------------

def _v(x: float, y: float, z: float) -> tuple[float, float, float]:
    return (x, y, z)


def _add(a: tuple[float, float, float],
         b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _sub(a: tuple[float, float, float],
         b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _scale(a: tuple[float, float, float],
           s: float) -> tuple[float, float, float]:
    return (a[0] * s, a[1] * s, a[2] * s)


def _dot(a: tuple[float, float, float],
         b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: tuple[float, float, float],
           b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _length(a: tuple[float, float, float]) -> float:
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def _normalise(a: tuple[float, float, float]) -> tuple[float, float, float]:
    ln = _length(a)
    if ln < _EPS:
        return (0.0, 0.0, 0.0)
    return (a[0] / ln, a[1] / ln, a[2] / ln)


# ---------------------------------------------------------------------------
# Plane representation
# ---------------------------------------------------------------------------

@dataclass
class _Plane:
    """A plane defined by a unit normal and signed distance from the origin.

    The plane equation is ``dot(normal, P) - dist = 0`` for points *P* on the
    plane.  Points with ``dot(normal, P) - dist > 0`` are on the *front*
    (outside) side.
    """

    normal: tuple[float, float, float]
    dist: float


def _plane_from_points(
    p0: tuple[float, float, float],
    p1: tuple[float, float, float],
    p2: tuple[float, float, float],
) -> _Plane:
    """Compute a plane from three non-collinear points.

    In the Valve / Quake ``.map`` format the three points on each face line
    are wound so that ``(p2 - p0) x (p1 - p0)`` yields the **outward-facing**
    normal (away from the brush interior).  The Sutherland-Hodgman clipper in
    this module keeps the *back* half-space (``dist <= 0``), which is the brush
    interior when normals point outward.
    """

    edge1 = _sub(p2, p0)
    edge2 = _sub(p1, p0)
    raw_normal = _cross(edge1, edge2)
    normal = _normalise(raw_normal)
    dist = _dot(normal, p0)
    return _Plane(normal=normal, dist=dist)


def _plane_point_distance(plane: _Plane,
                          point: tuple[float, float, float]) -> float:
    """Signed distance from *point* to *plane*.

    Positive means *point* is on the front (outside) side.
    """

    return _dot(plane.normal, point) - plane.dist


# ---------------------------------------------------------------------------
# Initial polygon generation
# ---------------------------------------------------------------------------

def _make_base_polygon(
    plane: _Plane,
) -> list[tuple[float, float, float]]:
    """Create a very large quad polygon lying on *plane*.

    The polygon is centred at the point on the plane nearest the origin and
    spans ``±_HUGE`` along two tangent axes.
    """

    n = plane.normal
    # Pick an 'up' vector not parallel to the normal.
    if abs(n[2]) < 0.9:
        up = (0.0, 0.0, 1.0)
    else:
        up = (0.0, 1.0, 0.0)

    # Tangent axes.
    u = _normalise(_cross(n, up))
    v = _cross(n, u)  # Already unit length since n and u are orthonormal.

    # Centre of the polygon: nearest point on plane to origin.
    centre = _scale(n, plane.dist)

    u_big = _scale(u, _HUGE)
    v_big = _scale(v, _HUGE)

    # Vertex order must be **counter-clockwise** when viewed from the front
    # (along the outward normal) so that Panda3D / OpenGL treats these as
    # front-facing polygons.  The previous order (-U+V, +U+V, +U-V, -U-V)
    # was clockwise from the front, causing all faces to be back-faces
    # ("inside-out" textures when backface culling is enabled).
    return [
        _sub(_sub(centre, u_big), v_big),   # -U -V
        _sub(_add(centre, u_big), v_big),   # +U -V
        _add(_add(centre, u_big), v_big),   # +U +V
        _add(_sub(centre, u_big), v_big),   # -U +V
    ]


# ---------------------------------------------------------------------------
# Sutherland-Hodgman polygon clipping
# ---------------------------------------------------------------------------

def _clip_polygon_by_plane(
    polygon: list[tuple[float, float, float]],
    plane: _Plane,
) -> list[tuple[float, float, float]]:
    """Clip *polygon* against *plane*, keeping the back (inside) half.

    Points with ``plane_point_distance <= 0`` are considered *inside*.
    """

    if not polygon:
        return []

    out: list[tuple[float, float, float]] = []
    count = len(polygon)

    for i in range(count):
        current = polygon[i]
        nxt = polygon[(i + 1) % count]

        d_cur = _plane_point_distance(plane, current)
        d_nxt = _plane_point_distance(plane, nxt)

        cur_inside = d_cur <= _EPS
        nxt_inside = d_nxt <= _EPS

        if cur_inside:
            out.append(current)
            if not nxt_inside:
                # Exiting: compute intersection.
                out.append(_intersect_edge(current, nxt, d_cur, d_nxt))
        elif nxt_inside:
            # Entering: compute intersection.
            out.append(_intersect_edge(current, nxt, d_cur, d_nxt))

    return out


def _intersect_edge(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
    da: float,
    db: float,
) -> tuple[float, float, float]:
    """Compute the point where edge ``a -> b`` crosses the plane.

    *da* and *db* are the signed distances of *a* and *b* to the plane.
    """

    denom = da - db
    if abs(denom) < _EPS:
        return a
    t = da / denom
    return (
        a[0] + t * (b[0] - a[0]),
        a[1] + t * (b[1] - a[1]),
        a[2] + t * (b[2] - a[2]),
    )


# ---------------------------------------------------------------------------
# Fan triangulation
# ---------------------------------------------------------------------------

def _fan_triangulate(
    polygon: list[tuple[float, float, float]],
) -> list[tuple[
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
]]:
    """Fan-triangulate a convex polygon.

    Returns a list of ``(v0, v1, v2)`` triangles.
    """

    if len(polygon) < 3:
        return []
    tris = []
    v0 = polygon[0]
    for i in range(1, len(polygon) - 1):
        tris.append((v0, polygon[i], polygon[i + 1]))
    return tris


# ---------------------------------------------------------------------------
# UV computation (Valve 220)
# ---------------------------------------------------------------------------

def _compute_uv(
    vertex: tuple[float, float, float],
    face: BrushFace,
    tex_w: int,
    tex_h: int,
) -> tuple[float, float]:
    """Compute texture UV for *vertex* using Valve 220 projection.

    Parameters
    ----------
    vertex:
        The vertex position in *map-space* (before the game-unit scale).
    face:
        The brush face carrying the texture axis data.
    tex_w, tex_h:
        Texture dimensions in pixels.  When unknown, pass ``1, 1`` to get
        raw pixel-space UVs (divide by actual texture size at render time).
    """

    u_axis = (face.u_axis.x, face.u_axis.y, face.u_axis.z)
    v_axis = (face.v_axis.x, face.v_axis.y, face.v_axis.z)

    sx = face.scale_x if face.scale_x != 0.0 else 1.0
    sy = face.scale_y if face.scale_y != 0.0 else 1.0

    u = (_dot(vertex, u_axis) + face.u_offset) / (sx * tex_w)
    # Negate V: GoldSrc textures have V=0 at the top (V increases downward),
    # while Panda3D / OpenGL have V=0 at the bottom (V increases upward).
    v = -(_dot(vertex, v_axis) + face.v_offset) / (sy * tex_h)
    return (u, v)


# ---------------------------------------------------------------------------
# Core: brush -> triangles
# ---------------------------------------------------------------------------

def brush_to_triangles(
    brush: Brush,
    *,
    scale: float = 0.03,
    texture_sizes: dict[str, tuple[int, int]] | None = None,
) -> list[Triangle]:
    """Convert a single :class:`Brush` into a list of renderable triangles.

    Parameters
    ----------
    brush:
        The brush to convert.
    scale:
        Uniform scale multiplier applied to all vertex positions.
        Default ``0.03`` matches the GoldSrc-to-game-unit convention.
    texture_sizes:
        Optional mapping from texture name to ``(width, height)`` in pixels.
        If a texture is not found (or the dict is *None*), UVs are computed
        with ``(1, 1)`` so that the raw pixel offset is preserved and
        division by texture size can happen at render time.

    Returns
    -------
    list[Triangle]
        Renderable triangles with positions already scaled.  Triangles whose
        texture matches one of the :data:`SKIP_RENDER_TEXTURES` are excluded.
    """

    if not brush.faces:
        return []

    tex_sizes = texture_sizes or {}

    # 1. Build planes from face definitions. ---------------------------------
    planes: list[_Plane] = []
    for face in brush.faces:
        pp = face.plane_points
        p0 = (pp[0].x, pp[0].y, pp[0].z)
        p1 = (pp[1].x, pp[1].y, pp[1].z)
        p2 = (pp[2].x, pp[2].y, pp[2].z)
        planes.append(_plane_from_points(p0, p1, p2))

    triangles: list[Triangle] = []

    # 2. For each face, clip a large polygon against all other planes. -------
    for fi, face in enumerate(brush.faces):
        tex_lower = face.texture.lower()

        # Skip tool textures entirely (no render, no collision from here;
        # collision for clip is handled by the caller via a separate pass).
        if tex_lower in SKIP_RENDER_TEXTURES and tex_lower not in COLLISION_ONLY_TEXTURES:
            continue

        plane = planes[fi]
        polygon = _make_base_polygon(plane)

        # Clip against every *other* plane.
        for pi, clip_plane in enumerate(planes):
            if pi == fi:
                continue
            polygon = _clip_polygon_by_plane(polygon, clip_plane)
            if not polygon:
                break

        if len(polygon) < 3:
            continue

        # Skip invisible tool textures from render output (but they are still
        # clipped above so collision callers can reuse the windings).
        if tex_lower in SKIP_RENDER_TEXTURES:
            continue

        # 3. Compute face normal for flat shading. --------------------------
        face_normal = plane.normal

        # 4. Texture dimensions for UV computation. -------------------------
        # GoldSrc texture names are case-insensitive; texture_sizes keys
        # are lowercased by the extractor.
        tw, th = tex_sizes.get(face.texture.lower(), (1, 1))

        # 5. Fan-triangulate and emit. --------------------------------------
        tris = _fan_triangulate(polygon)
        for v0, v1, v2 in tris:
            # Scale positions.
            sv0 = _scale(v0, scale)
            sv1 = _scale(v1, scale)
            sv2 = _scale(v2, scale)

            # UVs are computed in *map-space* (before scale).
            uv0 = _compute_uv(v0, face, tw, th)
            uv1 = _compute_uv(v1, face, tw, th)
            uv2 = _compute_uv(v2, face, tw, th)

            triangles.append(Triangle(
                positions=[
                    sv0[0], sv0[1], sv0[2],
                    sv1[0], sv1[1], sv1[2],
                    sv2[0], sv2[1], sv2[2],
                ],
                normals=[
                    face_normal[0], face_normal[1], face_normal[2],
                    face_normal[0], face_normal[1], face_normal[2],
                    face_normal[0], face_normal[1], face_normal[2],
                ],
                uvs=[uv0[0], uv0[1], uv1[0], uv1[1], uv2[0], uv2[1]],
                material=face.texture,
            ))

    return triangles


def brush_to_collision_triangles(
    brush: Brush,
    *,
    scale: float = 0.03,
) -> list[list[float]]:
    """Convert a brush into collision-only triangles (positions only).

    Includes all faces *except* those with tool textures that are neither
    collision-relevant (like ``clip``) nor visible.  ``clip`` faces are
    included.

    Returns
    -------
    list[list[float]]
        Each inner list has 9 floats (three XYZ vertices).
    """

    if not brush.faces:
        return []

    planes: list[_Plane] = []
    for face in brush.faces:
        pp = face.plane_points
        planes.append(_plane_from_points(
            (pp[0].x, pp[0].y, pp[0].z),
            (pp[1].x, pp[1].y, pp[1].z),
            (pp[2].x, pp[2].y, pp[2].z),
        ))

    collision: list[list[float]] = []

    for fi, face in enumerate(brush.faces):
        tex_lower = face.texture.lower()

        # Skip textures that generate neither render nor collision geometry.
        if tex_lower in SKIP_RENDER_TEXTURES and tex_lower not in COLLISION_ONLY_TEXTURES:
            continue

        polygon = _make_base_polygon(planes[fi])
        for pi, clip_plane in enumerate(planes):
            if pi == fi:
                continue
            polygon = _clip_polygon_by_plane(polygon, clip_plane)
            if not polygon:
                break

        if len(polygon) < 3:
            continue

        tris = _fan_triangulate(polygon)
        for v0, v1, v2 in tris:
            sv0 = _scale(v0, scale)
            sv1 = _scale(v1, scale)
            sv2 = _scale(v2, scale)
            collision.append([
                sv0[0], sv0[1], sv0[2],
                sv1[0], sv1[1], sv1[2],
                sv2[0], sv2[1], sv2[2],
            ])

    return collision


# ---------------------------------------------------------------------------
# Phong smooth normals
# ---------------------------------------------------------------------------

def apply_phong_normals(
    triangles: list[Triangle],
    *,
    phong_angle: float = 89.0,
) -> list[Triangle]:
    """Apply Phong smooth normals to a list of triangles.

    Vertices that are spatially coincident (within a small epsilon) and whose
    face normals differ by less than *phong_angle* degrees have their normals
    averaged.  This produces smooth shading across coplanar and near-coplanar
    brush faces.

    Parameters
    ----------
    triangles:
        The input triangle list (modified **in place** and also returned).
    phong_angle:
        Maximum angle (degrees) between two face normals for them to be
        smoothed together.  Default ``89.0`` (matching the typical
        ``_phong_angle`` default in Quake-family toolchains).

    Returns
    -------
    list[Triangle]
        The same list, with normals updated.
    """

    if not triangles:
        return triangles

    cos_threshold = math.cos(math.radians(phong_angle))

    # Build a spatial index: vertex position (rounded) -> list of
    # (triangle index, vertex-within-triangle index, face normal).
    _BUCKET_EPS = 0.01
    _INV_EPS = 1.0 / _BUCKET_EPS

    VertexInfo = tuple[int, int, tuple[float, float, float]]
    buckets: dict[tuple[int, int, int], list[VertexInfo]] = {}

    for ti, tri in enumerate(triangles):
        # Extract face normal from the first vertex (flat-shaded input).
        fn = (tri.normals[0], tri.normals[1], tri.normals[2])
        for vi in range(3):
            px = tri.positions[vi * 3]
            py = tri.positions[vi * 3 + 1]
            pz = tri.positions[vi * 3 + 2]
            key = (
                int(math.floor(px * _INV_EPS + 0.5)),
                int(math.floor(py * _INV_EPS + 0.5)),
                int(math.floor(pz * _INV_EPS + 0.5)),
            )
            buckets.setdefault(key, []).append((ti, vi, fn))

    # For each bucket, average normals of faces whose angle is within
    # the threshold.
    for entries in buckets.values():
        if len(entries) <= 1:
            continue

        # For each vertex in this bucket, compute its smoothed normal
        # by averaging all compatible face normals.
        for i, (ti_a, vi_a, fn_a) in enumerate(entries):
            nx, ny, nz = 0.0, 0.0, 0.0
            for _j, (ti_b, vi_b, fn_b) in enumerate(entries):
                d = _dot(fn_a, fn_b)
                # Clamp for numerical safety.
                d = max(-1.0, min(1.0, d))
                if d >= cos_threshold:
                    nx += fn_b[0]
                    ny += fn_b[1]
                    nz += fn_b[2]
            smooth = _normalise((nx, ny, nz))
            triangles[ti_a].normals[vi_a * 3] = smooth[0]
            triangles[ti_a].normals[vi_a * 3 + 1] = smooth[1]
            triangles[ti_a].normals[vi_a * 3 + 2] = smooth[2]

    return triangles


# ---------------------------------------------------------------------------
# High-level: entity brushes -> ConvertedBrushResult
# ---------------------------------------------------------------------------

def convert_entity_brushes(
    brushes: Sequence[Brush],
    *,
    scale: float = 0.03,
    texture_sizes: dict[str, tuple[int, int]] | None = None,
    phong: bool = False,
    phong_angle: float = 89.0,
) -> ConvertedBrushResult:
    """Convert all brushes in an entity to a :class:`ConvertedBrushResult`.

    This is the primary high-level entry point.  It handles:

    - Render triangles (with UVs and normals).
    - Collision triangles (positions only, includes ``clip`` faces).
    - Optional Phong smooth normals when *phong* is ``True``.

    Parameters
    ----------
    brushes:
        List of brushes from a single :class:`~ivan.maps.map_parser.MapEntity`.
    scale:
        Uniform scale multiplier (default ``0.03``).
    texture_sizes:
        Optional mapping of texture name -> ``(width, height)`` pixels.
    phong:
        Whether to apply Phong smooth normals.
    phong_angle:
        Maximum angle (degrees) for Phong smoothing.

    Returns
    -------
    ConvertedBrushResult
    """

    result = ConvertedBrushResult()

    for brush in brushes:
        result.triangles.extend(
            brush_to_triangles(brush, scale=scale, texture_sizes=texture_sizes),
        )
        result.collision_triangles.extend(
            brush_to_collision_triangles(brush, scale=scale),
        )

    if phong and result.triangles:
        apply_phong_normals(result.triangles, phong_angle=phong_angle)

    return result
