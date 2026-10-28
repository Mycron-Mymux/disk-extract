"""Mycron DATA (IBM 3740 style) diskette filesystem.

Directory: sectors 0.08..0.26, one full 128-byte sector per file entry:

| bytes  | content                                              |
|--------|------------------------------------------------------|
| 1-4    | 'HDR1'                                               |
| 5      | blank                                                |
| 6-13   | data set name (8 char, space padded)                 |
| 25-27  | logical record length, ASCII (e.g. '128')            |
| 29-33  | beginning of extent, ASCII 'tt0ss'                   |
| 35-39  | end of extent, ASCII 'tt0ss'                         |
| 41     | bypass ('B') or blank                                |
| 43     | write protect ('P') or blank                         |
| 45     | multivolume: blank / 'C' / 'L'                       |
| 75-79  | end of data = first UNUSED sector of the extent      |
| rest   | blank/spaces                                          |

Empty slot: 0x44 followed by 0xff to the end of the sector.

CHECK: byte 74 vs 75 for the EOD field is an open question (see base.py
docstring); we write at 75-79 to be symmetrical with the reader.
CHECK: fields beyond position 45 (multi-volume serials etc.) are left
blank; disks carrying multivolume markers are refused for writes.
"""
from .base import (MycronFS, FileEntry, SECTOR_SIZE, ts_to_lin, lin_to_ts)

DIR_FIRST_LIN = 7          # sector 0.08 (linear index)
DIR_LAST_LIN = 25          # sector 0.26 (linear index)
EMPTY_SLOT = b"\x44" + b"\xff" * (SECTOR_SIZE - 1)


def trim_eof(data: bytes) -> bytes:
    """File content up to (not including) the 0x00 EOF marker."""
    return data.partition(b"\x00")[0]


class DataFS(MycronFS):
    fs_type = "DATA"

    # ---------------- reading ----------------

    def _scan_slots(self):
        entries = []
        for dlin in range(DIR_FIRST_LIN, DIR_LAST_LIN + 1):
            sect = self._read_sector_lin(dlin)
            if sect[:5] != b"HDR1 ":
                continue                      # empty (0x44 0xff..) or junk
            ascii_ = sect.decode("ascii", "replace")
            name = ascii_[5:13]
            boe = ascii_[28:33]
            eoe = ascii_[34:39]
            eod = ascii_[74:79]               # CHECK 74/75, see docstring
            if boe[2] != "0" or eoe[2] != "0":
                continue                       # unparseable extent: skip entry
            entries.append(FileEntry(
                name=name,
                lin_start=ts_to_lin(int(boe[:2]), int(boe[3:])),
                lin_end=ts_to_lin(int(eod[:2]), int(eod[3:])),
                slot_lin=dlin, slot_off=0,
                meta={"reclen": ascii_[24:27],
                      "bypass": ascii_[40], "wp": ascii_[42],
                      "multivol": ascii_[44]}))
        return entries

    def _check_writable(self):
        for e in self.files():
            if e.meta["multivol"].strip():
                raise OSError(
                    f"file {e.name!r} is multivolume "
                    f"({e.meta['multivol']!r}); refusing to modify this diskette")

    def delete(self, name):
        self._check_writable()
        return super().delete(name)

    def put(self, name, data: bytes, reserve=0, **meta):
        self._check_writable()
        content = data + b"\x00"              # EOF marker inside the extent
        return super().put(name, content, reserve=reserve,
                           reclen=meta.get("reclen", "128"))

    def put_text(self, name, text, **kw):
        if isinstance(text, (bytes, bytearray)):
            text = bytes(text).decode("ascii")
        return self.put(name, text.encode("ascii"), **kw)

    def update(self, name, data: bytes, **kw):
        """In-place content replacement; EOF marker re-added."""
        self._check_writable()
        return super().update(name, bytes(data) + b"\x00")

    def compact(self):
        self._check_writable()
        return super().compact()

    # ---------------- writing ----------------

    def _entry_bytes(self, entry: FileEntry) -> bytes:
        bt, bs = lin_to_ts(entry.lin_start)
        et, es = lin_to_ts(entry.lin_end - 1)        # last USED sector
        dt, ds = lin_to_ts(entry.lin_end)            # first UNUSED sector
        sect = bytearray(b" " * SECTOR_SIZE)
        sect[0:4] = b"HDR1"
        sect[5:13] = entry.name.encode("ascii")
        sect[24:27] = entry.meta["reclen"].encode("ascii")
        sect[28:33] = f"{bt:02d}0{bs:02d}".encode("ascii")
        sect[34:39] = f"{et:02d}0{es:02d}".encode("ascii")
        sect[40] = ord(entry.meta.get("bypass", " "))
        sect[42] = ord(entry.meta.get("wp", " "))
        sect[44] = ord(entry.meta.get("multivol", " "))
        # CHECK: real data disks also carry the literals below in fields
        # the docs mark "reserved" (bytes 48-53 and 67-72); we replicate
        # them so rewritten entries look like factory-initialized ones.
        sect[47:53] = b"000000"
        sect[66:72] = b"999999"
        sect[74:79] = f"{dt:02d}0{ds:02d}".encode("ascii")
        return bytes(sect)

    def _free_slot(self):
        for dlin in range(DIR_FIRST_LIN, DIR_LAST_LIN + 1):
            if self._read_sector_lin(dlin)[:5] != b"HDR1 ":
                return dlin
        raise OSError("data diskette directory is full (max 19 data sets)")

    def _append_entry(self, name, lin, nsec, meta):
        slot_lin = self._free_slot()
        entry = FileEntry(name=name, lin_start=lin, lin_end=lin + nsec,
                          slot_lin=slot_lin,
                          meta={"reclen": meta.get("reclen", "128") or "128"})
        self._write_sector_lin(slot_lin, self._entry_bytes(entry))
        return entry

    def _relocate_entry(self, entry: FileEntry):
        # entry.lin_start/lin_end already updated by base.compact(); the
        # original record length / flags are kept from parse time.
        self._write_sector_lin(entry.slot_lin, self._entry_bytes(entry))

    def _clear_slot(self, entry: FileEntry):
        self._write_sector_lin(entry.slot_lin, EMPTY_SLOT)

    # ---------------- format ----------------

    def _format_track0(self, label):
        # CHECK: unused metadata sectors all-spaces (like real PROG disks)
        empty = b" " * SECTOR_SIZE
        for sno in (1, 2, 3, 4, 6):
            self._write_sector_lin(ts_to_lin(0, sno), empty)
        self._write_sector_lin(ts_to_lin(0, 5),
                               (b"ERMAP" + b" " * (SECTOR_SIZE - 5)))
        # CHECK: real DATA volume sectors carry 'W' at byte 80; replicate it.
        vol = (("VOL1" + (label or "IBMASC000000")).ljust(79, " ") + "W")
        vol = vol.ljust(SECTOR_SIZE, " ")
        self._write_sector_lin(ts_to_lin(0, 7), vol.encode("ascii"))
        for dlin in range(DIR_FIRST_LIN, DIR_LAST_LIN + 1):
            self._write_sector_lin(dlin, EMPTY_SLOT)
