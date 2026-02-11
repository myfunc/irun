from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path

_VIS_CACHE_MEM: dict[str, tuple["GoldSrcBspVis", int]] = {}


@dataclass(frozen=True)
class GoldSrcBspVis:
    """
    Minimal GoldSrc BSP visibility data for PVS-based occlusion culling.

    This is intentionally independent from lighting:
    - It only answers: "given camera position, which world faces should be rendered?"
    - Rendering can still choose any lighting mode (fullbright, lightmaps, vertex-lit, etc).
    """

    # Source identity (used to invalidate cache when the BSP changes).
    source_bsp: str
    source_mtime_ns: int

    # BSP traversal (model 0 hull 0).
    root_node: int
    # planes[i] = (nx, ny, nz, dist)
    planes: list[tuple[float, float, float, float]]
    # nodes[i] = (plane_idx, front_child, back_child)
    # child >= 0: node index
    # child < 0: leaf index encoded as -(leaf + 1)
    nodes: list[tuple[int, int, int]]

    # leaves[i] = (vis_offset, first_leaf_face, num_leaf_faces)
    leaves: list[tuple[int, int, int]]
    # leaf_faces is the LEAF_FACES lump; leaf ranges index into this.
    leaf_faces: list[int]
    # Raw VISIBILITY lump bytes (Quake/GoldSrc RLE).
    visdata: bytes

    # World model face range (model 0 surfaces). Brush entity submodels should not be PVS-culled this way.
    world_first_face: int
    world_num_faces: int

    @property
    def world_face_end(self) -> int:
        return int(self.world_first_face + self.world_num_faces)

    @property
    def leaf_count(self) -> int:
        return int(len(self.leaves))

    def point_leaf(self, *, x: float, y: float, z: float) -> int:
        """
        Walk the BSP node tree to find the leaf containing the given point.
        """

        idx = int(self.root_node)
        # Defensive cap to avoid infinite loops on corrupted data.
        for _ in range(100000):
            if idx < 0:
                return int(-idx - 1)
            if idx >= len(self.nodes):
                return 0
            plane_idx, front, back = self.nodes[int(idx)]
            if plane_idx < 0 or plane_idx >= len(self.planes):
                return 0
            nx, ny, nz, dist = self.planes[int(plane_idx)]
            d = float(x) * float(nx) + float(y) * float(ny) + float(z) * float(nz) - float(dist)
            idx = int(front) if d >= 0.0 else int(back)
        return 0

    def visible_world_face_flags_for_leaf(self, leaf_idx: int) -> bytearray:
        """
        Return a bytearray of length world_num_faces where 1 means "render this world face".
        """

        leaf_idx = int(leaf_idx)
        if leaf_idx < 0 or leaf_idx >= len(self.leaves):
            # Unknown: render everything in the world model.
            return bytearray(b"\x01" * int(self.world_num_faces))

        vis_offset, _, _ = self.leaves[leaf_idx]
        row = decode_pvs_row(visdata=self.visdata, offset=int(vis_offset), leaf_count=self.leaf_count)

        flags = bytearray(int(self.world_num_faces))
        world_end = int(self.world_face_end)

        # Union leaf face lists for all visible leaves.
        #
        # Defensive: ensure the current leaf is always included. Some toolchains can produce VIS
        # rows that do not include the leaf itself; culling away local faces causes obvious popping.
        visible_leaves = iter_visible_leaf_indices(row=row)
        if int(leaf_idx) not in visible_leaves:
            visible_leaves.append(int(leaf_idx))

        for other_leaf in visible_leaves:
            if other_leaf < 0 or other_leaf >= len(self.leaves):
                continue
            _, first, count = self.leaves[int(other_leaf)]
            first = int(first)
            count = int(count)
            if count <= 0 or first < 0:
                continue
            end = first + count
            if end > len(self.leaf_faces):
                end = len(self.leaf_faces)
            for i in range(first, end):
                try:
                    face_idx = int(self.leaf_faces[i])
                except Exception:
                    continue
                if face_idx < int(self.world_first_face) or face_idx >= world_end:
                    continue
                flags[int(face_idx - int(self.world_first_face))] = 1

        return flags

    def to_json(self) -> str:
        payload = {
            "format": "goldsrc_pvs_v1",
            "source_bsp": str(self.source_bsp),
            "source_mtime_ns": int(self.source_mtime_ns),
            "root_node": int(self.root_node),
            "planes": [[float(a), float(b), float(c), float(d)] for (a, b, c, d) in self.planes],
            "nodes": [[int(p), int(f), int(b)] for (p, f, b) in self.nodes],
            "leaves": [[int(o), int(first), int(n)] for (o, first, n) in self.leaves],
            "leaf_faces": [int(x) for x in self.leaf_faces],
            "visdata_b64": base64.b64encode(bytes(self.visdata)).decode("ascii"),
            "world_first_face": int(self.world_first_face),
            "world_num_faces": int(self.world_num_faces),
        }
        return json.dumps(payload, separators=(",", ":"))

    @staticmethod
    def from_json(raw: str) -> GoldSrcBspVis:
        payload = json.loads(raw)
        if not isinstance(payload, dict) or payload.get("format") != "goldsrc_pvs_v1":
            raise ValueError("Unknown visibility cache format")

        vis_b64 = payload.get("visdata_b64")
        if not isinstance(vis_b64, str):
            raise ValueError("Missing visdata_b64")
        visdata = base64.b64decode(vis_b64.encode("ascii"), validate=False)

        planes_raw = payload.get("planes")
        nodes_raw = payload.get("nodes")
        leaves_raw = payload.get("leaves")
        leaf_faces_raw = payload.get("leaf_faces")
        if not (isinstance(planes_raw, list) and isinstance(nodes_raw, list) and isinstance(leaves_raw, list)):
            raise ValueError("Invalid cache payload (arrays)")
        if not isinstance(leaf_faces_raw, list):
            leaf_faces_raw = []

        planes: list[tuple[float, float, float, float]] = []
        for row in planes_raw:
            if isinstance(row, list) and len(row) == 4:
                planes.append((float(row[0]), float(row[1]), float(row[2]), float(row[3])))

        nodes: list[tuple[int, int, int]] = []
        for row in nodes_raw:
            if isinstance(row, list) and len(row) == 3:
                nodes.append((int(row[0]), int(row[1]), int(row[2])))

        leaves: list[tuple[int, int, int]] = []
        for row in leaves_raw:
            if isinstance(row, list) and len(row) == 3:
                leaves.append((int(row[0]), int(row[1]), int(row[2])))

        leaf_faces: list[int] = []
        for x in leaf_faces_raw:
            try:
                leaf_faces.append(int(x))
            except Exception:
                continue

        return GoldSrcBspVis(
            source_bsp=str(payload.get("source_bsp") or ""),
            source_mtime_ns=int(payload.get("source_mtime_ns") or 0),
            root_node=int(payload.get("root_node") or 0),
            planes=planes,
            nodes=nodes,
            leaves=leaves,
            leaf_faces=leaf_faces,
            visdata=bytes(visdata),
            world_first_face=int(payload.get("world_first_face") or 0),
            world_num_faces=int(payload.get("world_num_faces") or 0),
        )


