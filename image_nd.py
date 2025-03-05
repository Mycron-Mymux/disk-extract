#!/usr/bin/env python3
"""
Image support for Norsk Data (ND) formatted 8 inch floppies.

This has been tested with a set of images from single sided, double density floppies.


Based on documentation from: 
http://heim.bitraf.no/tingo/files/nd/ND-60.052.04_NORD_File_System_April_1977_ocr.pdf
http://heim.bitraf.no/tingo/files/nd/ND-60.122.02_NORD_File_System_-_System_Documentation_January_1980_ocr.pdf

NB:
- the offsets in the figures in the ND documents are probably octal * word_size (2 bytes)


TODO:
- check for more than one user (to be on the safe side).
- check for files from more than one user.
"""

import argparse
import struct
import imd_common
from image_common import Archive, File

verbose = False


def bit_set(val, bit_no):
    return ((1 << bit_no) & val) > 0


def bts_to_ptr(buf):
    return struct.unpack(">L", buf)[0]


def bts_to_word(buf):
    return struct.unpack(">H", buf)[0]
    

def bts_to_word2(buf):
    return struct.unpack(">L", buf)[0]


def bts_extract(data, start, end):
    """The start and end are word offsets, with 2 bytes per offset
    start = 0o12, end = 0o13 means two words
    """
    match end-start:
        case 0:
            return bts_to_word(data[start*2:(end+1)*2])
        case 1:
            return bts_to_word2(data[start*2:(end+1)*2])
        case _:
            raise f"Not supported yet: bts_extract(data, {start}, {end})"
            
    
def decode_ptr(ptr):
    subindexed = bit_set(ptr, 31)
    indexed    = bit_set(ptr, 30)
    return (subindexed, indexed, ptr & 0x3fffffff)


def decode_name(raw_str):
    """returns a string that does not include the ending ' and 0s"""
    s = raw_str.decode('ascii').strip()
    s1 = s.split("'")[0]
    return s1
    

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


def decode_user_entry_info(word):
    u = bit_set(word, 15)
    f = bit_set(word,  8)
    return (u, f, word & 0xf)


class Entry:
    def __init__(self, data, img):
        self.data = data
        self.img = img
        self._decode()
        self.is_used = self.hu

    def dump(self):
        print(self.dump_str())

    def _get_words(self, start, end=None):
        """Converts the specified word offsets to a word or double word value"""
        if end is None:
            end = start
        return bts_extract(self.data, start, end)

    def _raw_words(self, start, end=None):
        if end is None:
            end = start
        return self.data[start*2:(end+1)*2]
        
