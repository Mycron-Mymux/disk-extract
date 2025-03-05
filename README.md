Tools for exploring and extracting data from floppy images
================================

The main goal is to be able to read diskette images from old 8-inch
floppies. We have used
[greaseweazle](https://github.com/keirf/greaseweazle) with an old
8-inch floppy drive and needed tools to inspect the images and extract
files.

Disclaimer: this is work in progress code, while I'm learning about
the diskette formats.  The code quality isn't quite there and requires
a bit of cleanup, especially where I explored or changed my mind about
how to do things.

Currently, there is support for some image formats that we have
encountered:

- [Mycron program diskettes](README-mycron.md)
- [Mycron data diskettes](README-mycron.md)
- [TRAM (text editor) diskettes for Mycron](README-tram.md)
- [ND (Norsk Data) diskettes](README-nd.md)

For CP/M formatted diskettes,
[cpmtools](https://github.com/lipro-cpm4l/cpmtools) works well.


The tools included here are:
- dump.py      (inspecting and extracting disk images)
- tram_cat.py  (formatted 'cat' for TRAM editor files)
- dump_imd.py  (inspect data in IMD images)

### dump.py

This is used to inspect a diskette image or copy data from it
- disk format is selected using '-tt', '-tn', or '-tm' (use -h for more info)
- '--dir' is used to extract to a directory
- '--zip' is used to extract files and store them in a zip file.
- '-l' list files / metadata about the floppy image

Warning: some tools used to store files 40+ years ago didn't correctly
interpret backspace characters, so you might find filenames with
backspaces in them. It is not necessarily a problem with the disk
image.