#!/usr/bin/env python

import sys
import imd
from collections import defaultdict
import imd_common
import argparse


def dump_tracks(im, dump_hex=False, ss=True):
    if ss:
        im = imd_common.conv_ds_to_ss(im)
    for track in im.tracks:
        print(f"==== track/cyl-head: {track.cylinder}-{track.head} =====")
        print(track.sector_numbering_map)
        t = track
        print(f"TINF:   {t.mode=} {t.cylinder=} {t.head=} {t.sector_count=} {t.sector_size=} {t.sector_numbering_map=} {t.sector_cylinder_map=} {t.sector_head_map=} {len(t.to_bytes())=}")
        tno = track.cylinder
        for sec, sdr in imd_common.get_sectors_in_order(track):
            if dump_hex:
                print(f"  {tno:02}.{t.head}.{sec:02} {len(sdr.data):3}")
                imd_common.hexdump_data(sdr.data)
            else:
                print(f"  {tno:02}.{t.head}.{sec:02} {len(sdr.data):3}", sdr)


def store_tracks(im, out_fname, ss=True):
    if ss:
        im = imd_common.conv_ds_to_ss(im)
    with open(out_fname, 'wb') as out:
        nsects = 0
        print(f"Duming raw image to {out_fname}")
        for track in im.tracks:
            for sec, sdr in imd_common.get_sectors_in_order(track):
                data = sdr.data
                if len(data) == 1:
                    # Expand compressed sector
                    data = data * track.sector_size
                out.write(data)
                nsects += 1
        print(f" - done - wrote {nsects} sectors.")


def store_imd(im, out_fname, ss=True):
    if ss:
        im = imd_common.conv_ds_to_ss(im)
    with open(out_fname, 'wb') as out:
        print(f"Duming IMD to {out_fname}")
        out.write(im.to_bytes())
    

def check_for_errors(im):
    for track in im.tracks:
        for sec, sdr in imd_common.get_sectors_in_order(track):
            if sdr.record_type.has_error:   # or sdr.record_type.is_deleted:
                print(f"- Error in sector {track.cylinder:02}.{track.head}.{sec:02}")
        

if __name__ == "__main__":                
    ap = argparse.ArgumentParser()
    ap.add_argument("-hex",   action="store_true")
    ap.add_argument("-toraw", nargs=1)
    ap.add_argument("-toimd", nargs=1)
    ap.add_argument("fname",  default="nd01.imd")
    ap.add_argument("-ds",    action="store_true", help="Process as double sided")
    ap.add_argument("-hdr",   action="store_true", help="Print IMD header")
    ap.add_argument("-ce",    action="store_true", help="Prints sectors that have errors")
    args = ap.parse_args()
    print(args)

    fname = args.fname
    d = imd_common.read_imd(fname)
    print(f"Date {d.date} Comment {d.comment.strip()} Version {d.version} #tracks {len(d.tracks)}")

    if all(not x for x in [args.toraw, args.toimd, args.hdr, args.ce]):
        dump_tracks(d, dump_hex=args.hex, ss=not args.ds)
    else:
        if args.toraw is not None:
            store_tracks(d, args.toraw[0], ss=not args.ds)
        if args.toimd is not None:
            store_imd(d, args.toimd[0], ss=not args.ds)
        if args.hdr:
            print("HDR from", args.fname)
            print(d.version)
            print(d.date)
            print(d.time)
            print(d.comment)
        if args.ce:
            print("Errors in", args.fname)
            check_for_errors(d)
        
        
    

