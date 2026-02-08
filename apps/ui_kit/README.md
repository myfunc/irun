# IRUN UI Kit (Experimental)

Procedural UI kit for IRUN, targeting Panda3D DirectGUI.

This package is intentionally **separate** from the main game runtime while we iterate on:
- consistent layout rules (padding/margins)
- theme/palette overrides
- reusable window/panel/control primitives

## Why This Exists
Our UI work is currently scattered across ad-hoc DirectGUI usage. This package exists to:
- standardize layout and component behavior (so UI does not drift stylistically)
- provide a small set of reusable primitives that compose cleanly
- keep UI iteration fast while staying procedural-first (no asset dependency required)

## Core Requirements (Baseline)
- Procedural-first baseline: no required shipped textures/fonts for the kit.
- Theme tokens: palette/layout/typography are configurable from the project.
- Local layout rule: each window/panel provides a **local coordinate space** for children.
  - Do not mix global coordinates into child `frameSize`/`pos` (it causes overlapping/giant rect bugs).
- UI must be usable in a single pass:
  - no text clipping in default sizes
  - no panels overlapping each other unexpectedly

## Current Components
Implemented as small wrappers around DirectGUI.
- `Theme` (`irun_ui_kit.theme.Theme`)
  - `with_overrides(**kwargs)` for in-code customization
  - `from_json(path)` for project-side theme overrides
  - retro defaults (burnt orange accent, heavy shadows)
  - renderer picks a low-res readable mono font by default (platform-dependent)
  - `Theme.with_dpi(scale)` can be used to scale typography/layout for high-DPI displays
- `Window` (`irun_ui_kit.widgets.window.Window`)
  - window frame + header
  - draggable by titlebar (implemented via task update while dragging)
  - `content` container for child widgets
- `Panel` (`irun_ui_kit.widgets.panel.Panel`)
  - outline + fill + optional header/title
  - local coordinate container for children
  - procedural drop shadow (theme-driven)
- `Button` (`irun_ui_kit.widgets.button.Button`)
  - consistent sizing + baseline text alignment
  - hover + pressed visual states (frame color)
- `TextInput` (`irun_ui_kit.widgets.text_input.TextInput`)
  - textbox suited for search fields and quick inputs
  - basic editing shortcuts (macOS-focused): copy/paste/cut, clear-all
- `Tabs` (`irun_ui_kit.widgets.tabs.Tabs`)
  - tab bar + pages (hide/show groups of controls)
- `Checkbox` (`irun_ui_kit.widgets.checkbox.Checkbox`)
  - visual checkbox (box + mark) with hover/pressed feedback
- `Slider` (`irun_ui_kit.widgets.slider.Slider`)
  - basic slider with value readout
- `CollapsiblePanel` (`irun_ui_kit.widgets.collapsible.CollapsiblePanel`)
  - panel section with a clickable header to hide/show its content

## Layout Helpers
- `GridSpec` (`irun_ui_kit.layout.GridSpec`)
  - simple fixed grid for placing controls
  - designed to be minimal: start with 1-2 grid patterns and expand only when needed

## Theme Overrides
Example JSON (colors can be floats 0..1 or ints 0..255):
```json
{
  "header": [200, 86, 25, 255],
  "panel": [0.14, 0.14, 0.16, 0.98],
  "pad": 0.06
}
```

Load it:
```py
from irun_ui_kit.theme import Theme

theme = Theme.from_json(\"/path/to/theme.json\")
```

## Run Demo (Using Ivan venv)

The monorepo already has a Panda3D venv under `apps/ivan/.venv/`.

Run from repo root:
```bash
apps/ivan/.venv/bin/python -m irun_ui_kit.demo
```

Optional: take a screenshot and exit:
```bash
apps/ivan/.venv/bin/python -m irun_ui_kit.demo --smoke-screenshot /tmp/irun-ui-kit.png
```

## Roadmap (Near Term)
Next features to add, in order:
1. Layout primitives
  - `Stack` (vertical/horizontal flow)
  - `Grid` presets (at most 2 initially): compact and roomy
2. Interaction + UX rules
   - consistent focus state and keyboard navigation (Up/Down/Tab/Enter/Esc)
   - hover/pressed/disabled states standardized via theme tokens
3. Controls
   - checkbox (single control, not two buttons) (done)
   - slider with value label (done)
   - list/select (for menus)
4. Window management
   - z-order (bring to front on click)
   - optional modal windows
5. Text + content
   - proper text clipping/ellipsis utilities
   - scroll container (for long debug/settings menus)

## More Docs
- Global overview: `docs/ui-kit.md`
