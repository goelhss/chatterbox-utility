import os
from pathlib import Path
ROOT=Path(os.environ.get('CHATTERBOX_HOME', Path(__file__).resolve().parents[1])).expanduser().resolve()
os.umask(0o077)
for k,v in {'NUMBA_CACHE_DIR':str(ROOT/'tools/numba-cache'),'HF_HOME':str(ROOT/'models'),'HF_HUB_DISABLE_TELEMETRY':'1','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','GRADIO_ANALYTICS_ENABLED':'False','GRADIO_TEMP_DIR':str(ROOT/'tools/tmp'),'PYTORCH_ENABLE_MPS_FALLBACK':'1'}.items(): os.environ[k]=v
import argparse, hashlib, json, re, subprocess, time, sys, shutil
import numpy as np
import soundfile as sf
import imageio_ffmpeg

def slug(s):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,60}',s): raise ValueError('Use a short name containing letters, numbers, hyphens or underscores.')
    return s

def register(name, recording):
    profile=ROOT/'recordings'/slug(name); profile.mkdir(parents=True,exist_ok=True)
    target=profile/'reference.wav'
    if target.exists(): raise ValueError('Voice name already exists. Choose a new name to preserve its approved recording.')
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-i',str(recording),'-t','15','-ac','1','-ar','24000',str(target)],check=True)
    data,sr=sf.read(target)
    if len(data)/sr<6: target.unlink(); raise ValueError('Please record at least 10–15 seconds of clean speech.')
    return str(target)

def saved_voice(name):
    if not name:
        return None, 'Choose a saved voice, or add a new speaker below.'
    ref=ROOT/'recordings'/slug(name)/'reference.wav'
    if not ref.exists():
        return None, f'No saved recording found for {name}. Add a recording for this speaker.'
    approval=ref.parent/'approved.json'
    approved=False
    if approval.exists():
        try:
            approved=json.loads(approval.read_text()).get('reference_sha256')==hashlib.sha256(ref.read_bytes()).hexdigest()
        except (ValueError, OSError):
            pass
    message=f'{name}: saved recording found locally. '
    message += 'Approved for chapters. You can go straight to Book chapters; no new recording is needed.' if approved else 'Listen to a generated sample and approve it before converting chapters. No new recording is needed.'
    return str(ref), message + chr(10) + f'Reference recording: {ref}'

def chunks(text,limit=280):
    result=[]
    for paragraph in re.split(r'\n\s*\n',text):
        current=''
        for sentence in re.split(r'(?<=[.!?])\s+',paragraph.strip()):
            for word in sentence.split():
                if len(current)+len(word)+1>limit:
                    result.append(current); current=''
                current=(current+' '+word).strip()
        if current: result.append(current)
    return result

_model=None
def model():
    global _model
    if _model is None:
        import torch
        from chatterbox.tts_turbo import ChatterboxTurboTTS
        device = 'cuda' if torch.cuda.is_available() else ('mps' if torch.backends.mps.is_available() else 'cpu')
        _model=ChatterboxTurboTTS.from_pretrained(device=device)
    return _model

def assemble_segments(files,destination):
    # Stream one small block at a time rather than retaining a book in RAM.
    sr=sf.info(files[0]).samplerate
    temporary=destination.with_suffix('.tmp.wav')
    with sf.SoundFile(temporary,'w',samplerate=sr,channels=1,subtype='PCM_16') as output:
        for file in files:
            info=sf.info(file)
            if info.samplerate!=sr or info.channels!=1 or not info.frames:
                raise ValueError(f'Invalid cached segment: {file}')
            for block in sf.blocks(file,blocksize=65536,dtype='float32'):
                output.write(block)
            output.write(np.zeros(int(sr*.25),dtype='float32'))
    temporary.replace(destination)

