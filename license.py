# Copyright (c) 2017 Kiel University and others.
# All rights reserved. This program and the accompanying materials
# are made available under the terms of the Eclipse Public License v1.0
# which accompanies this distribution, and is available at
# http://www.eclipse.org/legal/epl-v10.html

"""A program to create and update license headers for different kinds of file types."""

import argparse
from collections import deque
from datetime import datetime
import os
from pathlib import Path
import re
import subprocess
from subprocess import PIPE
from subprocess import SubprocessError
import sys
import tempfile


  #####
 #     #  ####  #    #  ####  #####   ##   #    # #####  ####
 #       #    # ##   # #        #    #  #  ##   #   #   #
 #       #    # # #  #  ####    #   #    # # #  #   #    ####
 #       #    # #  # #      #   #   ###### #  # #   #        #
 #     # #    # #   ## #    #   #   #    # #   ##   #   #    #
  #####   ####  #    #  ####    #   #    # #    #   #    ####

SUPPORTED_FILE_TYPES = [".elkg", ".elkt", ".java", ".xtend"]

LICENCE_HEADER = ["Copyright (c) {0} Kiel University and others.",
                  "All rights reserved. This program and the accompanying materials",
                  "are made available under the terms of the Eclipse Public License v1.0",
                  "which accompanies this distribution, and is available at",
                  "http://www.eclipse.org/legal/epl-v10.html"]
LICENCE_UPDATE = "Copyright (c) {0}, {1} Kiel University and others."
LICENCE_RE = re.compile(r"Copyright \(c\) ((?P<year_one>\d{4})"
                        r"(?P<year_two_full>, (?P<year_two>\d{4}))?) Kiel University and others\.")

# The number of lines we scan for the licence header until we determine that there is none
LINES_TO_SCAN = 5




 #     #
 #     # ##### # #      # ##### # ######  ####
 #     #   #   # #      #   #   # #      #
 #     #   #   # #      #   #   # #####   ####
 #     #   #   # #      #   #   # #           #
 #     #   #   # #      #   #   # #      #    #
  #####    #   # ###### #   #   # ######  ####

def parse_command_line():
    """Sets up and invokes the command line parser and returns the command line arguments."""

    parser = argparse.ArgumentParser(
        description="Ensures that valid license headers are present. "
                    "Select files the tool should look at "
                    "and optionally select to update existing license headers "
                    "to include the current year.")

    # Mode of operation
    parser.add_argument(
        "-u",
        "--update",
        help="also update existing license headers to include the current year",
        action="store_true")

    # File selection
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-a",
        "--all",
        help="select all files in the directory tree (Default)",
        action="store_true")
    group.add_argument(
        "--file",
        help="selects the specified files",
        nargs='+')
    group.add_argument(
        "--staged",
        help="select files staged for commit",
        action="store_true")
    group.add_argument(
        "--commit",
        help="selects the files changed in the commit with the given hash")

    # Miscellaneous things
    parser.add_argument(
        "-n",
        "--dry-run",
        help="don't actually change anything, just show what would be done",
        action="store_true")
    parser.add_argument(
        "-v",
        "--verbose",
        help="generate more output",
        action="store_true")

    return parser.parse_args()


def current_year_as_string():
    """The current year as a string. Probably not even necessary if I wasn't a Python n00b.
       Note to future self: don't be too hard on your past self, mate..."""

    return str(datetime.now().year)




 #######                     #####
 #       # #      ######    #     # ###### #      ######  ####  ##### #  ####  #    #
 #       # #      #         #       #      #      #      #    #   #   # #    # ##   #
 #####   # #      #####      #####  #####  #      #####  #        #   # #    # # #  #
 #       # #      #               # #      #      #      #        #   # #    # #  # #
 #       # #      #         #     # #      #      #      #    #   #   # #    # #   ##
 #       # ###### ######     #####  ###### ###### ######  ####    #   #  ####  #    #

def select_all_files(root_dir):
    """Selects all files in the directory tree rooted in the given directory.
       Returns a list of Path objects."""

    # What will become our result
    files = []

    # Do a BFS on the directory tree
    folder_queue = deque([Path(root_dir)])
    while folder_queue:
        folder = folder_queue.popleft()

        for item in folder.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                folder_queue.append(item)
            elif item.is_file():
                if item.suffix in SUPPORTED_FILE_TYPES:
                    files.append(item)

    return files


