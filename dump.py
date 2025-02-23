#!/usr/bin/env python

import argparse
import image_mycron
import image_tram
import image_nd


def main():
    parser = argparse.ArgumentParser(
        prog="Diskette Dumper",
        description="Displays info about a diskette image. Optionally extracts files and puts them in a zip file.",
        epilog="check this (TODO)")

    parser.add_argument('filename')
    parser.add_argument('-tm', action="store_true", help="Image type is Mycron diskette")
    parser.add_argument('-tt', action="store_true", help="Image type is Tram diskette")
    parser.add_argument('-tn', action="store_true", help="Image type is ND diskette")
    parser.add_argument('--zip', nargs=1, help="zip file to store extracted files in")
    parser.add_argument('--dir', nargs=1, help="directory to extract files into")
    parser.add_argument('-l', '--ls', action="store_true", help="List files in archive")
    args = parser.parse_args()

    disk = None
    if args.tm:
        disk = image_mycron.MycronDiskette(args.filename)
    if args.tt:
        disk = image_tram.TramDisk(args.filename)
    if args.tn:
        disk = image_nd.NDImage(args.filename)
        
    if args.zip:
        zip_fname = args.zip[0]
        arch = disk.get_archive()
        arch.write_to_zip(zip_fname)

    if args.dir:
        dpath = args.dir[0]
        arch = disk.get_archive()
        arch.write_to_dir(dpath)

    if args.ls:
        print(disk.get_metainf())


if __name__ == '__main__':
    main()

