#!/usr/bin/env python3
"""mdisk - mtools-like commands for Mycron PROG/DATA raw diskette images.

This is the thin command layer over the mycronfs library (a single
dispatcher with mdir/mcopy/mdel/mformat-style subcommands; add tiny
wrapper scripts if you want literal `mdir`/`mcopy`/... commands).

Examples:
    mdisk.py format empty-disk.img --type prog --label ASCII
    mdisk.py format empty-disk.img --type data --label IBMASC000001
    mdisk.py blank disk-03.img            # zero-filled 'no disk' placeholder
    mdisk.py ls empty-disk.img
    mdisk.py put empty-disk.img HELLO --string 'hello world'
    mdisk.py update empty-disk.img HELLO --string 'replaced, in place'
    mdisk.py put prog-disk.img FOO --addr 0x3000 --file foo.bin
    mdisk.py put prog-disk.img TWO --addr 0x3000 --string code --addr2 0x4000 --string2 data
    mdisk.py cat empty-disk.img HELLO
    mdisk.py get prog-disk.img FOO foo.bin
    mdisk.py rm empty-disk.img HELLO
    mdisk.py defrag empty-disk.img
    mdisk.py info empty-disk.img
"""
import argparse
import pathlib
import sys

import mycronfs
from mycronfs import ProgFS, DataFS
from mycronfs.data import trim_eof


def load(fs_type):
    fs_map = {PROG: ProgFS, DATA: DataFS}
    return fs_map[fs_type.upper()]


def cmd_format(args):
    path = pathlib.Path(args.image)
    if path.exists() and not args.force:
        sys.exit(f"refusing to overwrite existing {args.image} (use --force)")
    if args.type.lower() == "prog":
        fs = ProgFS.new(label=args.label)
    else:
        fs = DataFS.new(label=args.label or "IBMASC000000")
    fs.fname = str(path)
    fs.save()
    print(f"formatted {args.image} as empty {args.type.upper()} diskette")


def load_any(args):
    fname = args.image
    data = pathlib.Path(fname).read_bytes()
    fs = mycronfs.from_bytes(data)
    fs.fname = fname
    return fs


def cmd_blank(args):
    path = pathlib.Path(args.image)
    if path.exists() and not args.force:
        sys.exit(f"refusing to overwrite existing {args.image} (use --force)")
    path.write_bytes(bytes(b"\x00" * mycronfs.IMG_LEN))
    print(f"created blank (zero-filled, no filesystem) {args.image}")


def cmd_ls(args):
    fs = load_any(args)
    print(f"{fs.fname} [{fs.volume_label}] {len(fs.files())} files, "
          f"{len(fs.free_sectors())} free sectors")
    for e in fs.files():
        print(f"  {e}")


def cmd_info(args):
    fs = load_any(args)
    print(f"image:     {args.image}")
    print(f"type:      {fs.fs_type}")
    print(f"volume:    {fs.volume_label}")
    files = fs.files()
    print(f"files:     {len(files)}")
    for e in files:
        if args.name:
            if e.name.strip() == args.name.strip():
                data = fs.file_data(e)
                sys.stdout.buffer.write(f"--- {e.name.strip()} ({len(data)} bytes) ---\n".encode())
                sys.stdout.buffer.write(data)
                print("\n--- end ---")
            continue
    if not args.name:
        for e in files:
            print(f"  {e}")


def cmd_cat_or_get(args):
    fs = load_any(args)
    try:
        if isinstance(fs, ProgFS):
            # PROG files have NO byte-level length and NO EOF marker: the
            # stored bytes are the file (sector-padded). Never trim at 0x00
            # -- program binaries contain zeros by nature.
            g = fs.get_prog(args.name)
            segs = [g["seg1"]]
            if g["seg2"]:
                segs.append(g["seg2"])
        else:
            raw = fs.get(args.name)
            segs = [raw if getattr(args, "raw", False) else trim_eof(raw)]
    except OSError as e:
        sys.exit(str(e))

    if args.segment:
        if len(segs) < args.segment:
            sys.exit(f"{args.name.strip()} is not a {args.segment}-segment program")
        segs = [segs[args.segment - 1]]

    if args.command == "cat":
        if len(segs) > 1:
            print(f"note: {args.name.strip()} is a two-segment program "
                  f"({len(segs[0])}+{len(segs[1])} bytes); showing both "
                  f"concatenated, use --segment 1|2 for one",
                  file=sys.stderr)
        sys.stdout.buffer.write(b"".join(segs))
        sys.stdout.buffer.flush()
    else:  # get
        if len(segs) == 1:
            pathlib.Path(args.dest).write_bytes(segs[0])
            print(f"wrote {len(segs[0])} bytes to {args.dest}", file=sys.stderr)
        else:
            for i, seg in enumerate(segs, 1):
                fn = f"{args.dest}.seg{i}.bin"
                pathlib.Path(fn).write_bytes(seg)
                print(f"wrote {len(seg)} bytes to {fn}", file=sys.stderr)


