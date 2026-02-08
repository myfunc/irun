from __future__ import annotations

from ivan.console.core import CommandContext, Console


def test_console_semicolon_split_and_echo() -> None:
    con = Console()
    con.register_command(name="echo", help="", handler=lambda _ctx, argv: [" ".join(argv)])
    out = con.execute_line(ctx=CommandContext(role="client", origin="test"), line='echo a; echo "b c"')
    assert out == ["a", "b c"]


def test_console_cvar_get_set() -> None:
    con = Console()
    v = {"x": 1.0}
    con.register_cvar(name="sv_gravity", typ="float", get_value=lambda: v["x"], set_value=lambda nv: v.__setitem__("x", nv))

    out1 = con.execute_line(ctx=CommandContext(role="server", origin="test"), line="sv_gravity")
    assert out1 == ['sv_gravity "1.0"']

    out2 = con.execute_line(ctx=CommandContext(role="server", origin="test"), line="sv_gravity 800")
    assert out2 == ['sv_gravity "800.0"']
    assert v["x"] == 800.0

