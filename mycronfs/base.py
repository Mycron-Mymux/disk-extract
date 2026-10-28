"""Common core for the Mycron PROG and DATA diskette filesystems.

Both filesystems share the physical layout (the point of this shared
module): 8-inch, single-sided, single-density diskettes with

    77 tracks (0..76) x 26 sectors (1..26) x 128 bytes = 256 256 bytes

Track 0 holds the metadata: sector 0.05 the ERMAP marker, sector 0.07
the volume label (which identifies PROG vs DATA), and sectors 0.08..0.26
the file directory. File data therefore always starts at track 1 or
later; there is no live allocation bitmap - free space is discovered by
scanning which sectors are not covered by any extent.

A file in both filesystems boils down to: name + a *contiguous sector
run* (an extent) + entry-specific metadata. That model is what this base
class implements: parsing slots, allocation, deletion and defragmentation
are shared; prog.py and data.py only add the on-disk entry encoding.

Open questions / to check and update in the future (marked CHECK):
- CHECK: ERMAP sector internals (dim-1030 p. 6-37). We only ever write
  "ERMAP" followed by spaces, like the real disks we have.
- CHECK: DATA end-of-data field: the docs say bytes 74-78, but the
  read-side extractor uses 75-79 (74 left us with empty files). We write
  at 75-79 to match the reader; verify against the PROM disassembly.
- CHECK: contents of the unused metadata sectors (0.01-0.04, 0.06). Real
  PROG disks use all spaces; emulator templates used 0x40 ('@') fill
  (like TRAM disks). We use spaces for both; revisit when known.
- CHECK: reserved DATA fields and multivolume (C/L) handling: we keep
  those fields blank when writing and REFUSE to edit disks carrying a
  multivolume marker.
- CHECK: padding bytes after the EOF marker inside a file's last sector:
  we pad with 0x00.
"""
import os
import pathlib
from dataclasses import dataclass, field

TRACKS = 77        # tracks are numbered 0..76
SECTORS = 26       # sectors are numbered 1..26
SECTOR_SIZE = 128
IMG_LEN = TRACKS * SECTORS * SECTOR_SIZE   # 256256

# The whole first track holds metadata (headers, ERMAP, volume, directory)
RESERVED_SECTORS = SECTORS                 # linear sectors 0..25 == track 0
FIRST_FILE_LIN = SECTORS                   # files may only start on track >= 1


def ts_to_lin(track, sector):
    """(track, sector) -> linear sector index (track 0 sector 1 == 0)"""
    return track * SECTORS + (sector - 1)


def lin_to_ts(lin):
    """linear sector index -> (track, sector)"""
    return lin // SECTORS, (lin % SECTORS) + 1


def check_name(name):
    """Names are up to 8 chars; stored space-padded to 8."""
    if not isinstance(name, str) or not (1 <= len(name) <= 8):
        raise ValueError(f"invalid Mycron file name {name!r}: need 1..8 characters")
    return f"{name:<8}"


@dataclass
class FileEntry:
    """A file on a Mycron diskette, decoded from a directory entry."""
    name: str            # 8 chars, space padded
    lin_start: int       # linear index of first sector of the extent (incl.)
    lin_end: int         # linear index of first sector AFTER the extent (excl.)
    slot_lin: int        # linear index of the directory sector holding the entry
    slot_off: int = 0    # byte offset of the entry within that sector (PROG only)
    meta: dict = field(default_factory=dict)

    @property
    def nsec(self):
        return self.lin_end - self.lin_start

    def ts_start(self):
        return lin_to_ts(self.lin_start)

    def __str__(self):
        t, s = self.ts_start()
        return (f"{self.name.strip():8} start {t:02d}.{s:02d} "
                f"{self.nsec:3d} sectors {dict(sorted(self.meta.items()))}")


