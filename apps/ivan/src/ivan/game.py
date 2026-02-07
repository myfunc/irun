from __future__ import annotations

import math
import json
from pathlib import Path
from dataclasses import dataclass

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectEntry, DirectFrame, DirectLabel, DirectSlider
from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.bullet import (
    BulletBoxShape,
    BulletCapsuleShape,
    BulletRigidBodyNode,
    BulletTriangleMesh,
    BulletTriangleMeshShape,
    BulletWorld,
)
from panda3d.core import (
    AmbientLight,
    BitMask32,
    DirectionalLight,
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    KeyboardButton,
    LVector3f,
    LVector4f,
    PNMImage,
    Point3,
    TextNode,
    Texture,
    TransformState,
    WindowProperties,
    loadPrcFileData,
)


@dataclass
class PhysicsTuning:
    gravity: float = 34.0
    jump_speed: float = 11.0
    max_ground_speed: float = 16.0
    max_air_speed: float = 18.0
    ground_accel: float = 72.0
    air_accel: float = 16.0
    friction: float = 6.5
    air_control: float = 0.35
    air_counter_strafe_brake: float = 38.0
    sprint_multiplier: float = 1.2
    mouse_sensitivity: float = 0.14
    wall_jump_boost: float = 10.0
    coyote_time: float = 0.12
    jump_buffer_time: float = 0.12
    enable_coyote: bool = True
    enable_jump_buffer: bool = True
    walljump_enabled: bool = True
    wallrun_enabled: bool = False
    vault_enabled: bool = False
    grapple_enabled: bool = False
    # Quake3-style character collision parameters.
    max_ground_slope_deg: float = 46.0
    step_height: float = 0.55
    ground_snap_dist: float = 0.20


@dataclass(frozen=True)
class RunConfig:
    smoke: bool = False


@dataclass(frozen=True)
class AABB:
    minimum: LVector3f
    maximum: LVector3f


class NumberControl:
    def __init__(
        self,
        parent,
        name: str,
        x: float,
        y: float,
        value: float,
        minimum: float,
        maximum: float,
        on_change,
    ) -> None:
        self._name = name
        self._minimum = minimum
        self._maximum = maximum
        self._on_change = on_change

        self.label = DirectLabel(
            parent=parent,
            text=name,
            text_scale=0.042,
            text_align=TextNode.ALeft,
            text_fg=(0.93, 0.93, 0.93, 1),
            frameColor=(0, 0, 0, 0),
            pos=(x, 0, y),
        )
        self.slider = DirectSlider(
            parent=parent,
            range=(minimum, maximum),
            value=value,
            pageSize=max(0.001, (maximum - minimum) / 150.0),
            scale=0.19,
            pos=(x + 0.32, 0, y),
            frameColor=(0.16, 0.16, 0.16, 0.95),
            thumb_frameColor=(0.82, 0.82, 0.82, 1.0),
            thumb_relief=DGG.FLAT,
            command=self._from_slider,
        )
        self.entry = DirectEntry(
            parent=parent,
            initialText=f"{value:.3f}",
            numLines=1,
            focus=0,
            scale=0.045,
            width=6,
            text_align=TextNode.ACenter,
            text_fg=(0.08, 0.08, 0.08, 1),
            frameColor=(0.9, 0.9, 0.9, 1),
            relief=DGG.FLAT,
            pos=(x + 0.62, 0, y - 0.02),
            command=self._from_entry,
            suppressMouse=False,
        )

    def set_value(self, value: float) -> None:
        clamped = max(self._minimum, min(self._maximum, value))
        self.slider["value"] = clamped
        self.entry.enterText(f"{clamped:.3f}")
        self._on_change(clamped)

    def _from_slider(self) -> None:
        value = float(self.slider["value"])
        self.entry.enterText(f"{value:.3f}")
        self._on_change(value)

    def _from_entry(self, text: str) -> None:
        try:
            value = float(text)
        except ValueError:
            self.entry.enterText(f"{float(self.slider['value']):.3f}")
            return
        self.set_value(value)


