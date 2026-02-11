from __future__ import annotations

from ivan.world.lightstyles import lightstyle_pattern_scale


def parse_lightstyles(*, payload: dict) -> dict[int, str]:
    raw = payload.get("lightstyles")
    if not isinstance(raw, dict):
        return {}
    out: dict[int, str] = {}
    for k, v in raw.items():
        try:
            idx = int(k)
        except Exception:
            continue
        if not isinstance(v, str) or not v.strip():
            continue
        out[int(idx)] = v.strip()
    return out


def default_goldsrc_lightstyles() -> dict[int, str]:
    return {
        0: "m",
        1: "mmnmmommommnonmmonqnmmo",
        2: "abcdefghijklmnopqrstuvwxyzyxwvutsrqponmlkjihgfedcba",
        3: "mmmmmaaaaammmmmaaaaaabcdefgabcdefg",
        4: "mamamamamama",
        5: "jklmnopqrstuvwxyzyxwvutsrqponmlkjlk",
        6: "nmonqnmomnmomomno",
        7: "mmmaaaabcdefgmmmmaaaammmaamm",
        8: "mmmaaammmaaammmabcdefaaaammmmabcdefmmmaaaa",
        9: "aaaaaaaazzzzzzzz",
        10: "mmamammmmammamamaaamammma",
        11: "abcdefghijklmnopqrrqponmlkjihgfedcba",
    }


def resolve_lightstyles(*, payload: dict, cfg: dict | None) -> tuple[dict[int, str], str]:
    preset = "original"
    overrides: dict[int, str] = {}
    if isinstance(cfg, dict):
        p = cfg.get("preset")
        if isinstance(p, str) and p.strip():
            preset = p.strip()
        ov = cfg.get("overrides")
        if isinstance(ov, dict):
            for k, v in ov.items():
                try:
                    si = int(k)
                except Exception:
                    continue
                if isinstance(v, str) and v.strip():
                    overrides[int(si)] = v.strip()

    mode = "animate"
    if preset == "static":
        mode = "static"

    defaults = default_goldsrc_lightstyles()
    from_map = parse_lightstyles(payload=payload)

    if preset == "server_defaults":
        out = dict(defaults)
    else:
        out = dict(defaults)
        out.update(from_map)

    out.update(overrides)
    if 0 not in out:
        out[0] = "m"
    return (out, mode)


def lightstyle_scale(*, style: int, frame: int, styles: dict[int, str]) -> float:
    if style == 0:
        pat = styles.get(0) or "m"
    else:
        pat = styles.get(int(style))
    return float(lightstyle_pattern_scale(pat or "m", frame=int(frame)))

