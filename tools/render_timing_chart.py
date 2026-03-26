#!/usr/bin/env python3
"""Render suite timing windows as fixed-width ASCII schedule bars.

Input is JSON provided either through --input or stdin. The payload may be:

1. A list of timing objects:
   [
     {"name": "suite1", "returncode": 0, "start": 0.0, "end": 1.2},
     {"name": "suite2", "returncode": 0, "start": 0.2, "seconds": 5.7}
   ]

2. An object with a "results" key containing that same list:
   {"results": [...]}

Each timing object must include:
- name: display label
- returncode: integer status code for display
- either:
  - start and end
  - start and seconds

The rendered bar spans from the earliest start to the latest end across the
full collection. `[` is immediately before the first time bucket and `]` is
immediately after the last one.
"""

import argparse
import json
import sys


def load_timings(path):
    if path:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    else:
        payload = json.load(sys.stdin)

    if isinstance(payload, dict):
        payload = payload.get("results", payload.get("timings", payload))

    if not isinstance(payload, list):
        raise ValueError("Input JSON must be a list or an object with a 'results' key.")

    timings = []
    for item in payload:
        name = item.get("name", item.get("target"))
        if not name:
            raise ValueError("Each timing entry must define 'name' or 'target'.")
        if "returncode" not in item:
            raise ValueError(f"Timing entry '{name}' is missing 'returncode'.")
        if "start" not in item:
            raise ValueError(f"Timing entry '{name}' is missing 'start'.")

        start = float(item["start"])
        if "end" in item:
            end = float(item["end"])
        elif "seconds" in item:
            end = start + float(item["seconds"])
        else:
            raise ValueError(f"Timing entry '{name}' must define 'end' or 'seconds'.")

        if end < start:
            raise ValueError(f"Timing entry '{name}' has end < start.")

        timings.append(
            {
                "name": name,
                "returncode": int(item["returncode"]),
                "start": start,
                "end": end,
                "seconds": end - start,
            }
        )
    return timings


def render_bar(start, end, global_start, global_end, width, fill):
    if width <= 0:
        raise ValueError("Width must be greater than zero.")

    total = global_end - global_start
    if total <= 0:
        total = 1.0

    bar = [" "] * width
    for idx in range(width):
        cell_start = global_start + total * idx / width
        cell_end = global_start + total * (idx + 1) / width
        if start < cell_end and end > cell_start:
            bar[idx] = fill
    return "[" + "".join(bar) + "]"


def _status_text(item):
    """Return the fixed-width status token shown beside the suite name."""
    if "status" in item:
        return str(item["status"])
    return f"({item['returncode']})"


def _duration_text(item):
    """Return the duration column text.

    Most callers let the renderer build the standard `<seconds> seconds`
    string. Live progress views can pass `duration_text` explicitly when they
    want placeholder text while a suite is still pending.
    """
    if "duration_text" in item:
        return str(item["duration_text"])
    seconds = item.get("seconds", item["end"] - item["start"])
    return f"{seconds:.2f} seconds"


def render_lines(timings, width, fill, *, global_start=None, global_end=None):
    """Render one schedule line per timing entry.

    `global_start` and `global_end` normally come from the earliest start and
    latest end in the provided timing collection. Callers can override them to
    keep a live display on a stable time axis while work is still running.
    """
    if not timings:
        return []

    if global_start is None:
        global_start = min(item["start"] for item in timings)
    if global_end is None:
        global_end = max(item["end"] for item in timings)
    label_width = max(len(item["name"]) for item in timings)
    status_width = max(len(_status_text(item)) for item in timings)
    duration_width = max(len(_duration_text(item)) for item in timings)

    lines = []
    for item in timings:
        bar = render_bar(
            item["start"],
            item["end"],
            global_start,
            global_end,
            width,
            fill,
        )
        lines.append(
            f"{item['name'].ljust(label_width)} "
            f"{_status_text(item).rjust(status_width)} "
            f"{_duration_text(item).rjust(duration_width)} {bar}"
        )
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Render an ASCII chart for timing windows."
    )
    parser.add_argument(
        "--input",
        help="Path to a JSON file. If omitted, read JSON from stdin.",
    )
    parser.add_argument(
        "--width",
        type=int,
        required=True,
        help="Number of characters inside the [ ... ] schedule bar.",
    )
    parser.add_argument(
        "--fill",
        default=".",
        help="Single character used to mark active time buckets. [default: .]",
    )
    args = parser.parse_args(argv)

    if len(args.fill) != 1:
        raise ValueError("--fill must be exactly one character.")

    timings = load_timings(args.input)
    for line in render_lines(timings, args.width, args.fill):
        print(line)


if __name__ == "__main__":
    main()
