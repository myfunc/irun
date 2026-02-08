from __future__ import annotations


def lightstyle_pattern_scale(pattern: str, frame: int) -> float:
    """
    GoldSrc/Quake lightstyle convention:
    - pattern is a string of chars 'a'..'z'
    - each char maps to a brightness scale where 'm' is 1.0
    - the "server" updates at ~10Hz, so frame should be int(now * 10)
    """

    if not isinstance(pattern, str) or not pattern:
        pattern = "m"

    i = int(frame) % len(pattern)
    c = pattern[i]
    if not ("a" <= c <= "z"):
        c = c.lower()
    if not ("a" <= c <= "z"):
        return 1.0
    return max(0.0, float(ord(c) - ord("a")) / 12.0)


def lightstyle_pattern_is_animated(pattern: str) -> bool:
    """
    Return True if the pattern meaningfully changes brightness over time.

    Notes:
    - We treat patterns with <= 1 character as static.
    - We treat patterns where all valid brightness chars map to the same value as static.
    - Invalid chars are ignored (they fallback to 1.0 at runtime).
    """

    if not isinstance(pattern, str):
        return False
    pat = pattern.strip()
    if len(pat) <= 1:
        return False

    seen: set[str] = set()
    for ch in pat:
        c = ch
        if not ("a" <= c <= "z"):
            c = c.lower()
        if not ("a" <= c <= "z"):
            continue
        seen.add(c)
        if len(seen) >= 2:
            return True

    return False

