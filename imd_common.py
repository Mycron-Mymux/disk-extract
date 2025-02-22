#!/usr/bin/env python3

from collections import defaultdict
import imd


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


def get_tracks_skipping_dup_heads(im):
    """Yields tracks from the image, but skips head 1 if it's eaqual to head 0"""
    track_data = defaultdict(list)
    for track in im.tracks:
        track_data[track.cylinder].append(track)
    
    for tno, head_data in track_data.items():
        assert len(head_data) <= 2, f"  {len(head_data)}"
        assert head_data[0].head == 0
        if len(head_data) > 1:
            assert head_data[1].head == 1
        for hno, td in enumerate(head_data):
            if hno == 1 and same_data(head_data[0], td):
                continue
            yield (tno, hno, td)


def get_full_img_ss(im):
    img_data = b''
    for tno, no, tdata in get_tracks_skipping_dup_heads(im):
        for sec, sdr in enumerate(tdata.sector_data_records, start=1):
            data = sdr.data
            if len(data) == 1:
                data = data * tdata.sector_size
            img_data += data
    return img_data


def hexdump_data(data):
    print("     0  1  2  3  4  5  6  7   8  9  a  b  c  d  e  f    012345678 9abcdef")
    while len(data) > 0:
        cur = data[:16]
        buf = "   "
        buf2 = "  |"
        for i, c in enumerate(cur):
            buf += f" {c:02x}"
            c = chr(c)
            buf2 += c if c.isprintable() else '.'
            if i == 7:
                buf += ' '
                buf2 += ' '
        if len(cur) < 16:
            buf += "   " * (16 - len(cur))
        if len(cur) < 8:
            buf += " "
        print(buf, buf2)
        data = data[16:]
    