def convert(voice,text,title='sample',sample=True,progress=None,filename=None):
    voice=slug(voice); title=slug(title)
    filename=filename or (title+'.mp3')
    if Path(filename).name != filename or '/' in filename or '\\' in filename or not filename.lower().endswith('.mp3'):
        raise ValueError('Output filename must be an MP3 basename.')
    ref=ROOT/'recordings'/voice/'reference.wav'
    if not ref.exists(): raise ValueError('Add the voice recording first.')
    digest=hashlib.sha256(ref.read_bytes()).hexdigest()
    approval=ref.parent/'approved.json'
    if not sample and (not approval.exists() or json.loads(approval.read_text())['reference_sha256']!=digest):
        raise ValueError('Generate and review a sample, then approve this voice before chapter conversion.')
    parts=chunks(text)
    if not parts: raise ValueError('Enter some text.')
    if sample and len(text)>1000: raise ValueError('Keep the first sample below 1,000 characters.')
    key=hashlib.sha256((text+digest+'turbo-v1').encode()).hexdigest()[:12]
    folder=ROOT/'output'/voice/(title+'-'+key); folder.mkdir(parents=True,exist_ok=True)
    (folder/'original.txt').write_text(text,encoding='utf-8')
    if progress: progress(0,len(parts),'Loading model')
    m=model(); m.prepare_conditionals(str(ref))
    entries=[]
    for i,part in enumerate(parts):
        f=folder/f'part-{i:05d}.wav'; start=time.perf_counter(); cached=f.exists()
        if not cached:
            import torch
            torch.manual_seed(1000+i)
            with torch.inference_mode(): wav=m.generate(part)
            temporary=f.with_suffix('.tmp.wav')
            sf.write(temporary,wav.detach().cpu().numpy().reshape(-1),m.sr)
            temporary.replace(f)
            del wav
        info=sf.info(f); seconds=info.duration
        entries.append({'index':i,'text':part,'duration_seconds':seconds,'generation_seconds':None if cached else time.perf_counter()-start,'cached':cached})
        manifest=folder/'manifest.json'; temporary=manifest.with_suffix('.tmp')
        temporary.write_text(json.dumps({'voice':voice,'reference_sha256':digest,'model':'chatterbox-turbo','parts':entries,'reviewed':False},indent=2))
        temporary.replace(manifest)
        if progress: progress(i+1,len(parts),'Segments')
    if progress: progress(len(parts),len(parts),'Encoding MP3')
    assemble_segments([folder/f'part-{i:05d}.wav' for i in range(len(parts))],folder/'chapter.wav')
    mp3=folder/filename
    temporary=folder/'encoded.tmp.mp3'
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-y','-i',str(folder/'chapter.wav'),'-codec:a','libmp3lame','-b:a','128k','-metadata',f'title={title}',str(temporary)],check=True)
    temporary.replace(mp3)
    if progress: progress(len(parts),len(parts),'Complete')
    return str(mp3),json.dumps(entries,indent=2)

def approve(voice):
    ref=ROOT/'recordings'/slug(voice)/'reference.wav'
    if not list((ROOT/'output'/voice).glob('sample-*/*.mp3')): raise ValueError('Generate a sample first.')
    (ref.parent/'approved.json').write_text(json.dumps({'reference_sha256':hashlib.sha256(ref.read_bytes()).hexdigest(),'approved_at':time.time()}))
    return 'Voice approved for chapter conversion.'

CHAPTER_HEADING=re.compile(r'^\s*chapter\s+(?:\d+|[ivxlcdm]+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)\b[^\n]*$',re.I|re.M)

def split_chapters(text, fallback='Chapter'):
    headings=list(CHAPTER_HEADING.finditer(text))
    if not headings: return [(fallback,text)]
    result=[]
    if text[:headings[0].start()].strip(): result.append(('Opening pages',text[:headings[0].start()]))
    for i,heading in enumerate(headings):
        end=headings[i+1].start() if i+1<len(headings) else len(text)
        result.append((heading.group().strip(),text[heading.start():end]))
    return result

def load_book(title, files, detect=True):
    slug(title)
    if len(title)>36: raise ValueError('Keep the book name at 36 characters or fewer.')
    if not files: raise ValueError('Choose chapter text files or one whole-book text file.')
    chapters=[]; sources=[]
    for file in sorted(map(Path,files),key=lambda f:[int(x) if x.isdigit() else x.lower() for x in re.split(r'(\d+)',f.name)]):
        text=file.read_text(encoding='utf-8-sig')
        if not text.strip(): raise ValueError(f'{file.name} is empty.')
        sources.append((file.name,text))
        chapters.extend(split_chapters(text,file.stem) if detect and len(files)==1 else [(file.stem,text)])
    digest=hashlib.sha256(json.dumps(sources,ensure_ascii=False).encode()).hexdigest()[:12]
    book_id=title+'-'+digest; folder=ROOT/'books'/book_id; folder.mkdir(parents=True,exist_ok=True)
    manifest=folder/'book.json'
    if not manifest.exists():
        for i,(name,text) in enumerate(sources): (folder/f'original-{i+1:03d}.txt').write_text(text,encoding='utf-8')
        entries=[]
        for i,(name,text) in enumerate(chapters):
            filename=f'chapter-{i+1:03d}.txt'; (folder/filename).write_text(text,encoding='utf-8')
            entries.append({'title':name,'text_file':filename})
        manifest.write_text(json.dumps({'title':title,'source_names':[x[0] for x in sources],'chapters':entries,'completed':{}},indent=2))
    return book_id

