from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ivan.maps.catalog import (
    MapBundle,
    detect_goldsrc_like_mods,
    find_runnable_bundles,
    list_goldsrc_like_maps,
    resolve_goldsrc_install_root,
)
from ivan.maps.steam import detect_steam_halflife_game_root
from ivan.paths import app_root as ivan_app_root
from ivan.state import IvanState, load_state, resolve_map_json, update_state
from ivan.ui.native_dialogs import pick_directory
from ivan.ui.retro_menu_ui import RetroMenuItem, RetroMenuUI


@dataclass(frozen=True)
class ImportRequest:
    game_root: str
    mod: str
    map_label: str
    bsp_path: str


class MainMenuController:
    def __init__(
        self,
        *,
        aspect2d,
        initial_game_root: str | None,
        initial_mod: str | None,
        state: IvanState | None = None,
        on_start_map_json,
        on_import_bsp,
        on_quit,
    ) -> None:
        self._on_start_map_json = on_start_map_json
        self._on_import_bsp = on_import_bsp
        self._on_quit = on_quit

        self._app_root = ivan_app_root()
        self._state = state or load_state()
        self._ui = RetroMenuUI(
            aspect2d=aspect2d,
            title="IVAN",
            hint="Up/Down: select | Enter: choose | Esc: back/quit",
        )

        self._screen: str = "main"  # main | bundles | mods | maps
        self._bundles: list[MapBundle] = []
        self._game_root: str | None = initial_game_root or self._state.last_game_root
        self._mod: str | None = initial_mod or self._state.last_mod
        self._mods: list[str] = []
        self._maps = []

        self._continue_map_json: str | None = self._state.last_map_json
        self._continue_label: str | None = None
        self._continue_enabled: bool = False
        self._refresh_continue()
        self._normalize_game_root()
        self._refresh_main()

    def destroy(self) -> None:
        self._ui.destroy()

    def tick(self, now: float) -> None:
        self._ui.tick(now)

    def set_status(self, text: str) -> None:
        self._ui.set_status(text)

    def set_loading_status(self, text: str, *, started_at: float) -> None:
        self._ui.set_loading_status(text, started_at=started_at)

    def on_up(self) -> None:
        self._ui.move(-1)

    def on_down(self) -> None:
        self._ui.move(1)

    def on_escape(self) -> None:
        if self._screen == "main":
            self._on_quit()
            return
        self._screen = "main"
        self._refresh_main()

    def on_enter(self) -> None:
        idx = self._ui.selected_index()
        if idx is None:
            return

        if self._screen == "main":
            self._enter_main(idx)
            return
        if self._screen == "bundles":
            self._enter_bundle(idx)
            return
        if self._screen == "mods":
            self._enter_mod(idx)
            return
        if self._screen == "maps":
            self._enter_map(idx)
            return

    def _refresh_main(self) -> None:
        self._ui.set_title("IVAN :: Main Menu")
        items: list[RetroMenuItem] = []

        self._refresh_continue()
        self._normalize_game_root()
        if self._continue_map_json:
            label = self._continue_label or self._continue_map_json
            items.append(RetroMenuItem(f"Continue: {label}", enabled=self._continue_enabled))

        # Quick start: Bounce if present.
        bounce = (self._app_root / "assets" / "imported" / "halflife" / "valve" / "bounce" / "map.json")
        items.append(RetroMenuItem("Quick Start: Bounce", enabled=bounce.exists()))

        items.append(RetroMenuItem("Play Imported/Generated Map Bundle"))
        items.append(RetroMenuItem("Import GoldSrc/Xash3D Map From Game Directory"))
        items.append(RetroMenuItem("Auto-detect Steam Half-Life"))

        if self._game_root:
            items.append(RetroMenuItem(f"Game dir: {self._game_root}"))
        else:
            items.append(RetroMenuItem("Game dir: (not set)"))

        items.append(RetroMenuItem("Quit"))
        self._ui.set_items(items, selected=0)
        self._ui.set_status("")

    def _normalize_game_root(self) -> None:
        """
        Make the stored game root compatible with our importer expectations.

        On macOS, users often pick the Steam "common/<Game>" folder that contains `<Game>.app`.
        In that case, the actual mod folders live under `<Game>.app/Contents/Resources`.
        """

        if not self._game_root:
            return
        try:
            resolved = resolve_goldsrc_install_root(Path(self._game_root))
        except Exception:
            resolved = None
        if resolved is None:
            return
        # Only rewrite if it actually changes and points at something that exists.
        try:
            new_root = str(resolved)
            if new_root and Path(new_root).exists() and new_root != self._game_root:
                self._game_root = new_root
                update_state(last_game_root=self._game_root, last_mod=self._mod)
        except Exception:
            pass

    def _enter_main(self, idx: int) -> None:
        # Optional Continue is inserted at the top if we have any prior state.
        if self._continue_map_json:
            if idx == 0:
                if not self._continue_enabled:
                    self._ui.set_status("Last map is missing/unresolvable.")
                    return
                self._on_start_map_json(self._continue_map_json)
                return
            idx -= 1

        if idx == 0:
            bounce = self._app_root / "assets" / "imported" / "halflife" / "valve" / "bounce" / "map.json"
            if not bounce.exists():
                self._ui.set_status("Bounce bundle not found under assets/imported/halflife/valve/bounce.")
                return
            self._on_start_map_json(str(bounce))
            return

        if idx == 1:
            self._screen = "bundles"
            self._bundles = find_runnable_bundles(app_root=self._app_root)
            items = [RetroMenuItem(b.label) for b in self._bundles]
            self._ui.set_title("IVAN :: Map Bundles")
            self._ui.set_hint("Up/Down: select | Enter: run | Esc: back")
            self._ui.set_items(items, selected=0)
            self._ui.set_status(f"{len(items)} bundles found.")
            return

        if idx == 2:
            if not self._game_root:
                r = pick_directory(title="Select GoldSrc/Xash3D game directory")
                if not r.ok or not r.path:
                    self._ui.set_status(r.error or "Directory pick failed.")
                    return
                self._game_root = r.path
                self._normalize_game_root()
            self._mods = detect_goldsrc_like_mods(game_root=Path(self._game_root))
            if not self._mods:
                self._ui.set_status(
                    "No mods found (expected: <root>/<mod>/maps/*.bsp). "
                    "If you picked a macOS .app bundle, try selecting the parent folder or the .app itself."
                )
                return
            update_state(last_game_root=self._game_root, last_mod=self._mod)
            self._screen = "mods"
            self._ui.set_title("IVAN :: Select Mod")
            self._ui.set_hint("Up/Down: select | Enter: choose | Esc: back")
            selected = 0
            if self._mod and self._mod in self._mods:
                selected = self._mods.index(self._mod)
            self._ui.set_items([RetroMenuItem(m) for m in self._mods], selected=selected)
            self._ui.set_status(f"{len(self._mods)} mods found.")
            return

        if idx == 3:
            p = None
            try:
                p = detect_steam_halflife_game_root()
            except Exception:
                p = None
            if not p:
                self._ui.set_status("Steam Half-Life not found. Use 'Set Game Dir (Pick Folder)'.")
                return
            self._game_root = str(p)
            self._normalize_game_root()
            update_state(last_game_root=self._game_root, last_mod=self._mod)
            self._refresh_main()
            self._ui.set_status("Auto-detected Steam Half-Life game directory.")
            return

        if idx == 4:
            r = pick_directory(title="Select GoldSrc/Xash3D game directory")
            if not r.ok or not r.path:
                self._ui.set_status(r.error or "Directory pick failed.")
                return
            self._game_root = r.path
            self._normalize_game_root()
            update_state(last_game_root=self._game_root, last_mod=self._mod)
            self._refresh_main()
            self._ui.set_status("Game directory updated.")
            return

        if idx == 5:
            self._on_quit()
            return

    def _enter_bundle(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._bundles):
            return
        self._on_start_map_json(self._bundles[idx].map_json)

    def _enter_mod(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._mods) or not self._game_root:
            return
        self._mod = self._mods[idx]
        update_state(last_game_root=self._game_root, last_mod=self._mod)
        maps = list_goldsrc_like_maps(game_root=Path(self._game_root), mod=self._mod)
        if not maps:
            self._ui.set_status("No .bsp maps found in this mod.")
            return
        self._maps = maps
        self._screen = "maps"
        self._ui.set_title(f"IVAN :: Select Map ({self._mod})")
        self._ui.set_hint("Up/Down: select | Enter: import+run | Esc: back")
        self._ui.set_items([RetroMenuItem(m.label) for m in maps], selected=0)
        self._ui.set_status(f"{len(maps)} maps found.")

    def _enter_map(self, idx: int) -> None:
        if not self._game_root or not self._mod:
            return
        if idx < 0 or idx >= len(self._maps):
            return
        m = self._maps[idx]
        update_state(last_game_root=self._game_root, last_mod=self._mod)
        self._on_import_bsp(
            ImportRequest(
                game_root=self._game_root,
                mod=self._mod,
                map_label=m.label,
                bsp_path=m.bsp_path,
            )
        )

    def _refresh_continue(self) -> None:
        self._continue_label = None
        self._continue_enabled = False
        if not self._continue_map_json:
            return
        resolved = resolve_map_json(self._continue_map_json)
        if not resolved:
            return
        try:
            # Derive a label similar to the bundle list labels.
            assets = self._app_root / "assets"
            rel = resolved.resolve().relative_to(assets.resolve())
            if rel.name == "map.json":
                self._continue_label = rel.parent.as_posix()
            else:
                self._continue_label = rel.with_suffix("").as_posix()
        except Exception:
            self._continue_label = resolved.name
        self._continue_enabled = True
