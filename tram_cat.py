#!/usr/bin/env python
"""
Tool to cat formatted TRAM documents.

Documents are (mostly) in 7 bit ascii, but bit 8 is used to encode underlined characters.
"""

from rich.console import Console
import argparse

USE_RICH=False
USE_RICH=True

console = Console()


def val2chr(val):
    v = val & 0x7f
    c = bytes([v]).decode('latin1')
    c2 = chr(v)
    assert c == c2    # probably doesn't matter since we're decoding 7-bit ascii
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
with open(fname, 'rb') as f:
    data = f.read()
    lines = data.split(b"\n")
    
for line in lines:
    print(richify_tram_string(line))
