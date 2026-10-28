#!/usr/bin/env python

import argparse
import image_mycron
import image_tram
import image_nd

IMAGE_TYPES = {
    "mycron": image_mycron.MycronDiskette,
    "tram": image_tram.TramDisk,
    "nd": image_nd.NDImage,
}


def main():
    parser = argparse.ArgumentParser(
        prog="Diskette Dumper",
        description="Displays info about a diskette image. Optionally extracts files and puts them in a zip file.",
        epilog="check this (TODO)")

    parser.add_argument('filename')
    parser.add_argument('-t', '--type', required=True, choices=IMAGE_TYPES,
                       help = "Disk image filesystem type")
    parser.add_argument('--zip', metavar="FILE", help="zip file to store extracted files in")
    parser.add_argument('--dir', metavar="DIRECTORY", help="directory to extract files into")
    parser.add_argument('-l', '--ls', action="store_true", help="List files in archive")
    args = parser.parse_args()

    disk = None
    match args.type.lower():
        case 'mycron':
            disk = image_mycron.MycronDiskette(args.filename)
        case 'tram':
            disk = image_tram.TramDisk(args.filename)
        case 'nd':
            disk = image_nd.NDImage(args.filename)

    if args.zip or args.dir:
        arch = disk.get_archive()

        if args.zip:
            zip_fname = args.zip
            arch.write_to_zip(zip_fname)

        if args.dir:
            dpath = args.dir
            arch.write_to_dir(dpath)

    if args.ls:
        print(disk.get_metainf())


if __name__ == '__main__':
    main()
