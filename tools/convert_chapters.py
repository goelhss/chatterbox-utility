"""Convert one text book into ordered chapter MP3s, with optional parallel jobs."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

from narrate import ROOT, slug, split_chapters


def output_target(raw):
    path = Path(raw).expanduser().resolve()
    if path.exists() and not path.is_dir():
        raise ValueError(f'Output path is not a folder: {path}')
    return path


def voice_name(override):
    if override:
        return slug(override)
    path = ROOT / 'default_voice.txt'
    if not path.is_file():
        raise ValueError(f'Create {path} with one saved voice name, or pass --voice')
    return slug(path.read_text(encoding='utf-8').strip())


def plan_book(book_file, output_dir):
    text = book_file.read_text(encoding='utf-8-sig')
    if not text.strip():
        raise ValueError(f'Book is empty: {book_file}')
    chapters = split_chapters(text, book_file.stem)
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]
    cache = ROOT / 'books' / f'parallel-{digest}'
    jobs = []
    for index, (title, chapter_text) in enumerate(chapters, 1):
        source = cache / f'part-{index:04d}.txt'
        destination = output_dir / f'chapter{index}.mp3'
        jobs.append((source, destination, chapter_text, title))
    return jobs


def select_chapters(jobs, chapter_range):
    if chapter_range is None:
        return jobs
    match = re.fullmatch(r'([1-9]\d*)-([1-9]\d*)', chapter_range)
    if not match:
        raise ValueError('Use a chapter range such as 1-4 or 5-8')
    first, last = map(int, match.groups())
    if first > last or last > len(jobs):
        raise ValueError(f'Chapter range {chapter_range} is outside 1-{len(jobs)}')
    return jobs[first - 1:last]


def run_one(source, destination, voice, log_dir):
    if destination.exists() or destination.is_symlink():
        return source.name, f'FAILED: output already exists: {destination}'
    log = log_dir / f'{source.stem}.log'
    command = [sys.executable, str(ROOT / 'tools' / 'narrate.py'),
               '--voice', voice, '--text', str(source), '--whole-chapter',
               '--output', str(destination)]
    with log.open('w', encoding='utf-8') as stream:
        result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, check=False)
    return source.name, ('done' if result.returncode == 0
                         else f'FAILED (exit {result.returncode}; see {log})')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--text', required=True, type=Path,
                        help='One whole-book UTF-8 text file')
    parser.add_argument('--output', required=True, type=Path,
                        help='Folder for chapter1.mp3, chapter2.mp3, etc.')
    parser.add_argument('--voice', help='Override default_voice.txt')
    parser.add_argument('-n', '--jobs', type=int, default=2,
                        help='Concurrent chapters; each loads its own model (default: 2)')
    parser.add_argument('-chapters', '--chapters', metavar='START-END',
                        help='Convert only this inclusive chapter range, e.g. 1-4')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    if args.jobs < 1:
        parser.error('--jobs must be at least 1')
    book_file = args.text.expanduser().resolve()
    if not book_file.is_file():
        parser.error(f'Book file does not exist: {book_file}')
    try:
        voice = voice_name(args.voice)
        output_dir = output_target(args.output)
        all_jobs = plan_book(book_file, output_dir)
        jobs = select_chapters(all_jobs, args.chapters)
    except (ValueError, OSError, UnicodeError) as exc:
        parser.error(str(exc))
    existing = [destination for _, destination, _, _ in jobs
                if destination.exists() or destination.is_symlink()]
    if existing:
        parser.error('Selected output MP3 already exists; remove it manually before rerunning:\n'
                     + '\n'.join(str(path) for path in existing))
    print(f'{len(jobs)} of {len(all_jobs)} chapter(s) selected; '
          f'up to {min(args.jobs, len(jobs))} at once')
    if len(all_jobs) == 1:
        print("Only one chapter was detected; check the book's headings before converting.")
    for _, destination, _, title in jobs:
        print(f'{title} -> {destination}')
    if args.dry_run:
        return 0
    for source, _, chapter_text, _ in jobs:
        source.parent.mkdir(parents=True, exist_ok=True)
        if source.exists() and source.read_text(encoding='utf-8') != chapter_text:
            parser.error(f'Cached chapter text differs: {source}')
        source.write_text(chapter_text, encoding='utf-8')
    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir = ROOT / 'logs' / f'chapters-{int(time.time())}-{uuid.uuid4().hex[:6]}'
    log_dir.mkdir(parents=True, exist_ok=False)
    failures = 0
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(run_one, source, destination, voice, log_dir)
                   for source, destination, _, _ in jobs]
        for future in as_completed(futures):
            name, status = future.result()
            print(f'{name}: {status}', flush=True)
            failures += status.startswith('FAILED')
    if not failures:
        playlist = output_dir / 'chapters.m3u'
        available = [destination for _, destination, _, _ in all_jobs
                     if destination.is_file() and destination.stat().st_size > 0]
        playlist.write_text('#EXTM3U\n' + ''.join(f'{path.name}\n' for path in available),
                            encoding='utf-8')
        print(f'Ordered playlist: {playlist}')
    print(f'MP3 folder: {output_dir}')
    print(f'Progress logs: {log_dir}')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
