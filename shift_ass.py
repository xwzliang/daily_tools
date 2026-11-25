#!/usr/bin/env python
from __future__ import annotations

import argparse
import codecs
import io
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


DEFAULT_FIELDS = ("layer", "start", "end", "style", "name", "marginl", "marginr", "marginv", "effect", "text")


def shift_ass_dialogue_line(
    line: str,
    cutoff_cs: int,
    shift_cs: int,
    mode: str = "start_after",
    fields_order: tuple[str, ...] = DEFAULT_FIELDS,
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

    prefix, rest = content.split(":", 1)
    fields = rest.split(",", len(fields_order) - 1)
    if len(fields) != len(fields_order):
        return line

    try:
        start_index = fields_order.index("start")
        end_index = fields_order.index("end")
        start_cs = ass_time_to_cs(fields[start_index])
        end_cs = ass_time_to_cs(fields[end_index])
    except ValueError:
        return line

    if mode == "start_after":
        compare = start_cs
    elif mode in ("end_after", "overlap_after"):
        compare = end_cs
    else:
        raise ValueError(f"Unsupported mode: {mode}")
    if compare < cutoff_cs or shift_cs == 0:
        return line

    start = max(0, start_cs + shift_cs)
    end = max(start, end_cs + shift_cs)
    for index, value in [(start_index, start), (end_index, end)]:
        original = fields[index]
        fields[index] = original.replace(original.strip(), cs_to_ass_time(value), 1)
    return f"{prefix}:{','.join(fields)}{line_ending}"


def shift_ass_file(
    input_path: Path,
    output_path: Path,
    cutoff_time: str,
    shift_seconds: float,
    mode: str = "start_after",
) -> None:
    cutoff_cs = ass_time_to_cs(cutoff_time)
    shift_cs = int(round(shift_seconds * 100))

    data = input_path.read_bytes()
    bom, encoding = b"", "utf-8"
    for marker, codec in [(codecs.BOM_UTF8, "utf-8"), (codecs.BOM_UTF16_LE, "utf-16-le"),
                          (codecs.BOM_UTF16_BE, "utf-16-be")]:
        if data.startswith(marker):
            bom, encoding = marker, codec
            break
    text = data[len(bom):].decode(encoding)
    section = None
    fields = DEFAULT_FIELDS
    output = []
    for line in io.StringIO(text, newline=""):
        header = line.strip().lower()
        if header.startswith("[") and header.endswith("]"):
            section = header
            fields = DEFAULT_FIELDS
        elif section in (None, "[events]"):
            if header.startswith("format:"):
                fields = tuple(name.strip() for name in header.split(":", 1)[1].split(","))
            elif fields and fields[-1] == "text" and fields.count("start") == fields.count("end") == 1:
                line = shift_ass_dialogue_line(line, cutoff_cs, shift_cs, mode, fields)
        output.append(line)
    output_path.write_bytes(bom + "".join(output).encode(encoding))


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
