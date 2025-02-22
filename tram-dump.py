#!/usr/bin/env python

import sys
from collections import defaultdict
from rich.console import Console
import imd
import imd_common
import argparse

USE_RICH=False
USE_RICH=True

console = Console()


def val2chr(val):
    v = val & 0x7f
    c = bytes([v]).decode('latin1')
    c2 = chr(v)
    assert c == c2    # probably doesn't matter since we're decoding 7-bit ascii
    return c


def richify_tram_string(tstr):
    ENC='latin1'
    buf = ''
    for cv in tstr:
        c = val2chr(cv)
        if cv > 0x7f:
            if USE_RICH:
                # buf += f"[bold]{c}[/bold]"
                buf += f"\x1b[4m{c}\x1b[0m"
            else:
                buf += c
        else:
            buf += c
    return buf


def hex_str(bseq):
    return ' '.join([f'{v:2x}' for v in bseq])


# TODO: see notes.md - can probably cat a full document 

class TramDisk:
    def __init__(self, fname):
        d = imd.Disk.from_file(fname)
        self.disk = d
        self.track_data = dict()
        for t in d.tracks:
            k = (t.cylinder, t.head)
            if k in self.track_data:
                raise f"Failed... {k} already exists in track_data"
            self.track_data[(t.cylinder, t.head)] = t

        self.sectors = dict()
        for t in d.tracks:
            for sno, s in enumerate(t.sector_data_records, start=1):
                k = (t.cylinder, t.head, sno)
                if k in self.sectors:
                    raise f"Failed to add sectors {k} already exists in sectors dict"
                self.sectors[k] = s

        d = self.get_sector_data(0, 1)
        assert d[:5].decode('ascii') == "*TRAM"

    def get_sector_data(self, tno, sno):
        t = self.track_data[(tno, 0)]
        ssize = t.sector_size
        s = self.sectors[(tno, 0, sno)]
        d = s.data
        if len(d) == 1:
            return d * ssize
        return d

    def get_raw_hdr(self):
        return b''.join([self.get_sector_data(0, i) for i in range(1, 5)])
    
    def filenames(self):
        hdr = self.get_raw_hdr()

        # for simplicity, assume that filenames start at the end of sector 3,
        # so offset 3*128-3 and that the last entry is followed with a 0xff marker
        fn_start = hdr[3*128-3:]
        fnames = []
        while fn_start[0] != 0xff:
            fn = fn_start[:12].decode('ascii').strip()
            fnames.append(fn)
            # print(fn)
            fn_start = fn_start[12:]
        return fnames

    def doc_chunks(self, track):
        # A text track starts sith 0x01 at the first sectors.
        # It looks like text comes in chunks of a number/index plus 78 bytes.
        data = b''
        cur_sec = 0
        while True:
            if len(data) < 79:
                cur_sec += 1
                if cur_sec > 26:
                    return
                data += self.get_sector_data(track, cur_sec)
            num = data[0]
            txt = data[1:79]
            data = data[79:]
            yield (num, txt)

    def track_lines(self, track):
        lines = {}
        for lno, chunk in self.doc_chunks(track):
            if lno >= 0xe5:
                # print(f"Skipping eot {lno:#02x}", chunk)
                continue
            if lno in lines:
                if 0:
                    print("Skipping duplicate line", lno)
                    print("   - ", lines[lno])
                    print("     ", chunk)
                continue
            lines[lno] = chunk
        return [(lno, lines[lno]) for lno in sorted(lines.keys())]

    def hexdump_sector(self, track, sector):
        print(f"---- tr {track:2} s {sector:2} ---")
        s = self.get_sector_data(track, sector)
        imd_common.hexdump_data(s)

    def print_doc_track(self, track):
        print("------------- track ", track, hex(track))
        for num, chunk in self.track_lines(track):
            s = f"{track:2} {num:2} : " + richify_tram_string(chunk)
            if USE_RICH:
                console.print(s)
            else:
                print(s)

    def doc_get_track_numbers(self, doc_no):
        IDX_START=156    # start of document indexes (it's in the second sector of track 0 with some offset)
        hdr = self.get_raw_hdr()
        indexes = [int(x) for x in hdr[IDX_START: IDX_START+76]]
        tracks = [tno for tno, idx in enumerate(indexes, start=1) if idx == doc_no]
        # print(tracks, indexes)
        return tracks

    def doc_get_raw_lines(self, doc_no):
        track_nums = self.doc_get_track_numbers(doc_no)
        for track in track_nums:
            for lno, tl in self.track_lines(track):
                yield tl
            yield bytes(' ' * 78, encoding='ascii')

    def doc_get_formatted_lines(self, doc_no):
        """Underline chars (>=0x80) are underlined using escape sequences"""
        for line in self.doc_get_raw_lines(doc_no):
            yield richify_tram_string(line)
        
    def print_doc(self, doc_no):
        # TODO: tram may be page oriented (one page of output per track of text).
        for line in self.doc_get_formatted_lines(doc_no):
            print(line)
        
    def print_doc_with_raw(self, doc_no):
        # TODO: tram may be page oriented (one page of output per track of text).
        for line in self.doc_get_raw_lines(doc_no):
            print(richify_tram_string(line), hex_str(line))

def print_names(fnames):
    for i, fn in enumerate(fnames):
        print(f"  {i:2}  {fn}")

def print_t0():
    for i in range(1, 27):
        dinfo.hexdump_sector(0, i)
    

ap = argparse.ArgumentParser()
# ap.add_argument("-hex", action="store_true")
ap.add_argument("fname", nargs='?', default="tram-disk-01.imd")
ap.add_argument("-t0", action="store_true", help="print header track")
ap.add_argument("-c", nargs=1, help="Cat doc number (starting with 0)")
ap.add_argument("-cr", nargs=1, help="Cat doc number (starting with 0) with raw info per line")
ap.add_argument("-d", action="store_true", help="dump disk content as docs++")
ap.add_argument("-ls", action="store_true", help="list documents")
args = ap.parse_args()

fname = args.fname
dinfo = TramDisk(fname)

if args.ls:
    print_names(dinfo.filenames())

if args.t0:
    print_t0()

if args.d:
    for track in range(1, 76):
        dinfo.print_doc_track(track)

if args.c:
    doc_no = int(args.c[0])
    dinfo.print_doc(doc_no)

if args.cr:
    doc_no = int(args.cr[0])
    dinfo.print_doc_with_raw(doc_no)
    
