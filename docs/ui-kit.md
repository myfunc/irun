# UI Kit (Experimental)

The IRUN UI Kit is an **experimental, procedural** widget library targeting **Panda3D DirectGUI**.
It lives under `apps/ui_kit/` and is designed to stabilize UI primitives and theme rules before
wiring them into `apps/ivan`.

## Goals
- Procedural-first: no required shipped textures to get usable UI.
- Predictable layout: consistent padding/gaps, local coordinate containers, no ad-hoc magic numbers.
- Theme tokens: palette, typography, and layout constants live in `Theme`.
- Low-res readability: console-friendly mono fonts + crisp filtering; avoid tiny, low-contrast text.
- High-DPI tolerance: scale typography/layout based on framebuffer vs window ratio (best-effort).

## Coordinate System Rule (Non-Negotiable)
Panels/windows provide a **local coordinate space** for children:
- The returned node is positioned globally.
- Children should use local `pos` and local `frameSize` within `0..w` and `0..h`.

Mixing global coordinates into child `frameSize`/`pos` tends to cause overlapping and giant-rect bugs.

## Theme
Core token type: `irun_ui_kit.theme.Theme`.

Theme provides:
- Layout tokens: `pad`, `gap`, `outline_w`, `header_h`, `accent_h`.
- Typography tokens: `title_scale`, `label_scale`, `small_scale`.
- Palette tokens: background/panel colors and an **accent** color (orange) used as outline/underline.
- Depth cues: procedural shadow color + offsets (no textures required).

Overrides:
- `Theme.with_overrides(...)` for code-level tweaks.
- `Theme.from_json(path)` for project-side overrides.

High-DPI:
- `Theme.with_dpi(scale)` scales typography aggressively and layout conservatively.
- `UIRenderer` applies DPI scaling automatically using framebuffer/window ratio when available.

Fonts:
- `UIRenderer` tries to pick a console-friendly mono font on the host platform (eg. macOS Monaco),
  and loads it with nearest filtering for crisp low-res rendering.

## Components
All components are thin DirectGUI wrappers in `apps/ui_kit/src/irun_ui_kit/widgets/`.

Containers:
- `Window`: draggable titlebar; `content` container for child widgets.
- `Panel`: local container with accent outline and drop shadow.
- `Tabs`: tab bar + pages (hide/show groups of controls).
- `CollapsiblePanel`: header-click collapsible section; collapses to header-only height and supports relayout.

Controls:
- `Button`: hover + pressed state via per-state frame colors.
- `Checkbox`: visual checkbox (box + mark) with hover/pressed feedback.
- `Slider`: compact horizontal slider with value readout.
- `TextInput`: DirectEntry wrapper with a consistent frame and basic editing hotkeys (macOS-focused).

## Demo / Playground
The kit includes an interactive playground to exercise the components on one screen:

```bash
PYTHONPATH=apps/ui_kit/src apps/ivan/.venv/bin/python -m irun_ui_kit.demo
```

Smoke screenshot:
```bash
PYTHONPATH=apps/ui_kit/src apps/ivan/.venv/bin/python -m irun_ui_kit.demo --smoke-screenshot /tmp/irun-ui-kit.png
```

## Integration Plan
- Iterate UI primitives and theme rules in `apps/ui_kit`.
- Once stable, selectively port/wire components into `apps/ivan` UI screens.
- Keep `apps/ui_kit` free of game-specific content; it should remain a reusable library.