def book_manifest(book_id):
    path=ROOT/'books'/slug(book_id)/'book.json'
    return path,json.loads(path.read_text())

def book_status(book_id,voice):
    _,book=book_manifest(book_id)
    ref=ROOT/'recordings'/slug(voice)/'reference.wav'
    key=voice+'-'+hashlib.sha256(ref.read_bytes()).hexdigest()
    done=book['completed'].get(key,{})
    lines=[f'{i+1:03d}. {chapter["title"]} — '+('ready' if str(i) in done and (ROOT/done[str(i)]).exists() else 'waiting') for i,chapter in enumerate(book['chapters'])]
    return '\n'.join(lines)

def next_chapter(book_id,voice,progress=None):
    path,book=book_manifest(book_id)
    ref=ROOT/'recordings'/slug(voice)/'reference.wav'
    key=voice+'-'+hashlib.sha256(ref.read_bytes()).hexdigest()
    done=book['completed'].setdefault(key,{})
    for i,chapter in enumerate(book['chapters']):
        if str(i) in done and (ROOT/done[str(i)]).is_file(): continue
        text=(path.parent/chapter['text_file']).read_text(encoding='utf-8')
        options={'progress':progress} if progress else {}
        audio,report=convert(voice,text,f'{book_id}-{i+1:03d}',False,**options)
        done[str(i)]=str(Path(audio).relative_to(ROOT))
        temporary=path.with_suffix('.tmp'); temporary.write_text(json.dumps(book,indent=2)); temporary.replace(path)
        return audio,f'Completed {i+1}/{len(book["chapters"])}: {chapter["title"]}\n'+book_status(book_id,voice)+'\n\n'+report
    return None,'All chapters are ready.\n'+book_status(book_id,voice)

def cli_progress(done,total,stage):
    width=24; filled=int(width*done/total) if total else 0
    line=f'{stage}: [{"#"*filled}{"-"*(width-filled)}] {done}/{total}'
    print(('\r' if sys.stderr.isatty() else '')+line,
          end=('\n' if not sys.stderr.isatty() or stage=='Complete' else ''),file=sys.stderr,flush=True)

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--voice',required=True)
    source=p.add_mutually_exclusive_group(required=True)
    source.add_argument('--text',type=Path)
    source.add_argument('--next-book')
    p.add_argument('--chapter',help='Override the input-derived output name (without .mp3)')
    p.add_argument('--whole-chapter',action='store_true')
    p.add_argument('-o','--output',type=Path,help='Export MP3 to this file; existing files are never overwritten')
    a=p.parse_args(argv)
    destination=a.output.expanduser().resolve() if a.output else None
    if destination:
        if destination.suffix.lower()!='.mp3': p.error('--output must end in .mp3')
        if destination.exists(): p.error(f'Output already exists: {destination}')
        if not destination.parent.is_dir(): p.error(f'Output directory does not exist: {destination.parent}')
    if a.next_book:
        audio,report=next_chapter(a.next_book,a.voice,progress=cli_progress)
        print(report)
        if audio is None: return
    else:
        name=a.chapter if a.chapter is not None else a.text.stem
        if not name or '/' in name or '\\' in name or name in ('.','..'):
            p.error('Use a filename without directory separators for --chapter')
        # Keep sample cache names compatible with voice approval checks.
        title='sample' if not a.whole_chapter else (re.sub(r'[^A-Za-z0-9_-]+','_',name).strip('_') or 'chapter')[:60]
        audio,_=convert(a.voice,a.text.read_text(encoding='utf-8-sig'),title,not a.whole_chapter,
                        progress=cli_progress,filename=name+'.mp3')
    if destination:
        # Exclusive creation also protects against a file appearing during generation.
        with open(audio,'rb') as src, destination.open('xb') as dst:
            shutil.copyfileobj(src,dst)
        audio=str(destination)
    print(audio)

if __name__=='__main__': main()
