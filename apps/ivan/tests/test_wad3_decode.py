from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

from ivan import __version__  # noqa: F401


def _add_tools_to_syspath() -> None:
    tools_dir = Path(__file__).resolve().parents[1] / "tools" / "importers" / "goldsrc"
    sys.path.insert(0, str(tools_dir))


def _build_miptex_lump(*, name: str, width: int, height: int, indices: bytes, palette: bytes) -> bytes:
    assert len(indices) == width * height
    assert len(palette) == 256 * 3

    # Header: name[16], w, h, offsets[4]
    name_raw = name.encode("ascii")[:16].ljust(16, b"\x00")
    header_size = 16 + 4 + 4 + 16
    o0 = header_size
    o1 = o0 + (width * height)
    o2 = o1 + max(1, width // 2) * max(1, height // 2)
    o3 = o2 + max(1, width // 4) * max(1, height // 4)
    hdr = name_raw + struct.pack("<II", width, height) + struct.pack("<IIII", o0, o1, o2, o3)

    # Mip chain (we only care about mip0, but WAD expects the chain to exist for palette offset).
    mip0 = indices
    mip1 = b"\x00" * (max(1, width // 2) * max(1, height // 2))
    mip2 = b"\x00" * (max(1, width // 4) * max(1, height // 4))
    mip3 = b"\x00" * (max(1, width // 8) * max(1, height // 8))

    pal_size = struct.pack("<H", 256)
    return hdr + mip0 + mip1 + mip2 + mip3 + pal_size + palette


def test_wad3_miptex_decode_rgba() -> None:
    _add_tools_to_syspath()
    from goldsrc_wad import decode_wad3_miptex  # noqa: E402

    width, height = 2, 2
    # Indices: 0,1,2,3 in a 2x2.
    indices = bytes([0, 1, 2, 3])
    # Palette: entry i -> (i, 0, 0) (red ramp).
    palette = bytes([i for i in range(256) for _ in (0,)])  # placeholder, overwritten below
    pal = bytearray(256 * 3)
    for i in range(256):
        pal[i * 3 + 0] = i
        pal[i * 3 + 1] = 0
        pal[i * 3 + 2] = 0
    palette = bytes(pal)

    lump = _build_miptex_lump(name="TEST", width=width, height=height, indices=indices, palette=palette)
    tex = decode_wad3_miptex(name="TEST", data=lump)
    assert tex.width == 2
    assert tex.height == 2
    # Pixel 0 -> palette[0] => (0,0,0,255)
    assert tex.rgba[0:4] == bytes([0, 0, 0, 255])
    # Pixel 1 -> (1,0,0,255)
    assert tex.rgba[4:8] == bytes([1, 0, 0, 255])


def test_wad3_transparent_texture_uses_index_255_as_alpha0() -> None:
    _add_tools_to_syspath()
    from goldsrc_wad import decode_wad3_miptex  # noqa: E402

    width, height = 2, 2
    indices = bytes([255, 0, 0, 0])
    pal = bytearray(256 * 3)
    pal[255 * 3 + 0] = 10
    pal[255 * 3 + 1] = 20
    pal[255 * 3 + 2] = 30
    palette = bytes(pal)

    lump = _build_miptex_lump(name="{TRN", width=width, height=height, indices=indices, palette=palette)
    tex = decode_wad3_miptex(name="{TRN", data=lump)
    assert tex.rgba[0:4] == bytes([10, 20, 30, 0])
