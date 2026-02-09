from __future__ import annotations

from ivan.game.input_system import _InputCommand
from ivan.replays.demo import DemoFrame


def test_input_command_roundtrip_preserves_raw_held_states() -> None:
    cmd = _InputCommand(
        look_dx=11,
        look_dy=-7,
        look_scale=256,
        move_forward=1,
        move_right=-1,
        jump_pressed=True,
        jump_held=True,
        crouch_held=False,
        grapple_pressed=True,
        noclip_toggle_pressed=False,
        key_w_held=True,
        key_a_held=True,
        key_s_held=False,
        key_d_held=False,
        arrow_up_held=False,
        arrow_down_held=True,
        arrow_left_held=False,
        arrow_right_held=True,
        mouse_left_held=True,
        mouse_right_held=True,
    )

    frame = cmd.to_demo_frame()
    replay_cmd = _InputCommand.from_demo_frame(frame, look_scale=256)

    assert replay_cmd.look_dx == 11
    assert replay_cmd.look_dy == -7
    assert replay_cmd.move_forward == 1
    assert replay_cmd.move_right == -1
    assert replay_cmd.key_w_held is True
    assert replay_cmd.key_a_held is True
    assert replay_cmd.key_s_held is False
    assert replay_cmd.key_d_held is False
    assert replay_cmd.arrow_down_held is True
    assert replay_cmd.arrow_right_held is True
    assert replay_cmd.mouse_left_held is True
    assert replay_cmd.mouse_right_held is True
    assert replay_cmd.raw_wasd_available is False


def test_from_demo_frame_without_raw_flags_marks_wasd_unavailable() -> None:
    legacy_frame = DemoFrame(
        look_dx=0,
        look_dy=0,
        move_forward=-1,
        move_right=1,
        jump_pressed=False,
        jump_held=False,
        crouch_held=False,
        grapple_pressed=False,
        noclip_toggle_pressed=False,
    )

    cmd = _InputCommand.from_demo_frame(legacy_frame, look_scale=256)

    assert cmd.key_w_held is False
    assert cmd.key_s_held is False
    assert cmd.key_a_held is False
    assert cmd.key_d_held is False
    assert cmd.raw_wasd_available is False
