from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _safe_key(np: Any) -> str:
    try:
        k = np.getKey()
        return str(int(k))
    except Exception:
        return str(id(np))


def _safe_name(np: Any) -> str:
    try:
        return str(np.getName())
    except Exception:
        return str(type(np).__name__)


def _safe_type(np: Any) -> str:
    try:
        n = np.node()
        if n is None:
            return "None"
        return str(type(n).__name__)
    except Exception:
        return str(type(np).__name__)


def _safe_pos(np: Any) -> list[float]:
    try:
        p = np.getPos()
        return [float(p.x), float(p.y), float(p.z)]
    except Exception:
        return [0.0, 0.0, 0.0]


def _safe_hpr(np: Any) -> list[float]:
    try:
        p = np.getHpr()
        return [float(p.x), float(p.y), float(p.z)]
    except Exception:
        return [0.0, 0.0, 0.0]


def _safe_scale(np: Any) -> list[float]:
    try:
        s = np.getScale()
        return [float(s.x), float(s.y), float(s.z)]
    except Exception:
        return [1.0, 1.0, 1.0]


def _safe_path(np: Any) -> str:
    try:
        return str(np.getName()) if np.getParent().isEmpty() else f"{_safe_path(np.getParent())}/{np.getName()}"
    except Exception:
        return _safe_name(np)


def _safe_children(np: Any) -> list[Any]:
    out: list[Any] = []
    try:
        coll = np.getChildren()
        n = int(coll.getNumPaths())
        for i in range(n):
            out.append(coll.getPath(i))
        return out
    except Exception:
        pass
    try:
        raw = getattr(np, "children", None)
        if isinstance(raw, list):
            return list(raw)
    except Exception:
        pass
    return out


def _safe_tag_keys(np: Any) -> list[str]:
    keys: list[str] = []
    try:
        coll = np.getTagKeys()
        n = int(coll.getNumTags())
        for i in range(n):
            keys.append(str(coll.getTag(i)))
        return keys
    except Exception:
        return keys


@dataclass
class _Group:
    group_id: str
    node: Any


