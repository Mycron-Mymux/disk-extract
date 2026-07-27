#!/usr/bin/env python

def hex_str(bseq):
    return ' '.join([f'{v:2x}' for v in bseq])

def hexdump_as_lines(data):
    """Yields lines of text that can be used to print a hexdump of the provided data"""
    yield "          0  1  2  3  4  5  6  7   8  9  a  b  c  d  e  f    012345678 9abcdef"
    offs = 0
    while len(data) > 0:
        cur = data[:16]
        buf = f"   {offs:4x} "
        offs += 16
        buf2 = "  |"
        for i, c in enumerate(cur):
            buf += f" {c:02x}"
            c = chr(c)
            buf2 += c if c.isprintable() else '.'
            if i == 7:
                buf += ' '
                buf2 += ' '
        if len(cur) < 16:
            buf += "   " * (16 - len(cur))
        if len(cur) < 8:
            buf += " "
        yield f"{buf} {buf2}"
        data = data[16:]


def hexdump_data(data):
    for line in hexdump_as_lines(data):
        print(line)