def select_specific_files(file_paths, include_folders, error_on_invalid, verbose):
    """Selects the files specified in the given list.
       If a file name refers to a folder, all files under that folder are added
       if include_folders is set to True.
       If a file could not be found and error_on_invalid is True,
       an error is produced and the script is killed. Violently.
       Otherwise, returns a list of Path objects."""

    # What will become our result
    files = []

    for file_path in file_paths:
        file = Path(file_path)

        # If the file is a file, great. If it's a folder, call select_all_files.
        # If it's nothing, terminate with an error
        if file.is_file() and file.suffix in SUPPORTED_FILE_TYPES:
            files.append(file)
        elif file.is_dir() and include_folders:
            files.extend(select_all_files(file))
        else:
            if error_on_invalid:
                sys.exit("Not a valid file or directory: " + str(file))
            elif verbose:
                print("Unable to find " + str(file))

    return files


def select_commit(commit_id, verbose):
    """Selects files based on information from git.
       If commit_id is None, the currently staged files are added, if existing.
       Otherwise, the files affected by the commit with the given ID are added, if existing.
       If verbose is True, information about files we couldn't find are printed."""

    command_line = ["git", ]

    if commit_id is None:
        command_line.extend(["diff", "--name-only", "--staged"])
    else:
        command_line.extend(["diff-tree", "--no-commit-id", "--name-only", "-r", commit_id])

    try:
        git = subprocess.run(command_line,
                             encoding="utf8",
                             check=True,
                             stdin=PIPE, stdout=PIPE, stderr=PIPE)

        file_list = []
        for output_line in git.stdout.split("\n"):
            if output_line:
                file_list.append(output_line)

        return select_specific_files(file_list, False, False, verbose)

    except SubprocessError:
        sys.exit("Git not found or exited with an error. Command-line: " + str(command_line))


def select_files(args):
    """Selects files based on the command line arguments.
       Returns a list of Path objects."""

    if args.file != None:
        return select_specific_files(args.file, True, True, args.verbose)
    elif args.staged:
        return select_commit(None, args.verbose)
    elif args.commit:
        return select_commit(args.commit, args.verbose)

    return select_all_files(".")




 #######                    #
 #       # #    # #####     #       #  ####  ###### #    #  ####  ######
 #       # ##   # #    #    #       # #    # #      ##   # #    # #
 #####   # # #  # #    #    #       # #      #####  # #  # #      #####
 #       # #  # # #    #    #       # #      #      #  # # #      #
 #       # #   ## #    #    #       # #    # #      #   ## #    # #
 #       # #    # #####     ####### #  ####  ###### #    #  ####  ######

def has_licence_header(file):
    """Check if the given file already has a licence header."""

    try:
        with file.open("r", encoding="utf8") as in_file:
            for _ in range(LINES_TO_SCAN):
                # Read next line, if any
                line = in_file.readline()
                if not line:
                    break

                # Check if we can find a file header
                if LICENCE_RE.search(line):
                    return True
    except IOError:
        sys.exit("Could not open file: " + str(file))

    return False


def needs_licence_header_update(file):
    """Check if the given file's licence header needs an update regarding the year.
       This function assumes that has_licence_header(file) would return True."""

    current_year = current_year_as_string()

    try:
        with file.open("r", encoding="utf8") as in_file:
            for _ in range(LINES_TO_SCAN):
                # Read next line
                line = in_file.readline()

                # Check if we can find a file header
                match = LICENCE_RE.search(line)
                if match:
                    if match.group("year_two"):
                        # There is a second year; update needed if it doesn't match the current year
                        return match.group("year_two") != current_year

                    # Update needed if the first year doesn't match the current year
                    return match.group("year_one") != str(datetime.now().year)

    except IOError:
        sys.exit("Could not open file: " + str(file))

    # This line should never be reached
    return False




  #####                                       #
 #     # #####  ######   ##   ##### ######    #       #  ####  ###### #    #  ####  ######
 #       #    # #       #  #    #   #         #       # #    # #      ##   # #    # #
 #       #    # #####  #    #   #   #####     #       # #      #####  # #  # #      #####
 #       #####  #      ######   #   #         #       # #      #      #  # # #      #
 #     # #   #  #      #    #   #   #         #       # #    # #      #   ## #    # #
  #####  #    # ###### #    #   #   ######    ####### #  ####  ###### #    #  ####  ######

