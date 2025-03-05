#!/usr/bin/env python3

import copy
from collections import defaultdict
import imd
from common import hexdump_data


def read_imd(fname):
    return imd.Disk.from_file(fname)


def same_data(head0, head1):
    if len(head0.sector_data_records) != len(head1.sector_data_records):
        print("lens different", len(head0.sector_data_records), (head1.sector_data_records))
        return False

    for s0, s1 in zip(head0.sector_data_records, head1.sector_data_records):
        if s0.data != s1.data:
            print("DATA DIFFERENT")
            return False

    return True


def conv_ds_to_ss(img):
    """Converts a DS Disk image to SS. 
    NB: this also verifies that head 1 (if present) is a copy of head 0.
    And that head 1 data (if present) is identical to head 0 data.
    This happens if an imd has been created from a single sided drive that was
    scanned a double sided drive.
    """
    # make sure all tracks are extracted and sorted by track/head
    tracks_h0 = {track.cylinder : track for track in img.tracks if track.head == 0}
    tracks_h1 = {track.cylinder : track for track in img.tracks if imdtrack.head == 1}
    assert len(tracks_h0) + len(tracks_h1) == len(img.tracks)

    assert all(tno in tracks_h0 for tno in tracks_h1.keys()), f"all head 1 should have a corresponding head 0 track"
    for tno, track1 in tracks_h1.items():
        track0 = tracks_h0[tno]
        assert same_data(track0, track1)

    ntracks = sorted(tracks_h0.values(), key = lambda track: track.cylinder)
    # A little naughty, but it _should_ work
    im2 = copy.deepcopy(img)
    im2.tracks = ntracks
    return im2


def get_sectors_in_order(track):
    """A track may have the sectors out of order
    This returns a list of sectors in the correct order
    Returns a list of (sector number, track) in sorted order.
    """
    sectors = sorted(zip(track.sector_numbering_map, track.sector_data_records))
    return sectors
        

def get_full_img_ss(im):
    s_im = conv_ds_to_ss(im)
    img_data = b''
    for track in s_im.tracks:
        for sec, sdr in get_sectors_in_order(track):
            data = sdr.data
            if len(data) == 1:
                data = data * tdata.sector_size
            img_data += data
    return img_data


