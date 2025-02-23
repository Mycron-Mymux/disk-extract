TRAM diskettes
===============

TRAM was a text editor for the Mycron computers.

Instead of using Mycron data file systems, the diskettes used their
own file system. What is described under comes from reverse
engineering 2 diskettes with TRAM documents on them. This is probably
incomplete as we don't have a source that describes how the file
format and file system worked.

File system and file metadata
----------------

- The first sector of the diskette starts with the 5 character text
  string '*TRAM'
- File names start at the end of sector 3 (last 3 characters).
  - Each entry has 12 characters (space padded)
  - Unused entries start with 0xff
- Each file is stored as a set of (possibly) pages with each page
  taking one track of the drive.
- Starting at offset 0x1c in sector 00.02, document numbers stored for
  each of the tracks on the drive (starting with track 1).

Figuring out the tracks involved in a document involves scanning 76
bytes from offset 0x1c in sector 00.02 and noting all tracks with the
corresponding document numbers.  The first filename corresponds to
document number 0. Unused tracks are indicated with a document number
of 0xff.


File/text format
----------------

- Characters in the text file appear to be stored as 8-bit bytes,
  where the most significant bit indicates formatting and the lower 7
  bit represent 7-bit ASCII. At the moment, the assumption is that if
  the formatting bit is set, it indicates underline of that character.
- Each track is split into lines of 79 characters
  - The first byte of a line indicates the line number relative to this page.
    If a line number is >= 0xe5, it is unused.
  - The next 78 characters are the space padded text of that line (without a newline)


Note:
- There may be extra formatting information stored in the rows with line numbers >= 0xe5.
- Lines in a track come out of order and must be sorted before
  presenting the text.
- There may be multiple lines with the same line number. These may be
  old versions of that line that are not overwritten by 'blank' lines.
- The assumption is that the document's tracks on the disk are in the
  same order as the text in the document. This appears to be the case with
  the documents found so far.


The 'tram_cat.py' program prints the raw (extracted) TRAM document
with formattting.

