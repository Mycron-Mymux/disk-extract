#!/usr/bin/env python

import zipfile
import pathlib
import itertools
import imd_common
from pathlib import Path
import imd

# The first generations of Mycron computers used Single Side Single Density diskettes.
TRACKS      =  77       # tracks are numbered 0..76
SECTORS     =  26       # sectors are numbered 1..26
SECTOR_SIZE = 128


def split_disk(data, tracks=TRACKS, sectors=SECTORS, sector_size=SECTOR_SIZE):
    """splits a disk into tracks and sectors
    returns a dict with (track,sector): sector_data.
    """
    expected_size = tracks * sectors * sector_size
    if len(data) != expected_size:
        raise ValueError(f"splitting data of len {len(data)} failed. Expected len = {expected_size}")

    disk = {}
    for index in range(tracks * sectors):
        track, sector = divmod(index, sectors)
        offset = index * sector_size
        d = data[offset:offset + sector_size]
        assert len(d) == sector_size, f"Sector #{index} ({track}.{sector+1}) has incorrect size: {len(d)}"
        disk[(track, sector + 1)] = d
    return disk


def split_sect(sect, psize):
    """Split a sector into equal size parts"""
    return [sect[offset:offset+psize] for offset in range(0, len(sect), psize)]


def sector_index(track, sector, sectors_per_track=SECTORS):
    if sector < 1 or sector > sectors_per_track:
        raise ValueError(f"Invalid sector: {sector}")
    return track * sectors_per_track + sector - 1


def sector_address(index, sectors_per_track=SECTORS):
    track, sector = divmod(index, sectors_per_track)
    return track, sector + 1


def add_sects(track, sector, count, sectors_per_track=SECTORS):
    """add sectors to address starting at track and sect, returning new track,sect"""
    return sector_address(sector_index(track, sector, sectors_per_track) + count,
                          sectors_per_track)


def extract_ascii(sect, start, stop):
    part = sect[start:stop]
    try:
        return part.decode('ASCII')
    except UnicodeDecodeError:
        print(f"Couldn't decode {start}:{stop} = '{part}' from {sect}")
        raise


# NB: a given archive should present metadata files as .meta files
class File:
    def __init__(self, path, data):
        self.path = path
        self.data = data
        assert isinstance(self.data, (bytes, bytearray))
    def safe_fn(self):
        """When extracting the file, it might need to be rewritten slightly"""
        return self.path


def ensure_dir(path):
    """Ensure that directory of path exists. Prints a warning if it has to
    create a directory (likely caused by a / character in the filename)"""
    path = pathlib.Path(path)
    if not path.parent.exists():
        print(f"WARNING: creating subdir {path.parent} for {path}")
        path.parent.mkdir(parents=True, exist_ok=True)


def read_image_bytes(path):
    data = Path(path).read_bytes()

    if data.startswith(b"IMD "):
        image = imd.Disk.from_bytes(data)
        return imd_common.get_full_img_ss(image), "imd"

    return data, "raw"


class DiskImage:
    """
    NB: The ND diskettes found so far have 154 and 154 tracks (as reported by imd)
    """
    def __init__(self, fname, data, sectors, imgtype):
        self.fname = fname
        self.data = data
        self.sectors = sectors
        self.imgtype = imgtype

    def read_sector(self, track, sector):
        key = (track, sector)
        if key not in self.sectors:
            raise ValueError(f"Sector not in image: {track=} {sector=}")
        return self.sectors[key]

    @classmethod
    def from_file(cls, fname):
        data, imgtype = read_image_bytes(fname)
        # TODO: this is not going to work for ND images. They use a different disk format
        # that will end up with significantly more data per diskette.
        try:
            sectors = split_disk(data)
        except ValueError:
            print(f"WARNING: {fname} splitting into sectors failed for data of len {len(data)}, could be a non-mycron disk format. sector index is blank")
            sectors = {}
        return cls(fname, data, sectors, imgtype)

    def detect_filesystem(self):
        if len(self.sectors) == 0:
            print(f"WARNING: {self.fname} no sectors defined, assuming non-mycron disk format")
            return
        if self.sectors[(0, 1)].startswith(b"*TRAM"):
            return "tram"
        s5 = self.sectors[(0, 5)]
        s7 = self.sectors[(0, 7)]
        if s5.startswith(b'ERMAP'):
            if s7.startswith(b'PROG'):
                return "mycron-prog"
            if s7.startswith(b'VOL1'):
                return "mycron-data"


class Archive:
    """Keeps a list of files extracted from a disk"""
    def __init__(self, fname):
        self.fname = fname
        self.files = dict()   # indexed by path

    def add_file(self, file):
        """ """
        path = file.path
        if path in self.files:
            print(f"Path to file '{path}' added previously.")
            for count in itertools.count(1):
                if (new_fn := f"{path}--duplicate-{count:03d}") not in self.files:
                    print(f"Adding file as {new_fn}")
                    path = new_fn
                    file.path = path    # can't access the file afterwards if not. TODO: consider handling this in each of the write_X
                    self.files[path] = file
                    return
        self.files[path] = file

    def write_to_zip(self, fname):
        print("Storing in zip file:", fname)
        with zipfile.ZipFile(fname, 'w') as zfile:
            for file in self.files.values():
                print(" - ", file.safe_fn())
                # writestr also handles bytes.
                zfile.writestr(file.path, file.data)

    def write_to_dir(self, fname):
        dpath = pathlib.Path(fname)
        if not dpath.exists() or not dpath.is_dir():
            print("Can't dump to nonexisting directory", dpath)
            return

        print("Extracting to directory:", dpath)
        for file in self.files.values():
            fn = dpath / file.safe_fn()
            ensure_dir(fn)
            print("  - ", fn)
            pathlib.Path(fn).write_bytes(file.data)


def simple_test():
    # figuring-out-testing, not proper testing
    import sys
    for fname in sys.argv[1:]:
        try:
            img = DiskImage.from_file(fname)
        except AssertionError as e:
            print("file was", fname)
            raise
        print(f"-- {fname} {img.imgtype}", img.detect_filesystem())
        if len(img.sectors) > 0:
            for track in range(TRACKS):
                for sector in range(1, SECTORS +1):
                    img.read_sector(track, sector)

if __name__ == "__main__":
    test()
