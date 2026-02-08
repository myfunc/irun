# Passport C: CRT HUD (Lime)



## Intent

- Minimal PS1/PS2-era UI: flat panels, hard edges, clear focus, high readability while moving.
- Procedural-only: no shipped fonts/textures required for the baseline kit.
- Suitable for boomer-shooter style menus/HUD and in-game debug panels.

## Tokens (Core)

- bg0: `#060A08`
- bg1: `#0A100C`
- panel: `#0A100C`
- panel2: `#0E1610`
- outline: `#5ADC78`
- text: `#D2FFDC`
- text_muted: `#82BE96`
- accent: `#78FFA0`
- ok: `#78FFA0`
- danger: `#FF5C5C`

## Typography (Procedural Baseline)

- Base grid: 640x360 logical pixels, scaled 3x to 1920x1080 with nearest-neighbor.
- Font: default bitmap (placeholder). When a custom font is introduced later, keep the same sizes and spacing rules.
- Text rules: short labels, avoid long paragraphs; use tooltips for explanations.

## Spacing + Layout

- Grid step: 2px (base). Padding common: 6px (base) inside panels.
- Safe margins: 12px (base) from screen edge for primary containers.
- Focus: always visible outline + subtle glow fill; never rely on color alone for selection.

## Component Contract

- Window/Panel: titlebar band, 1px outline, dither fill, optional drop shadow.
- Button states: default, hover/focus, pressed, disabled, danger.
- List: single selection, always shows cursor marker, selection outline, scroll hints when needed.
- Toggle: OFF/ON segmented control.
- Slider: thick track + chunky knob.
- Entry: outlined field with readable contrast.
- Dropdown: single-line select with chevron.
- Tooltip: anchored, never overlaps cursor, single responsibility: explain focused item.
- Meter: labeled bar, color-coded by semantics (ok/accent/danger).

## Do-Not

- No soft gradients; no blurry shadows; no tiny hit targets.
- No inconsistent paddings per screen; no ad-hoc colors outside tokens.