"""FFmpeg-backed implementation of the personal to_mp3 and to_mp4 commands."""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from publication import move_without_overwrite


def convert(source, destination, options):
    if os.path.lexists(destination):
        raise FileExistsError(f"Output already exists: {destination}")
    with tempfile.TemporaryDirectory(prefix=".media-convert-", dir=destination.parent) as tmp:
        staged = Path(tmp).resolve() / destination.name
        subprocess.run(["ffmpeg", "-nostdin", "-n", "-nostats", "-loglevel", "error",
                        "-i", source, *options, str(staged)], check=True)
        if not staged.is_file() or not staged.stat().st_size:
            raise OSError("FFmpeg produced no output.")
        move_without_overwrite(staged, destination)


def main(mode, args):
    parser = argparse.ArgumentParser(prog="to_" + mode)
    if mode == "mp3":
        parser.add_argument("input")
        parser.add_argument("output", type=Path, nargs="?")
        values = parser.parse_args(args)
        destination = values.output or Path(values.input).with_suffix(".mp3")
        jobs = [(values.input, destination)]
        options = ["-vn", "-acodec", "libmp3lame", "-ab", "192k", "-ar", "44100"]
    else:
        parser.add_argument("extension", help="source file extension in the current directory")
        extension = parser.parse_args(args).extension.lstrip(".")
        if not extension or "/" in extension:
            parser.error("expected a filename extension")
        sources = sorted(p for p in Path.cwd().iterdir()
                         if p.is_file() and p.suffix[1:].lower() == extension.lower())
        if not sources:
            parser.exit(1, f"No .{extension} files found.\n")
        jobs = [(str(source), source.with_suffix(".mp4")) for source in sources]
        options = ["-vcodec", "libx264", "-acodec", "aac"]

    failed = False
    for source, destination in jobs:
        try:
            convert(source, destination, options)
        except (OSError, subprocess.CalledProcessError) as error:
            print(f"{source}: {error}", file=sys.stderr)
            failed = True
        else:
            print(f"Ready: {destination}")
    return int(failed)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2:]))