class ObjectEntry(Entry):

    # http://heim.bitraf.no/tingo/files/nd/ND-60.052.04_NORD_File_System_April_1977_ocr.pdf
    # page 39
    # NB: offsets in the documentation are in octal form!
    def _decode(self):
        # entry info (first 2 bytes)
        # u - entry used
        # m - file modiefied (opened for write), or magnetic tape file
        # r - file reserved
        # w - currently opened for write
        self.info = self._get_words(0)
        self.hu, self.hw, self.hr, self.hm = decode_obj_entry_info(self.info)

        # TODO: stop decoding if self.hu is false.

        # 16 bytes object name
        # TODO: trim 0s from the end of the file.
        self.name = decode_name(self._raw_words(0o1, 0o10))

        # type - 4 chars
        self.otype = decode_name(self._raw_words(0o11, 0o12))

        # pointers to version
        self.ptr_next_ver = self._get_words(0o13)
        self.ptr_prev_ver = self._get_words(0o14)

        self.access_bits = self._get_words(0o15)   # 3 fields (public, friend, owner), each field ix DCAWR
        self.access_owner = self.access_bits & 0x1f
        self.access_friend = (self.access_bits >> 5) & 0x1f
        self.access_public = (self.access_bits >> 10) & 0x1f
        self.ftype       = self._get_words(0o16)
        self.device_num  = self._get_words(0o17)
        self.usr_idx_res = self._get_words(0o20)  
        self.obj_idx     = self._get_words(0o21)  
        self.cur_open    = self._get_words(0o22)  
        self.tot_open    = self._get_words(0o23)  
        self.date_create = self._get_words(0o24, 0o25) 
        self.date_last_rd = self._get_words(0o26, 0o27) # last data opened for read
        self.date_last_wr = self._get_words(0o30, 0o31) # last data opened for write
        self.pages_in_file = self._get_words(0o32, 0o33) # bts_to_word2(self.data[52:56])
        self.max_byte_pointer = self._get_words(0o34, 0o35) # bts_to_word2(self.data[56:60])
        self.file_pointer = self._get_words(0o36, 0o37) # bts_to_word2(self.data[60:64]) 

    def dump_str(self):
        s = "\n".join([
            f"--- object entry {self.name}",
            f" - {self.hu=} {self.hw=}, {self.hr=} {self.hm=}  {self.otype=}",
            f" - {self.ptr_next_ver=:#x} {self.ptr_prev_ver=:#x}",
            f" - {self.access_bits=:#x} : {self.access_public=:#x}, {self.access_friend=:#x}, {self.access_owner=:#x}",
            f" - {self.ftype=:#x} {self.obj_idx=:#x}",
            f" - {self.date_create=:#x} {parse_date(self.date_create)}", 
            f" - {self.date_last_rd=:#x} {parse_date(self.date_last_rd)}",
            f" - {self.date_last_wr=:#x} {parse_date(self.date_last_wr)}",
            f" - {self.pages_in_file=:#x}",
            f" - {self.max_byte_pointer=:#x}  bytes in pages={self.pages_in_file * NDImage.PAGE_SIZE:#x}",
            f" - {self.file_pointer=:#x}",
        ])
        # print(self.data)
        s += self.get_file_info()
        return s

    def get_file_info(self):
        # if not indexed, continuous file.
        # if indexed, defined by an 1K index block, which contains pointers to the 1K data page of the file
        subidx, idx, fptr = decode_ptr(self.file_pointer)
        pg = self.img.get_page(fptr)
        s = ""
        if idx:
            for i in range(self.pages_in_file):
                fpg = bts_to_word2(pg[i*4:(i+1)*4])
                # print(hex(fpg), self.img.get_page(fpg)[:32])
                if verbose:
                    # print(f"{i:2} {fpg:#02x}", self.img.get_page(fpg))
                    s += f"{i:2} {fpg:#02x} {self.img.get_page(fpg)}\n"
        return s
    
    def get_file(self):
        # if not indexed, continuous file.
        # if indexed, defined by an 1K index block, which contains pointers to the 1K data page of the file
        subidx, idx, fptr = decode_ptr(self.file_pointer)
        pg = self.img.get_page(fptr)
        data = b''
        if idx:
            for i in range(self.pages_in_file):
                fpg = bts_to_word2(pg[i*4:(i+1)*4])
                # print(hex(fpg), self.img.get_page(fpg)[:32])
                data += self.img.get_page(fpg)
                if verbose:
                    print(f"{i:2} {fpg:#02x}", self.img.get_page(fpg))
        else:
            # Continuous files on the disk
            print("NB: continuous file on disk", self.name, self.otype)
            for i in range(self.pages_in_file):
                data += self.img.get_page(fptr + i)
            
        print(self.name, self.otype, len(data), self.max_byte_pointer)
        if len(data) < self.max_byte_pointer:
            print("WARNING: length of data shouldn't be lower than the max_byte_pointer", subidx, idx, fptr)
            imd_common.hexdump_data(pg)
        if 1:
            return data[:self.max_byte_pointer+1]   # Assuming this is the actual end of the file
        return data


class UserEntry(Entry):
    def _decode(self):
        self.info = self._get_words(0, 0)
        self.hu, self.hf, self.enter_count  = decode_user_entry_info(self.info)
        # print(self.hu, self.hf, self.enter_count)
        self.user_name = decode_name(self.data[2:18])       # octal dword 1-10
        self.password = self.data[18:20]                    # octal dword 11
        self.date_created      = self._get_words(0o12, 0o13)
        self.date_last_entered = self._get_words(0o14, 0o15)
        self.no_pages_reserved = self._get_words(0o16, 0o17)
        self.no_pages_used     = self._get_words(0o20, 0o21)
        self.user_index        = self._get_words(0o22, 0o22)
        self.mail_flag         = self._get_words(0o23, 0o23)
        self.user_default_file_access = self._get_words(0o24, 0o24)
        # TODO:
        # friend table which should be from 0o30 to 0o37

    def dump_str(self):
        s = "\n".join([
            f"--- user entry: {self.user_name}", 
            f" - {self.hu=} {self.hf=}",
            f" - password            : {self.password}",
            f" - date created        : {parse_date(self.date_created)}  - {self.date_created:#x}",
            f" - date last entered   : {parse_date(self.date_last_entered)} - {self.date_last_entered:#x}",
            f" - no pages reserved   : {self.no_pages_reserved}",
            f" - no pages used       : {self.no_pages_used}",
            f" - user index          : {self.user_index}",
            f" - mail flag           : {self.mail_flag}",
            f" - default file access : {self.user_default_file_access:#x}"
        ])
        # imd_common.hexdump_data(self.data)
        return s


