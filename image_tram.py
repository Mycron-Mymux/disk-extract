#!/usr/bin/env python

import sys
import argparse
import imd
import imd_common
from image_common import Archive, File


class TramDisk:
    def __init__(self, fname):
        self.fname = fname
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
        """Fetches a sector from the IMD image.
        Expands compressed sectors.
        """
        t = self.track_data[(tno, 0)]
        ssize = t.sector_size
        s = self.sectors[(tno, 0, sno)]
        d = s.data
        if len(d) == 1:
            return d * ssize
        return d

    def get_raw_hdr(self):
        """Assuming that sector 1-5 are header sectors - returns a raw byte string
        of these sectors"""
        return b''.join([self.get_sector_data(0, i) for i in range(1, 5)])
    
    def filenames(self):
        """Returns a list of filenames on the image"""
        hdr = self.get_raw_hdr()
        # For simplicity, assume that filenames start at the end of sector 3,
        # so offset 3*128-3 and that the last entry is followed with a 0xff
        # marker (unused file entries start with 0xff)
        fn_start = hdr[3*128-3:]
        fnames = []
        while fn_start[0] != 0xff:
            fn = fn_start[:12].decode('ascii').strip()
            fnames.append(fn)
            # print(fn)
            fn_start = fn_start[12:]
        return fnames

    def doc_chunks(self, track):
        """Returns (line num, 78 char text) for each line in the track.
        Since 42 * 79 < 26*128, there will be 10 bytes at the end of the track
        that are not returned.
        NB: line numbers may be out of order.
        """
        # A text track starts sith 0x01 at the first sectors.
        # It looks like text comes in chunks of a number/index plus 78 bytes.
        data = b''
        cur_sec = 0
        while True:
            if len(data) < 79:
                # Add next sector
                cur_sec += 1
                if cur_sec > 26:
                    return
                data += self.get_sector_data(track, cur_sec)
            num = data[0]
            txt = data[1:79]
            data = data[79:]
            yield (num, txt)

    def track_lines(self, track):
        """Returns the sorted lines in a document, skipping
        - duplicate lines (assuming lines with the same number as an existing
          one is old data that is not overwritten)
        - lines with line numbers >= 0xe5 (assuming they are unused). These
          _may_ have other formatting information in them (TODO).
        """
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

    def doc_get_track_numbers(self, doc_no):
        """The header has a region of 76 bytes indicating which document number
        the are stored in the corresponding tracks (1..76)
        Unused tracks are stored as 0xff
        This function returns the tracks corresponding to document doc_no.
        """
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
            # TODO: maybe insert a page break between tracks? (depends on interpretation)
            yield bytes(' ' * 78, encoding='ascii')

    def get_metainf(self):
        s = f"{self.fname}\n"
        return s + "\n".join(self.filenames())

    def get_archive(self):
        archive = Archive(self.fname)
        archive.add_file(File(".meta", self.get_metainf().encode("ascii")))
        for fno, fname in enumerate(self.filenames()):
            print(" -- ", fname)
            data = b'\n'.join(self.doc_get_raw_lines(fno))
            archive.add_file(File(fname, data))
        return archive


def tram_raw_dump_documents(fname):
    tdisk = TramDisk(fname)
    fnames = tdisk.filenames()
    print(f"********* {fname} *********")
    print("********************************")

    for doc_no, fn in enumerate(fnames):
        print(f"------- {doc_no} {fn} ---------")
        print("-------------------------------")
        for track_no in tdisk.doc_get_track_numbers(doc_no):
            print(f"---- track {track_no}")
            seen = set()
            for rno, (lno, txt) in enumerate(tdisk.doc_chunks(track_no)):
                print(f"  -- {rno:3} {lno=:3} {txt}")
                if 0xe5 in txt or 0xff in txt:
                    imd_common.hexdump_data(txt)
            sec = tdisk.get_sector_data(track_no, 26)
            remainder = sec[-10:]
            print("   -- remaining bytes of track", remainder)
            imd_common.hexdump_data(remainder)

    

def main():
    """For inspecting the document formats"""
    argp = argparse.ArgumentParser()
    argp.add_argument('fname')
    args = argp.parse_args()
    tram_raw_dump_documents(args.fname)


if __name__ == '__main__':
    main()
