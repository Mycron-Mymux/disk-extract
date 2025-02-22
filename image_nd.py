#!/usr/bin/env python3
"""
TODO:
- check for more than one user (to be on the safe side).
- check for files from more than one user.
- export files.
"""

import argparse
import struct


def bit_set(val, bit_no):
    return ((1 << bit_no) & val) > 0


def bts_to_ptr(buf):
    return struct.unpack(">L", buf)[0]


def bts_to_word(buf):
    return struct.unpack(">H", buf)[0]
    

def bts_to_word2(buf):
    return struct.unpack(">L", buf)[0]
    
    
def decode_ptr(ptr):
    subindexed = bit_set(ptr, 31)
    indexed    = bit_set(ptr, 30)
    return (subindexed, indexed, ptr & 0x3fffffff)


def parse_date(word2):
    # 6 bits - year - 1950
    # 4 bits - month
    # 5 bits - day
    # 5 bits - hour
    # 6 bits - minute
    # 6 bits - second
    secs  =  word2         & 0x3f
    mins  = (word2 >>  6)  & 0x3f
    hour  = (word2 >> 12)  & 0x1f
    day   = (word2 >> 17)  & 0x1f
    month = (word2 >> 22)  & 0xf
    year  = (word2 >> 26)  & 0x3f
    return (year + 1950, month, day, hour, mins, secs)
    

def decode_obj_entry_info(word):
    u = bit_set(word, 15)
    w = bit_set(word, 14)
    r = bit_set(word, 13)
    m = bit_set(word, 12)
    return (u, w, r, m)


class ObjectEntry:
    def __init__(self, data, img):
        self.data = data
        self.img = img
        self.__decode()
        self.is_used = self.hu

    # http://heim.bitraf.no/tingo/files/nd/ND-60.052.04_NORD_File_System_April_1977_ocr.pdf
    # page 39
    def __decode(self):
        # entry info (first 2 bytes)
        # u - entry used
        # m - file modiefied (opened for write), or magnetic tape file
        # r - file reserved
        # w - currently opened for write
        self.info = bts_to_word(self.data[:2])
        u, w, r, m = decode_obj_entry_info(self.info)
        self.hu, self.hw, self.hr, self.hm = u, w, r, m

        # TODO: stop decoding if self.hu is false.

        # 16 bytes object name
        # TODO: trim 0s from the end of the file.
        self.name = self.data[2:18].decode('ascii')

        # type - 4 chars
        self.otype = self.data[18:22].decode('ascii')

        # pointers to version
        self.ptr_next_ver = bts_to_word(self.data[22:24])
        self.ptr_prev_ver = bts_to_word(self.data[24:26])

        self.access_bits = bts_to_word(self.data[26:28])
        self.ftype =       bts_to_word(self.data[28:30])
        self.device_num =  bts_to_word(self.data[30:32])
        self.usr_idx_res = bts_to_word(self.data[32:34])
        self.obj_idx     = bts_to_word(self.data[34:36])
        self.cur_open    = bts_to_word(self.data[36:38])
        self.tot_open    = bts_to_word(self.data[38:40])
        self.date_create = bts_to_word2(self.data[40:44])   # 2 words
        self.date_last_rd = bts_to_word2(self.data[44:48])  # 2 words - last data opened for read
        self.date_last_wr = bts_to_word2(self.data[48:52])  # 2 words - last data opened for write
        self.pages_in_file = bts_to_word2(self.data[52:56])
        self.max_byte_pointer = bts_to_word2(self.data[56:60])
        self.file_pointer = bts_to_word2(self.data[60:64]) 

    def dump(self):
        print("--- object entry ", self.name)
        print(f" - {self.hu=} {self.hw=}, {self.hr=} {self.hm=}  {self.otype=}")
        print(f" - {self.ptr_next_ver=:#x} {self.ptr_prev_ver=:#x}")
        print(f" - {self.access_bits=:#x}, {self.ftype=:#x} {self.obj_idx=:#x}")
        print(f" - {self.date_last_rd=:#x} {parse_date(self.date_last_rd)}")
        print(f" - {self.date_last_wr=:#x} {parse_date(self.date_last_wr)}")
        print(f" - {self.pages_in_file=:#x}")
        print(f" - {self.max_byte_pointer=:#x}")
        print(f" - {self.file_pointer=:#x}")
        print(self.data)
        self.get_file()

    def get_file(self):
        # if not indexed, continuous file.
        # if indexed, defined by an 1K index block, which contains pointers to the 1K data page of the file
        subidx, idx, fptr = decode_ptr(self.file_pointer)
        pg = self.img.get_page(fptr)
        if idx:
            for i in range(self.pages_in_file):
                fpg = bts_to_word2(pg[i*4:(i+1)*4])
                # print(hex(fpg), self.img.get_page(fpg)[:32])
                if args.v:
                    print(f"{i:2} {fpg:#02x}", self.img.get_page(fpg))


class NDImage:
    PAGE_SIZE = 2048   # 1024 words of 16 bits
    PTR_SIZE  = 4      # 4 bytes
    
    def __init__(self, fname):
        self.fname = fname
        self.data = open(fname, 'rb').read()
        self._extract_hdr()

    def get_page(self, pno):
        return self.data[pno * self.PAGE_SIZE: (pno+1) * self.PAGE_SIZE]

    def _extract_hdr(self):
        # Strictly speaking, this is the master block.
        # The start of the master block can contain bootable code.
        # The last bit of it contains the directory entry for the floppy
        self.hdr = self.data[0x7e0:0x800]
        self.name = self.hdr[:16].decode('ascii')
        self.obj_file_ptr = bts_to_ptr(self.hdr[16:20])
        self.usr_file_ptr = bts_to_ptr(self.hdr[20:24])
        self.bit_file_ptr = bts_to_ptr(self.hdr[24:28])
        self.not_res_pgs  = bts_to_ptr(self.hdr[28:32])
        
    def print_hdr(self):
        # print('raw', self.hdr)
        print(f"{self.name}")
        for v in self.obj_file_ptr, self.usr_file_ptr, self.bit_file_ptr, self.not_res_pgs:
            print(f"{v:#10x}", decode_ptr(v))

    def _obj_file_pg(self, pg_no):
        print(f"--- decoding obj file entry from page {pg_no:#x}")
        page = self.get_page(pg_no)
        objs = []
        for i in range(32):
            obj = ObjectEntry(page[64 * i:64 * (i + 1)], self)
            if obj.is_used:
                obj.dump()
                objs.append(obj)
        
    def obj_file(self):
        subidx, idx, ptr = decode_ptr(self.obj_file_ptr)
        if subidx:
            print("CANNOT PARSE SUBIDX YET")
            return

        if idx:
            pg_idx = self.get_page(ptr)
            # print(pg_idx)
            # Theres up to 8 * 32 = 256 files per user on a disk
            # http://heim.bitraf.no/tingo/files/nd/ND-60.122.02_NORD_File_System_-_System_Documentation_January_1980_ocr.pdf
            # page 21
            for i in range(8):
                pg_no = bts_to_word2(pg_idx[i*4:(i+1)*4])
                if pg_no > 0:
                    self._obj_file_pg(pg_no)
        else:
            self._obj_file_pg(ptr)


ap = argparse.ArgumentParser()
ap.add_argument("-hex", action="store_true")
ap.add_argument("-t0raw", nargs=1)
ap.add_argument("fname", default="nd01.imd")
ap.add_argument("-v", action="store_true")
args = ap.parse_args()
print(args)

img = NDImage(args.fname)
img.print_hdr()
img.obj_file()

