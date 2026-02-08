# Passport B: PS2 Minimal Industrial (Cyan) / Variant E: Bevel + Heavy Shadow

## Intent
- Same PS1/PS2-era minimal UI direction, but with a distinct layout/framing recipe.
## Variant Parameters
- margin: `14px` (base 640x360)
- pad: `8px` (base 640x360)
- outline width: `1px`
- shadow offset: `4px`
- bevel: `True`

## Tokens (Core)
- outline: `#5A5C62`
- text: `#ECEEF4`
- accent: `#46DCE6`

## Rules
- Buttons must always fit inside their parent panel; layout adapts (4-wide or 2x2) based on available width.
- Padding/margins are part of the style and must not vary per-screen.