class SceneRuntimeRegistry:
    """
    Runtime object index for scene introspection/manipulation commands.
    """

    def __init__(self, *, runner: Any) -> None:
        self._runner = runner
        self._selected_id: str | None = None
        self._groups: dict[str, _Group] = {}
        self._cached_objects: dict[str, Any] = {}
        self._last_scan_s = 0.0
        self._scan_count = 0

    def _root(self) -> Any | None:
        return getattr(self._runner, "world_root", None)

    def _scan(self, *, force: bool = False, max_nodes: int = 2500) -> dict[str, Any]:
        now = perf_counter()
        # Small TTL to avoid repeated full scans when tooling polls quickly.
        if (not force) and self._cached_objects and (now - self._last_scan_s) < 0.15:
            return self._cached_objects
        out: dict[str, Any] = {}
        root = self._root()
        if root is None:
            self._cached_objects = out
            self._last_scan_s = now
            self._scan_count = 0
            return out
        q = [root]
        seen = 0
        while q and seen < int(max_nodes):
            cur = q.pop(0)
            key = _safe_key(cur)
            out[key] = cur
            seen += 1
            q.extend(_safe_children(cur))
        self._cached_objects = out
        self._last_scan_s = now
        self._scan_count = seen
        return out

    def _find(self, target: str | None) -> Any | None:
        if target is None or not str(target).strip():
            if self._selected_id:
                return self._cached_objects.get(self._selected_id)
            return None
        scan = self._scan(force=False)
        t = str(target).strip()
        if t in scan:
            return scan.get(t)
        low = t.casefold()
        # Best effort by node name.
        for np in scan.values():
            if _safe_name(np).casefold() == low:
                return np
        return None

    def list_objects(
        self,
        *,
        name: str = "",
        typ: str = "",
        tag: str = "",
        page: int = 1,
        page_size: int = 25,
    ) -> dict[str, Any]:
        objs = self._scan(force=False)
        name_cf = str(name or "").strip().casefold()
        typ_cf = str(typ or "").strip().casefold()
        tag_cf = str(tag or "").strip().casefold()
        rows: list[dict[str, Any]] = []
        for key, np in objs.items():
            n = _safe_name(np)
            t = _safe_type(np)
            if name_cf and name_cf not in n.casefold():
                continue
            if typ_cf and typ_cf not in t.casefold():
                continue
            if tag_cf:
                keys = [k.casefold() for k in _safe_tag_keys(np)]
                if tag_cf not in keys:
                    continue
            rows.append(
                {
                    "id": key,
                    "name": n,
                    "type": t,
                    "path": _safe_path(np),
                    "pos": _safe_pos(np),
                }
            )
        rows.sort(key=lambda x: (str(x.get("name") or "").casefold(), str(x.get("id") or "")))
        p = max(1, int(page))
        ps = max(1, min(200, int(page_size)))
        start = (p - 1) * ps
        end = start + ps
        return {
            "total": len(rows),
            "page": p,
            "page_size": ps,
            "page_count": max(1, (len(rows) + ps - 1) // ps) if rows else 1,
            "scan_count": int(self._scan_count),
            "items": rows[start:end],
        }

    def select_object(self, *, target: str) -> dict[str, Any]:
        np = self._find(target)
        if np is None:
            raise ValueError(f"target not found: {target!r}")
        key = _safe_key(np)
        self._selected_id = key
        return {
            "id": key,
            "name": _safe_name(np),
            "type": _safe_type(np),
            "path": _safe_path(np),
        }

    def inspect_selected(self, *, target: str | None = None) -> dict[str, Any]:
        np = self._find(target)
        if np is None:
            raise ValueError("no target selected")
        tags: dict[str, str] = {}
        for k in _safe_tag_keys(np):
            try:
                tags[str(k)] = str(np.getTag(str(k)))
            except Exception:
                continue
        return {
            "id": _safe_key(np),
            "selected_id": self._selected_id,
            "name": _safe_name(np),
            "type": _safe_type(np),
            "path": _safe_path(np),
            "pos": _safe_pos(np),
            "hpr": _safe_hpr(np),
            "scale": _safe_scale(np),
            "tags": tags,
        }

    def create_object(self, *, object_type: str, name: str = "runtime_obj") -> dict[str, Any]:
        root = self._root()
        if root is None:
            raise ValueError("world root unavailable")
        loader = getattr(self._runner, "loader", None)
        kind = str(object_type or "").strip().lower()
        if kind not in ("box", "sphere", "empty"):
            raise ValueError("object_type must be one of: box, sphere, empty")
        if kind == "empty":
            node = root.attachNewNode(str(name or "runtime_empty"))
        else:
            if loader is None:
                raise ValueError("loader unavailable")
            model_name = "models/box" if kind == "box" else "models/misc/sphere"
            node = loader.loadModel(model_name)
            node.reparentTo(root)
            node.setName(str(name or f"runtime_{kind}"))
            if kind == "box":
                node.setScale(0.6, 0.6, 0.6)
            else:
                node.setScale(0.4, 0.4, 0.4)
            node.setColor(0.76, 0.44, 0.28, 1.0)
        key = _safe_key(node)
        self._cached_objects[key] = node
        self._selected_id = key
        return self.inspect_selected(target=key)

    def delete_object(self, *, target: str | None = None) -> dict[str, Any]:
        np = self._find(target)
        if np is None:
            raise ValueError("target not found")
        key = _safe_key(np)
        try:
            np.removeNode()
        except Exception as e:
            raise ValueError(f"delete failed: {e}") from e
        self._cached_objects.pop(key, None)
        if self._selected_id == key:
            self._selected_id = None
        return {"deleted_id": key}

    def transform_object(
        self,
        *,
        target: str | None,
        mode: str,
        x: float,
        y: float,
        z: float,
        relative: bool,
    ) -> dict[str, Any]:
        np = self._find(target)
        if np is None:
            raise ValueError("target not found")
        rel = bool(relative)
        m = str(mode).strip().lower()
        if m == "move":
            if rel:
                np.setPos(np, float(x), float(y), float(z))
            else:
                np.setPos(float(x), float(y), float(z))
        elif m == "rotate":
            if rel:
                np.setHpr(np, float(x), float(y), float(z))
            else:
                np.setHpr(float(x), float(y), float(z))
        elif m == "scale":
            if rel:
                s = _safe_scale(np)
                np.setScale(float(s[0]) + float(x), float(s[1]) + float(y), float(s[2]) + float(z))
            else:
                np.setScale(float(x), float(y), float(z))
        else:
            raise ValueError(f"unsupported transform mode: {mode}")
        return self.inspect_selected(target=_safe_key(np))

    def group_objects(self, *, group_id: str, targets: list[str]) -> dict[str, Any]:
        gid = str(group_id or "").strip()
        if not gid:
            raise ValueError("group_id is required")
        root = self._root()
        if root is None:
            raise ValueError("world root unavailable")
        row = self._groups.get(gid)
        if row is None:
            node = root.attachNewNode(f"group:{gid}")
            row = _Group(group_id=gid, node=node)
            self._groups[gid] = row
        moved = 0
        for t in targets:
            np = self._find(t)
            if np is None:
                continue
            try:
                np.wrtReparentTo(row.node)
                moved += 1
            except Exception:
                continue
        if moved <= 0:
            raise ValueError("no objects were grouped")
        return {"group_id": gid, "moved": moved}

    def ungroup(self, *, group_id: str) -> dict[str, Any]:
        gid = str(group_id or "").strip()
        row = self._groups.get(gid)
        if row is None:
            raise ValueError(f"unknown group: {gid}")
        root = self._root()
        if root is None:
            raise ValueError("world root unavailable")
        moved = 0
        for child in _safe_children(row.node):
            try:
                child.wrtReparentTo(root)
                moved += 1
            except Exception:
                continue
        try:
            row.node.removeNode()
        except Exception:
            pass
        self._groups.pop(gid, None)
        return {"group_id": gid, "moved": moved}

    def group_transform(
        self,
        *,
        group_id: str,
        mode: str,
        x: float,
        y: float,
        z: float,
        relative: bool,
    ) -> dict[str, Any]:
        gid = str(group_id or "").strip()
        row = self._groups.get(gid)
        if row is None:
            raise ValueError(f"unknown group: {gid}")
        m = str(mode).strip().lower()
        rel = bool(relative)
        if m == "move":
            if rel:
                row.node.setPos(row.node, float(x), float(y), float(z))
            else:
                row.node.setPos(float(x), float(y), float(z))
        elif m == "rotate":
            if rel:
                row.node.setHpr(row.node, float(x), float(y), float(z))
            else:
                row.node.setHpr(float(x), float(y), float(z))
        elif m == "scale":
            if rel:
                s = _safe_scale(row.node)
                row.node.setScale(float(s[0]) + float(x), float(s[1]) + float(y), float(s[2]) + float(z))
            else:
                row.node.setScale(float(x), float(y), float(z))
        else:
            raise ValueError("mode must be move|rotate|scale")
        return {
            "group_id": gid,
            "pos": _safe_pos(row.node),
            "hpr": _safe_hpr(row.node),
            "scale": _safe_scale(row.node),
        }

    def player_look_target(self, *, distance: float = 256.0) -> dict[str, Any]:
        collision = getattr(self._runner, "collision", None)
        camera = getattr(self._runner, "camera", None)
        render = getattr(self._runner, "render", None)
        direction_fn = getattr(self._runner, "_view_direction", None)
        if collision is None or camera is None or render is None or not callable(direction_fn):
            raise ValueError("raycast unavailable")
        direction = direction_fn()
        if float(direction.lengthSquared()) <= 1e-12:
            raise ValueError("view direction unavailable")
        origin = camera.getPos(render)
        end = origin + direction * max(1.0, float(distance))
        hit = collision.ray_closest(origin, end)
        if not bool(hit.hasHit()):
            return {
                "hit": False,
                "origin": [float(origin.x), float(origin.y), float(origin.z)],
                "end": [float(end.x), float(end.y), float(end.z)],
            }
        hit_pos = hit.getHitPos() if hasattr(hit, "getHitPos") else (origin + (end - origin) * float(hit.getHitFraction()))
        node_name = ""
        try:
            node_name = str(hit.getNode().getName())
        except Exception:
            node_name = ""
        return {
            "hit": True,
            "origin": [float(origin.x), float(origin.y), float(origin.z)],
            "end": [float(end.x), float(end.y), float(end.z)],
            "hit_pos": [float(hit_pos.x), float(hit_pos.y), float(hit_pos.z)],
            "hit_fraction": float(hit.getHitFraction()) if hasattr(hit, "getHitFraction") else 0.0,
            "hit_node": node_name,
        }

    def set_world_fog(
        self,
        *,
        mode: str,
        start: float,
        end: float,
        density: float,
        color_r: float,
        color_g: float,
        color_b: float,
    ) -> dict[str, Any]:
        scene = getattr(self._runner, "scene", None)
        world_root = getattr(self._runner, "world_root", None)
        cfg = getattr(self._runner, "_active_run_cfg", None)
        if scene is None or world_root is None:
            raise ValueError("scene unavailable")
        mode_s = str(mode or "").strip().lower()
        if mode_s not in ("off", "linear", "exp", "exp2"):
            raise ValueError("mode must be off|linear|exp|exp2")
        enabled = mode_s != "off"
        fog = {
            "enabled": bool(enabled),
            "mode": "linear" if mode_s == "off" else mode_s,
            "start": float(start),
            "end": float(end),
            "density": float(max(0.0, density)),
            "color": [_clamp01(color_r), _clamp01(color_g), _clamp01(color_b)],
        }
        setattr(scene, "_runtime_fog_override", fog)
        setattr(scene, "_pending_map_fog", dict(fog))
        apply_fn = getattr(scene, "_apply_fog", None)
        if callable(apply_fn):
            apply_fn(cfg=cfg, render=world_root)
        diag_fn = getattr(scene, "runtime_world_diagnostics", None)
        if callable(diag_fn):
            return dict(diag_fn())
        return {"ok": True}

    def save_world_map(self, *, include_fog: bool = True) -> dict[str, Any]:
        scene = getattr(self._runner, "scene", None)
        if scene is None:
            raise ValueError("scene unavailable")
        map_json = getattr(scene, "_map_json_path", None)
        if not isinstance(map_json, Path):
            raise ValueError("map is not backed by writable map.json")
        if map_json.suffix.lower() != ".json":
            raise ValueError("current map source is not map.json (direct .map is not writable here)")
        # Packed .irunmap maps are extracted to cache; writing there is misleading.
        extracted_marker = map_json.parent / ".irunmap-extracted.json"
        if extracted_marker.exists():
            raise ValueError("packed .irunmap is read-only in runtime cache; save to source bundle instead")
        if not map_json.exists() or not map_json.is_file():
            raise ValueError(f"map.json not found: {map_json}")

        try:
            raw = json.loads(map_json.read_text(encoding="utf-8"))
        except Exception as e:
            raise ValueError(f"failed to parse map.json: {e}") from e
        if not isinstance(raw, dict):
            raise ValueError("map.json root must be an object")

        payload = dict(raw)
        changed = False
        if include_fog:
            fog_pending = getattr(scene, "_pending_map_fog", None)
            if not isinstance(fog_pending, dict):
                fog_pending = getattr(scene, "_runtime_fog_override", None)
            if isinstance(fog_pending, dict):
                payload["fog"] = dict(fog_pending)
                setattr(scene, "_pending_map_fog", None)
                changed = True

        if not changed:
            return {"ok": True, "saved": [], "map_json": str(map_json), "note": "no pending map changes"}

        map_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        setattr(scene, "_map_payload", dict(payload))
        return {
            "ok": True,
            "saved": ["fog"] if include_fog else [],
            "map_json": str(map_json),
            "fog": payload.get("fog"),
        }

    def set_world_skybox(self, *, skyname: str) -> dict[str, Any]:
        scene = getattr(self._runner, "scene", None)
        loader = getattr(self._runner, "loader", None)
        camera = getattr(self._runner, "camera", None)
        if scene is None or loader is None or camera is None:
            raise ValueError("scene unavailable")
        list_fn = getattr(scene, "list_available_skyboxes", None)
        available: list[str] = []
        if callable(list_fn):
            available = list_fn()
        wanted = str(skyname or "").strip()
        if not wanted:
            raise ValueError("skyname is required")
        if available and wanted not in set(available):
            raise ValueError(f"unknown skyname: {wanted}. available={', '.join(sorted(available)[:16])}")
        set_fn = getattr(scene, "set_runtime_skybox", None)
        if callable(set_fn):
            payload = set_fn(loader=loader, camera=camera, skyname=wanted)
        else:
            raise ValueError("runtime skybox switching unavailable")
        return dict(payload if isinstance(payload, dict) else {"ok": True, "skyname": wanted})

