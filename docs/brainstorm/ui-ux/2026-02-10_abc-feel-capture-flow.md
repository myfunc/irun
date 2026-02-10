# ABC Feel Capture Flow (Draft)

## Problem Observed
- Recording/export flow felt ambiguous during A/B/C route sessions.
- Users were unsure whether compare used latest replay globally or latest run for the selected route.
- Single free-text field mixed two intents:
  - run notes (what happened)
  - tuning prompt (what to change)

## Proposed UX Direction
- Keep replay capture in gameplay loop, not hidden in ESC tab:
  - `G` opens a quick capture popup.
- Popup fields:
  - route selector (`A/B/C`)
  - `Route Name` (optional, human-readable label)
  - `Run Notes` (optional)
  - `Feedback` (optional tuning prompt)
- Actions:
  - `Save + Export`
  - `Export + Apply`

## Data/Comparison Behavior
- Export always saves the current recording first, then exports that exact replay.
- Route compare is route-scoped:
  - latest route run vs preferred prior route run
  - preferred prior run = latest prior run with notes/feedback, else immediate prior
- Keep longer-term context:
  - compare vs baseline run (first run for route) when available
  - per-route history context JSON for trend analysis

## Why This Helps
- Removes ambiguity for 3-run A/B/C iterations.
- Makes each run a clear artifact (one replay + one export package).
- Preserves future tuning context without requiring manual file hunting.

## Follow-up Ideas
- Add compact in-popup route stats (run count, last compare summary).
- Add route presets beyond `A/B/C` if sessions outgrow three fixed lanes.
- Add one-click "Export current and open compare file" action for analyst workflow.
