import pytest

from launcher.commands import CommandBus, EditMapCommand, PackMapCommand, PlayCommand


def test_command_bus_dispatches_typed_handler() -> None:
    bus = CommandBus()
    seen: list[str] = []

    def _on_play(cmd: PlayCommand) -> None:
        seen.append(f"play:{cmd.use_advanced}")

    bus.register(PlayCommand, _on_play)
    bus.dispatch(PlayCommand(use_advanced=True))

    assert seen == ["play:True"]


def test_command_bus_raises_for_unregistered_type() -> None:
    bus = CommandBus()

    with pytest.raises(LookupError):
        bus.dispatch(PackMapCommand())


def test_command_bus_dispatches_edit_command() -> None:
    bus = CommandBus()
    seen: list[str] = []

    def _on_edit(cmd: EditMapCommand) -> None:
        seen.append("edit")

    bus.register(EditMapCommand, _on_edit)
    bus.dispatch(EditMapCommand())

    assert seen == ["edit"]