def decode_pvs_row(*, visdata: bytes, offset: int, leaf_count: int) -> bytes:
    """
    Decode one PVS row from the GoldSrc/Quake VISIBILITY lump.

    - leaf_count is the number of leaves in the map.
    - offset is leaf.vis_offset (byte offset into visdata), or <0 for "all visible".
    """

    rowbytes = (int(leaf_count) + 7) // 8
    if offset < 0:
        return bytes([0xFF]) * rowbytes
    if offset >= len(visdata):
        return bytes([0xFF]) * rowbytes

    out = bytearray()
    i = int(offset)
    # Quake RLE: nonzero bytes copied through, zero byte means "next byte is count of zeros".
    while len(out) < rowbytes and i < len(visdata):
        b = visdata[i]
        i += 1
        if b != 0:
            out.append(int(b))
            continue
        if i >= len(visdata):
            break
        count = int(visdata[i])
        i += 1
        if count <= 0:
            continue
        out.extend(b"\x00" * count)

    if len(out) < rowbytes:
        out.extend(b"\x00" * (rowbytes - len(out)))
    return bytes(out[:rowbytes])


def iter_visible_leaf_indices(*, row: bytes) -> list[int]:
    """
    Expand a PVS row (bitset bytes) to leaf indices.

    Note: This allocates a Python list. For performance-critical paths, this can be replaced
    with a generator, but in practice leaf changes are not per-frame for most movement.
    """

    out: list[int] = []
    for bi, b in enumerate(row):
        bb = int(b)
        if bb == 0:
            continue
        base = bi * 8
        for j in range(8):
            if bb & (1 << j):
                out.append(int(base + j))
    return out


