from __future__ import annotations

from ivan.console.command_bus import CommandArgSpec, CommandBus, CommandMetadata, CommandResult
from ivan.console.core import CommandContext


def test_command_bus_validates_named_and_positional_arguments() -> None:
    bus = CommandBus()
    bus.register(
        metadata=CommandMetadata(
            name="demo",
            summary="demo",
            args=(
                CommandArgSpec(name="count", typ="int", required=True, minimum=1, maximum=5),
                CommandArgSpec(name="flag", typ="bool", required=False, default=False),
            ),
        ),
        handler=lambda _ctx, data: CommandResult.success(out=[f"{data['count']}:{int(bool(data['flag']))}"]),
    )

    ok = bus.dispatch(ctx=CommandContext(role="client", origin="test"), name="demo", argv=["3", "--flag"])
    assert ok.ok is True
    assert ok.out == ["3:1"]

    bad = bus.dispatch(ctx=CommandContext(role="client", origin="test"), name="demo", argv=["9"])
    assert bad.ok is False
    assert any("must be <=" in line for line in bad.out)


def test_command_bus_rejects_unknown_options() -> None:
    bus = CommandBus()
    bus.register(
        metadata=CommandMetadata(
            name="echo2",
            summary="echo2",
            args=(CommandArgSpec(name="text", typ="str", required=True),),
        ),
        handler=lambda _ctx, data: CommandResult.success(out=[str(data["text"])]),
    )
    res = bus.dispatch(
        ctx=CommandContext(role="client", origin="test"),
        name="echo2",
        argv=["hello", "--unknown", "1"],
    )
    assert res.ok is False
    assert any("unknown option" in line for line in res.out)

