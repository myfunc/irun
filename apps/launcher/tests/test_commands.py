import pytest

from launcher.commands import (
    AssignPackToMapCommand,
    BuildPackCommand,
    CommandBus,
    CreateTemplateMapCommand,
    DiscoverPacksCommand,
    EditMapCommand,
    GenerateTBTexturesCommand,
    PlayCommand,
    SyncTBProfileCommand,
    ValidatePackCommand,
)


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
        bus.dispatch(BuildPackCommand())


def test_command_bus_dispatches_edit_command() -> None:
    bus = CommandBus()
    seen: list[str] = []

    def _on_edit(cmd: EditMapCommand) -> None:
        seen.append("edit")

    bus.register(EditMapCommand, _on_edit)
    bus.dispatch(EditMapCommand())

    assert seen == ["edit"]


def test_command_bus_dispatches_pack_centric_commands() -> None:
    bus = CommandBus()
    seen: list[str] = []

    def _on(cmd) -> None:
        seen.append(type(cmd).__name__)

    bus.register(DiscoverPacksCommand, _on)
    bus.register(BuildPackCommand, _on)
    bus.register(ValidatePackCommand, _on)
    bus.register(AssignPackToMapCommand, _on)
    bus.register(SyncTBProfileCommand, _on)
    bus.register(GenerateTBTexturesCommand, _on)
    bus.register(CreateTemplateMapCommand, _on)

    bus.dispatch(DiscoverPacksCommand())
    bus.dispatch(BuildPackCommand())
    bus.dispatch(ValidatePackCommand())
    bus.dispatch(AssignPackToMapCommand())
    bus.dispatch(SyncTBProfileCommand())
    bus.dispatch(GenerateTBTexturesCommand())
    bus.dispatch(CreateTemplateMapCommand())

    assert seen == [
        "DiscoverPacksCommand",
        "BuildPackCommand",
        "ValidatePackCommand",
        "AssignPackToMapCommand",
        "SyncTBProfileCommand",
        "GenerateTBTexturesCommand",
        "CreateTemplateMapCommand",
    ]
