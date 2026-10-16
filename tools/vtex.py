"""A minimal reader for Source 2 compiled textures (.vtex_c) -> RGBA picture, the fallback of tools/extract_icons.py.

Why: Source2Viewer-CLI 19.2 / 20.0 stops on the art of the heroes released 2026-10-14 (Violet, Deadman Danny, Solomon's
new ability, the new item art): Valve's newer texture compiler writes a value type (26) into the file's edit-info block
(RED2) that the CLI does not know, so it gives up on the whole file. The picture itself sits in the DATA block and the
bytes after it, in the old layout; this reader skips the edit info and decodes only that.

Layout (as ValveResourceFormat reads it): a 16-byte header (file size, header version, version, block table offset,
block count), a table of (4-char type, relative offset, size) blocks, the DATA block of a texture (width, height,
format, mip count, extra data), then the mip levels from the smallest to the largest — the full picture is the last.
Supported formats: the uncompressed 8-bit ones, DXT1/DXT5/BC4/BC5/BC7 (Pillow's BCn decoder) and an embedded
PNG / JPEG / WebP; mips packed with LZ4 need the `lz4` module. Anything else raises ValueError.
"""
from __future__ import annotations

import io
import struct
from pathlib import Path

# VTexFormat (ValveResourceFormat/Resource/Enums/VTexFormat.cs) -> (kind, Pillow BCn number or raw mode, bytes per
# block / pixel)
_FORMATS = {
    1: ('bcn', 1, 8),          # DXT1
    2: ('bcn', 3, 16),         # DXT5
    3: ('raw', 'L', 1),        # I8
    4: ('raw', 'RGBA', 4),     # RGBA8888
    15: ('file', None, 0),     # JPEG_RGBA8888
    16: ('file', None, 0),     # PNG_RGBA8888
    17: ('file', None, 0),     # JPEG_DXT5
    18: ('file', None, 0),     # PNG_DXT5
    20: ('bcn', 7, 16),        # BC7
    21: ('bcn', 5, 16),        # ATI2N (BC5)
    22: ('raw', 'LA', 2),      # IA88
    27: ('bcn', 4, 8),         # ATI1N (BC4)
    28: ('raw', 'BGRA', 4),    # BGRA8888
    29: ('file', None, 0),     # WEBP_RGBA8888
    30: ('file', None, 0),     # WEBP_DXT5
}
_FILL_TO_POWER_OF_TWO, _COMPRESSED_MIP_SIZE = 1, 2


def _blocks(data: bytes) -> dict[bytes, tuple[int, int]]:
    """Block type -> (absolute offset, size)."""
    _size, _header_version, _version, table, count = struct.unpack_from('<IHHII', data, 0)
    pos, out = 8 + table, {}
    for _ in range(count):
        kind = data[pos:pos + 4]
        offset, size = struct.unpack_from('<II', data, pos + 4)
        out[kind] = (pos + 4 + offset, size)
        pos += 12
    return out


def _extra(data: bytes, at: int) -> dict[int, bytes]:
    """The texture's extra data entries (type -> bytes); `at` is the position of the extra-data offset field."""
    offset, count = struct.unpack_from('<II', data, at)
    pos, out = at + offset, {}
    for _ in range(count):
        kind, rel, size = struct.unpack_from('<III', data, pos)
        start = pos + 4 + rel
        out[kind] = data[start:start + size]
        pos += 12
    return out


