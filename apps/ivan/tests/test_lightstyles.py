from __future__ import annotations


def test_lightstyle_pattern_is_animated() -> None:
    from ivan.world.lightstyles import lightstyle_pattern_is_animated

    assert lightstyle_pattern_is_animated("") is False
    assert lightstyle_pattern_is_animated("m") is False
    assert lightstyle_pattern_is_animated("mmmm") is False
    assert lightstyle_pattern_is_animated("aaaa") is False
    assert lightstyle_pattern_is_animated("ma") is True
    assert lightstyle_pattern_is_animated("mmnmmommommnonmmonqnmmo") is True


def test_lightstyle_pattern_scale_basic() -> None:
    from ivan.world.lightstyles import lightstyle_pattern_scale

    # "m" is 1.0
    assert abs(lightstyle_pattern_scale("m", frame=0) - 1.0) < 1e-9
    # "a" is 0.0
    assert abs(lightstyle_pattern_scale("a", frame=0) - 0.0) < 1e-9
    # cycles by frame index
    assert abs(lightstyle_pattern_scale("ma", frame=0) - 1.0) < 1e-9
    assert abs(lightstyle_pattern_scale("ma", frame=1) - 0.0) < 1e-9

