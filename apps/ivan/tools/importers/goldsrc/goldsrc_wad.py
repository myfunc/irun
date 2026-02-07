from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path


class WadError(RuntimeError):
    pass


@dataclass(frozen=True)
class WadTexture:
    name: str
    width: int
    height: int
    rgba: bytes  # width*height*4


def _read_cstr(raw: bytes) -> str:
    if b"\x00" in raw:
        raw = raw.split(b"\x00", 1)[0]
    return raw.decode("ascii", errors="ignore")


def decode_wad3_miptex(*, name: str, data: bytes) -> WadTexture:
    """
    Decode a WAD3 MIPTEX lump to RGBA.

    Layout (little-endian):
    - name[16], width(u32), height(u32), offsets[4](u32)
    - pixel data for mip 0..3 at given offsets (relative to start of this struct)
    - after mip3: palette_size(u16) (usually 256) then palette[palette_size]*3 (RGB)
    """
    if len(data) < 16 + 4 + 4 + 16:
        raise WadError("miptex lump too small")

    tex_name = _read_cstr(data[0:16]) or name
    width, height = struct.unpack_from("<II", data, 16)
    o0, o1, o2, o3 = struct.unpack_from("<IIII", data, 24)
    if width <= 0 or height <= 0:
        raise WadError(f"invalid texture dimensions: {width}x{height}")

    # Mip0 is the full-res indexed image.
    mip0_len = width * height
    if o0 == 0 or o0 + mip0_len > len(data):
        raise WadError("invalid mip0 offset/length")
    mip0 = data[o0 : o0 + mip0_len]

    # Mip chain sizes: w*h, w/2*h/2, w/4*h/4, w/8*h/8.
    # Palette follows immediately after the last mip level.
    mip1_len = max(1, (width // 2)) * max(1, (height // 2))
    mip2_len = max(1, (width // 4)) * max(1, (height // 4))
    mip3_len = max(1, (width // 8)) * max(1, (height // 8))

    palette_off = o3 + mip3_len
    if palette_off + 2 > len(data):
        raise WadError("missing palette size")
    (palette_size,) = struct.unpack_from("<H", data, palette_off)
    if palette_size <= 0:
        raise WadError("invalid palette size")
    palette_bytes = palette_size * 3
    pal_start = palette_off + 2
    pal_end = pal_start + palette_bytes
    if pal_end > len(data):
        raise WadError("palette out of bounds")
    palette = data[pal_start:pal_end]

    transparent = tex_name.startswith("{")
    out = bytearray(width * height * 4)
    for i, idx in enumerate(mip0):
        pi = int(idx) * 3
        r = palette[pi + 0]
        g = palette[pi + 1]
        b = palette[pi + 2]
        a = 0 if (transparent and idx == 255) else 255
        o = i * 4
        out[o + 0] = r
        out[o + 1] = g
        out[o + 2] = b
        out[o + 3] = a

    return WadTexture(name=tex_name, width=int(width), height=int(height), rgba=bytes(out))


@dataclass(frozen=True)
class WadDirEntry:
    offset: int
    disk_size: int
    size: int
    lump_type: int
    name: str


class Wad3:
    def __init__(self, path: Path, entries: list[WadDirEntry], blob: bytes) -> None:
        self.path = path
        self.entries = entries
        self._blob = blob

    @staticmethod
    def load(path: Path) -> "Wad3":
        blob = path.read_bytes()
        if len(blob) < 12:
            raise WadError("file too small")
        magic = blob[0:4]
        if magic != b"WAD3":
            raise WadError(f"unsupported magic: {magic!r}")
        num, dir_off = struct.unpack_from("<II", blob, 4)
        if dir_off <= 0 or dir_off >= len(blob):
            raise WadError("invalid directory offset")
        entries: list[WadDirEntry] = []
        # Directory entry: offset(u32), disk_size(u32), size(u32), type(u8), compression(u8), pad(u16), name[16]
        ent_sz = 32
        for i in range(int(num)):
            off = dir_off + i * ent_sz
            if off + ent_sz > len(blob):
                raise WadError("directory out of bounds")
            e_off, disk_size, size = struct.unpack_from("<III", blob, off)
            lump_type = blob[off + 12]
            name = _read_cstr(blob[off + 16 : off + 32])
            entries.append(
                WadDirEntry(
                    offset=int(e_off),
                    disk_size=int(disk_size),
                    size=int(size),
                    lump_type=int(lump_type),
                    name=name,
                )
            )
        return Wad3(path=path, entries=entries, blob=blob)

    def iter_textures(self) -> list[WadTexture]:
        # Common texture lump type for MIPTEX in WAD3 is 0x43 (67).
        out: list[WadTexture] = []
        for e in self.entries:
            if e.lump_type != 0x43:
                continue
            if e.offset <= 0 or e.offset + e.size > len(self._blob):
                continue
            lump = self._blob[e.offset : e.offset + e.size]
            try:
                out.append(decode_wad3_miptex(name=e.name, data=lump))
            except WadError:
                continue
        return out