class NDImage:
    PAGE_SIZE = 2048   # 1024 words of 16 bits
    PTR_SIZE  = 4      # 4 bytes
    
    def __init__(self, fname):
        self.fname = fname
        # TODO: should perhaps check a bit more robustly for IMD files.
        self.data = open(fname, 'rb').read()
        if self.data[:4] == b'IMD ':
            im = imd_common.read_imd(fname)
            self.data = imd_common.get_full_img_ss(im)
        self._extract_hdr()
        self.usr_file()
        self.obj_file()

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
        
    def _obj_file_pg(self, pg_no):
        # print(f"--- decoding obj file entry from page {pg_no:#x}")
        page = self.get_page(pg_no)
        objs = []
        for i in range(32):
            obj = ObjectEntry(page[64 * i:64 * (i + 1)], self)
            if obj.is_used:
                # obj.dump()
                objs.append(obj)
        return objs
        
    def obj_file(self):
        self.objects = []
        subidx, idx, ptr = decode_ptr(self.obj_file_ptr)
        if subidx:
            print("CANNOT PARSE SUBIDX YET")
            return

        if idx:
            pg_idx = self.get_page(ptr)
            # imd_common.hexdump_data(pg_idx)
            # print(pg_idx)
            # Theres up to 8 * 32 = 256 files per user on a disk
            # http://heim.bitraf.no/tingo/files/nd/ND-60.122.02_NORD_File_System_-_System_Documentation_January_1980_ocr.pdf
            # page 21
            # NB: this assumes there is only one user! 
            for i in range(8):
                pg_no = bts_to_word2(pg_idx[i*4:(i+1)*4])
                if pg_no > 0:
                    self.objects.extend(self._obj_file_pg(pg_no))
        else:
            self.objects.extend(self._obj_file_pg(ptr))
        
            
    # ND-60.122.02 page 2-8
    # The user file contains information on all the users of the medium.
    # Each medium may have 256 users. Each user has a 32 word entry in the user file.
    # 
    # The user file is organized as an indexed file, i.e., the user file pointer in the
    # directory entry points to an inciex block. The index block contains up to 8 double
    # word pointers to user file pages. This structure is illustrated in Figure 2.10.
    def _usr_file_pg(self, pg_no):
        page = self.get_page(pg_no)
        objs = []
        for i in range(32):
            obj = UserEntry(page[64 * i:64 * (i + 1)], self)
            if obj.is_used:
                # obj.dump()
                objs.append(obj)
        return objs
    
    def usr_file(self):
        self.users = []
        subidx, idx, ptr = decode_ptr(self.usr_file_ptr)
        if subidx:
            print("CANNOT PARSE SUBIDX YET")
            return

        # print(f"User file {subidx} {idx} {ptr:#x}")
        if idx:
            pg_idx = self.get_page(ptr)
            for i in range(8):
                pg_no = bts_to_word2(pg_idx[i*4:(i+1)*4])
                if pg_no > 0:
                    # print(f" --- valid usr pg {pg_no:#x}")
                    self.users.extend(self._usr_file_pg(pg_no))
        else:
            self.users.extend(self._usr_file_pg(pg_no))

    def get_metainf(self):
        s = f"{self.fname}\n"
        s += f"# users {len(self.users)}  # objects {len(self.objects)}\n"
        s += "\n".join([o.dump_str() for o in self.users + self.objects])
        return s

    def get_archive(self):
        archive = Archive(self.fname)
        archive.add_file(File(".meta", self.get_metainf().encode("ascii")))
        for obj in self.objects:
            archive.add_file(File(f"{obj.name}.{obj.otype}", obj.get_file()))
        return archive
            

    def print_hdr(self):
        # print('raw', self.hdr)
        print(f"{self.name}")
        for v in self.obj_file_ptr, self.usr_file_ptr, self.bit_file_ptr, self.not_res_pgs:
            print(f"{v:#10x}", decode_ptr(v))

    def print_pages(self):
        """ND format diskettes ignore tracks/sectors etc and instead focus on the logical pages.
        This dumps data per page.
        """
        n_pages = len(self.data) // self.PAGE_SIZE
        for pno in range(n_pages):
            page = self.get_page(pno)
            print(f"--- {self.fname} page {pno:3} {pno:#3x}")
            imd_common.hexdump_data(page)
            

def main():
    global verbose
    ap = argparse.ArgumentParser()
    ap.add_argument("-hex", action="store_true")
    ap.add_argument("-toraw", nargs=1)
    ap.add_argument("fname", default="nd01.imd")
    ap.add_argument("-v", action="store_true")
    ap.add_argument("-pd", action="store_true", help="dump_pages")
    ap.add_argument("-ls", action="store_true", help="list users and objects")
    args = ap.parse_args()
    print(args)

    verbose = args.v

    img = NDImage(args.fname)
    if args.pd:
        img.print_pages()
        return
    if args.ls:
        print(img.get_metainf())
        
    # img.print_hdr()
    

if __name__ == '__main__':
    main()
