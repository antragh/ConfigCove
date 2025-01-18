#!/usr/bin/env python3
import os
import sys
import glob

# Define the tracked file path in the user's home directory
TRACKED_FILE = os.path.join(os.path.expanduser("~"), "tracked_files.txt")

def get_absolute_path(path):
    """
    Converts a file or directory path to an absolute path.
    """
    return os.path.abspath(os.path.expanduser(path))


def track_files_or_directories(paths):
    """
    Tracks multiple files, directories, or patterns by adding their absolute paths
    to the tracked file list if they are not already tracked. Keeps only unique entries.
    """
    # Ensure the directory for the tracked file exists
    os.makedirs(os.path.dirname(TRACKED_FILE), exist_ok=True)

    # Read existing tracked paths, ensuring uniqueness
    if os.path.exists(TRACKED_FILE):
        with open(TRACKED_FILE, "r") as f:
            tracked_entries = set(f.read().splitlines())
    else:
        tracked_entries = set()

    # Add new entries to the set
    for path in paths:
        abs_path = get_absolute_path(path)

        # Check for existence and expand patterns or directories
        if os.path.isfile(abs_path):
            # Add individual file
            tracked_entries.add(abs_path)
            print(f"Tracked file: {abs_path}")
        elif os.path.isdir(abs_path):
            # Add directory
            tracked_entries.add(abs_path + '/')
            print(f"Tracked directory: {abs_path}/")
        else:
            # Expand patterns and add matching files recursively
            matches = glob.glob(abs_path, recursive=True)
            if matches:
                for match in matches:
                    match_abs = get_absolute_path(match)
                    if os.path.isfile(match_abs):
                        tracked_entries.add(match_abs)
                        print(f"Tracked file (from pattern): {match_abs}")
            else:
                print(f"Error: {path} does not exist or no matches found. Skipping.")

    # Rewrite the file with unique entries
    with open(TRACKED_FILE, "w") as f:
        f.write("\n".join(sorted(tracked_entries)))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <file_or_directory1> <file_or_pattern2> ...")
        sys.exit(1)

    inputs_to_track = sys.argv[1:]
    track_files_or_directories(inputs_to_track)

# Docker_configs/**/*.sh