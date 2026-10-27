import contextlib
import importlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

class ConvertChaptersTest(unittest.TestCase):
    def setUp(self):
        self.converter = importlib.import_module('convert_chapters')
        temporary = tempfile.TemporaryDirectory(prefix='chatterbox-chapters-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.book = self.root / 'book.txt'
        self.book.write_text(''.join(f'Chapter {i}\nStory {i}.\n' for i in range(1, 5)),
                             encoding='utf-8')
        self.output = self.root / 'mp3'
        self.args = ['--text', str(self.book), '--output', str(self.output),
                     '--voice', 'TestVoice', '-n', '1']

    def run_command(self, *extra):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = self.converter.main(self.args + list(extra))
        return result, stdout.getvalue(), stderr.getvalue()

    @staticmethod
    def fake_conversion(source, destination, voice, log_dir):
        destination.write_bytes(b'mp3 data')
        return source.name, 'done'

    def test_selected_ranges_keep_book_numbers_and_build_ordered_playlist(self):
        with patch.object(self.converter, 'ROOT', self.root), \
             patch.object(self.converter, 'run_one', side_effect=self.fake_conversion):
            result, output, _ = self.run_command('-chapters', '1-2')
            self.assertEqual(result, 0)
            self.assertIn('chapter1.mp3', output)
            self.assertNotIn('chapter3.mp3', output)
            self.assertEqual(sorted(p.name for p in self.output.glob('*.mp3')),
                             ['chapter1.mp3', 'chapter2.mp3'])

            result, _, _ = self.run_command('--chapters', '3-4')
            self.assertEqual(result, 0)
            self.assertEqual((self.output / 'chapters.m3u').read_text().splitlines(),
                             ['#EXTM3U', 'chapter1.mp3', 'chapter2.mp3',
                              'chapter3.mp3', 'chapter4.mp3'])

    def test_existing_selected_mp3_stops_before_any_chapter_runs(self):
        self.output.mkdir()
        (self.output / 'chapter2.mp3').write_bytes(b'existing')
        with patch.object(self.converter, 'ROOT', self.root), \
             patch.object(self.converter, 'run_one', side_effect=self.fake_conversion) as run:
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as error:
                self.converter.main(self.args + ['-chapters', '1-2'])
            self.assertEqual(error.exception.code, 2)
            self.assertIn('chapter2.mp3', stderr.getvalue())
            self.assertIn('remove it manually', stderr.getvalue())
            run.assert_not_called()
        self.assertFalse((self.output / 'chapter1.mp3').exists())
        self.assertEqual((self.output / 'chapter2.mp3').read_bytes(), b'existing')

    def test_invalid_ranges_are_rejected(self):
        with patch.object(self.converter, 'ROOT', self.root):
            for value in ('0-2', '3-2', '1', '1-', '2-5'):
                with self.subTest(value=value), contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as error:
                        self.converter.main(self.args + ['-chapters', value])
                    self.assertEqual(error.exception.code, 2)
        self.assertFalse(self.output.exists())

    def test_late_existing_mp3_is_an_error(self):
        destination = self.root / 'chapter1.mp3'
        destination.write_bytes(b'existing')
        _, status = self.converter.run_one(self.root / 'part-0001.txt', destination,
                                           'TestVoice', self.root)
        self.assertTrue(status.startswith('FAILED'))
        self.assertEqual(destination.read_bytes(), b'existing')


if __name__ == '__main__':
    unittest.main()