class MycronFS:
    """Base for the PROG and DATA raw-image filesystems.

    Subclasses implement the on-disk encoding of directory entries:
      _scan_slots()                 -> list[FileEntry] (all valid entries)
      _write_slot(entry)            -> write entry bytes into its slot sector
      _clear_slot(entry)            -> blank the slot sector/region of entry
      _slot_is_free(sector_bytes)   -> bool (used to find a free slot)
    """

    fs_type = None            # "PROG" or "DATA", set by subclasses

    def __init__(self, barr: bytearray, fname=None):
        assert isinstance(barr, bytearray) and len(barr) == IMG_LEN, \
            f"image must be {IMG_LEN} bytes, got {len(barr)}"
        self.barr = barr
        self.fname = fname

    # ---------------- raw sector access ----------------

    def read_sector(self, track, sector) -> bytes:
        return self._read_sector_lin(ts_to_lin(track, sector))

    def _read_sector_lin(self, lin) -> bytes:
        off = lin * SECTOR_SIZE
        return bytes(self.barr[off:off + SECTOR_SIZE])

    def _write_sector_lin(self, lin, data: bytes):
        assert len(data) == SECTOR_SIZE
        off = lin * SECTOR_SIZE
        self.barr[off:off + SECTOR_SIZE] = data

    def write_sector(self, track, sector, data: bytes):
        self._write_sector_lin(ts_to_lin(track, sector), data)

    # ---------------- volume label ----------------

    @property
    def volume_label(self) -> str:
        """Full contents of sector 0.07 (type marker + label), trailing spaces cut."""
        return self._read_sector_lin(ts_to_lin(0, 7)).rstrip(b" ").decode("ascii", "replace")

    def _write_vol_sector(self, marker: str, label: str):
        vol = marker + label
        if len(vol) > SECTOR_SIZE:
            raise ValueError("volume label too long")
        self._write_sector_lin(
            ts_to_lin(0, 7), (vol + " " * (SECTOR_SIZE - len(vol))).encode("ascii"))

    # ---------------- generic file model ----------------

    def files(self):
        """All valid entries, sorted by start of extent."""
        return sorted(self._scan_slots(), key=lambda e: e.lin_start)

    def file_data(self, entry: FileEntry) -> bytes:
        """Full raw content of a file: the whole sector run of its extent."""
        return b"".join(
            self._read_sector_lin(lin) for lin in range(entry.lin_start, entry.lin_end))

    def used_sectors(self):
        used = set(range(RESERVED_SECTORS))
        for e in self.files():
            used.update(range(e.lin_start, e.lin_end))
        return used

    def free_sectors(self):
        return sorted(set(range(FIRST_FILE_LIN, TRACKS * SECTORS)) - self.used_sectors())

    def _alloc_run(self, count):
        """Find the first contiguous run of `count` free sectors."""
        free = set(self.free_sectors())
        start = FIRST_FILE_LIN
        end = TRACKS * SECTORS - count
        while start <= end:
            if all((start + i) in free for i in range(count)):
                return start
            start += 1
        raise OSError(f"no free run of {count} sectors available")

    def _write_run(self, lin, data: bytes):
        for i, off in enumerate(range(0, len(data), SECTOR_SIZE)):
            chunk = data[off:off + SECTOR_SIZE]
            if len(chunk) < SECTOR_SIZE:
                chunk = chunk + b"\x00" * (SECTOR_SIZE - len(chunk))  # CHECK (see module doc)
            self._write_sector_lin(lin + i, chunk)

    # ---------------- mutating operations (shared logic) ----------------

    def put(self, name, data: bytes, reserve=0, **meta) -> FileEntry:
        """Write data as a NEW file. Raises if the name already exists.
        reserve: extra sectors appended to the end of the extent (the PL/M
        tooling never grows extents past their pre-allocation, so over-
        allocating is good practice for files that will be edited on-disk).
        """
        name = check_name(name)
        if any(e.name == name for e in self.files()):
            raise OSError(f"file {name!r} already exists on this diskette")
        nsec = max(1, -(-len(data) // SECTOR_SIZE)) + max(0, reserve)
        lin = self._alloc_run(nsec)
        self._write_run(lin, data)
        return self._append_entry(name, lin, nsec, meta)

    def delete(self, name) -> FileEntry:
        """Blank the slot of the (first) file with this name. Returns it.
        NB: PROG disks may hold duplicate names; deletes the first."""
        name = check_name(name)
        for e in self.files():
            if e.name == name:
                self._clear_slot(e)
                return e
        raise OSError(f"no file named {name!r} on this diskette")

    def get(self, name) -> bytes:
        name8 = check_name(name)
        for e in self.files():
            if e.name == name8:
                return self.file_data(e)
        raise OSError(f"no file named {name!r} on this diskette")

    def update(self, name, data: bytes) -> FileEntry:
        """Replace the content of an existing file IN PLACE: same directory
        slot, same extent, same pre-allocation. Only a no-op for position;
        the new content must fit in the existing extent (delete+put if you
        need to grow or shrink the extent itself)."""
        name8 = check_name(name)
        for e in self.files():
            if e.name == name8:
                need = max(1, -(-len(data) // SECTOR_SIZE))
                if need > e.nsec:
                    raise OSError(
                        f"{name!r} needs {need} sectors but its extent holds "
                        f"{e.nsec}; cannot grow an extent in place")
                self._write_run(e.lin_start, data)
                return e
        raise OSError(f"no file named {name!r} on this diskette")

    def compact(self):
        """Defragment: rewrite every file so that extents are packed,
        in order of current start, from the first sector of track 1.
        Returns the list of names that actually moved."""
        entries = self.files()
        entries.sort(key=lambda e: e.lin_start)
        new_start = FIRST_FILE_LIN
        moved = []
        for e in entries:
            nsec = e.nsec
            data = self.file_data(e)
            if e.lin_start != new_start:
                self._write_run(new_start, data)
                moved.append(e.name)
            # point the entry at its (new) position & rewrite the slot bytes
            e.lin_start, e.lin_end = new_start, new_start + nsec
            self._relocate_entry(e)
            new_start = e.lin_end
        return moved

    # ---------------- construction / serialization ----------------

    @classmethod
    def new(cls, label="", barr=None):
        """Build a fresh, empty image of this fs type. Subclass provides
        the metadata-sector templates via _format_track0()."""
        fs = cls(barr if barr is not None else bytearray(b"\x00" * IMG_LEN))
        fs._format_track0(label)
        return fs

    @classmethod
    def from_file(cls, fname):
        return cls(bytearray(pathlib.Path(fname).read_bytes()), fname=str(fname))

    def save(self, fname=None):
        """Write via temp file + atomic rename. The emulator opens the image
        per sector at run time, so never truncate in place; rename is atomic."""
        fname = fname or self.fname
        if fname is None:
            raise ValueError("no filename given")
        tmp = str(fname) + ".tmp"
        pathlib.Path(tmp).write_bytes(bytes(self.barr))
        os.replace(tmp, fname)

    # ---------------- hooks to be implemented by prog.py / data.py -------

    def _scan_slots(self):        raise NotImplementedError
    def _append_entry(self, name, lin, nsec, meta): raise NotImplementedError
    """_append_entry must construct the FileEntry (with slot info), write the
    entry bytes via self._write_slot-like logic, and return it."""
    def _clear_slot(self, entry): raise NotImplementedError
    def _relocate_entry(self, entry): raise NotImplementedError
    """_relocate_entry re-encodes entry.meta (and entry.lin_start/lin_end,
    already updated by the caller) into the directory bytes at entry.slot_*"""
    def _format_track0(self, label): raise NotImplementedError
