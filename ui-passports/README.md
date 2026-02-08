# UI Passports (Experimental)

This folder is intentionally **separate from the main game code**. It exists to iterate on UI style direction
and to standardize UI composition before we wire themes/widgets into runtime UI.

## Contents
- `render_kits.py`: Procedurally renders UI kit previews (no external assets) to `ui-passports/out/`.
- `ps1_amber.md`: Passport A: PS1 Dev Console (Amber)
- `ps2_cyan.md`: Passport B: PS2 Minimal Industrial (Cyan)
- `crt_lime.md`: Passport C: CRT HUD (Lime)

## Render
Run from repo root:
```bash
python ui-passports/render_kits.py
```

Outputs:
- `ui-passports/out/kit_ps1_amber.png`
- `ui-passports/out/kit_ps2_cyan.png`
- `ui-passports/out/kit_crt_lime.png`

## Interactive Prototype
Run the click-through prototype (uses Panda3D from the Ivan venv):
```bash
apps/ivan/.venv/bin/python ui-passports/run_prototype.py
```
