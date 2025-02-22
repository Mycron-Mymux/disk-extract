#!/usr/bin/env python3

"""
Documentation for file format : see dim-1030 documentation.
http://fileformats.archiveteam.org/wiki/IBM_3740_format

TODO:
- mycron-bin disk 23 and 24 have files with backspace in their filename.
  When creating zip files, the zip library handles this.
  When extracting to directories directly, the files get the backspace added.

"""
import struct
import argparse
import zipfile
import pathlib
import image_common
from image_common import split_disk, split_sect, add_sects, extract_ascii
from image_common import File, Archive

# The first generations of Mycron computers used Single Side Single Density diskettes.
TRACKS=77        # tracks are numbered 0..76
SECTORS=26       # sectors are numbered 1..26
SECTOR_SIZE=128


# program entry, 16 bytes
# bytes:
# 1-8 program name (padded with spaces at the end)
# 9 - first track #
# 10 - first sector #
# 11 - high order byte of load addr seg 1
# 12 - low order byte of load addr seg 1
# 13 - number of sectors seg 1
# 14 - high order byte of load addr seg 2
# 15 - low order byte of load addr seg 2
# 16 - number of sectors seg 2
class ProgEntry:
    def __init__(self, ebytes, disk):
        self.ebytes = ebytes
        self.name = ebytes[:8].decode("ASCII").strip()
        self.valid = len(self.name) > 0  # TODO: could also check if the other vars are also 0
        # big endian > since high order byte is first..
        self.track0, self.sec0, self.seg1addr, self.seg1sz, self.seg2addr, self.seg2sz = struct.unpack(">BBHBHB", ebytes[8:])

        et1, es1 = add_sects(self.track0, self.sec0, self.seg1sz)
        et2, es2 = add_sects(et1, es1, self.seg2sz)
        
        self.sects1 = disk.get_sectors(self.track0, self.sec0, et1, es1)
        self.sects2 = disk.get_sectors(et1, es1, et2, es2)
        self.seg1 = b''.join(self.sects1.values())
        self.seg2 = b''.join(self.sects2.values())
        if self.valid and 0:
            print('seg1', self.sects1.keys())
            print('seg2', self.sects2.keys())

    def __str__(self):
        s = f"ProgEntry({self.name:8}, t/s0={self.track0:2}.{self.sec0:2}, "
        s += f"seg 1 at {self.seg1addr:#6x} sz {self.seg1sz:#6x} len {len(self.seg1):#6x}, "
        s += f"seg 2 at {self.seg2addr:#6x} sz {self.seg2sz:#6x} len {len(self.seg2):#6x}) "
        # s += str(self.ebytes)
        return s

    def files(self):
        yield File(f"{self.name}.meta", bytes(str(self), encoding="ascii"))
        if len(self.seg1) > 0:
            yield File(f"{self.name}.seg1.bin", self.seg1)
        if len(self.seg2) > 0:
            yield File(f"{self.name}.seg2.bin", self.seg2)


# positions starting with 1 (not 0) in the docs
# see page 6-38 for more details
# - 1-4   is HDR1
# - 5     is space
# - 6-13  data set name (initialized with DATA, user defined)
# - 14-24 reserved or blank
# - 25-27 logical record length (max 128)  must be 080 on 3742 or > 000, less than 128 on 3741 or on the 3742 with 128 feature (init 080)
# - 28    reserved or blank
# - 29-33 beginning of extent (BOE) - first sector addr. 29+30 track number, 31 must be 0, 32+33 sector number.
# - 34    reserved or blank
# - 35-39 end of extent (last sector for data set)
# - 40    reserved or blank
# - 41    bypass data set - if B, 3747 will ignore, if blank - processed
# - 42    accessibility must be blank
# - 43    data set write protect P if protected, else blank
# - 44    reserved or blank
# - 45    multivolume inidicator.  blank=not multivol, C continued on another diskette, L this is the last diskette.
# - 46-72 reserved or blank
# - 73    verify mark: V = has been verified
# - 74    end of Data. indicates address of next unused sector of data set (init  was 01001 sect 8, 74001 on sect 9-26)
# - 80    reserved or blank
# TODO: I'm not verifying all of the above. 
class DataEntry:
    @classmethod
    def verify_data_entry(cls, sect):
        """True if this seems to be a sector describing a data file entry"""
        try:
            hdr = sect[:5].decode("ASCII")
        except:
            # print("Couldn't decode", sect[:5])
            return False
        if hdr != "HDR1 ":
            return False
        return True
    
    def __init__(self, sect, disk):
        self.sect = sect
        try:
            self.ascii = sect.decode('ascii')
        except:
            print("Could not decode", sect)
            raise
        assert self._sub(1, 5) == 'HDR1 '
        self.name = self._sub(6, 13).strip()
        self.raw_reclen = self._sub(25, 27)
        self.raw_beo = self._sub(29, 33)
        self.raw_eoe = self._sub(35, 39)
        # This is the first free sector in the dataset, so it's not supposed to be included in the files.
        self.raw_eod = self._sub(75, 79)
        assert self.raw_beo[2] == '0' and self.raw_eoe[2] == '0'
        self.rec_len = int(self.raw_reclen)
        self.start_track = int(self.raw_beo[:2])
        self.start_sect  = int(self.raw_beo[3:])
        self.end_track = int(self.raw_eoe[:2])
        self.end_sect  = int(self.raw_eoe[3:])
        # end of data
        self.eda_track = int(self.raw_eod[:2])
        self.eda_sect  = int(self.raw_eod[3:])

        self.fsectors = disk.get_sectors(self.start_track, self.start_sect, self.eda_track, self.eda_sect)
        self.raw_file = b''.join(s for s in self.fsectors.values())

    def _sub(self, start, end):
        return self.ascii[start-1:end]

    def ascii_file(self):
        """Returns an ascii file, trimmed at the EOF mark"""
        txt = self.raw_file.decode('ascii')
        n_eof = txt.count('\000')
        assert n_eof <= 1
        txt = txt.split('\000')[0]
        return txt

    def raw_file_to_eof(self):
        rf = self.raw_file
        n_eof = rf.count(0)
        assert n_eof <= 1
        return rf.split(b'\000')[0]

    def files(self, dump_raw=True):
        if dump_raw:
            data = self.raw_file_to_eof()
        else:
            data = self.ascii_file()
        yield File(self.name, data)

    def __str__(self):
        s = f"DataEntry({self.name:8}, len {len(self.ascii_file()):7}, start {self.start_track:02}.{self.start_sect:02})"
        return s


