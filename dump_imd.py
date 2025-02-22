#!/usr/bin/env python

import sys
import imd
from collections import defaultdict
import imd_common
import argparse


def dump_tracks(im, dump_hex=False):
    prev = None
    for tno, hno, tdata in imd_common.get_tracks_skipping_dup_heads(im):
        if tno != prev:
            print(f"==== track/cyl {tno} =====")
            prev = tno

        t = tdata
        print(f"TINF:   {t.mode=} {t.cylinder=} {t.head=} {t.sector_count=} {t.sector_size=} {t.sector_numbering_map=} {t.sector_cylinder_map=} {t.sector_head_map=} {len(t.to_bytes())=}")
        # NB:
        # - head 0 and head 1 are probably copies of the same data since it's a single head drive
        #   - could the head map in head 1 be reflecting this? 
        # - is_compressed in sdr probably means full sector with just a single value, so just repeat the given value for the full sector
        for sec, sdr in enumerate(tdata.sector_data_records, start=1):
            if dump_hex:
                print(f"  {tno:02}.{sec:02} {len(sdr.data):3}")
                imd_common.hexdump_data(sdr.data)
            else:
                print(f"  {tno:02}.{sec:02} {len(sdr.data):3}", sdr)


def store_tracks(im, out_fname):
    with open(out_fname, 'wb') as out:
        nsects = 0
        print(f"Duming t0 to {out_fname}")
        for tno, no, tdata in imd_common.get_tracks_skipping_dup_heads(im):
            for sec, sdr in enumerate(tdata.sector_data_records, start=1):
                data = sdr.data
                if len(data) == 1:
                    data = data * tdata.sector_size
                out.write(data)
                nsects += 1
        print(f" - done - wrote {nsects} sectors.")
        

ap = argparse.ArgumentParser()
ap.add_argument("-hex", action="store_true")
ap.add_argument("-t0raw", nargs=1)
ap.add_argument("fname", default="nd01.imd")
args = ap.parse_args()
print(args)

fname = args.fname
d = imd_common.read_imd(fname)
print(f"Date {d.date} Comment {d.comment.strip()} Version {d.version} #tracks {len(d.tracks)}")
if args.t0raw is not None:
    store_tracks(d, args.t0raw[0])
else:    
    dump_tracks(d, dump_hex=args.hex)
    

