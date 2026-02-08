from __future__ import annotations

import json
from pathlib import Path

from ivan.maps.bundle_io import PACKED_BUNDLE_EXT, pack_bundle_dir_to_irunmap, resolve_bundle_handle_path
from ivan.state import resolve_map_json


def test_resolve_map_json_supports_irunmap_absolute_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("IRUN_IVAN_STATE_DIR", str(tmp_path / "state"))
    packed = tmp_path / f"m{PACKED_BUNDLE_EXT}"
    packed.write_bytes(b"not-a-zip")
    assert resolve_map_json(str(packed)) == packed


def test_packed_bundle_extracts_to_cache_and_resolves_map_json(tmp_path: Path, monkeypatch) -> None:
    # Ensure cache writes don't touch the real user home in tests.
    monkeypatch.setenv("IRUN_IVAN_STATE_DIR", str(tmp_path / "state"))

    bundle_dir = tmp_path / "bundle"
    (bundle_dir / "materials").mkdir(parents=True)
    (bundle_dir / "materials" / "a.txt").write_text("ok", encoding="utf-8")
    (bundle_dir / "map.json").write_text(json.dumps({"format_version": 2, "map_id": "t"}), encoding="utf-8")

    packed = tmp_path / f"bundle{PACKED_BUNDLE_EXT}"
    pack_bundle_dir_to_irunmap(bundle_dir=bundle_dir, out_path=packed, compresslevel=1)

    h = resolve_bundle_handle_path(packed)
    assert h is not None
    assert h.bundle_ref == packed
    assert h.map_json.name == "map.json"
    payload = json.loads(h.map_json.read_text(encoding="utf-8"))
    assert payload["map_id"] == "t"
    assert (h.map_json.parent / "materials" / "a.txt").read_text(encoding="utf-8") == "ok"

