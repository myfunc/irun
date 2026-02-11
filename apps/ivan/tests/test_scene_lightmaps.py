from __future__ import annotations


def test_resolve_lightmaps_skips_faces_when_files_missing(tmp_path) -> None:
    from ivan.world.scene import WorldScene

    map_json = tmp_path / "map.json"
    map_json.write_text("{}", encoding="utf-8")

    payload = {
        "lightmaps": {
            "faces": {
                "10": {
                    "paths": ["lightmaps/f10_lm0.png", None, None, None],
                    "styles": [0, None, None, None],
                }
            }
        }
    }

    out = WorldScene._resolve_lightmaps(map_json=map_json, payload=payload)
    assert out is None


def test_resolve_lightmaps_keeps_only_faces_with_existing_files(tmp_path) -> None:
    from ivan.world.scene import WorldScene

    map_json = tmp_path / "map.json"
    map_json.write_text("{}", encoding="utf-8")

    lightmaps_dir = tmp_path / "lightmaps"
    lightmaps_dir.mkdir(parents=True, exist_ok=True)
    existing = (lightmaps_dir / "f0_lm0.png").resolve()
    existing.write_bytes(b"")

    payload = {
        "lightmaps": {
            "faces": {
                "0": {
                    "paths": ["lightmaps/f0_lm0.png", None, None, None],
                    "styles": [0, None, None, None],
                },
                "1": {
                    "paths": ["lightmaps/f1_lm0.png", None, None, None],
                    "styles": [0, None, None, None],
                },
            }
        }
    }

    out = WorldScene._resolve_lightmaps(map_json=map_json, payload=payload)
    assert isinstance(out, dict)
    assert 0 in out
    assert 1 not in out
    assert out[0]["paths"][0] == existing


def test_lights_from_payload_parses_goldsrc_light_entities() -> None:
    from ivan.world.scene import WorldScene

    payload = {
        "lights": [
            {
                "classname": "light_spot",
                "origin": [1, 2, 3],
                "color": [0.5, 0.25, 0.125],
                "brightness": 350,
                "pitch": -30,
                "angles": [0, 90, 0],
                "inner_cone": 20,
                "outer_cone": 35,
                "fade": 1.5,
                "falloff": 2,
                "style": 3,
            }
        ]
    }

    lights = WorldScene._lights_from_payload(payload=payload)
    assert len(lights) == 1
    le = lights[0]
    assert le.classname == "light_spot"
    assert le.origin == (1.0, 2.0, 3.0)
    assert le.angles == (0.0, 90.0, 0.0)
    assert le.inner_cone == 20.0
    assert le.outer_cone == 35.0
