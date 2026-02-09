from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

from ivan.maps.catalog import (
    MapBundle,
    detect_goldsrc_like_mods,
    find_runnable_bundles,
    list_goldsrc_like_maps,
    resolve_goldsrc_install_root,
)
from ivan.maps.steam import detect_steam_halflife_game_root
from ivan.maps.run_metadata import set_run_metadata_lighting
from ivan.maps.bundle_io import PACKED_BUNDLE_EXT, resolve_bundle_handle
from ivan.paths import app_root as ivan_app_root
from ivan.state import IvanState, load_state, resolve_map_json, update_state
from ivan.ui.native_dialogs import pick_directory
from irun_ui_kit.theme import Theme
from irun_ui_kit.widgets.list_menu import ListMenu, ListMenuItem


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
        theme: Theme,
        initial_game_root: str | None,
        initial_mod: str | None,
        state: IvanState | None = None,
        on_start_map_json,
        on_import_bsp,
        on_quit,
        on_apply_video=None,
    ) -> None:
        self._on_start_map_json = on_start_map_json
        self._on_import_bsp = on_import_bsp
        self._on_quit = on_quit
        self._on_apply_video = on_apply_video

        self._app_root = ivan_app_root()
        self._state = state or load_state()
        self._ui = ListMenu(
            aspect2d=aspect2d,
            theme=theme,
            title="IVAN",
            hint="Click or Enter: choose | Scroll: navigate | Esc: back/quit",
            on_click=self.on_enter,
        )

        self._screen: str = "main"  # main | bundles | mods | maps | video
        self._bundles: list[MapBundle] = []
        self._selected_bundle: MapBundle | None = None
        self._delete_target: MapBundle | None = None
        self._game_root: str | None = initial_game_root or self._state.last_game_root
        self._mod: str | None = initial_mod or self._state.last_mod
        self._mods: list[str] = []
        self._maps = []

        # Video settings state for the settings sub-screen.
        self._video_fullscreen: bool = self._state.fullscreen
        self._video_width: int = self._state.window_width
        self._video_height: int = self._state.window_height

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

    def is_search_active(self) -> bool:
        return self._ui.is_search_active()

    def toggle_search(self) -> None:
        self._ui.toggle_search()

    def set_status(self, text: str) -> None:
        self._ui.set_status(text)

    def set_loading_status(self, text: str, *, started_at: float) -> None:
        self._ui.set_loading_status(text, started_at=started_at)

    def on_up(self) -> None:
        if self._ui.is_search_active():
            return
        self._ui.move(-1)

    def on_down(self) -> None:
        if self._ui.is_search_active():
            return
        self._ui.move(1)

    def move(self, delta: int) -> None:
        if self._ui.is_search_active():
            return
        self._ui.move(int(delta))

    def on_escape(self) -> None:
        if self._ui.is_search_active():
            self._ui.hide_search()
            return
        if self._screen == "main":
            self._on_quit()
            return
        if self._screen == "delete_confirm":
            self._delete_target = None
            self._screen = "bundles"
            self._refresh_bundles()
            return
        if self._screen == "bundle_options":
            self._screen = "bundles"
            self._refresh_bundles()
            return
        if self._screen == "video":
            self._screen = "main"
            self._refresh_main()
            return
        self._screen = "main"
        self._refresh_main()

    def on_enter(self) -> None:
        if self._ui.is_search_active():
            self._ui.hide_search()
            return
        idx = self._ui.selected_index()
        if idx is None:
            return

        if self._screen == "main":
            self._enter_main(idx)
            return
        if self._screen == "bundles":
            self._enter_bundle(idx)
            return
        if self._screen == "bundle_options":
            self._enter_bundle_option(idx)
            return
        if self._screen == "delete_confirm":
            self._enter_delete_confirm(idx)
            return
        if self._screen == "mods":
            self._enter_mod(idx)
            return
        if self._screen == "maps":
            self._enter_map(idx)
            return
        if self._screen == "video":
            self._enter_video(idx)
            return

    def _refresh_main(self) -> None:
        self._ui.set_title("IVAN :: Main Menu")
        items: list[ListMenuItem] = []

        self._refresh_continue()
        self._normalize_game_root()
        if self._continue_map_json:
            label = self._continue_label or self._continue_map_json
            items.append(ListMenuItem(f"Continue: {label}", enabled=self._continue_enabled))

        # Quick start: Bounce if present.
        bounce_dir = self._app_root / "assets" / "imported" / "halflife" / "valve" / "bounce" / "map.json"
        bounce_packed = self._app_root / "assets" / "imported" / "halflife" / "valve" / f"bounce{PACKED_BUNDLE_EXT}"
        bounce = bounce_dir if bounce_dir.exists() else bounce_packed
        items.append(ListMenuItem("Quick Start: Bounce", enabled=bounce.exists()))

        items.append(ListMenuItem("Play Imported/Generated Map Bundle"))
        items.append(ListMenuItem("Import GoldSrc/Xash3D Map From Game Directory"))
        items.append(ListMenuItem("Auto-detect Steam Half-Life"))

        if self._game_root:
            items.append(ListMenuItem(f"Game dir: {self._game_root}"))
        else:
            items.append(ListMenuItem("Game dir: (not set)"))

        items.append(ListMenuItem("Video Settings"))
        items.append(ListMenuItem("Quit"))
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
                self._on_start_map_json(self._continue_map_json, None)
                return
            idx -= 1

        if idx == 0:
            bounce_dir = self._app_root / "assets" / "imported" / "halflife" / "valve" / "bounce" / "map.json"
            bounce_packed = self._app_root / "assets" / "imported" / "halflife" / "valve" / f"bounce{PACKED_BUNDLE_EXT}"
            bounce = bounce_dir if bounce_dir.exists() else bounce_packed
            if not bounce.exists():
                self._ui.set_status("Bounce bundle not found under assets/imported/halflife/valve/bounce.")
                return
            self._on_start_map_json(str(bounce), None)
            return

        if idx == 1:
            self._screen = "bundles"
            self._bundles = find_runnable_bundles(app_root=self._app_root)
            items = [ListMenuItem(b.label) for b in self._bundles]
            self._ui.set_title("IVAN :: Map Bundles")
            self._ui.set_hint("Up/Down: select | Enter: options | Del/Backspace: delete | Esc: back")
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
            self._ui.set_items([ListMenuItem(m) for m in self._mods], selected=selected)
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
            self._screen = "video"
            self._refresh_video()
            return

        if idx == 6:
            self._on_quit()
            return

    def _enter_bundle(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._bundles):
            return
        self._selected_bundle = self._bundles[idx]
        self._screen = "bundle_options"
        self._ui.set_title(f"IVAN :: Run Options ({self._selected_bundle.label})")
        self._ui.set_hint("Up/Down: select | Enter: choose | Del/Backspace: delete | Esc: back")
        self._ui.set_items(
            [
                ListMenuItem("Run (saved config)"),
                ListMenuItem("Run: Lighting = Original (bundle)"),
                ListMenuItem("Run: Lighting = Server defaults"),
                ListMenuItem("Run: Lighting = Static (no animation)"),
                ListMenuItem("Save default: Lighting = Original (bundle)"),
                ListMenuItem("Save default: Lighting = Server defaults"),
                ListMenuItem("Save default: Lighting = Static (no animation)"),
            ],
            selected=0,
        )
        self._ui.set_status("")

    def _enter_bundle_option(self, idx: int) -> None:
        if self._selected_bundle is None:
            return
        map_json = self._selected_bundle.map_json
        handle = resolve_bundle_handle(map_json)
        bundle_ref = handle.bundle_ref if handle is not None else None

        if idx == 0:
            self._on_start_map_json(map_json, None)
            return
        if idx == 1:
            self._on_start_map_json(map_json, {"preset": "original"})
            return
        if idx == 2:
            self._on_start_map_json(map_json, {"preset": "server_defaults"})
            return
        if idx == 3:
            self._on_start_map_json(map_json, {"preset": "static"})
            return
        if idx in (4, 5, 6):
            if bundle_ref is None:
                self._ui.set_status("Cannot save: bundle root not resolved for this map.")
                return
            preset = "original" if idx == 4 else ("server_defaults" if idx == 5 else "static")
            try:
                set_run_metadata_lighting(bundle_ref=bundle_ref, lighting={"preset": preset})
                self._ui.set_status(f"Saved run.json lighting preset: {preset}")
            except Exception as e:
                self._ui.set_status(f"Save failed: {e}")
            return

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
        self._ui.set_items([ListMenuItem(m.label) for m in maps], selected=0)
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

    # -- Video Settings sub-screen ------------------------------------

    _VIDEO_RESOLUTIONS: list[tuple[int, int]] = [
        (1280, 720),
        (1600, 900),
        (1920, 1080),
        (2560, 1440),
    ]

    def _refresh_video(self) -> None:
        self._ui.set_title("IVAN :: Video Settings")
        self._ui.set_hint("Click or Enter: apply | Esc: back")
        items: list[ListMenuItem] = []
        for w, h in self._VIDEO_RESOLUTIONS:
            active = (not self._video_fullscreen and self._video_width == w and self._video_height == h)
            tag = " [active]" if active else ""
            items.append(ListMenuItem(f"Windowed {w} x {h}{tag}"))
        fs_tag = " [active]" if self._video_fullscreen else ""
        items.append(ListMenuItem(f"Fullscreen{fs_tag}"))
        items.append(ListMenuItem("Back"))
        self._ui.set_items(items, selected=0)
        current = "Fullscreen" if self._video_fullscreen else f"Windowed {self._video_width}x{self._video_height}"
        self._ui.set_status(f"Current: {current}")

    def _enter_video(self, idx: int) -> None:
        n_res = len(self._VIDEO_RESOLUTIONS)
        if 0 <= idx < n_res:
            w, h = self._VIDEO_RESOLUTIONS[idx]
            self._video_fullscreen = False
            self._video_width = w
            self._video_height = h
        elif idx == n_res:
            self._video_fullscreen = True
        elif idx == n_res + 1:
            # Back
            self._screen = "main"
            self._refresh_main()
            return
        else:
            return
        if self._on_apply_video:
            self._on_apply_video(
                fullscreen=self._video_fullscreen,
                width=self._video_width,
                height=self._video_height,
            )
        self._refresh_video()

    # -- Continue / misc helpers ------------------------------------

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

    def on_delete(self) -> None:
        if self._ui.is_search_active():
            return
        if self._screen == "bundles":
            idx = self._ui.selected_index()
            if idx is None or idx < 0 or idx >= len(self._bundles):
                return
            self._delete_target = self._bundles[idx]
            self._open_delete_confirm()
            return
        if self._screen == "bundle_options" and self._selected_bundle is not None:
            self._delete_target = self._selected_bundle
            self._open_delete_confirm()
            return

    def _refresh_bundles(self) -> None:
        items = [ListMenuItem(b.label) for b in self._bundles]
        self._ui.set_title("IVAN :: Map Bundles")
        self._ui.set_hint("Up/Down: select | Enter: options | Del/Backspace: delete | Esc: back")
        self._ui.set_items(items, selected=0)
        self._ui.set_status(f"{len(items)} bundles found.")

    def _open_delete_confirm(self) -> None:
        if self._delete_target is None:
            return
        label = self._delete_target.label
        self._screen = "delete_confirm"
        self._ui.set_title(f"IVAN :: Delete Map ({label})")
        self._ui.set_hint("Enter: confirm | Esc: cancel")
        self._ui.set_items(
            [
                ListMenuItem(f"DELETE permanently: {label}"),
                ListMenuItem("Cancel"),
            ],
            selected=1,
        )
        self._ui.set_status("Only imported/generated bundles can be deleted from the UI.")

    def _enter_delete_confirm(self, idx: int) -> None:
        if self._delete_target is None:
            self._screen = "bundles"
            self._refresh_bundles()
            return
        if idx != 0:
            self._delete_target = None
            self._screen = "bundles"
            self._refresh_bundles()
            return

        # Confirm delete.
        target = self._delete_target
        self._delete_target = None
        ok, msg = self._delete_bundle(target)
        self._screen = "bundles"
        self._bundles = find_runnable_bundles(app_root=self._app_root)
        self._refresh_bundles()
        self._ui.set_status(msg if msg else ("Deleted." if ok else "Delete failed."))

    def _delete_bundle(self, bundle: MapBundle) -> tuple[bool, str]:
        try:
            map_json = Path(bundle.map_json)
            if not map_json.exists():
                return (False, "Map bundle is missing on disk.")

            assets = (self._app_root / "assets").resolve()
            mj = map_json.resolve()
            try:
                rel = mj.relative_to(assets)
            except Exception:
                return (False, "Refusing to delete: bundle is outside apps/ivan/assets/.")

            # Allow deleting only:
            # - assets/imported/**/map.json -> delete the containing directory
            # - assets/imported/**/*.irunmap -> delete the file (and sidecar run json)
            # - assets/generated/*_map.json -> delete the file
            # This avoids deleting hand-authored bundles under assets/maps/.
            if rel.parts and rel.parts[0] == "imported":
                if mj.suffix.lower() == PACKED_BUNDLE_EXT:
                    # Packed bundle: remove the archive and its metadata sidecar if present.
                    sidecar = mj.with_name(mj.name + ".run.json")
                    try:
                        if sidecar.exists():
                            sidecar.unlink()
                    except Exception:
                        pass
                    mj.unlink()
                    return (True, f"Deleted imported bundle: {bundle.label}")
                # Directory bundle: delete the containing folder.
                root = mj.parent
                shutil.rmtree(root)
                return (True, f"Deleted imported bundle: {bundle.label}")

            if rel.parts and rel.parts[0] == "generated" and mj.suffix.lower() == ".json":
                mj.unlink()
                return (True, f"Deleted generated bundle: {bundle.label}")

            return (False, "Refusing to delete: only assets/imported and assets/generated are deletable from UI.")
        except Exception as e:
            return (False, f"Delete failed: {e}")
