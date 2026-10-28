#!/usr/bin/env python3
"""Tests for the mycronfs library + mdisk CLI (run: python3 test_mycronfs.py or pytest)."""
import pathlib
import random
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import image_mycron                      # the read-only extractor (interop check)
import mycronfs
from mycronfs import ProgFS, DataFS
from mycronfs.data import trim_eof


class TestProg(unittest.TestCase):
    def test_format_and_ls(self):
        fs = ProgFS.new(label="TST")
        self.assertEqual(fs.volume_label, "PROGTST")
        self.assertEqual(len(fs.files()), 0)
        self.assertEqual(len(fs.free_sectors()), 76 * 26)

    def test_put_get_roundtrip(self):
        fs = ProgFS.new(label="TST")
        payload = bytes(random.Random(1).randrange(256) for _ in range(300))
        e = fs.put_prog("FOO", payload, addr1=0x3000)
        self.assertEqual(e.name, "FOO     ")
        got = fs.file_data(e)
        self.assertEqual(got[:len(payload)], payload)
        self.assertEqual(got, payload + b"\x00" * (len(got) - len(payload)))

    def test_delete_frees_sectors(self):
        fs = ProgFS.new(label="TST")
        e = fs.put_prog("FOO", b"\xc3" * 200, addr1=0x3000)
        n_free_before = len(fs.free_sectors())
        fs.delete("FOO")
        self.assertEqual(fs.files(), [])
        self.assertEqual(len(fs.free_sectors()), 76 * 26)
        self.assertEqual(len(fs.free_sectors()), n_free_before + 2)

    def test_duplicate_name_refused(self):
        fs = ProgFS.new(label="TST")
        fs.put_prog("FOO", b"\x00", addr1=0x100)
        with self.assertRaises(OSError):
            fs.put_prog("FOO", b"\x00", addr1=0x200)

    def test_update_prog_in_place(self):
        fs = ProgFS.new(label="TST")
        e = fs.put_prog("BAR", b"\x00" * 200, addr1=0x3000)
        e2 = fs.update("BAR", b"\xc3\x00")
        self.assertEqual((e2.lin_start, e2.nsec), (e.lin_start, e.nsec))
        self.assertEqual(fs.get("BAR")[:2], b"\xc3\x00")

    def test_two_segment_prog(self):
        fs = ProgFS.new(label="TST")
        seg1 = bytes(range(128))                      # exactly 1 sector
        seg2 = b"S" * 200                             # 2 sectors, padded
        e = fs.put_prog("TWO", seg1, addr1=0x3000, seg2=seg2, addr2=0x4000)
        self.assertEqual(e.nsec, 3)                   # 1 + 2 sectors
        got = fs.get_prog("TWO")
        self.assertEqual(got["seg1"], seg1)
        self.assertEqual(got["seg2"][:200], seg2)
        self.assertEqual(got["seg1addr"], 0x3000)
        self.assertEqual(got["seg2addr"], 0x4000)
        # seg2 must immediately follow seg1 on the diskette
        raw = fs.file_data(e)
        self.assertEqual(raw[:128], seg1)
        self.assertEqual(raw[128:128 + 200], seg2)
        # seg2 data without addr2 is refused
        with self.assertRaises(ValueError):
            fs.put_prog("BAD", b"x", addr1=0x100, seg2=b"y")

    def test_interop_read_side_extractor(self):
        """An image created here must read back with image_mycron.MycronDiskette."""
        with tempfile.TemporaryDirectory() as d:
            img = pathlib.Path(d) / "t.img"
            fs = ProgFS.new(label="TST")
            prog = bytes([0xc3, 0x00, 0x00]) + b"\x00" * 125
            fs.put_prog("FOO", prog, addr1=0x4000, seg2=b"HELLO", addr2=0x4100)
            fs.fname = str(img)
            fs.save()
            data = img.read_bytes()
            self.assertEqual(len(data), 256256)
            old = image_mycron.MycronDiskette(str(img))
            self.assertEqual(old.disktype, "PROG")
            names = [pe.name for pe in old.files]
            self.assertEqual(names, ["FOO"])
            pe = old.files[0]
            self.assertEqual(pe.seg1addr, 0x4000)
            self.assertEqual(pe.seg2addr, 0x4100)
            self.assertEqual(pe.seg1, prog)              # exactly one sector
            self.assertEqual(pe.seg2[:5], b"HELLO")
            self.assertEqual([pe.track0, pe.sec0], [1, 1])


