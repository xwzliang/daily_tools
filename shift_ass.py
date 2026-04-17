#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path


def ass_time_to_cs(time_str: str) -> int:
    """
    Convert ASS time format H:MM:SS.cc to centiseconds.
    Example: 0:04:12.35 -> total centiseconds
    """
    h, m, s_cs = time_str.strip().split(":")
    s, cs = s_cs.split(".")
    return int(h) * 3600 * 100 + int(m) * 60 * 100 + int(s) * 100 + int(cs)


def cs_to_ass_time(total_cs: int) -> str:
    """
    Convert centiseconds back to ASS time format H:MM:SS.cc.
    Negative times are clamped to 0.
    """
    total_cs = max(0, total_cs)
    h = total_cs // (3600 * 100)
    rem = total_cs % (3600 * 100)
    m = rem // (60 * 100)
    rem %= 60 * 100
    s = rem // 100
    cs = rem % 100
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def split_line_ending(line: str) -> tuple[str, str]:
    """
    Split a line into (content_without_line_ending, original_line_ending).
    Preserves CRLF/LF/CR exactly, so we don't accidentally add blank lines.
    """
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n"):
        return line[:-1], "\n"
    if line.endswith("\r"):
        return line[:-1], "\r"
    return line, ""


def shift_ass_dialogue_line(
    line: str,
    cutoff_cs: int,
    shift_cs: int,
    mode: str = "start_after",
) -> str:
    """
    Shift ASS dialogue/event line timestamps.

    mode:
        - 'start_after': shift if start >= cutoff
        - 'end_after': shift if end >= cutoff
        - 'overlap_after': shift if any part is after cutoff
    """
    content, line_ending = split_line_ending(line)

    prefixes = ("Dialogue:", "Comment:")
    stripped = content.lstrip()

    if not stripped.startswith(prefixes):
        return line

    # ASS event format:
    # Dialogue: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
    # Split only first 9 commas after "Dialogue:" or "Comment:"
    try:
        prefix, rest = content.split(":", 1)
        fields = rest.split(",", 9)
        if len(fields) < 10:
            return line

        start_str = fields[1]
        end_str = fields[2]

        start_cs = ass_time_to_cs(start_str)
        end_cs = ass_time_to_cs(end_str)

        should_shift = False
        if mode == "start_after":
            should_shift = start_cs >= cutoff_cs
        elif mode == "end_after":
            should_shift = end_cs >= cutoff_cs
        elif mode == "overlap_after":
            should_shift = end_cs >= cutoff_cs
        else:
            raise ValueError(f"Unsupported mode: {mode}")

        if not should_shift:
            return line

        new_start = max(0, start_cs + shift_cs)
        new_end = max(0, end_cs + shift_cs)

        # Safety: ensure end is not before start
        if new_end < new_start:
            new_end = new_start

        fields[1] = cs_to_ass_time(new_start)
        fields[2] = cs_to_ass_time(new_end)

        return f"{prefix}:{','.join(fields)}{line_ending}"

    except Exception:
        # Leave malformed lines unchanged
        return line


def shift_ass_file(
    input_path: Path,
    output_path: Path,
    cutoff_time: str,
    shift_seconds: float,
    mode: str = "start_after",
) -> None:
    cutoff_cs = ass_time_to_cs(cutoff_time)
    shift_cs = int(round(shift_seconds * 100))

    with input_path.open("r", encoding="utf-8-sig", newline="") as f:
        lines = f.readlines()

    new_lines = [
        shift_ass_dialogue_line(line, cutoff_cs, shift_cs, mode=mode) for line in lines
    ]

    with output_path.open("w", encoding="utf-8", newline="") as f:
        f.writelines(new_lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Shift ASS subtitle timestamps after a cutoff time."
    )
    parser.add_argument("input", type=Path, help="Input .ass file")
    parser.add_argument("output", type=Path, help="Output .ass file")
    parser.add_argument(
        "--cutoff",
        required=True,
        help="Cutoff ASS time, e.g. 0:04:00.00",
    )
    parser.add_argument(
        "--shift",
        required=True,
        type=float,
        help="Shift in seconds, e.g. -10 or 10",
    )
    parser.add_argument(
        "--mode",
        choices=["start_after", "end_after", "overlap_after"],
        default="start_after",
        help="How to decide which subtitle lines to shift",
    )

    args = parser.parse_args()

    shift_ass_file(
        input_path=args.input,
        output_path=args.output,
        cutoff_time=args.cutoff,
        shift_seconds=args.shift,
        mode=args.mode,
    )


if __name__ == "__main__":
    # Example usage:
    # Move all subtitles whose start time is at or after 4:00 by 10 seconds earlier:
    # python shift_ass.py input.ass output.ass --cutoff 0:04:00.00 --shift -10
    #
    # Move them 10 seconds later:
    # python shift_ass.py input.ass output.ass --cutoff 0:04:00.00 --shift 10
    main()
