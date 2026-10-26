import os,tempfile,unittest
from pathlib import Path
os.environ['CHATTERBOX_HOME']=tempfile.mkdtemp(prefix='chatterbox-tests-')
import narrate
from unittest.mock import patch
class ChaptersTest(unittest.TestCase):
    def test_saved_voice_reports_existing_recording_and_approval(self):
        import hashlib,json
        profile=narrate.ROOT/'recordings'/'Saved';profile.mkdir(parents=True)
        ref=profile/'reference.wav';ref.write_bytes(b'synthetic voice')
        path,message=narrate.saved_voice('Saved')
        self.assertEqual(path,str(ref));self.assertIn('No new recording',message)
        (profile/'approved.json').write_text(json.dumps({'reference_sha256':hashlib.sha256(ref.read_bytes()).hexdigest()}))
        self.assertIn('Approved for chapters',narrate.saved_voice('Saved')[1])
        ref.write_bytes(b'changed reference')
        self.assertNotIn('Approved for chapters',narrate.saved_voice('Saved')[1])
    def test_headings_and_opening_text(self):
        text='Opening\n\nChapter 1\nFirst story.\n\nCHAPTER TWO\nSecond story.'
        parts=narrate.split_chapters(text)
        self.assertEqual(len(parts),3)
        self.assertEqual(''.join(x[1] for x in parts),text)
    def test_no_headings_is_one_chapter(self):
        self.assertEqual(narrate.split_chapters('Story text.','Book'),[('Book','Story text.')])
    def test_resume_skips_finished_and_separates_voices(self):
        root=narrate.ROOT
        f=root/'input.txt';f.write_text('Chapter 1\nOne.\nChapter 2\nTwo.')
        for voice in ('A','B'):
            p=root/'recordings'/voice;p.mkdir(parents=True);(p/'reference.wav').write_bytes(voice.encode())
        book=narrate.load_book('story',[f])
        calls=[]
        def fake(voice,text,title,sample):
            calls.append(text);p=root/'output'/voice;p.mkdir(parents=True,exist_ok=True);p=p/(title+'.mp3');p.write_bytes(b'test');return str(p),'timing'
        with patch.object(narrate,'convert',fake):
            narrate.next_chapter(book,'A');narrate.next_chapter(book,'A')
            self.assertEqual(len(calls),2)
            self.assertIsNone(narrate.next_chapter(book,'A')[0])
            self.assertEqual(len(calls),2)
            narrate.next_chapter(book,'B');self.assertEqual(len(calls),3)
        self.assertEqual(narrate.load_book('story',[f]),book)
        self.assertIn('ready',narrate.book_status(book,'A'))
        self.assertIn('waiting',narrate.book_status(book,'B'))
if __name__=='__main__': unittest.main()