class TestData(unittest.TestCase):
    def test_format_and_ls(self):
        fs = DataFS.new(label="IBMASC000001")
        self.assertEqual(fs.volume_label, "VOL1IBMASC000001".ljust(79) + "W")
        self.assertEqual(fs.files(), [])

    def test_put_get_roundtrip(self):
        fs = DataFS.new()
        e = fs.put_text("TMP1", "hello mycron")
        self.assertEqual(trim_eof(fs.file_data(e)), b"hello mycron")
        self.assertEqual(fs.get("TMP1"), fs.file_data(e))

    def test_delete_and_refill(self):
        fs = DataFS.new()
        fs.put_text("A", "first")
        fs.put_text("B", "second file contents")
        fs.delete("A")
        names = [e.name.strip() for e in fs.files()]
        self.assertEqual(names, ["B"])
        fs.put_text("C", "reused")
        names = sorted(e.name.strip() for e in fs.files())
        self.assertEqual(names, ["B", "C"])

    def test_full_directory(self):
        fs = DataFS.new()
        for i in range(19):
            fs.put_text(f"F{i}", b"x")
        with self.assertRaises(OSError):
            fs.put_text("OVERFLOW", b"x")

    def test_multivolume_refused(self):
        fs = DataFS.new()
        e = fs.put_text("X", "y")
        # fake a multivolume marker into the entry
        sect = bytearray(fs._read_sector_lin(e.slot_lin))
        sect[44] = ord("C")
        fs._write_sector_lin(e.slot_lin, bytes(sect))
        with self.assertRaises(OSError):
            fs.delete("X")

    def test_compact(self):
        fs = DataFS.new()
        fs.put_text("A", "a" * 400)        # 4 sectors
        fs.put_text("B", "b" * 100)         # 1 sector
        fs.delete("A")
        # B now sits at the tail; defrag should move it back to 01.01
        e = fs.files()[0]
        self.assertNotEqual((e.lin_start), 26)
        moved = fs.compact()
        self.assertEqual([m.strip() for m in moved], ["B"])
        e = fs.files()[0]
        self.assertEqual(e.lin_start, 26)
        self.assertEqual(trim_eof(fs.file_data(e)), b"b" * 100)

    def test_reserve(self):
        fs = DataFS.new()
        e = fs.put_text("R", "small", reserve=5)
        self.assertEqual(e.nsec, 6)

    def test_update_in_place(self):
        fs = DataFS.new()
        fs.put_text("A", "first", reserve=3)
        fs.put_text("B", "second", reserve=3)
        pos_before = [(e.name, e.lin_start, e.nsec) for e in fs.files()]
        e2u = fs.update("B", b"replaced content")
        # slot, position and extent size are untouched (pre-allocation kept)
        self.assertEqual([(e.name, e.lin_start, e.nsec) for e in fs.files()],
                         pos_before)
        self.assertEqual(trim_eof(fs.file_data(e2u)), b"replaced content")
        # too-big content cannot fit the existing extent -> must delete+put
        with self.assertRaises(OSError):
            fs.update("A", b"x" * 600)       # needs 5 sectors, A has 4
        # updating a name that does not exist fails cleanly
        with self.assertRaises(OSError):
            fs.update("NOPE", b"x")

    def test_interop_read_side_extractor(self):
        with tempfile.TemporaryDirectory() as d:
            img = pathlib.Path(d) / "t.img"
            fs = DataFS.new(label="IBMASC000042")
            fs.put_text("GREET", "hei verden")
            fs.fname = str(img)
            fs.save()
            old = image_mycron.MycronDiskette(str(img))
            self.assertEqual(old.disktype, "DATA")
            self.assertEqual(old.volid, "IBMASC")
            names = [de.name for de in old.files]
            self.assertEqual(names, ["GREET"])
            self.assertEqual(old.files[0].ascii_file(), "hei verden")


class TestMdiskCLI(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.img = str(pathlib.Path(self.dir.name) / "d.img")

    def tearDown(self):
        self.dir.cleanup()

    def run_cli(self, *args, **kw):
        r = subprocess.run([sys.executable, "mdisk.py", *args],
                           capture_output=True, text=True, cwd=pathlib.Path(__file__).parent)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def test_cli_flow(self):
        self.run_cli("format", self.img, "--type", "data", "--label", "IBMASCCLI")
        self.run_cli("put", self.img, "HELLO", "--string", "hello cli")
        r = self.run_cli("ls", self.img)
        self.assertIn("HELLO", r.stdout)
        r = self.run_cli("cat", self.img, "HELLO")
        self.assertEqual(r.stdout, "hello cli")
        self.run_cli("update", self.img, "HELLO", "--string", "updated cli")
        r = self.run_cli("cat", self.img, "HELLO")
        self.assertEqual(r.stdout, "updated cli")
        self.run_cli("rm", self.img, "HELLO")
        r = self.run_cli("ls", self.img)
        self.assertIn("0 files", r.stdout)
        # prog flow (after the earlier data-disk checks)
        self.run_cli("format", self.img, "--type", "prog", "--label", "CLIP", "--force")
        self.run_cli("put", self.img, "FOO", "--string", "progdata", "--addr", "0x4000")
        r = self.run_cli("cat", self.img, "FOO")
        # PROG files are NOT trimmed at 0x00: the full padded sector is content
        self.assertEqual(r.stdout, "progdata".ljust(128, "\x00"))
        # zero bytes in program content survive: content is returned as
        # stored (no EOF trimming), at library level too
        zn = pathlib.Path(self.dir.name) / "z.bin"
        zn.write_bytes(b"\x00\xff\x00")
        self.run_cli("put", self.img, "Z", "--file", str(zn), "--addr", "0x1000")
        from mycronfs import ProgFS as _P
        self.assertEqual(_P.from_file(self.img).get("Z")[:3], b"\x00\xff\x00")
        # two-segment program: get writes the pair, --segment picks one
        self.run_cli("put", self.img, "TWO", "--string", "code", "--addr", "0x3000",
                     "--string2", "seg2data", "--addr2", "0x4000")
        base = str(pathlib.Path(self.dir.name) / "two")
        self.run_cli("get", self.img, "TWO", base)
        # PROG content is sector-terminated: padded runs, never trimmed
        self.assertEqual(pathlib.Path(base + ".seg1.bin").read_bytes(), b"code".ljust(128, b"\x00"))
        self.assertEqual(pathlib.Path(base + ".seg2.bin").read_bytes(), b"seg2data".ljust(128, b"\x00"))
        r = self.run_cli("cat", self.img, "TWO", "--segment", "2")
        self.assertEqual(r.stdout, "seg2data".ljust(128, "\x00"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
