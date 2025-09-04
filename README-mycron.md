Mycron diskettes
=================

The main target is diskettes for the [Mycro-1](https://en.wikipedia.org/wiki/MYCRO-1) computers
developed by [Mycron](https://en.wikipedia.org/wiki/Mycron).
These were 8-inch Single Side, Single Density diskettes.

These are formatted using 77 tracks (numbered 0-76) and 26 sectors
(numbered 1-26) with a sector size of 128 bytes. This gives us a raw
capacity of '77*26*128=256256' bytes.

The first track is usually used for file system metadata, so the
effective space for files is slightly smaller.

There are typically no suffixes to files, and no subdirectories.

Interestingly, the diskettes use what is, effectively, separate file
systems for program and data diskettes. You cannot store data files
(like text/source files) on program diskettes and vice versa.

Program diskettes
-----------
Programs can be executed using the 'L' command in the Mycrop monitor
PROM. The format of the command is:

* LNAME     (for diskette 0)
* Lx/NAME   (for diskette 0..7)

The number prefix is optional for drive 0. For the other drives,
it's necessary to load from the right drive.

The Mycrop monitor doesn't read any executable file format (like
ELF). Instead, metadata about segments of the program and where to load
it in memory are stored in the directory entry of the file system.

A program diskette is identified by the text string 'PROG' found at
the start of sector 00.07 (track 0, sector 7) followed by a volume
label.

There is an ERMAP in sector 00.05.

File entries are 16 bytes each, starting from sector 00.08, apparently
making room for entries up to 00.26.

Each file entry is made up of (bytes are numbered 1-16):

| byte numbers | content                              |
|--------------|--------------------------------------|
| 1-8          | program name (8 bytes, space padded) |
| 9            | first track number                   |
| 10           | first sector number                  |
| 11           | high order byte of load addr seg 1   |
| 12           | low order byte of load addr seg 1    |
| 13           | number of sectors seg 1              |
| 14           | high order byte of load addr seg 2   |
| 15           | low order byte of load addr seg 2    |
| 16           | number of sectors seg 2              |

Empty slots use spaces for all 8 bytes of the file name and zeros for the other values in the slot.

This makes room for 8 slots/files per sector of sectors 00.08 to
00.26, or 152 entries.

Data diskettes
-----------

The dim-1030 documentation (for the Mycron floppy controller) states
that the diskettes are formatted using the [IBM 3740
format](http://fileformats.archiveteam.org/wiki/IBM_3740_format).

The diskettes can be identified as follows:
- 'ERMAP' in sector 00.05
- 'VOL1' in the beginning of sector 00.07 followed by a volume ID
- Data file entries in sector 00.08-00.26

Each data file directory entry takes up one full sector. They are made up of
(bytes are numbered starting from 1 corresponding to page 6-37 in the
DIM-1030 documentation):

| byte num | content                                                        |
|----------|----------------------------------------------------------------|
| 1-4      | HDR1                                                           |
| 5        | blank or reserved (space in our disks)                         |
| 6-13     | Data set name (8 char file name), space padded                 |
| 14-24    | reserved or blank                                              |
| 25-27    | logical record length (max 128).                               |
| 28       | reserved or blank                                              |
| 29-33    | beginning of extent.                                           |
| 34       | reeserved or blank                                             |
| 35-39    | end of extent (last sector for data set)                       |
| 40       | reserved or blank                                              |
| 41       | bypass data set - if B, 3747 will ignore, if blank - processed |
| 42       | accessibility (must be blank)                                  |
| 43       | data set write protect (P if protected, else blank)            |
| 44       | reserved or blank                                              |
| 45       | multivolume indicator.                                         |
| 46-72    | reserved or blank                                              |
| 73       | verify mark: V = has been verified  (unused?)                  |
| 74       | end of data                                                    |
| 80       | reserved or blank                                              |
| 81-128   | The rest of the sector is blank/spaces                         |



- Note that values are ASCII strings, not raw bytes or words.
- An extent is the allocated space for a file. The way to interpret
  the numbers are "tt0ss", with tt the track number and ss the sector
  number.
- The multivolume indicator is blank (space) if this is not a
  multivolume. C if continued on another diskette, and L if this is
  the last diskette.
- End of data actually indicates the next *unused* sector of the
  dataset/extent. The last used sector of the file would be the sector
  before this.

Files occupy full sectors. A file that ends before the end of the last
sector in the dataset needs an EOF marker (like 0x00).

Empty slots are filled with a 0x44 followed by 0xff for the rest of
the sector.

Some tools (like the PL/Mycro compiler) require that extents are
pre-allocated for files.  It will give up writing to the file if it
runs out of extents for a given file.

