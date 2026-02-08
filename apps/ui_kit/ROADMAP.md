# UI Kit Roadmap

This file tracks planned UI-kit work. It is intentionally focused on library capabilities,
not game-specific screens.

## Goals
- One consistent style across all screens.
- Procedural-first baseline: no required assets to ship a usable UI.
- Composition-first architecture: small widgets with explicit APIs.
- Predictable layout: reusable panels/grids/stack layouts, no ad-hoc positioning per screen.

## Milestones

### M0: Stabilize Primitives (Now)
- Window
  - draggable titlebar
  - content area container
- Panel
  - consistent outline/fill/header
- Button
  - consistent sizing and baseline text alignment
- Text input
  - search-friendly textbox control
- Theme tokens
  - palette/layout/typography tokens
  - `Theme.from_json()` for project-side overrides

### M1: Layout System
- `Stack` layout (vertical/horizontal flow + spacing)
- `Grid` presets
  - Compact grid (dense debug-style)
  - Roomy grid (menu/settings-style)
- Constraints
  - safe margins
  - minimum hit target sizes

### M2: Interaction Model
- Focus system
  - visible focus ring / highlight
  - keyboard navigation (Tab/Shift+Tab, arrows)
- Input capture rules
  - when UI is open, gameplay input is blocked (game continues running)

### M3: Controls
- Checkbox (single toggle widget)
- Slider (track + knob + value label)
- List/select
  - selection highlight
  - optional scroll
- Tooltip
  - anchored to focused control
  - does not overlap cursor

### M4: Window Manager
- Bring-to-front on click
- Optional modal overlay
- Optional snap/dock helpers (only if needed)

## Quality Bar (Definition of Done)
- No overlapping panels in default layouts.
- No clipped text in default sizes (unless explicitly elided with `...`).
- All interactive widgets have visible focus and pressed states.
- All layout constants come from `Theme` (no random per-screen padding).

