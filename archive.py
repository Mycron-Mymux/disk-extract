#!/usr/bin/env python


class File:
    def __init__(self, path, data, meta):
        self.path = path
        self.data = data
        self.meta = meta


class Archive:
    """Keeps a list of files extracted from a disk"""

    def __init__(self):
        self.files = dict()   # indexed by path

    def add_file(self, file):
        """ """
        if file.name in self.files:
            print(f"Path to file '{file.name}' added previously.")
        self.files[file.name] = file

