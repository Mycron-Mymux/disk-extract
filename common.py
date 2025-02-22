#!/usr/bin/env python

def hex_str(bseq):
    return ' '.join([f'{v:2x}' for v in bseq])


    # def hexdump_sector(self, track, sector):
    #     print(f"---- tr {track:2} s {sector:2} ---")
    #     s = self.get_sector_data(track, sector)
    #     imd_common.hexdump_data(s)