def _mip_size(kind: str, unit: int, w: int, h: int) -> int:
    if kind == 'bcn':
        return ((w + 3) // 4) * ((h + 3) // 4) * unit
    return w * h * unit


def _from_ycocg(im):
    """A DXT5 picture the compiler stored as scaled YCoCg (its edit info names "Image YCoCg Conversion"): Co in red,
    Cg in green, the scale in blue, luma in alpha -> RGB, opaque."""
    from PIL import Image
    co_b, cg_b, sc_b, y_b = (ch.tobytes() for ch in im.split())
    r, g, b = bytearray(len(y_b)), bytearray(len(y_b)), bytearray(len(y_b))
    for i, (co, cg, sc, y) in enumerate(zip(co_b, cg_b, sc_b, y_b)):
        scale = (sc >> 3) + 1
        co_f, cg_f = (co - 128) / scale, (cg - 128) / scale
        r[i] = min(255, max(0, round(y + co_f - cg_f)))
        g[i] = min(255, max(0, round(y + cg_f)))
        b[i] = min(255, max(0, round(y - co_f - cg_f)))
    size = im.size
    alpha = Image.new('L', size, 255)
    return Image.merge('RGBA', [Image.frombytes('L', size, bytes(c)) for c in (r, g, b)] + [alpha])


def decode(data: bytes):
    """The full-size picture of a .vtex_c file's bytes, as a Pillow RGBA image. A file it cannot read (cut short, a
    layout or format it does not know) raises ValueError, whatever broke inside."""
    try:
        return _decode(data)
    except ValueError:
        raise
    except (struct.error, IndexError, OSError, ImportError, RuntimeError) as exc:     # RuntimeError: lz4's own
        raise ValueError(f'unreadable texture: {exc}') from exc


def _decode(data: bytes):
    from PIL import Image
    blocks = _blocks(data)
    if b'DATA' not in blocks:
        raise ValueError('no DATA block')
    at, size = blocks[b'DATA']
    w, h, depth = struct.unpack_from('<HHH', data, at + 20)
    fmt, mips = struct.unpack_from('<BB', data, at + 26)
    if fmt not in _FORMATS:
        raise ValueError(f'texture format {fmt} not supported')
    if depth > 1:
        raise ValueError('volume / array textures not supported')
    kind, how, unit = _FORMATS[fmt]
    extra = _extra(data, at + 32)
    pixels = at + size                        # the mips follow the DATA block, the smallest first
    if kind == 'file':                        # an image file packed as it is
        return Image.open(io.BytesIO(data[pixels:])).convert('RGBA')
    sizes = [_mip_size(kind, unit, max(1, w >> m), max(1, h >> m)) for m in range(mips)]
    packed = sizes
    lz4 = False
    if _COMPRESSED_MIP_SIZE in extra:
        flag, rel, n = struct.unpack_from('<III', extra[_COMPRESSED_MIP_SIZE], 0)
        lz4 = flag == 1
        packed = list(struct.unpack_from(f'<{n}i', extra[_COMPRESSED_MIP_SIZE], 4 + rel))
    start = pixels + sum(packed[1:])
    raw = data[start:start + packed[0]]
    if lz4:
        import lz4.block
        raw = lz4.block.decompress(raw, uncompressed_size=sizes[0])
    if len(raw) < sizes[0]:
        raise ValueError(f'truncated mip: {len(raw)} of {sizes[0]} bytes')
    if kind == 'bcn':
        bw, bh = (w + 3) // 4 * 4, (h + 3) // 4 * 4
        im = Image.frombytes('RGBA', (bw, bh), raw, 'bcn', how).crop((0, 0, w, h))
        red2 = blocks.get(b'RED2') or blocks.get(b'REDI')
        if fmt == 2 and red2 and b'YCoCg' in data[red2[0]:red2[0] + red2[1]]:
            im = _from_ycocg(im)
    else:
        im = Image.frombytes('RGBA', (w, h), raw, 'raw', how) if how in ('RGBA', 'BGRA') else \
            Image.frombytes(how, (w, h), raw).convert('RGBA')
    if _FILL_TO_POWER_OF_TWO in extra:        # a picture padded to a power of two: its real size
        _, real_w, real_h = struct.unpack_from('<HHH', extra[_FILL_TO_POWER_OF_TWO], 0)
        if 0 < real_w <= w and 0 < real_h <= h:
            im = im.crop((0, 0, real_w, real_h))
    return im


def to_png(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    decode(src.read_bytes()).save(dst)
