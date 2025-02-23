Norsk Data / ND diskette format
================================

This is based on documentation from: 
- [ND-60.052.04 Nord File System - 1977](http://heim.bitraf.no/tingo/files/nd/ND-60.052.04_NORD_File_System_April_1977_ocr.pdf)
- [ND-60.122.02 Nord File System - 1980](http://heim.bitraf.no/tingo/files/nd/ND-60.122.02_NORD_File_System_-_System_Documentation_January_1980_ocr.pdf)


The low level formatting of the 8-inch double density single sided
diskette is ignored in the documentation. It instead refers to 2 KiB
pages. Entries are typically in 2-byte words or 4-byte double words.

NB: The documentation often uses octal numbers to refer to offsets in
records.

Master block with directory
----------------------

The diskettes contain a master block with information about "Directory
Name" and pointers to the Object File, User File and Bit File.

- The User File contains information about each of the possible 256
  users in the file system.
- The Object File contains information about each of the possible 256
  files per user in the file system.
- The Bit file contains information about free/reserved pages on the
  storage medium.

Each pointer corresponds to page numbers on the storage device. The
two most significant bits indicate whether sub-indexing (most
significant bit) or indexing (next bit) is used:

- (0, 0) = no indexing is used
- (0, 1) = indexing is used
- (1, 0) = sub-indexing is used
- (1, 1) = error - should not be present

Basically, this corresponds to: 
- Contiguous files/meta data if no indexing is used


Object File
-----------

The object file pointer points to a page on the storage medium. 
This page is interpreted as follows:

- If no indexing is used, then the 32 first entries of the page are
  interpreted as object entries of 64 bytes each (filling one page) for
  the first user. If there are more users, it seems like the following
  pages are used to list files for each of the users.
  
- If indexing is used, the level 0 index page now contains 8 pointers
  to level 1 index pages per user. Each of the level 1 index pages
  contain 32 64-byte object entries corresponding to a file, giving
  users up to 256 files.
  
- If subindex is used, the storage system now adds another level of
  indexing.

### Object Entry

Each ObjectEntry (corresponding to a file) has a 64 byte record (32 words). 

The contents of this entry are documented in page 2-12 in the 1980
document, but a quick summary is that it contains:

- Flags about whether an entry is used
- Protection information
- Name of the object (file name) 
- Type of the object (interpreted as suffix in the extraction program)
- Pointers to previous and next versions
- Date created (with year starting at 1950)
- Last date opened for read
- Last date opened for write
- Number of pages in file
- Max byte pointer (last byte in file / corresponding to the file size)
- File pointer 

The file pointer uses a similar pointer scheme with sub-indexing and
indexing.

- If no indexing is flagged in the file pointer, then the pointer 
  points to the first page of a contiguous set of pages on the storage
  medium. 
- If indexing is flagged, the file pointer points to a level 1 index.
  The level 1 index has a sequence of 4 byte pointers to pages in the
  file.
- Sub-indexing indicates another level of indexes.


