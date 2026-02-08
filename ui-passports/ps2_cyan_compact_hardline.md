# Passport B: PS2 Minimal Industrial (Cyan) / Variant D: Compact Hardline

## Intent
- Same PS1/PS2-era minimal UI direction, but with a distinct layout/framing recipe.
## Variant Parameters
- margin: `10px` (base 640x360)
- pad: `6px` (base 640x360)
- outline width: `2px`
- shadow offset: `2px`
- bevel: `False`

## Tokens (Core)
- outline: `#5A5C62`
- text: `#ECEEF4`
- accent: `#46DCE6`

## Rules
- Buttons must always fit inside their parent panel; layout adapts (4-wide or 2x2) based on available width.
- Padding/margins are part of the style and must not vary per-screen.