def cmd_put(args):
    fs = load_any(args)
    if args.file:
        data = pathlib.Path(args.file).read_bytes()
    elif args.string is not None:
        data = args.string.encode("ascii")
    else:
        data = sys.stdin.buffer.read()
    if args.command == "update":
        # in-place content replacement: keeps slot, extent position and
        # pre-allocation; only works while the content fits the extent
        entry = fs.update(args.name, data)
    elif isinstance(fs, ProgFS):
        if args.addr is None:
            sys.exit("prog diskettes need --addr (segment 1 load address)")
        seg2 = b""
        if args.file2:
            seg2 = pathlib.Path(args.file2).read_bytes()
        elif args.string2 is not None:
            seg2 = args.string2.encode("ascii")
        entry = fs.put_prog(args.name, data, int(args.addr, 0),
                            seg2=seg2,
                            addr2=(int(args.addr2, 0) if args.addr2 else None),
                            reserve=args.reserve or 0)
    else:
        entry = fs.put(args.name, data, reserve=args.reserve or 0)
    fs.save()
    print(f"{args.command}d {entry.name.strip()} "
          f"({len(data)} bytes -> {entry.nsec} sectors)", file=sys.stderr)


def cmd_rm(args):
    fs = load_any(args)
    e = fs.delete(args.name)
    fs.save()
    print(f"deleted {e.name.strip()}", file=sys.stderr)


def cmd_defrag(args):
    fs = load_any(args)
    moved = fs.compact()
    fs.save()
    print(f"defragmented {args.image}: {len(moved)} files moved", file=sys.stderr)
    for name in moved:
        print(f"  moved {name.strip()}", file=sys.stderr)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mdisk", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("format", help="create a new empty PROG/DATA image")
    p.add_argument("image")
    p.add_argument("--type", required=True, choices=["prog", "data"])
    p.add_argument("--label", default="")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_format)

    p = sub.add_parser("blank", help="write a zero-filled 256256-byte image "
                                    "('no disk' placeholder for the emulator; "
                                    "NOT a Mycron filesystem)")
    p.add_argument("image")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_blank)

    for name, hlp in [("ls", "list files"), ("info", "volume + file info"),
                     ("cat", "print file content"), ("get", "extract file"),
                     ("put", "store a file"), ("update", "replace an existing file in place"),
                     ("rm", "delete a file"),
                     ("defrag", "compact/defragment extents")]:
        p = sub.add_parser(name, help=hlp)
        p.add_argument("image")
        if name in ("cat", "get", "put", "update", "rm"):
            p.add_argument("name")
        if name == "get":
            p.add_argument("dest")
        if name in ("put", "update"):
            p.add_argument("--file", help="read content from this host file")
            p.add_argument("--string", help="use this string as content")
            p.add_argument("--file2", help="PROG: read segment 2 content from this host file")
            p.add_argument("--string2", help="PROG: use this string as segment 2 content")
            p.add_argument("--addr", help="PROG: segment 1 load address (hex)")
            p.add_argument("--addr2", help="PROG: segment 2 load address (hex); implies two-segment program")
            p.add_argument("--reserve", type=int, default=0,
                           help="extra sectors to pre-allocate for the extent")
        if name == "cat":
            p.add_argument("--raw", action="store_true",
                           help="DATA: don't trim at the EOF marker (no effect on PROG)")
        if name in ("cat", "get"):
            p.add_argument("--segment", type=int, choices=[1, 2],
                           help="PROG: extract only this segment of a two-segment program")
        if name == "info":
            p.add_argument("name", nargs="?", default=None)
        p.set_defaults(func=cmd_ls if name == "ls" else
                       cmd_info if name == "info" else
                       cmd_cat_or_get if name in ("cat", "get") else
                       cmd_put if name in ("put", "update") else
                       cmd_rm if name == "rm" else cmd_defrag)

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
