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
- dump.py      (inspecting and extracting disk images, read-only)
- mycronfs/    (the read/**write** library for Mycron PROG & DATA images:
                the inverse of the extractor - format/put/delete/defrag;
                see NOTES-mdtools.md in the project root for the plan
                and the open format questions marked CHECK in the code)
- mdisk.py     (mtools-like command line over mycronfs:
                format / blank / ls / info / cat / get / put / update / rm / defrag)
- tram_cat.py  (formatted 'cat' for TRAM editor files; read-only)
- dump_imd.py  (inspect data in IMD images)

The Mycron PROG/DATA **write** path deliberately lives in one library
(mycronfs), not scattered over the CLIs. The emulator's old `makedisk`
utility has been **removed** — the emulator repo now points here: this
`mdisk.py` CLI (+ mdisk `blank` for zero-filled "no disk" placeholders)
is the one tool for everything diskette-image related.

### dump.py

This is used to inspect a diskette image or copy data from it
- disk format is selected using `-t mycron`, `-t tram`, or `-t nd` (use -h for more info)
- '--dir' is used to extract to a directory
- '--zip' is used to extract files and store them in a zip file.
- '-l' list files / metadata about the floppy image

Warning: some tools used to store files 40+ years ago didn't correctly
interpret backspace characters, so you might find filenames with
backspaces in them. It is not necessarily a problem with the disk
image.

### mdisk.py / mycronfs (creating and editing Mycron diskettes)

The mdisk tool and library was developed using Qwen 3.8 flash next.  

```
mdisk.py format disk-00.img --type prog --label ASCII   # new empty program disk
mdisk.py put   disk-00.img FOO --file foo.bin --addr 0x3000
mdisk.py put   disk-00.img TWO --string code --addr 0x3000 --string2 data --addr2 0x4000
mdisk.py ls    disk-00.img
mdisk.py cat   disk-00.img FOO
mdisk.py update disk-00.img FOO --file new-contents.bin   # in place, same extent
mdisk.py rm    disk-00.img FOO
mdisk.py defrag disk-00.img
```

`update` replaces the content of an existing file **in place**: same
directory slot, same extent position, same pre-allocation — but it can
never grow an extent. To resize or reposition a file, use `rm` + `put`.

**PROG files are strange on purpose — know the semantics:** a program
file has **no byte-level length and no EOF marker**. What is on the
diskette is exactly `seg1sz` (+ `seg2sz`) sectors; the program itself
knows where it ends. Therefore `cat`/`get` on PROG **never trim at
0x00** (program binaries contain zeros!), and content is always the
full padded sector run. For a two-segment program, `get` writes
`<dest>.seg1.bin` + `<dest>.seg2.bin` so the split is never lost, and
`cat`/`get --segment 1|2` picks one segment; `ls`/`info` show both load
addresses and sector counts.

PROG files need a load address (`--addr`); a program with a second load
segment is stored with `--addr2` plus `--file2/--string2` (the segments
are stored back-to-back, and `L` loads each at its own address). 

DATA `put`/`--reserve` leaves room for data files to grow in the future.
Files are allocated on the diskette as contiguous sectors, or extents. 
The effect of this is that increasing the size of a file requires free 
sectors immediately after the file. This will fail if another file
is stored there. To handle this, the file will often be allocated
with more sectors than immediately needed.

Note: the following is a claim from the AI model. While it is true
that it uses a temp file, it may not use a safe temp name. Be aware.
   Images are always updated atomically (temp file + rename), which is what
   makes it safe against the emulator opening the image per-sector.
