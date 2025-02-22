#!/usr/bin/env python

# The first generations of Mycron computers used Single Side Single Density diskettes.
TRACKS=77        # tracks are numbered 0..76
SECTORS=26       # sectors are numbered 1..26
SECTOR_SIZE=128


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


