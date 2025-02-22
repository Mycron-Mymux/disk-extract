#!/usr/bin/env python

import zipfile
import pathlib

# The first generations of Mycron computers used Single Side Single Density diskettes.
TRACKS      =  77       # tracks are numbered 0..76
SECTORS     =  26       # sectors are numbered 1..26
SECTOR_SIZE = 128


def split_disk(data, tracks=TRACKS, sectors=SECTORS, sector_size=SECTOR_SIZE):
    """splits a disk into tracks and sectors
    returns a (track,sector) list
    """
    disk = {}
    assert len(data) % sector_size == 0
    assert len(data) == tracks * sectors * sector_size
    for track in range(tracks):
        # print(track, end=' ')
        for sector in range(sectors):
            # print(f's{sector}', end=',')
            offset = (track * sectors + sector ) * sector_size
            d = data[offset:offset + sector_size]
            assert len(d) == sector_size
            # looks like the mycron docs address sectors 1..26
            disk[(track, sector + 1)] = d
        # print()
    # print(track * sector * sector_size + sector_size)
    return disk


def split_sect(sect, psize):
    """Split a sector into equal size parts"""
    parts = []
    for offset in range(0, len(sect), psize):
        parts.append(sect[offset:offset+psize])
    return parts


def add_sects(track, sect, nsect, num_sectors=SECTORS):
    """add sectors to address starting at track and sect, returning track,sect or
    result"""
    # TODO: I'm just tired now, and I can't use modulo here - at least not without thinking.
    # The solution is probably to reduce sect with 1 to work with base 0 and then just add 1 to the result
    for _ in range(nsect):
        sect += 1
        if sect > num_sectors:
            sect = 1
            track += 1
    return track, sect


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


def ensure_dir(path):
    """Ensure that directory of path exists"""
    path = pathlib.Path(path)
    if not path.parent.exists():
        print(f"WARNING: creating subdir {path.parent} for {path}")
        path.parent.mkdir(exist_ok=True)

        
class Archive:
    """Keeps a list of files extracted from a disk"""
    def __init__(self, fname):
        self.fname = fname
        self.files = dict()   # indexed by path

    def add_file(self, file):
        """ """
        if file.path in self.files:
            print(f"Path to file '{file.path}' added previously.")
        self.files[file.path] = file

    def write_to_zip(self, fname):
        print("Storing in zip file:", fname)
        with zipfile.ZipFile(fname, 'w') as zfile:
            for file in self.files.values():
                print(" - ", file.path)
                # TODO: will this be correct for binary files?
                # Let file figure out if it's binary or text?
                zfile.writestr(file.path, file.data)
                
    def write_to_dir(self, fname):
        dpath = pathlib.Path(fname)
        if not dpath.exists() or not dpath.is_dir():
            print("Can't dump to nonexisting directory", dpath)
            return

        print("Extracting to directory:", dpath)
        for file in self.files.values():
            fn = dpath / file.path
            ensure_dir(fn)
            print("  - ", fn)
            with open(fn, 'wb') as f:
                f.write(file.data)
            
