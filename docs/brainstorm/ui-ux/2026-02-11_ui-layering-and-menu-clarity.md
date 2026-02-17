# UI Layering and Menu Clarity (Session Notes)

## Timestamped Notes

### 2026-02-11 00:00 (local session capture)
**User Goal**
- Rework menu/UI so elements stop overlapping and the interface feels significantly cleaner and more intuitive.

**User Motivation**
- Current runtime UI has visible collisions between overlays/menu elements.
- The user expects a stronger, more polished visual hierarchy (not just small fixes).

**Current Direction**
- Move from scattered per-screen coordinates to shared layout anchors in `ivan/ui/ui_layout.py`.
- Enforce explicit render-layer ordering for all major UI roots in `RunnerDemo` (`HUD < overlays < menus < console`).
- Reduce overlap noise by making `F2` input-debug gameplay-only and suppressing the error console while the full console is open.
- Keep the procedural `ui-kit` path as the default, while improving in-game integration around it.

**Open Questions / Risks**
- Some roots (for example list-menu-backed overlays) still depend on creation timing unless they also expose explicit root-node layering hooks.
- No broad window-resize reflow pass was done for every UI surface yet; further responsive cleanup may be needed for extreme aspect ratios.
- Additional polish pass may be needed for typography/spacing consistency across all tabs after gameplay validation.

### 2026-02-11 05:15 (hotfix + polish)
**User Goal**
- Unblock runtime crash and continue UI refinement.

**User Motivation**
- Current build fails at startup, preventing further UI validation.

**Current Direction**
- Hotfix applied: `debug_ui` bottom status-bar width now uses numeric `screen_ar` (not function object), resolving startup `TypeError`.
- Continued pause-menu clarity pass: slightly wider panel and clearer tab labels (`Options`, `Online`) to reduce truncation and improve scanability.

**Open Questions / Risks**
- Need in-game screenshot validation across multiple resolutions to ensure wider pause panel never collides with edge overlays.
### 2026-02-15 06:20 (runtime UI overhaul docs update)
**User Goal**
- Update project documentation so the pps/ivan-godot runtime UI overhaul is accurately captured and easy to hand off.

**User Motivation**
- Keep implementation and docs synchronized for collaboration and reduce ambiguity around runtime controls and persistence behavior.
- Preserve a durable session record in brainstorm notes per repository policy.

**Current Direction**
- Document runtime UI capabilities explicitly: console autocomplete/hints/history/favorites, movement runtime body controls (gravity_scale, standing_height), persistence layout in user://runtime_ui/..., and overflow/readability handling.
- Add a concise free/permissive UI asset shortlist (Kenney UI Pack, Kenney UI Pack Sci-Fi, Jamie Cross GUI Kit) with links and fit rationale for rapid iteration.
- Keep updates scoped to docs only, without changing unrelated implementation files.

**Open Questions / Risks**
- External asset licenses should be re-verified at integration/release time in case pack metadata or terms change upstream.
- UI readability/overflow behavior may still need an additional real-device pass across unusual aspect ratios.

