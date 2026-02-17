from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from pathlib import Path


RPG_MODEL_FILES = (
    "v_rpg.mdl",
    "p_rpg.mdl",
    "w_rpg.mdl",
    "w_rpgt.mdl",
    "rpgrocket.mdl",
)

SDK_RPG_REL = Path("Weapon Models") / "v_rpg"


@dataclass(frozen=True)
class CopyResult:
    copied: list[str]
    missing: list[str]
    skipped_up_to_date: list[str]


def _copy_if_needed(src: Path, dst: Path) -> str:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        try:
            if dst.stat().st_size == src.stat().st_size and dst.stat().st_mtime >= src.stat().st_mtime:
                return "skipped"
        except OSError:
            pass
    shutil.copy2(src, dst)
    return "copied"


def _copy_models_from_game(*, hl_root: Path, out_raw_root: Path) -> CopyResult:
    models_root = hl_root / "valve" / "models"
    copied: list[str] = []
    missing: list[str] = []
    skipped: list[str] = []
    for filename in RPG_MODEL_FILES:
        src = models_root / filename
        rel = f"valve/models/{filename}"
        if not src.exists():
            missing.append(rel)
            continue
        dst = out_raw_root / filename
        status = _copy_if_needed(src, dst)
        if status == "copied":
            copied.append(rel)
        else:
            skipped.append(rel)
    return CopyResult(copied=copied, missing=missing, skipped_up_to_date=skipped)


def _copy_sdk_sources(*, sdk_root: Path, out_raw_root: Path) -> CopyResult:
    src_root = sdk_root / SDK_RPG_REL
    out_root = out_raw_root / "v_rpg_sdk"
    copied: list[str] = []
    missing: list[str] = []
    skipped: list[str] = []
    if not src_root.exists() or not src_root.is_dir():
        missing.append(str(SDK_RPG_REL).replace("\\", "/"))
        return CopyResult(copied=copied, missing=missing, skipped_up_to_date=skipped)

    sdk_rel_root = str(SDK_RPG_REL).replace("\\", "/")
    for src in sorted(src_root.iterdir()):
        if not src.is_file():
            continue
        rel = f"{sdk_rel_root}/{src.name}"
        dst = out_root / src.name
        status = _copy_if_needed(src, dst)
        if status == "copied":
            copied.append(rel)
        else:
            skipped.append(rel)
    return CopyResult(copied=copied, missing=missing, skipped_up_to_date=skipped)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Sync Half-Life RPG reference assets (models + SDK sources) into "
            "apps/ivan/assets/models/halflife/raw."
        )
    )
    parser.add_argument("--hl-root", required=True, help="Path to Half-Life install root.")
    parser.add_argument("--sdk-root", required=True, help="Path to Half-Life SDK install root.")
    parser.add_argument(
        "--out-root",
        default=None,
        help="Optional output root for halflife model assets (default: apps/ivan/assets/models/halflife).",
    )
    args = parser.parse_args()

    script_root = Path(__file__).resolve().parent
    app_root = script_root.parent
    default_out_root = app_root / "assets" / "models" / "halflife"

    hl_root = Path(args.hl_root)
    sdk_root = Path(args.sdk_root)
    out_root = Path(args.out_root) if args.out_root else default_out_root
    raw_root = out_root / "raw"
    raw_root.mkdir(parents=True, exist_ok=True)

    model_res = _copy_models_from_game(hl_root=hl_root, out_raw_root=raw_root)
    sdk_res = _copy_sdk_sources(sdk_root=sdk_root, out_raw_root=raw_root)

    report = {
        "hl_root": str(hl_root),
        "sdk_root": str(sdk_root),
        "out_root": str(out_root),
        "models": {
            "copied": model_res.copied,
            "skipped_up_to_date": model_res.skipped_up_to_date,
            "missing": model_res.missing,
        },
        "sdk_sources": {
            "copied": sdk_res.copied,
            "skipped_up_to_date": sdk_res.skipped_up_to_date,
            "missing": sdk_res.missing,
        },
    }
    report_path = raw_root / "rpg_sync_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    copied_count = len(model_res.copied) + len(sdk_res.copied)
    skipped_count = len(model_res.skipped_up_to_date) + len(sdk_res.skipped_up_to_date)
    missing_count = len(model_res.missing) + len(sdk_res.missing)
    print(
        f"[sync-rpg] copied={copied_count} skipped_up_to_date={skipped_count} "
        f"missing={missing_count} report={report_path}"
    )


if __name__ == "__main__":
    main()
