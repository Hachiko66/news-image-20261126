#!/usr/bin/env python3
"""Copy the news-image-20261126 front page to the output directory.

The entry image is bundled in this repository as entry.png. This program
only validates it (PNG magic, size, dimensions, complete IEND chunk) and
copies it atomically to $MAKEFUN_OUTPUT_DIR/entry.png with mode 0644.
It performs no network access and writes byte-identical output on
every run.
"""

import hashlib
import os
import shutil
import struct
import sys
import tempfile
import zlib

MAX_BYTES = 1_048_576
MAX_DIMENSION = 1024
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def fail(message):
    print("error: " + message, file=sys.stderr)
    raise SystemExit(1)


def validate_png(path):
    """Check the file is a whole PNG within the competition limits."""
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError as exc:
        fail("cannot read %s: %s" % (path, exc))

    if len(data) > MAX_BYTES:
        fail("entry.png is %d bytes, over the 1 MiB limit" % len(data))
    if len(data) < 8 or data[:8] != PNG_MAGIC:
        fail("entry.png does not start with the PNG magic bytes")

    offset = 8
    saw_ihdr = False
    saw_iend = False
    width = height = None
    while offset + 8 <= len(data):
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        chunk_type = data[offset + 4:offset + 8]
        end = offset + 12 + length
        if end > len(data):
            fail("truncated %s chunk" % chunk_type.decode("latin-1"))
        payload = data[offset + 8:offset + 8 + length]
        stored_crc = struct.unpack(">I", data[offset + 8 + length:end])[0]
        actual_crc = zlib.crc32(chunk_type + payload) & 0xFFFFFFFF
        if stored_crc != actual_crc:
            fail("bad CRC in %s chunk" % chunk_type.decode("latin-1"))
        if chunk_type == b"IHDR":
            if length != 13:
                fail("IHDR chunk has the wrong length")
            width, height = struct.unpack(">II", payload[:8])
            saw_ihdr = True
        elif chunk_type == b"IEND":
            if length != 0:
                fail("IEND chunk has a non-zero length")
            saw_iend = True
            if end != len(data):
                fail("bytes follow the IEND chunk")
            break
        offset = end

    if not saw_ihdr:
        fail("no IHDR chunk found")
    if not saw_iend:
        fail("no complete IEND chunk found")
    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        fail("image is %dx%d, over the 1024x1024 limit" % (width, height))
    return width, height


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    source = os.path.join(here, "entry.png")
    width, height = validate_png(source)

    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    try:
        os.makedirs(out_dir, exist_ok=True)
    except OSError as exc:
        fail("cannot create output directory %s: %s" % (out_dir, exc))
    target = os.path.join(out_dir, "entry.png")

    fd, tmp_path = tempfile.mkstemp(prefix=".entry-", dir=out_dir)
    try:
        with os.fdopen(fd, "wb") as out:
            with open(source, "rb") as src:
                shutil.copyfileobj(src, out)
        os.chmod(tmp_path, 0o644)
        os.replace(tmp_path, target)
    except OSError as exc:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        fail("cannot write %s: %s" % (target, exc))
    os.chmod(target, 0o644)
    with open(source, "rb") as src, open(target, "rb") as out:
        source_hash = hashlib.sha256(src.read()).hexdigest()
        target_hash = hashlib.sha256(out.read()).hexdigest()
    if source_hash != target_hash:
        fail("written output does not match entry.png")
    print("wrote %s (%dx%d, mode 0644)" % (target, width, height))


if __name__ == "__main__":
    main()
