"""Convert separate chapter text files concurrently into one output folder."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

from narrate import ROOT


def natural_key(path):
    return [int(part) if part.isdigit() else part.casefold()
            for part in re.split(r"(\d+)", path.name)]


def plan(input_dir, output_dir):
    sources = sorted(input_dir.glob("*.txt"), key=natural_key)
    if not sources:
        raise ValueError(f"No .txt files found in {input_dir}")
    names = [source.stem.casefold() for source in sources]
    if len(names) != len(set(names)):
        raise ValueError("Chapter filenames must have unique names (ignoring case).")
    return [(source, output_dir / f"{source.stem}.mp3") for source in sources]


def run_one(source, destination, voice, log_dir):
    if destination.exists():
        if destination.stat().st_size == 0:
            return source.name, "FAILED: empty output already exists"
        return source.name, "already exists; skipped (check this MP3 before relying on it)"
    log = log_dir / f"{source.stem}.log"
    command = [sys.executable, str(ROOT / "tools" / "narrate.py"),
               "--voice", voice, "--text", str(source), "--whole-chapter",
               "--output", str(destination)]
    with log.open("w", encoding="utf-8") as stream:
        result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, check=False)
    return source.name, ("done" if result.returncode == 0
                         else f"FAILED (exit {result.returncode}; see {log})")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--voice", required=True)
    parser.add_argument("--input-dir", type=Path, required=True,
                        help="Directory containing separate chapter .txt files")
    parser.add_argument("--output-dir", type=Path,
                        default=ROOT / "output" / "chapters")
    parser.add_argument("--jobs", type=int, default=2,
                        help="Concurrent chapters; each job loads its own model (default: 2)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.jobs < 1:
        parser.error("--jobs must be at least 1")
    input_dir = args.input_dir.expanduser().resolve()
    if not input_dir.is_dir():
        parser.error(f"Input directory does not exist: {input_dir}")
    output_dir = args.output_dir.expanduser().resolve()
    try:
        jobs = plan(input_dir, output_dir)
    except ValueError as exc:
        parser.error(str(exc))
    print(f"{len(jobs)} chapter(s); up to {min(args.jobs, len(jobs))} at once")
    for source, destination in jobs:
        print(f"{source.name} -> {destination}")
    if args.dry_run:
        return 0
    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir = ROOT / "logs" / f"chapters-{int(time.time())}-{uuid.uuid4().hex[:6]}"
    log_dir.mkdir(parents=True, exist_ok=False)
    failures = 0
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(run_one, source, destination, args.voice, log_dir)
                   for source, destination in jobs]
        for future in as_completed(futures):
            name, status = future.result()
            print(f"{name}: {status}", flush=True)
            failures += status.startswith("FAILED")
    print(f"MP3 folder: {output_dir}")
    print(f"Progress logs: {log_dir}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
