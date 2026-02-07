from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path


# VTF image formats (subset).
IMAGE_FORMAT_RGBA8888 = 0
IMAGE_FORMAT_DXT1 = 13
IMAGE_FORMAT_DXT5 = 15


@dataclass(frozen=True)
class VTFHeader:
    version_major: int
    version_minor: int
    header_size: int
    width: int
    height: int
    high_format: int
    mip_count: int
    low_format: int
    low_width: int
    low_height: int


def _rgb565_to_rgb888(c: int) -> tuple[int, int, int]:
    r = (c >> 11) & 0x1F
    g = (c >> 5) & 0x3F
    b = c & 0x1F
    # Scale to 0..255.
    r = (r << 3) | (r >> 2)
    g = (g << 2) | (g >> 4)
    b = (b << 3) | (b >> 2)
    return r, g, b


def _dxt1_block_to_rgba(block: bytes) -> list[tuple[int, int, int, int]]:
    c0, c1 = struct.unpack_from("<HH", block, 0)
    r0, g0, b0 = _rgb565_to_rgb888(c0)
    r1, g1, b1 = _rgb565_to_rgb888(c1)
    colors: list[tuple[int, int, int, int]] = [(r0, g0, b0, 255), (r1, g1, b1, 255)]

    if c0 > c1:
        colors.append(((2 * r0 + r1) // 3, (2 * g0 + g1) // 3, (2 * b0 + b1) // 3, 255))
        colors.append(((r0 + 2 * r1) // 3, (g0 + 2 * g1) // 3, (b0 + 2 * b1) // 3, 255))
    else:
        colors.append(((r0 + r1) // 2, (g0 + g1) // 2, (b0 + b1) // 2, 255))
        colors.append((0, 0, 0, 0))

    idx = struct.unpack_from("<I", block, 4)[0]
    out: list[tuple[int, int, int, int]] = []
    for i in range(16):
        out.append(colors[(idx >> (2 * i)) & 0x3])
    return out


def _dxt5_alpha_table(a0: int, a1: int) -> list[int]:
    if a0 > a1:
        return [
            a0,
            a1,
            (6 * a0 + 1 * a1) // 7,
            (5 * a0 + 2 * a1) // 7,
            (4 * a0 + 3 * a1) // 7,
            (3 * a0 + 4 * a1) // 7,
            (2 * a0 + 5 * a1) // 7,
            (1 * a0 + 6 * a1) // 7,
        ]
    return [
        a0,
        a1,
        (4 * a0 + 1 * a1) // 5,
        (3 * a0 + 2 * a1) // 5,
        (2 * a0 + 3 * a1) // 5,
        (1 * a0 + 4 * a1) // 5,
        0,
        255,
    ]


def _decode_dxt1(data: bytes, width: int, height: int) -> bytes:
    blocks_x = (width + 3) // 4
    blocks_y = (height + 3) // 4
    out = bytearray(width * height * 4)

    off = 0
    for by in range(blocks_y):
        for bx in range(blocks_x):
            block = data[off : off + 8]
            off += 8
            px = _dxt1_block_to_rgba(block)
            for iy in range(4):
                for ix in range(4):
                    x = bx * 4 + ix
                    y = by * 4 + iy
                    if x >= width or y >= height:
                        continue
                    r, g, b, a = px[iy * 4 + ix]
                    dst = (y * width + x) * 4
                    out[dst : dst + 4] = bytes((r, g, b, a))
    return bytes(out)


def _decode_dxt5(data: bytes, width: int, height: int) -> bytes:
    blocks_x = (width + 3) // 4
    blocks_y = (height + 3) // 4
    out = bytearray(width * height * 4)

    off = 0
    for by in range(blocks_y):
        for bx in range(blocks_x):
            a0 = data[off]
            a1 = data[off + 1]
            alpha_bits = int.from_bytes(data[off + 2 : off + 8], "little")
            alphas = _dxt5_alpha_table(a0, a1)
            off += 8

            color_block = data[off : off + 8]
            off += 8
            colors = _dxt1_block_to_rgba(color_block)

            for i in range(16):
                a_idx = (alpha_bits >> (3 * i)) & 0x7
                r, g, b, _ = colors[i]
                a = alphas[a_idx]
                x = bx * 4 + (i % 4)
                y = by * 4 + (i // 4)
                if x >= width or y >= height:
                    continue
                dst = (y * width + x) * 4
                out[dst : dst + 4] = bytes((r, g, b, a))
    return bytes(out)


def _mip_level_size(fmt: int, width: int, height: int) -> int:
    if fmt == IMAGE_FORMAT_DXT1:
        return ((width + 3) // 4) * ((height + 3) // 4) * 8
    if fmt == IMAGE_FORMAT_DXT5:
        return ((width + 3) // 4) * ((height + 3) // 4) * 16
    if fmt == IMAGE_FORMAT_RGBA8888:
        return width * height * 4
    raise ValueError(f"Unsupported VTF format {fmt} for {width}x{height}")


def parse_vtf_header(blob: bytes) -> VTFHeader:
    if blob[:4] != b"VTF\x00":
        raise ValueError("Not a VTF file (bad magic)")

    ver_major, ver_minor = struct.unpack_from("<II", blob, 4)
    header_size = struct.unpack_from("<I", blob, 12)[0]
    width, height = struct.unpack_from("<HH", blob, 16)

    low_format = struct.unpack_from("<I", blob, 44)[0]
    low_width = blob[48]
    low_height = blob[49]

    high_format = struct.unpack_from("<I", blob, 52)[0]
    mip_count = blob[56]

    return VTFHeader(
        version_major=int(ver_major),
        version_minor=int(ver_minor),
        header_size=int(header_size),
        width=int(width),
        height=int(height),
        high_format=int(high_format),
        mip_count=int(mip_count),
        low_format=int(low_format),
        low_width=int(low_width),
        low_height=int(low_height),
    )


def decode_vtf_highres_rgba(path: str | Path) -> tuple[int, int, bytes]:
    p = Path(path)
    blob = p.read_bytes()
    h = parse_vtf_header(blob)
    if (h.version_major, h.version_minor) != (7, 2):
        raise ValueError(f"Unsupported VTF version {h.version_major}.{h.version_minor} ({p})")
    if h.low_format != 0:
        # This repo's textures appear to have no low-res thumbnail; keep scope small.
        raise ValueError(f"Unsupported VTF low-res thumbnail format {h.low_format} ({p})")
    if h.mip_count <= 0:
        raise ValueError(f"Bad mip count {h.mip_count} ({p})")

    # VTF 7.2 layout (common): header + [lowres] + highres mip chain.
    # Mips are stored from smallest to largest (mip N-1 .. mip 0).
    sizes: list[int] = []
    for mip in range(h.mip_count - 1, -1, -1):
        w = max(1, h.width >> mip)
        hh = max(1, h.height >> mip)
        sizes.append(_mip_level_size(h.high_format, w, hh))

    total = sum(sizes)
    # Some tools emit extra per-file metadata chunks even for VTF 7.2. Since the high-res mip chain
    # is typically stored at the end of the file, locate it by slicing from EOF.
    data_off = len(blob) - total
    if data_off < h.header_size:
        raise ValueError(
            f"Unexpected VTF layout for {p}: data_off={data_off} header={h.header_size} total={total}"
        )

    # Largest mip (mip 0) is last in the chain.
    largest_off = data_off + sum(sizes[:-1])
    largest_size = sizes[-1]
    payload = blob[largest_off : largest_off + largest_size]

    if h.high_format == IMAGE_FORMAT_DXT1:
        rgba = _decode_dxt1(payload, h.width, h.height)
    elif h.high_format == IMAGE_FORMAT_DXT5:
        rgba = _decode_dxt5(payload, h.width, h.height)
    elif h.high_format == IMAGE_FORMAT_RGBA8888:
        rgba = payload
    else:
        raise ValueError(f"Unsupported VTF high format {h.high_format} ({p})")

    return h.width, h.height, rgba
