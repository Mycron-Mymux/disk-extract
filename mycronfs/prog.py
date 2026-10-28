"""Mycron PROG (program) diskette filesystem.

Directory: sectors 0.08..0.26, each holding 8 x 16-byte entries:

| bytes | content                              |
|-------|--------------------------------------|
| 1-8   | program name, space padded           |
| 9     | first track number                   |
| 10    | first sector number                  |
| 11-12 | hi/lo load address segment 1         |
| 13    | number of sectors segment 1          |
| 14-15 | hi/lo load address segment 2         |
| 16    | number of sectors segment 2          |

Empty slot: 8 spaces followed by 8 zero bytes. A slot is *valid* if the
name is not all spaces. Loaded by the Mycrop monitor with 'LNAME'.
"""
import struct

from .base import (MycronFS, FileEntry, SECTOR_SIZE, ts_to_lin, lin_to_ts,
                  check_name)

DIR_FIRST_LIN = 7          # sector 0.08 (linear index)
DIR_LAST_LIN = 25          # sector 0.26 (linear index)
EMPTY_SLOT = b" " * 8 + b"\x00" * 8


class ProgFS(MycronFS):
    fs_type = "PROG"

    # ---------------- reading ----------------

    def _scan_slots(self):
        entries = []
        for dlin in range(DIR_FIRST_LIN, DIR_LAST_LIN + 1):
            sect = self._read_sector_lin(dlin)
            for i in range(SECTOR_SIZE // 16):
                ebytes = sect[i * 16:(i + 1) * 16]
                name = ebytes[:8].decode("ascii", "replace")
                if not name.strip():
                    continue        # empty slot (spaces name + zero values)
                track0, sec0, seg1addr, seg1sz, seg2addr, seg2sz = \
                    struct.unpack(">BBHBHB", ebytes[8:])
                if not (0 <= track0 < 77 and 1 <= sec0 <= 26):
                    continue        # same validity check as the read side
                lin = ts_to_lin(track0, sec0)
                entries.append(FileEntry(
                    name=name,
                    lin_start=lin, lin_end=lin + seg1sz + seg2sz,
                    slot_lin=dlin, slot_off=i * 16,
                    meta={"track0": track0, "sec0": sec0,
                          "seg1addr": seg1addr, "seg1sz": seg1sz,
                          "seg2addr": seg2addr, "seg2sz": seg2sz}))
        return entries

    def _slot_bytes(self, entry: FileEntry) -> bytes:
        name = entry.name.encode("ascii")
        vals = struct.pack(">BBHBHB", entry.meta["track0"], entry.meta["sec0"],
                           entry.meta["seg1addr"], entry.meta["seg1sz"],
                           entry.meta["seg2addr"], entry.meta["seg2sz"])
        return name + vals

    # ---------------- writing ----------------

    def _free_slot(self):
        """First (sector, offset) whose 16 bytes are an empty slot."""
        for dlin in range(DIR_FIRST_LIN, DIR_LAST_LIN + 1):
            sect = self._read_sector_lin(dlin)
            for i in range(SECTOR_SIZE // 16):
                if sect[i * 16:(i + 1) * 16] == EMPTY_SLOT:
                    return dlin, i * 16
        raise OSError("program diskette directory is full")

    def _append_entry(self, name, lin, nsec, meta):
        t0, s0 = lin_to_ts(lin)
        slot_lin, slot_off = self._free_slot()
        entry = FileEntry(
            name=name, lin_start=lin, lin_end=lin + nsec,
            slot_lin=slot_lin, slot_off=slot_off,
            meta={"track0": t0, "sec0": s0,
                  "seg1addr": meta.get("seg1addr", 0), "seg1sz": nsec,
                  "seg2addr": meta.get("seg2addr", 0), "seg2sz": 0})
        self._write_entry(entry)
        return entry

    def _write_entry(self, entry: FileEntry):
        dlin = entry.slot_lin
        sect = bytearray(self._read_sector_lin(dlin))
        sect[entry.slot_off:entry.slot_off + 16] = self._slot_bytes(entry)
        self._write_sector_lin(dlin, bytes(sect))

    def _relocate_entry(self, entry: FileEntry):
        t0, s0 = lin_to_ts(entry.lin_start)
        entry.meta["track0"], entry.meta["sec0"] = t0, s0
        # keep segment sizes in sync with the (possibly new) full extent
        entry.meta["seg1sz"] = entry.nsec
        entry.meta["seg2sz"] = 0
        self._write_entry(entry)

    def _clear_slot(self, entry: FileEntry):
        dlin = entry.slot_lin
        sect = bytearray(self._read_sector_lin(dlin))
        sect[entry.slot_off:entry.slot_off + 16] = EMPTY_SLOT
        self._write_sector_lin(dlin, bytes(sect))

    # ---------------- format ----------------

    def _format_track0(self, label):
        # CHECK: unused metadata sectors are all-spaces on real PROG disks
        empty = b" " * SECTOR_SIZE
        for sno in (1, 2, 3, 4, 6):
            self._write_sector_lin(ts_to_lin(0, sno), empty)
        self._write_sector_lin(ts_to_lin(0, 5),
                               (b"ERMAP" + b" " * (SECTOR_SIZE - 5)))
        self._write_vol_sector("PROG", label or "ASCII")
        empty_dir = EMPTY_SLOT * 8
        for dlin in range(DIR_FIRST_LIN, DIR_LAST_LIN + 1):
            self._write_sector_lin(dlin, empty_dir)

    # convenience: program disks store up to TWO load segments per file
    def put_prog(self, name, seg1: bytes, addr1: int, seg2: bytes = b"",
                 addr2: int = None, reserve: int = 0):
        """Write a program file with one or two load segments.

        The Mycrop monitor 'L' command loads segment 1 at addr1 and
        (if present) segment 2 at addr2; on the diskette the two segments
        are stored back-to-back: seg1's sectors first, then seg2's.

        - seg1 is padded (0x00, CHECK) to whole sectors -> seg1sz sectors
        - seg2 empty => single-segment program
        - seg2 given => addr2 required
        - reserve: extra sectors added behind the segments (a program
          extent can never be extended later; rm + put to change layout).
        """
        name8 = check_name(name)
        if any(e.name == name8 for e in self.files()):
            raise OSError(f"file {name8!r} already exists on this diskette")
        if not (0 <= int(addr1) <= 0xFFFF):
            raise ValueError(f"load address {addr1!r} out of range")
        seg1sz = max(1, -(-len(seg1) // SECTOR_SIZE))
        seg2sz = -(-len(seg2) // SECTOR_SIZE) if seg2 else 0
        if seg2sz and addr2 is None:
            raise ValueError("two-segment program needs addr2")
        if seg2sz and not (0 <= int(addr2) <= 0xFFFF):
            raise ValueError(f"load address {addr2!r} out of range")
        if not seg2sz and addr2 is not None:
            raise ValueError("addr2 given without seg2 data")
        need = seg1sz + seg2sz
        total = need + max(0, reserve)
        lin = self._alloc_run(total)
        self._write_run(lin, seg1)
        if seg2sz:
            self._write_run(lin + seg1sz, seg2)
        t0, s0 = lin_to_ts(lin)
        slot_lin, slot_off = self._free_slot()
        entry = FileEntry(
            name=name8, lin_start=lin, lin_end=lin + total,
            slot_lin=slot_lin, slot_off=slot_off,
            meta={"track0": t0, "sec0": s0,
                  "seg1addr": int(addr1), "seg1sz": seg1sz,
                  "seg2addr": int(addr2) if seg2sz else 0,
                  "seg2sz": seg2sz})
        self._write_entry(entry)
        return entry

    def get_prog(self, name):
        """Return {'seg1': bytes, 'seg2': bytes, 'seg1addr': int, 'seg2addr': int}
        for a program file; the segment byte counts come from the directory
        entry, so this also works for the demo/legacy program files."""
        name8 = check_name(name)
        for e in self.files():
            if e.name == name8:
                raw = self.file_data(e)
                n1 = e.meta["seg1sz"] * SECTOR_SIZE
                return {"seg1": raw[:n1],
                        "seg2": raw[n1:] if e.meta["seg2sz"] else b"",
                        "seg1addr": e.meta["seg1addr"],
                        "seg2addr": e.meta["seg2addr"]}
        raise OSError(f"no program file named {name!r} on this diskette")