class RunnerDemo(ShowBase):
    def __init__(self, cfg: RunConfig) -> None:
        loadPrcFileData("", "audio-library-name null")
        if cfg.smoke:
            loadPrcFileData("", "window-type offscreen")

        super().__init__()

        self.cfg = cfg
        self.tuning = PhysicsTuning()
        self.disableMouse()

        self.spawn_point = LVector3f(0, 35, 1.9)
        self.player_pos = LVector3f(self.spawn_point)
        self.velocity = LVector3f(0, 0, 0)
        self.player_half = LVector3f(0.35, 0.35, 1.05)
        self.player_node = self.render.attachNewNode("player-node")
        self.player_node.setPos(self.player_pos)

        self._yaw = 0.0
        self._pitch = 0.0
        self._pointer_locked = True

        self._grounded = False
        self._ground_timer = 0.0
        self._jump_buffer_timer = 0.0

        self._wall_contact_timer = 999.0
        self._wall_normal = LVector3f(0, 0, 0)
        self._ground_normal = LVector3f(0, 0, 1)

        self._aabbs: list[AABB] = []
        self._triangles: list[list[float]] | None = None
        self._external_map_loaded = False
        self._triangle_collision_mode = False

        # Bullet-based collision queries (sweep tests) for robust wall/ceiling/slope handling.
        self._bworld: BulletWorld | None = None
        self._player_sweep_shape = None
        self._static_bodies: list[BulletRigidBodyNode] = []

        self._build_scene()
        self._setup_window()
        self._setup_input()
        self._setup_debug_ui()
        self._setup_bullet_collision()

        self.taskMgr.add(self._update, "runner-update")

        if cfg.smoke:
            self._smoke_frames = 10
            self.taskMgr.add(self._smoke_exit, "smoke-exit")

    def _setup_window(self) -> None:
        if self.cfg.smoke:
            return
        props = WindowProperties()
        props.setCursorHidden(True)
        props.setTitle("IRUN IVAN Demo")
        props.setSize(self.pipe.getDisplayWidth(), self.pipe.getDisplayHeight())
        self.win.requestProperties(props)
        self.camLens.setFov(96)
        self._center_mouse()

    def _setup_input(self) -> None:
        self.accept("escape", self._toggle_pointer_lock)
        self.accept("r", self._respawn)
        self.accept("space", self._queue_jump)
        self.accept("mouse1", self._grapple_mock)

    def _build_scene(self) -> None:
        ambient = AmbientLight("ambient")
        ambient.setColor(LVector4f(0.30, 0.30, 0.33, 1))
        self.render.setLight(self.render.attachNewNode(ambient))

        sun = DirectionalLight("sun")
        sun.setColor(LVector4f(0.95, 0.93, 0.86, 1))
        sun_np = self.render.attachNewNode(sun)
        sun_np.setHpr(34, -58, 0)
        self.render.setLight(sun_np)

        self._external_map_loaded = self._try_load_generated_dust2_map()
        if not self._external_map_loaded:
            # Official Panda3D sample environment model used in basic tutorial scenes.
            env = self.loader.loadModel("models/environment")
            env.reparentTo(self.render)
            env.setScale(0.25)
            env.setPos(-8, 42, 0)
            self._build_graybox_scene()

    def _build_graybox_scene(self) -> None:
        # Broad collision-safe floor under the full play area to avoid edge fallthrough perception.
        self._add_block((0, 35, -2.0), (140, 140, 2.0), (0.15, 0.17, 0.2, 1))
        # Visible center platform used as reliable spawn landmark.
        self._add_block((0, 35, 0.4), (3.5, 3.5, 0.4), (0.24, 0.44, 0.60, 1))

        self._add_block((-2, 10, 0.8), (1.0, 1.0, 0.8), (0.35, 0.45, 0.55, 1))
        self._add_block((2, 16, 1.1), (1.0, 1.0, 1.1), (0.35, 0.45, 0.55, 1))
        self._add_block((-1.8, 22, 1.3), (1.0, 1.0, 1.3), (0.35, 0.45, 0.55, 1))

        self._add_block((-5.5, 36, 2.8), (0.55, 7.0, 2.8), (0.2, 0.52, 0.72, 1))
        self._add_block((5.5, 47, 2.8), (0.55, 7.0, 2.8), (0.2, 0.52, 0.72, 1))

        self._add_block((0, 57, 0.8), (3.8, 2.2, 0.8), (0.30, 0.35, 0.4, 1))
        self._add_block((0, 66, 2.6), (4.0, 4.0, 0.6), (0.2, 0.56, 0.36, 1))

        self._add_block((8, 56, 1.6), (2.5, 8.0, 0.4), (0.45, 0.3, 0.18, 1))

    def _try_load_generated_dust2_map(self) -> bool:
        app_root = Path(__file__).resolve().parents[2]
        asset_path = app_root / "assets" / "generated" / "de_dust2_largo_map.json"
        if not asset_path.exists():
            return False

        try:
            payload = json.loads(asset_path.read_text(encoding="utf-8"))
        except Exception:
            return False

        triangles = payload.get("triangles")
        if not isinstance(triangles, list) or not triangles:
            return False

        spawn = payload.get("spawn", {})
        spawn_pos = spawn.get("position")
        if isinstance(spawn_pos, list) and len(spawn_pos) == 3:
            self.spawn_point = LVector3f(float(spawn_pos[0]), float(spawn_pos[1]), float(spawn_pos[2]) + 1.2)
            self.player_pos = LVector3f(self.spawn_point)
        spawn_yaw = spawn.get("yaw")
        if isinstance(spawn_yaw, (int, float)):
            self._yaw = float(spawn_yaw)

        self._triangles = triangles
        self._attach_triangle_map_geometry(triangles)
        self._triangle_collision_mode = True
        return True

    def _add_block(self, pos: tuple[float, float, float], half: tuple[float, float, float], color) -> None:
        model = self.loader.loadModel("models/box")
        model.reparentTo(self.render)
        model.setPos(*pos)
        model.setScale(*half)
        model.setColor(*color)

        p = LVector3f(*pos)
        h = LVector3f(*half)
        self._aabbs.append(AABB(minimum=p - h, maximum=p + h))

    def _attach_triangle_map_geometry(self, triangles: list[list[float]]) -> None:
        # Generated Dust2 asset currently includes positions only (no UV/material data).
        # For visibility we generate world-space UVs and apply a debug checker texture.
        vdata = GeomVertexData("dust2-map", GeomVertexFormat.getV3n3t2(), Geom.UHStatic)
        vertex_writer = GeomVertexWriter(vdata, "vertex")
        normal_writer = GeomVertexWriter(vdata, "normal")
        uv_writer = GeomVertexWriter(vdata, "texcoord")
        prim = GeomTriangles(Geom.UHStatic)

        uv_scale = 0.20
        for tri in triangles:
            if len(tri) != 9:
                continue

            p0 = LVector3f(tri[0], tri[1], tri[2])
            p1 = LVector3f(tri[3], tri[4], tri[5])
            p2 = LVector3f(tri[6], tri[7], tri[8])

            edge1 = p1 - p0
            edge2 = p2 - p0
            normal = edge1.cross(edge2)
            if normal.lengthSquared() <= 1e-10:
                continue
            normal.normalize()

            base_idx = vdata.getNumRows()
            vertex_writer.addData3f(p0)
            normal_writer.addData3f(normal)
            uv_writer.addData2f(p0.x * uv_scale, p0.y * uv_scale)
            vertex_writer.addData3f(p1)
            normal_writer.addData3f(normal)
            uv_writer.addData2f(p1.x * uv_scale, p1.y * uv_scale)
            vertex_writer.addData3f(p2)
            normal_writer.addData3f(normal)
            uv_writer.addData2f(p2.x * uv_scale, p2.y * uv_scale)
            prim.addVertices(base_idx, base_idx + 1, base_idx + 2)

        geom = Geom(vdata)
        geom.addPrimitive(prim)
        geom_node = GeomNode("dust2-map-geom")
        geom_node.addGeom(geom)

        map_np = self.render.attachNewNode(geom_node)
        map_np.setColor(0.73, 0.67, 0.53, 1)
        map_np.setTwoSided(False)
        map_np.setTexture(self._make_debug_checker_texture(), 1)

    @staticmethod
    def _make_debug_checker_texture() -> Texture:
        img = PNMImage(256, 256)
        # Simple high-contrast checker + grid, so collision/scale issues are visible.
        for y in range(256):
            for x in range(256):
                cx = (x // 32) % 2
                cy = (y // 32) % 2
                base = 0.82 if (cx ^ cy) else 0.25
                if x % 32 == 0 or y % 32 == 0:
                    img.setXel(x, y, 1.0, 0.15, 0.15)
                else:
                    img.setXel(x, y, base, base, base)

        tex = Texture("debug-checker")
        tex.load(img)
        tex.setWrapU(Texture.WM_repeat)
        tex.setWrapV(Texture.WM_repeat)
        tex.setMinfilter(Texture.FT_linear_mipmap_linear)
        tex.setMagfilter(Texture.FT_linear)
        tex.generateRamMipmapImages()
        return tex


    def _setup_debug_ui(self) -> None:
        self.debug_root = DirectFrame(
            parent=self.aspect2d,
            frameColor=(0.08, 0.08, 0.08, 0.80),
            frameSize=(-1.30, -0.12, -0.95, 0.95),
            pos=(0, 0, 0),
            relief=DGG.FLAT,
        )

        DirectLabel(
            parent=self.debug_root,
            text="Debug / Physics Tuning (ESC)",
            text_scale=0.055,
            text_align=TextNode.ALeft,
            text_fg=(0.95, 0.95, 0.95, 1),
            frameColor=(0, 0, 0, 0),
            pos=(-1.22, 0, 0.88),
        )

        self.speed_hud_label = DirectLabel(
            parent=self.aspect2d,
            text="Speed: 0 u/s",
            text_scale=0.042,
            text_align=TextNode.ACenter,
            text_fg=(0.94, 0.94, 0.94, 0.95),
            frameColor=(0, 0, 0, 0),
            pos=(0.0, 0, 0.93),
        )

        controls = [
            ("gravity", 8.0, 60.0),
            ("jump_speed", 3.0, 25.0),
            ("max_ground_speed", 3.0, 40.0),
            ("max_air_speed", 3.0, 45.0),
            ("ground_accel", 5.0, 140.0),
            ("air_accel", 1.0, 90.0),
            ("friction", 0.0, 25.0),
            ("air_control", 0.0, 1.0),
            ("air_counter_strafe_brake", 5.0, 90.0),
            ("sprint_multiplier", 1.0, 2.0),
            ("mouse_sensitivity", 0.02, 0.40),
            ("wall_jump_boost", 1.0, 20.0),
            ("coyote_time", 0.0, 0.35),
            ("jump_buffer_time", 0.0, 0.35),
        ]

        self._number_controls: dict[str, NumberControl] = {}
        x = -1.22
        y = 0.72
        step = 0.105

        for name, minimum, maximum in controls:
            ctrl = NumberControl(
                parent=self.debug_root,
                name=name,
                x=x,
                y=y,
                value=float(getattr(self.tuning, name)),
                minimum=minimum,
                maximum=maximum,
                on_change=lambda val, field=name: setattr(self.tuning, field, val),
            )
            self._number_controls[name] = ctrl
            y -= step

        self._toggle_buttons: dict[str, DirectButton] = {}
        self._make_toggle_button("enable_coyote", -1.22, -0.68)
        self._make_toggle_button("enable_jump_buffer", -0.90, -0.68)
        self._make_toggle_button("walljump_enabled", -1.22, -0.78)
        self._make_toggle_button("wallrun_enabled", -0.90, -0.78)
        self._make_toggle_button("vault_enabled", -1.22, -0.88)
        self._make_toggle_button("grapple_enabled", -0.90, -0.88)

        self.status_label = DirectLabel(
            parent=self.debug_root,
            text="",
            text_scale=0.047,
            text_align=TextNode.ALeft,
            text_fg=(0.95, 0.95, 0.95, 1),
            frameColor=(0, 0, 0, 0),
            pos=(-1.22, 0, -0.58),
        )
        self.debug_root.hide()

    def _setup_bullet_collision(self) -> None:
        # We use Bullet for collision queries (convex sweeps) and implement a Quake3-like
        # kinematic controller (step + slide). This gives correct wall/ceiling/slope behavior.
        self._bworld = BulletWorld()
        # We integrate gravity ourselves (for Quake-style tuning), so keep Bullet gravity neutral.
        self._bworld.setGravity(LVector3f(0, 0, 0))

        # Player collision hull: capsule aligned with Z.
        radius = float(self.player_half.x)
        # Bullet capsule height is cylinder height (excluding hemispherical caps).
        cyl_h = max(0.01, float(self.player_half.z * 2.0 - radius * 2.0))
        self._player_sweep_shape = BulletCapsuleShape(radius, cyl_h, 2)

        if self._triangle_collision_mode and self._triangles:
            tri_mesh = BulletTriangleMesh()
            for tri in self._triangles:
                if len(tri) != 9:
                    continue
                p0 = Point3(float(tri[0]), float(tri[1]), float(tri[2]))
                p1 = Point3(float(tri[3]), float(tri[4]), float(tri[5]))
                p2 = Point3(float(tri[6]), float(tri[7]), float(tri[8]))
                tri_mesh.addTriangle(p0, p1, p2, False)

            shape = BulletTriangleMeshShape(tri_mesh, dynamic=False)
            body = BulletRigidBodyNode("dust2-static")
            body.setMass(0.0)
            body.addShape(shape)
            self.render.attachNewNode(body)
            self._bworld.attachRigidBody(body)
            self._static_bodies.append(body)
            return

        # Graybox fallback: build static boxes for the blocks we placed.
        for box in self._aabbs:
            half = (box.maximum - box.minimum) * 0.5
            center = box.minimum + half
            shape = BulletBoxShape(LVector3f(float(half.x), float(half.y), float(half.z)))
            body = BulletRigidBodyNode("graybox-block")
            body.setMass(0.0)
            body.addShape(shape)
            np = self.render.attachNewNode(body)
            np.setPos(float(center.x), float(center.y), float(center.z))
            self._bworld.attachRigidBody(body)
            self._static_bodies.append(body)

    def _make_toggle_button(self, field: str, x: float, y: float) -> None:
        button = DirectButton(
            parent=self.debug_root,
            text="",
            text_scale=0.036,
            text_fg=(0.95, 0.95, 0.95, 1),
            frameColor=(0.20, 0.20, 0.20, 0.95),
            relief=DGG.FLAT,
            command=self._toggle_bool_field,
            extraArgs=[field],
            scale=0.07,
            frameSize=(-2.1, 2.1, -0.55, 0.55),
            pos=(x, 0, y),
        )
        self._toggle_buttons[field] = button
        self._refresh_toggle_button(field)

    def _refresh_toggle_button(self, field: str) -> None:
        value = bool(getattr(self.tuning, field))
        state = "ON" if value else "OFF"
        self._toggle_buttons[field]["text"] = f"{field}: {state}"

    def _toggle_bool_field(self, field: str) -> None:
        setattr(self.tuning, field, not bool(getattr(self.tuning, field)))
        self._refresh_toggle_button(field)

    def _toggle_pointer_lock(self) -> None:
        self._pointer_locked = not self._pointer_locked
        props = WindowProperties()
        props.setCursorHidden(self._pointer_locked)
        self.win.requestProperties(props)
        if self._pointer_locked:
            self.debug_root.hide()
        else:
            self.debug_root.show()
        if self._pointer_locked:
            self._center_mouse()

    def _center_mouse(self) -> None:
        if self.cfg.smoke:
            return
        x = self.win.getXSize() // 2
        y = self.win.getYSize() // 2
        self.win.movePointer(0, x, y)

    def _update_look(self) -> None:
        if self.cfg.smoke or not self._pointer_locked:
            return
        cx = self.win.getXSize() // 2
        cy = self.win.getYSize() // 2
        pointer = self.win.getPointer(0)
        dx = pointer.getX() - cx
        dy = pointer.getY() - cy

        self._yaw -= dx * self.tuning.mouse_sensitivity
        self._pitch = max(-88.0, min(88.0, self._pitch - dy * self.tuning.mouse_sensitivity))
        self._center_mouse()

    def _wish_direction(self) -> LVector3f:
        if self.mouseWatcherNode is None:
            return LVector3f(0, 0, 0)
        h_rad = math.radians(self._yaw)
        forward = LVector3f(-math.sin(h_rad), math.cos(h_rad), 0)
        right = LVector3f(forward.y, -forward.x, 0)

        move = LVector3f(0, 0, 0)
        if self.mouseWatcherNode.isButtonDown(KeyboardButton.ascii_key("w")):
            move += forward
        if self.mouseWatcherNode.isButtonDown(KeyboardButton.ascii_key("s")):
            move -= forward
        if self.mouseWatcherNode.isButtonDown(KeyboardButton.ascii_key("d")):
            move += right
        if self.mouseWatcherNode.isButtonDown(KeyboardButton.ascii_key("a")):
            move -= right

        if move.lengthSquared() > 0:
            move.normalize()
        return move

    def _queue_jump(self) -> None:
        self._jump_buffer_timer = self.tuning.jump_buffer_time

    def _consume_jump_request(self) -> bool:
        return self._jump_buffer_timer > 0.0

    def _can_ground_jump(self) -> bool:
        if self._grounded:
            return True
        return self.tuning.enable_coyote and self._ground_timer <= self.tuning.coyote_time

    def _has_wall_for_jump(self) -> bool:
        return self._wall_contact_timer <= 0.18 and self._wall_normal.lengthSquared() > 0.01

    def _apply_jump(self) -> None:
        self.velocity.z = self.tuning.jump_speed
        self._jump_buffer_timer = 0.0
        self._grounded = False

    def _apply_wall_jump(self) -> None:
        away = LVector3f(self._wall_normal.x, self._wall_normal.y, 0)
        if away.lengthSquared() > 0.001:
            away.normalize()
        h_rad = math.radians(self._yaw)
        forward = LVector3f(-math.sin(h_rad), math.cos(h_rad), 0)
        boost = away * self.tuning.wall_jump_boost + forward * (self.tuning.wall_jump_boost * 0.45)
        self.velocity.x = boost.x
        self.velocity.y = boost.y
        self.velocity.z = self.tuning.jump_speed * 0.95
        self._jump_buffer_timer = 0.0

    def _grapple_mock(self) -> None:
        if not self.tuning.grapple_enabled:
            return
        h_rad = math.radians(self._yaw)
        forward = LVector3f(-math.sin(h_rad), math.cos(h_rad), 0)
        self.velocity += forward * 4.5 + LVector3f(0, 0, 1.8)

    def _apply_friction(self, dt: float) -> None:
        speed = math.sqrt(self.velocity.x * self.velocity.x + self.velocity.y * self.velocity.y)
        if speed <= 0.0001:
            return
        drop = speed * self.tuning.friction * dt
        new_speed = max(0.0, speed - drop)
        if new_speed == speed:
            return
        scale = new_speed / speed
        self.velocity.x *= scale
        self.velocity.y *= scale

    def _accelerate(self, wish_dir: LVector3f, wish_speed: float, accel: float, dt: float) -> None:
        if wish_dir.lengthSquared() <= 0.0:
            return
        current_speed = self.velocity.dot(wish_dir)
        add_speed = wish_speed - current_speed
        if add_speed <= 0:
            return
        accel_speed = accel * dt * wish_speed
        if accel_speed > add_speed:
            accel_speed = add_speed
        self.velocity += wish_dir * accel_speed

    def _air_control(self, wish_dir: LVector3f, dt: float) -> None:
        if wish_dir.lengthSquared() <= 0.0:
            return
        steer = self.tuning.air_control * dt
        self.velocity.x += wish_dir.x * steer
        self.velocity.y += wish_dir.y * steer

    def _apply_air_counter_strafe_brake(self, wish_dir: LVector3f, dt: float) -> None:
        horiz = LVector3f(self.velocity.x, self.velocity.y, 0)
        speed = horiz.length()
        if speed <= 0.01 or wish_dir.lengthSquared() <= 0.0:
            return
        horiz.normalize()
        if horiz.dot(wish_dir) < -0.2:
            decel = min(speed, self.tuning.air_counter_strafe_brake * dt + speed * 8.0 * dt)
            self.velocity.x -= horiz.x * decel
            self.velocity.y -= horiz.y * decel

    def _player_aabb(self) -> AABB:
        return AABB(self.player_pos - self.player_half, self.player_pos + self.player_half)

    @staticmethod
    def _overlap(a: AABB, b: AABB) -> bool:
        eps = 1e-4
        return (
            a.minimum.x < (b.maximum.x - eps)
            and a.maximum.x > (b.minimum.x + eps)
            and a.minimum.y < (b.maximum.y - eps)
            and a.maximum.y > (b.minimum.y + eps)
            and a.minimum.z < (b.maximum.z - eps)
            and a.maximum.z > (b.minimum.z + eps)
        )

    @staticmethod
    def _walkable_threshold_z(max_slope_deg: float) -> float:
        # Equivalent to Quake3 MIN_WALK_NORMAL (0.7) when max_slope_deg ~= 45.57.
        return float(math.cos(math.radians(max_slope_deg)))

    @staticmethod
    def _clip_velocity(vel: LVector3f, normal: LVector3f, overbounce: float = 1.001) -> LVector3f:
        # Quake-style clip against a collision plane.
        v = LVector3f(vel)
        n = LVector3f(normal)
        if n.lengthSquared() > 1e-12:
            n.normalize()
        backoff = v.dot(n)
        if backoff < 0.0:
            backoff *= overbounce
        else:
            backoff /= overbounce
        v -= n * backoff
        # Avoid tiny oscillations.
        if abs(v.x) < 1e-6:
            v.x = 0.0
        if abs(v.y) < 1e-6:
            v.y = 0.0
        if abs(v.z) < 1e-6:
            v.z = 0.0
        return v

    def _bullet_sweep_closest(self, from_pos: LVector3f, to_pos: LVector3f):
        assert self._bworld is not None
        assert self._player_sweep_shape is not None
        return self._bworld.sweepTestClosest(
            self._player_sweep_shape,
            TransformState.makePos(from_pos),
            TransformState.makePos(to_pos),
            BitMask32.allOn(),
            0.0,
        )

    def _bullet_ground_trace(self) -> None:
        walkable_z = self._walkable_threshold_z(self.tuning.max_ground_slope_deg)
        down = LVector3f(0, 0, -max(0.06, float(self.tuning.ground_snap_dist)))
        hit = self._bullet_sweep_closest(self.player_pos, self.player_pos + down)
        if not hit.hasHit():
            self._grounded = False
            return

        n = LVector3f(hit.getHitNormal())
        if n.lengthSquared() > 1e-12:
            n.normalize()
        self._ground_normal = n
        self._grounded = n.z > walkable_z

    def _bullet_slide_move(self, delta: LVector3f) -> None:
        # Iterative slide move (Quake-style): sweep -> move -> clip velocity -> repeat.
        if delta.lengthSquared() <= 1e-12:
            return

        pos = LVector3f(self.player_pos)
        remaining = LVector3f(delta)
        planes: list[LVector3f] = []

        self._wall_normal = LVector3f(0, 0, 0)
        self._wall_contact_timer = 999.0

        walkable_z = self._walkable_threshold_z(self.tuning.max_ground_slope_deg)
        skin = 0.006

        for _ in range(4):
            if remaining.lengthSquared() <= 1e-10:
                break

            move = LVector3f(remaining)
            target = pos + move
            hit = self._bullet_sweep_closest(pos, target)
            if not hit.hasHit():
                pos = target
                break

            hit_frac = max(0.0, min(1.0, float(hit.getHitFraction())))
            # Move to contact (slightly before), then push out along normal (skin).
            pos = pos + move * max(0.0, hit_frac - 1e-4)

            n = LVector3f(hit.getHitNormal())
            if n.lengthSquared() > 1e-12:
                n.normalize()
            planes.append(n)
            pos = pos + n * skin

            # Contact classification.
            if n.z > walkable_z:
                self._grounded = True
                self._ground_normal = LVector3f(n)
                if self.velocity.z < 0.0:
                    self.velocity.z = 0.0
            elif abs(n.z) < 0.65:
                self._wall_normal = LVector3f(n.x, n.y, 0)
                if self._wall_normal.lengthSquared() > 1e-12:
                    self._wall_normal.normalize()
                self._wall_contact_timer = 0.0
            elif n.z < -0.65 and self.velocity.z > 0.0:
                # Ceiling.
                self.velocity.z = 0.0

            self.velocity = self._clip_velocity(self.velocity, n)
            time_left = 1.0 - hit_frac
            remaining = move * time_left
            remaining = self._clip_velocity(remaining, n, overbounce=1.0)

            # Multi-plane clip: if we're still going into any previous plane, clip again.
            for p in planes[:-1]:
                if remaining.dot(p) < 0.0:
                    remaining = self._clip_velocity(remaining, p, overbounce=1.0)
                if self.velocity.dot(p) < 0.0:
                    self.velocity = self._clip_velocity(self.velocity, p)

        self.player_pos = pos

    def _bullet_step_slide_move(self, delta: LVector3f) -> None:
        # StepSlideMove: try regular slide; then try stepping up and sliding; choose the best.
        if delta.lengthSquared() <= 1e-12:
            return

        start_pos = LVector3f(self.player_pos)
        start_vel = LVector3f(self.velocity)

        # First attempt: plain slide.
        self._bullet_slide_move(delta)
        pos1 = LVector3f(self.player_pos)
        vel1 = LVector3f(self.velocity)

        # Second attempt: step up, move horizontally, then step down.
        self.player_pos = LVector3f(start_pos)
        self.velocity = LVector3f(start_vel)

        step_up = LVector3f(0, 0, float(self.tuning.step_height))
        hit_up = self._bullet_sweep_closest(self.player_pos, self.player_pos + step_up)
        if not hit_up.hasHit():
            self.player_pos += step_up
            horiz = LVector3f(float(delta.x), float(delta.y), 0.0)
            self._bullet_slide_move(horiz)

            step_down = LVector3f(0, 0, -float(self.tuning.step_height) - 0.01)
            hit_down = self._bullet_sweep_closest(self.player_pos, self.player_pos + step_down)
            if hit_down.hasHit():
                frac = max(0.0, float(hit_down.getHitFraction()) - 1e-4)
                self.player_pos = self.player_pos + step_down * frac

        pos2 = LVector3f(self.player_pos)
        vel2 = LVector3f(self.velocity)

        d1 = (pos1 - start_pos)
        d2 = (pos2 - start_pos)
        dist1 = d1.x * d1.x + d1.y * d1.y
        dist2 = d2.x * d2.x + d2.y * d2.y

        if dist1 >= dist2:
            self.player_pos = pos1
            self.velocity = vel1
        else:
            self.player_pos = pos2
            self.velocity = vel2

    def _bullet_ground_snap(self) -> None:
        # Keep the player glued to ground on small descents (Quake-style ground snap).
        if self.velocity.z > 0.0:
            return

        walkable_z = self._walkable_threshold_z(self.tuning.max_ground_slope_deg)
        down = LVector3f(0, 0, -float(self.tuning.ground_snap_dist))
        hit = self._bullet_sweep_closest(self.player_pos, self.player_pos + down)
        if not hit.hasHit():
            return
        n = LVector3f(hit.getHitNormal())
        if n.lengthSquared() > 1e-12:
            n.normalize()
        if n.z <= walkable_z:
            return

        frac = max(0.0, float(hit.getHitFraction()) - 1e-4)
        self.player_pos = self.player_pos + down * frac
        self._grounded = True
        self._ground_normal = LVector3f(n)
        if self.velocity.z < 0.0:
            self.velocity.z = 0.0

    def _move_and_collide(self, delta: LVector3f) -> None:
        self._grounded = False
        max_component = max(abs(delta.x), abs(delta.y), abs(delta.z))
        steps = max(1, int(math.ceil(max_component / 0.35)))
        step = delta / float(steps)

        for _ in range(steps):
            self.player_pos.x += step.x
            self._resolve_axis("x", step.x)

            self.player_pos.y += step.y
            self._resolve_axis("y", step.y)

            self.player_pos.z += step.z
            self._resolve_axis("z", step.z)

    def _resolve_axis(self, axis: str, delta: float) -> None:
        if abs(delta) < 1e-7:
            return

        paabb = self._player_aabb()
        for box in self._aabbs:
            if not self._overlap(paabb, box):
                continue

            if axis in ("x", "y"):
                z_overlap = min(paabb.maximum.z, box.maximum.z) - max(paabb.minimum.z, box.minimum.z)
                # Ignore almost-flat contact so floor standing does not become side collision.
                if z_overlap <= 0.08:
                    continue

            if axis == "x":
                if delta > 0:
                    self.player_pos.x = box.minimum.x - self.player_half.x
                    self._wall_normal = LVector3f(-1, 0, 0)
                else:
                    self.player_pos.x = box.maximum.x + self.player_half.x
                    self._wall_normal = LVector3f(1, 0, 0)
                self.velocity.x = 0
                self._wall_contact_timer = 0.0
            elif axis == "y":
                if delta > 0:
                    self.player_pos.y = box.minimum.y - self.player_half.y
                    self._wall_normal = LVector3f(0, -1, 0)
                else:
                    self.player_pos.y = box.maximum.y + self.player_half.y
                    self._wall_normal = LVector3f(0, 1, 0)
                self.velocity.y = 0
                self._wall_contact_timer = 0.0
            else:
                if delta > 0:
                    self.player_pos.z = box.minimum.z - self.player_half.z
                else:
                    self.player_pos.z = box.maximum.z + self.player_half.z
                    self._grounded = True
                self.velocity.z = 0

            paabb = self._player_aabb()

    def _respawn(self) -> None:
        self.player_pos = LVector3f(self.spawn_point)
        self.velocity = LVector3f(0, 0, 0)
        self._yaw = 0.0
        self._pitch = 0.0
        self.player_node.setPos(self.player_pos)

    def _is_sprinting(self) -> bool:
        if self.mouseWatcherNode is None:
            return False
        return (
            self.mouseWatcherNode.isButtonDown(KeyboardButton.shift())
            or self.mouseWatcherNode.isButtonDown(KeyboardButton.lshift())
            or self.mouseWatcherNode.isButtonDown(KeyboardButton.rshift())
        )

    def _update(self, task: Task) -> int:
        dt = min(globalClock.getDt(), 1.0 / 30.0)

        self._update_look()
        self._wall_contact_timer += dt

        self._jump_buffer_timer = max(0.0, self._jump_buffer_timer - dt)

        # Determine grounded state before applying friction/accel (otherwise friction appears to "break"
        # whenever you don't happen to collide with the floor during this frame).
        if self._bworld is not None:
            self._bullet_ground_trace()

        wish = self._wish_direction()
        sprint_multiplier = self.tuning.sprint_multiplier if self._is_sprinting() else 1.0
        target_ground_speed = self.tuning.max_ground_speed * sprint_multiplier

        if self._grounded:
            self._apply_friction(dt)
            self._accelerate(wish, target_ground_speed, self.tuning.ground_accel, dt)
            if self._consume_jump_request() and self._can_ground_jump():
                self._apply_jump()
        else:
            self._accelerate(wish, self.tuning.max_air_speed, self.tuning.air_accel, dt)
            self._air_control(wish, dt)
            self._apply_air_counter_strafe_brake(wish, dt)

            gravity_scale = 1.0
            if self.tuning.wallrun_enabled and self._has_wall_for_jump() and self.velocity.z <= 0.0:
                gravity_scale = 0.38
                self.velocity.z = max(self.velocity.z, -2.0)

            self.velocity.z -= self.tuning.gravity * gravity_scale * dt

            if self._consume_jump_request() and self.tuning.walljump_enabled and self._has_wall_for_jump():
                self._apply_wall_jump()

        # Movement + collision resolution.
        if self._bworld is not None:
            self._bullet_step_slide_move(self.velocity * dt)
            self._bullet_ground_snap()
            # Update grounded state after movement (e.g. walking off a ledge).
            self._bullet_ground_trace()
        else:
            self._move_and_collide(self.velocity * dt)

        if not self._grounded:
            self._ground_timer += dt
        else:
            self._ground_timer = 0.0

        if self.player_pos.z < -18:
            self._respawn()

        self.player_node.setPos(self.player_pos)
        self.camera.setPos(self.player_pos.x, self.player_pos.y, self.player_pos.z + 0.65)
        self.camera.setHpr(self._yaw, self._pitch, 0)

        hspeed = math.sqrt(self.velocity.x * self.velocity.x + self.velocity.y * self.velocity.y)
        self.speed_hud_label["text"] = f"Speed: {int(hspeed)} u/s"
        self.status_label["text"] = (
            f"speed: {hspeed:.2f} | z-vel: {self.velocity.z:.2f} | grounded: {self._grounded} | "
            f"wall: {self._has_wall_for_jump()}"
        )

        return Task.cont

    def _smoke_exit(self, task: Task) -> int:
        self._smoke_frames -= 1
        if self._smoke_frames <= 0:
            self.userExit()
            return Task.done
        return Task.cont


def run(*, smoke: bool = False) -> None:
    app = RunnerDemo(RunConfig(smoke=smoke))
    app.run()
