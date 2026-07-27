#!/usr/bin/env python
"""
Tool to cat formatted TRAM documents.

Documents are (mostly) in 7 bit ascii, but bit 8 is used to encode underlined characters.
"""

from rich.console import Console
import argparse
import pathlib

USE_RICH=True

console = Console()


def val2chr(val):
    c = chr(val & 0x7f)  # should be safe with 7-bit ascii
    return c


def richify_tram_string(tstr):
    ENC='latin1'
    buf = ''
    for cv in tstr:
        c = val2chr(cv)
        if cv > 0x7f:
            if USE_RICH:
                # buf += f"[bold]{c}[/bold]"
                buf += f"\x1b[4m{c}\x1b[0m"
            else:
                buf += c
        else:
            buf += c
    return buf

ap = argparse.ArgumentParser()
# ap.add_argument("-hex", action="store_true")
ap.add_argument("fname", nargs='?')
args = ap.parse_args()

fname = args.fname
data = pathlib.Path(fname).read_bytes()
lines = data.split(b"\n")
    
for line in lines:
    print(richify_tram_string(line))
