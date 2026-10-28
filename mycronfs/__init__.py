"""mycronfs - read/write access to raw Mycron PROG & DATA diskette images.

This is the "libfat" layer of the mtools-style Mycron tooling:
a filesystem object per 256 256-byte raw image, with ls/get/put/delete and
defragmentation. The read path here is deliberately symmetrical to (and
independent from) the read-only extractor in ../image_mycron.py.

Typical use:

    import mycronfs
    fs = mycronfs.from_file("disk-00.img")   # -> ProgFS or DataFS
    for e in fs.files(): print(e)
    data = fs.get("README")
    fs.put_text(...) / fs.put_prog(...)     # see prog.py / data.py
    fs.save()                                # tmp file + atomic rename

Out of scope (by design): TRAM and ND filesystems (still read-only via
image_tram.py / image_nd.py), CP/M (use cpmtools), multivolume diskettes.
"""
from .base import (TRACKS, SECTORS, SECTOR_SIZE, IMG_LEN,
                   MycronFS, FileEntry, ts_to_lin, lin_to_ts, check_name)
from .prog import ProgFS
from .data import DataFS, trim_eof

__all__ = ["TRACKS", "SECTORS", "SECTOR_SIZE", "IMG_LEN", "MycronFS",
           "FileEntry", "ProgFS", "DataFS", "trim_eof",
           "ts_to_lin", "lin_to_ts", "detect_type", "from_bytes", "from_file"]


def detect_type(data: bytes) -> str:
    """'PROG' or 'DATA' from the volume sector (track 0, sector 7)."""
    if len(data) != IMG_LEN:
        raise ValueError(f"not a Mycron raw image: {len(data)} bytes, expected {IMG_LEN}")
    sect7 = data[ts_to_lin(0, 7) * SECTOR_SIZE: ts_to_lin(0, 7) * SECTOR_SIZE + 4]
    if sect7 == b"PROG":
        return "PROG"
    if sect7 == b"VOL1":
        return "DATA"
    raise ValueError(f"unrecognized Mycron filesystem, sector 0.07 starts with {sect7!r} "
                     f"(expected b'PROG' or b'VOL1'; a blank image is not a Mycron filesystem)")


def from_bytes(data: bytes):
    t = detect_type(data)
    cls = ProgFS if t == "PROG" else DataFS
    return cls(bytearray(data))


def from_file(fname):
    with open(fname, "rb") as f:
        return from_bytes(f.read())