def licence_text_for_extension(extension):
    """Creates a string with the licence text suitable for files with the given extension."""

    licence = ""

    if extension == ".elkg":
        # XML Syntax
        licence = "<!-- " + "\n     ".join(LICENCE_HEADER) + "\n-->\n"
    else:
        # Java Syntax
        licence = "/* " + "\n * ".join(LICENCE_HEADER) + "\n */\n\n"

    return licence.format(current_year_as_string())


def create_licence_header(file):
    """Creates a licence header for the given file."""

    try:
        # Generate a temporary file
        temp_file = tempfile.NamedTemporaryFile(dir=file.parent,
                                                mode="w",
                                                encoding="utf8",
                                                newline="\n",
                                                delete=False)

        with  temp_file, file.open("r") as old_file:
            # Write the licence header
            temp_file.write(licence_text_for_extension(file.suffix))

            # Write the original file's content
            for line in old_file:
                temp_file.write(line)

        # Replace the old file with the temp file
        os.replace(temp_file.name, file)

    except OSError:
        sys.exit("Unable to access or replace file: " + str(file))




 #     #                                      #
 #     # #####  #####    ##   ##### ######    #       #  ####  ###### #    #  ####  ######
 #     # #    # #    #  #  #    #   #         #       # #    # #      ##   # #    # #
 #     # #    # #    # #    #   #   #####     #       # #      #####  # #  # #      #####
 #     # #####  #    # ######   #   #         #       # #      #      #  # # #      #
 #     # #      #    # #    #   #   #         #       # #    # #      #   ## #    # #
  #####  #      #####  #    #   #   ######    ####### #  ####  ###### #    #  ####  ######

def update_licence_header(file):
    """Updates the licence header of the given file. If the file has only one year,
       a second is added. If it has two years, the second is updated."""

    try:
        # Generate a temporary file
        temp_file = tempfile.NamedTemporaryFile(dir=file.parent,
                                                mode="w",
                                                encoding="utf8",
                                                newline="\n",
                                                delete=False)

        with  temp_file, file.open("r") as old_file:
            # Iterate over the original file's lines and simply copy everything over,
            # except for the first licence header line we encounter
            found_line_to_update = False

            for line in old_file:
                # If we haven't found the line to update, look for it
                if not found_line_to_update:
                    match = LICENCE_RE.search(line)
                    if match:
                        new_line = LICENCE_RE.sub(
                            LICENCE_UPDATE.format(
                                match.group("year_one"),
                                current_year_as_string()),
                            line)
                        temp_file.write(new_line)
                        found_line_to_update = True
                    else:
                        temp_file.write(line)
                else:
                    temp_file.write(line)

        # Replace the old file with the temp file
        os.replace(temp_file.name, file)

    except OSError:
        sys.exit("Unable to update: " + str(file))




 #     #                     #####
 ##   ##   ##   # #    #    #     #  ####  #####  ######
 # # # #  #  #  # ##   #    #       #    # #    # #
 #  #  # #    # # # #  #    #       #    # #    # #####
 #     # ###### # #  # #    #       #    # #    # #
 #     # #    # # #   ##    #     # #    # #    # #
 #     # #    # # #    #     #####   ####  #####  ######

def traverse_files(files, also_update, dry_run, verbose):
    """Traverses the given files and creates a licence header if not already present.
       If also_update is true, an existing licence header is updated to include the current year.
       If dry_run is true, only information about what we would do is printed."""

    for file in files:
        if not has_licence_header(file):
            if dry_run:
                print("Would create licence header for", file)
            else:
                if verbose:
                    print("Creating licence header for", file)
                create_licence_header(file)
        elif also_update and needs_licence_header_update(file):
            if dry_run:
                print("Would update licence header for", file)
            else:
                if verbose:
                    print("Updating licence header for", file)
                update_licence_header(file)


ARGS = parse_command_line()
FILES = select_files(ARGS)

if FILES is None or not FILES:
    if args.verbose:
        print("No files found.")
else:
    traverse_files(FILES, ARGS.update, ARGS.dry_run, ARGS.verbose)