def load_or_build_visibility_cache(
    *,
    cache_path: Path,
    source_bsp_path: Path | None,
    diagnostics: dict[str, object] | None = None,
) -> GoldSrcBspVis | None:
    """
    Load GoldSrc visibility cache from cache_path, or build it from a source BSP if missing/stale.
    """

    cache_path = Path(cache_path)
    cache_key = str(cache_path.resolve())
    cache_mtime_ns = -1
    if cache_path.exists() and cache_path.is_file():
        try:
            st = cache_path.stat()
            cache_mtime_ns = int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)))
        except Exception:
            cache_mtime_ns = -1

    warm = _VIS_CACHE_MEM.get(cache_key)
    if isinstance(warm, tuple) and len(warm) == 2:
        vis0, cached_cache_mtime_ns = warm
        if int(cached_cache_mtime_ns) == int(cache_mtime_ns):
            if source_bsp_path is None:
                if diagnostics is not None:
                    diagnostics["result"] = "memory-hit"
                return vis0
            if source_bsp_path.exists():
                try:
                    st = source_bsp_path.stat()
                    source_mtime_ns = int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)))
                except Exception:
                    source_mtime_ns = 0
                if str(source_bsp_path) == str(vis0.source_bsp) and int(source_mtime_ns) == int(vis0.source_mtime_ns):
                    if diagnostics is not None:
                        diagnostics["result"] = "memory-hit"
                    return vis0

    if cache_path.exists() and cache_path.is_file():
        try:
            vis = GoldSrcBspVis.from_json(cache_path.read_text(encoding="utf-8"))
        except Exception:
            vis = None
        if vis is not None and source_bsp_path is not None and source_bsp_path.exists():
            try:
                st = source_bsp_path.stat()
                mtime_ns = int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)))
            except Exception:
                mtime_ns = 0
            # If the cache matches the on-disk BSP, keep it.
            if str(source_bsp_path) == str(vis.source_bsp) and int(mtime_ns) == int(vis.source_mtime_ns):
                _VIS_CACHE_MEM[cache_key] = (vis, int(cache_mtime_ns))
                if diagnostics is not None:
                    diagnostics["result"] = "disk-hit"
                return vis
        elif vis is not None and source_bsp_path is None:
            _VIS_CACHE_MEM[cache_key] = (vis, int(cache_mtime_ns))
            if diagnostics is not None:
                diagnostics["result"] = "disk-hit"
            return vis

    if source_bsp_path is None or not source_bsp_path.exists():
        if diagnostics is not None:
            diagnostics["result"] = "miss-no-source"
        return None

    vis = build_visibility_from_goldsrc_bsp(source_bsp_path=source_bsp_path)
    if vis is None:
        if diagnostics is not None:
            diagnostics["result"] = "build-failed"
        return None

    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(vis.to_json(), encoding="utf-8")
        try:
            st = cache_path.stat()
            cache_mtime_ns = int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)))
        except Exception:
            cache_mtime_ns = -1
    except Exception:
        # Cache is optional; if we can't write, still return the in-memory data.
        pass
    _VIS_CACHE_MEM[cache_key] = (vis, int(cache_mtime_ns))
    if diagnostics is not None:
        diagnostics["result"] = "rebuilt"
    return vis


