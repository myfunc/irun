"""Schema-driven definitions for the runtime tweak panel.

Each entry maps UI controls to console commands. The panel reads/writes via typed
console commands only (e.g. vm_rpg_pos, vm_rpg_hpr). Values are parsed from
vm_rpg_print output (vm_rpg.pos=[x,y,z], vm_rpg.hpr=[h,p,r], etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TweakFieldSpec:
    """Single tweak field: label, command for set, output key from vm_rpg_print."""

    key: str  # Key in parsed state (e.g. "pos", "hpr", "model_hpr", "model_scale", "target_longest")
    label: str
    set_cmd: str  # Command name for set (e.g. "vm_rpg_pos")
    components: tuple[str, ...]  # ("x","y","z") or ("h","p","r") or ("size",)
    min_val: float
    max_val: float
    precision: int = 3


# RPG viewmodel tuning fields. Output keys match vm_rpg_print JSON keys.
RPG_VIEWMODEL_FIELDS: tuple[TweakFieldSpec, ...] = (
    TweakFieldSpec(
        key="pos",
        label="Position (x y z)",
        set_cmd="vm_rpg_pos",
        components=("x", "y", "z"),
        min_val=-5.0,
        max_val=5.0,
    ),
    TweakFieldSpec(
        key="hpr",
        label="Rotation (h p r)",
        set_cmd="vm_rpg_hpr",
        components=("h", "p", "r"),
        min_val=-180.0,
        max_val=180.0,
    ),
    TweakFieldSpec(
        key="model_hpr",
        label="Model pivot HPR (h p r)",
        set_cmd="vm_rpg_model_hpr",
        components=("h", "p", "r"),
        min_val=-180.0,
        max_val=180.0,
    ),
    TweakFieldSpec(
        key="model_scale",
        label="Model scale (x y z)",
        set_cmd="vm_rpg_model_scale",
        components=("x", "y", "z"),
        min_val=-2.0,
        max_val=2.0,
    ),
    TweakFieldSpec(
        key="target_longest",
        label="Size scalar",
        set_cmd="vm_rpg_size",
        components=("size",),
        min_val=0.01,
        max_val=10.0,
    ),
)

# Map vm_rpg_print output keys to field specs.
RPG_FIELD_BY_KEY: dict[str, TweakFieldSpec] = {f.key: f for f in RPG_VIEWMODEL_FIELDS}


def parse_vm_rpg_state(lines: list[str]) -> dict[str, list[float]]:
    """Parse vm_rpg_print output lines into a dict of key -> [values].

    Expects lines like:
      vm_rpg.pos=[1.0, 2.0, 3.0]
      vm_rpg.hpr=[0.0, 0.0, 0.0]
      vm_rpg.target_longest=[1.5]
    """
    import json

    out: dict[str, list[float]] = {}
    for line in lines:
        line = str(line or "").strip()
        if "=" not in line or not line.startswith("vm_rpg."):
            continue
        key_part, val_part = line.split("=", 1)
        key = key_part.replace("vm_rpg.", "").strip()
        if key not in RPG_FIELD_BY_KEY:
            continue
        try:
            raw = json.loads(val_part.strip())
            if isinstance(raw, list):
                out[key] = [float(v) for v in raw]
            elif isinstance(raw, (int, float)):
                out[key] = [float(raw)]
            else:
                continue
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    return out


def build_console_script(state: dict[str, list[float]]) -> str:
    """Build a console-script config text from current state for clipboard export."""
    lines: list[str] = []
    for spec in RPG_VIEWMODEL_FIELDS:
        vals = state.get(spec.key)
        if vals is None:
            continue
        if spec.set_cmd == "vm_rpg_pos":
            lines.append(f"vm_rpg_pos {' '.join(f'{v:.4f}' for v in vals[:3])}")
        elif spec.set_cmd == "vm_rpg_hpr":
            lines.append(f"vm_rpg_hpr {' '.join(f'{v:.4f}' for v in vals[:3])}")
        elif spec.set_cmd == "vm_rpg_model_hpr":
            lines.append(f"vm_rpg_model_hpr {' '.join(f'{v:.4f}' for v in vals[:3])}")
        elif spec.set_cmd == "vm_rpg_model_scale":
            lines.append(f"vm_rpg_model_scale {' '.join(f'{v:.4f}' for v in vals[:3])}")
        elif spec.set_cmd == "vm_rpg_size":
            if vals:
                lines.append(f"vm_rpg_size {vals[0]:.4f}")
    return "\n".join(lines) if lines else "vm_rpg_reset"
