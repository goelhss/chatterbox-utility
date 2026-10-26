"""Read-only inventory of audio and cache files for cleanup review."""

import argparse
from collections import defaultdict
from pathlib import Path


def size(path):
    try:
        count = path.stat().st_size
    except OSError:
        return "unknown size"
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if count < 1024 or unit == "TiB":
            return f"{count:.1f} {unit}"
        count /= 1024


def report(root):
    output = root / "output"
    if not output.is_dir():
        print(f"No output folder: {output}")
        return

    print("READ-ONLY CLEANUP REVIEW — nothing is deleted\n")
    mp3s = sorted(output.rglob("*.mp3"))
    print(f"MP3s under {output} ({len(mp3s)}):")
    for path in mp3s:
        print(f"  {size(path):>10}  {path}")

    exports = sorted(root.glob("*.mp3"))
    if exports:
        print(f"\nMP3 exports in {root} ({len(exports)}):")
        for path in exports:
            print(f"  {size(path):>10}  {path}")

    groups = defaultdict(list)
    for part in output.rglob("part-*.wav"):
        groups[part.parent].append(part)
    print(f"\nCached segment folders ({len(groups)}):")
    for folder, files in sorted(groups.items()):
        originals = folder / "original.txt"
        expected = None
        if originals.is_file():
            from narrate import chunks
            try:
                expected = len(chunks(originals.read_text(encoding="utf-8")))
            except (OSError, UnicodeError):
                pass
        total = sum(f.stat().st_size for f in files if f.is_file())
        finished = expected is not None and len(files) == expected
        mp3_ready = any(p.name != "encoded.tmp.mp3" for p in folder.glob("*.mp3"))
        if not finished:
            advice = "KEEP if you want to resume this conversion"
        elif not mp3_ready:
            advice = "KEEP: segments are ready but no final MP3 is here"
        else:
            advice = "Review after verifying the final MP3; deleting loses the segment cache"
        count = f"{len(files)}/{expected}" if expected is not None else f"{len(files)}/?"
        print(f"  {count} segments, {size_bytes(total):>10}  {folder}\n    {advice}")

    extras = sorted(p for p in output.rglob("*") if p.is_file()
                    and (p.name == "chapter.wav" or ".tmp" in p.name))
    print(f"\nAssembled WAV and temporary files ({len(extras)}):")
    for path in extras:
        print(f"  {size(path):>10}  {path}")
    print("\nReview these paths before removing anything. A running conversion may be writing files now.")


def size_bytes(count):
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if count < 1024 or unit == "TiB":
            return f"{count:.1f} {unit}"
        count /= 1024


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1],
                        help="Chatterbox installation root")
    args = parser.parse_args()
    report(args.root.expanduser().resolve())