def build_visibility_from_goldsrc_bsp(*, source_bsp_path: Path) -> GoldSrcBspVis | None:
    """
    Build visibility data from a GoldSrc BSP using bsp_tool.
    """

    try:
        import bsp_tool  # type: ignore
    except Exception:
        return None

    source_bsp_path = Path(source_bsp_path)
    try:
        st = source_bsp_path.stat()
        mtime_ns = int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)))
    except Exception:
        mtime_ns = 0

    try:
        bsp = bsp_tool.load_bsp(str(source_bsp_path))
    except Exception:
        return None

    # Root node: model 0, hull 0 (Quake-style).
    root_node = 0
    try:
        m0 = bsp.MODELS[0]
        node = getattr(m0, "node", 0)
        if isinstance(node, (tuple, list)) and node:
            root_node = int(node[0])
        else:
            root_node = int(node)
    except Exception:
        root_node = 0

    # World face range: model 0.
    world_first_face = 0
    world_num_faces = 0
    try:
        m0 = bsp.MODELS[0]
        world_first_face = int(getattr(m0, "first_face", 0) or 0)
        world_num_faces = int(getattr(m0, "num_faces", 0) or 0)
    except Exception:
        world_first_face = 0
        world_num_faces = 0

    planes: list[tuple[float, float, float, float]] = []
    try:
        for p in getattr(bsp, "PLANES", []) or []:
            n = getattr(p, "normal", None)
            dist = getattr(p, "distance", None)
            planes.append((float(getattr(n, "x", 0.0)), float(getattr(n, "y", 0.0)), float(getattr(n, "z", 0.0)), float(dist)))
    except Exception:
        planes = []

    nodes: list[tuple[int, int, int]] = []
    try:
        for n in getattr(bsp, "NODES", []) or []:
            plane_idx = int(getattr(n, "plane", 0) or 0)
            ch = getattr(n, "children", None)
            front = int(getattr(ch, "front", 0) if ch is not None else 0)
            back = int(getattr(ch, "back", 0) if ch is not None else 0)
            nodes.append((plane_idx, front, back))
    except Exception:
        nodes = []

    leaves: list[tuple[int, int, int]] = []
    try:
        for lf in getattr(bsp, "LEAVES", []) or []:
            vis_offset = int(getattr(lf, "vis_offset", -1) or -1)
            first = int(getattr(lf, "first_leaf_face", 0) or 0)
            count = int(getattr(lf, "num_leaf_faces", 0) or 0)
            leaves.append((vis_offset, first, count))
    except Exception:
        leaves = []

    leaf_faces: list[int] = []
    try:
        for x in getattr(bsp, "LEAF_FACES", []) or []:
            leaf_faces.append(int(x))
    except Exception:
        leaf_faces = []

    try:
        visdata = bytes(getattr(bsp, "VISIBILITY", b"") or b"")
    except Exception:
        visdata = b""

    if not (planes and nodes and leaves and leaf_faces and visdata):
        # Some GoldSrc maps may not have VIS (unvis'd) - treat as unsupported for now.
        # (We can later fall back to "all visible".)
        return None

    return GoldSrcBspVis(
        source_bsp=str(source_bsp_path),
        source_mtime_ns=int(mtime_ns),
        root_node=int(root_node),
        planes=planes,
        nodes=nodes,
        leaves=leaves,
        leaf_faces=leaf_faces,
        visdata=bytes(visdata),
        world_first_face=int(world_first_face),
        world_num_faces=int(world_num_faces),
    )