class MycronDiskette:
    def __init__(self, fname):
        self.fname = fname
        self.data = open(fname, 'rb').read()
        self.disk = split_disk(self.data)
        self._scan_volume_id()
        match self.disktype:
            case "DATA":
                self.files = self._get_data_files()
            case "PROG":
                self.files = self._get_prog_files()

    def check_errmap(self):
        # errmap is on track 0, sector 5
        sect = self.disk[(0, 5)]
        s = sect[:5].decode("ASCII")
        # print("Checking that ERMAP is present at sector 5")
        assert s == "ERMAP"
        # TODO: check errmap (page 6-37 in dim-1030 docs)

    def _scan_volume_id(self):
        sect = self.disk[(0, 7)]
        vol1 = extract_ascii(sect, 0, 4)
        match vol1:
            case "VOL1":
                self.disktype = "DATA"
                self.volid = extract_ascii(sect, 4, 10)  # should be IBMASC
                assert vol1 == "VOL1" and self.volid in ["IBMASC", "QUASAR", "IBMIRD"], f"Failed to find IBMASC or QUASAR in {sect}"
                self.check_errmap()
            case "PROG":
                self.disktype = "PROG"
                self.volid = extract_ascii(sect, 4, 10)  # should be IBMASC
            case _:
                self.disktype = "ERROR"
                self.volid = "ERROR"
                raise f"blarg {sect}"

    def _get_data_files(self):
        dl = []
        for sno in range(8, SECTORS+1):
            sect = self.disk[(0, sno)]
            if not DataEntry.verify_data_entry(sect):
                continue
            entry = DataEntry(sect, self)
            print(entry)
            dl.append(entry)
        return dl

    def _get_prog_files(self):
        pl = []
        for sno in range(8, SECTORS+1):
            sect = self.disk[(0, sno)]
            entries = split_sect(sect, 16)
            # print(entries)
            for rpe in entries:
                pe = ProgEntry(rpe, self)
                if pe.valid:
                    print(pe)
                    pl.append(pe)
        return pl

    def get_metainf(self):
        s = f"{self.fname}\n"
        return s + "\n".join([str(f) for f in self.files])

    def get_archive(self):
        # TODO: add a .meta file for the archive?
        archive = Archive(self.fname)
        archive.add_file(File(".meta", self.get_metainf().encode("ascii")))
        for entry in self.files:
            for file in entry.files():
                archive.add_file(file)
        return archive

    def get_sectors(self, start_track, start_sector, end_track, end_sector):
        """Returns the sectors from (including) start track/sector up to (but not including) end track and sector.
        Returned as a dict with key = (trk,sect)
        """
        trk = start_track
        sct = start_sector
        sectors = {}
        while trk <= end_track:
            if trk == end_track and sct >= end_sector:
                break
            k = (trk, sct)
            sectors[k] = self.disk[k]
            sct += 1
            if sct > SECTORS:
                trk += 1
                sct = 1
        return sectors


def main():
    parser = argparse.ArgumentParser(
        prog="Mycron Diskette Dumper",
        description="Displays info about a diskette image. Optionally extracts files and puts them in a zip file.",
        epilog="check this (TODO)")

    parser.add_argument('filename')
    parser.add_argument('--zip', nargs=1, help="zip file to store extracted files in")
    parser.add_argument('--dir', nargs=1, help="directory to extract files into")
    args = parser.parse_args()


    disk = MycronDiskette(args.filename)
    if args.zip:
        zip_fname = args.zip[0]
        print("Adding to zip file", zip_fname)
        arch = disk.get_archive()
        arch.write_to_zip(zip_fname)

    if args.dir:
        dpath = args.dir[0]
        arch = disk.get_archive()
        arch.write_to_dir(dpath)


if __name__ == '__main__':
    main()




