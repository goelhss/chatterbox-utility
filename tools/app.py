from narrate import ROOT, register, convert, approve, load_book, next_chapter, book_status, saved_voice
import os, json, secrets
import gradio as gr
SCRIPT='The morning light reached across the kitchen table. I opened my book and took a slow breath. Outside, a small bird paused on the garden fence. There was no need to hurry. Today, I would follow the story one page at a time, and enjoy the journey.'
def profiles(): return sorted(p.parent.name for p in (ROOT/'recordings').glob('*/reference.wav'))
def add(name,audio,consent):
    if not consent: raise gr.Error('Confirm the speaker agreed to this use of their voice.')
    if not audio: raise gr.Error('Choose a recording first.')
    register(name,audio)
    return gr.Dropdown(choices=profiles(),value=name),'Voice saved locally. Generate a sample next.'
def sample(voice,text): return convert(voice,text)
def chapter(voice,title,file):
    if not file: raise gr.Error('Choose a UTF-8 chapter text file.')
    return convert(voice,open(file,encoding='utf-8').read(),title,False)
def review(voice,confirmed):
    if not confirmed: raise gr.Error('Listen and compare the sample first.')
    return approve(voice)
def queue_book(title,files,detect,voice):
    if not voice: raise gr.Error('Select a saved voice first.')
    book_id=load_book(title,files,detect)
    return book_id,book_status(book_id,voice),gr.Dropdown(choices=saved_books(),value=book_id)
def saved_books(): return sorted(p.parent.name for p in (ROOT/'books').glob('*/book.json'))
def resume_book(book_id,voice): return book_id,book_status(book_id,voice)
with gr.Blocks(title='Personal Voice', analytics_enabled=False) as app:
    gr.Markdown('# Personal Voice\nYour voices, your books, locally. Select a saved voice to reuse it, or add a new speaker. Then convert your chapters.')
    voice=gr.Dropdown(choices=profiles(),value=profiles()[0] if profiles() else None,label='Selected voice')
    saved_status=gr.Textbox(label='Saved voice status',interactive=False)
    book_shortcut=gr.Button('Go to book chapters')
    with gr.Tabs(selected=2 if profiles() else 1) as tabs:
        with gr.Tab('1 · Add a new voice',id=1):
            gr.Markdown('Record 20–30 seconds in a quiet room. Speak naturally with no long opening silence. This is only for a new speaker. The status above confirms your selected recording is saved and does not need to be recorded again. Each speaker gets a separate profile.\n\n**Read this:** '+SCRIPT)
            name=gr.Textbox(label='Voice name',placeholder='alex')
            consent=gr.Checkbox(label='This speaker agrees to voice cloning for these narrations')
            recording=gr.Audio(sources=['upload','microphone'],type='filepath',label='Record on this device, or import a phone recording')
            save=gr.Button('Save voice',variant='primary')
            status=gr.Textbox(label='Status')
        with gr.Tab('2 · Listen to a sample',id=2):
            text=gr.Textbox(value='At half past seven, Maya opened the blue notebook. She had packed three apples, a raincoat, and a map. Would the old bridge still be there? She smiled and began the journey.',label='Sample text',lines=5)
            generate=gr.Button('Generate sample',variant='primary')
            audio=gr.Audio(label='Local sample')
            timing=gr.Textbox(label='Segment text and timing',lines=6)
            checked=gr.Checkbox(label='I checked likeness, pronunciation, pacing, and missing or repeated words')
            accept=gr.Button('Approve this voice for chapters')
            accepted=gr.Textbox(label='Review status')
        with gr.Tab('3 · Convert a chapter',id=3):
            title=gr.Textbox(value='001-chapter',label='Numbered chapter filename')
            book=gr.File(file_types=['.txt'],label='One UTF-8 text file per chapter')
            run=gr.Button('Convert chapter',variant='primary')
            output=gr.File(label='Download portable MP3')
            report=gr.Textbox(label='Conversion details',lines=6)
            gr.Markdown('Original text and segment audio are retained locally. Review every chapter. The chapter MP3 is ready to download or copy.')
        with gr.Tab('4 · Book chapters',id=4):
            gr.Markdown('Load separate numbered chapter files, or one whole text book with headings such as Chapter 1 or CHAPTER ONE. Check the chapter list before conversion. Progress is saved locally for each voice. If no headings are found, the book appears as one chapter.')
            book_title=gr.Textbox(label='Short book name',placeholder='my-book')
            files=gr.File(file_count='multiple',file_types=['.txt'],label='Whole book or numbered chapter text files')
            detect=gr.Checkbox(value=True,label='Detect chapter headings when loading one book file')
            load=gr.Button('Load chapter queue')
            selected_book=gr.Dropdown(choices=saved_books(),label='Resume a saved book')
            queue_id=gr.State('')
            chapter_list=gr.Textbox(label='Chapter list and saved progress',lines=10)
            next_button=gr.Button('Convert next chapter',variant='primary')
            next_audio=gr.Audio(label='Listen to the latest chapter')
            next_file=gr.File(label='Download chapter MP3')
            next_report=gr.Textbox(label='Result and timing',lines=8)
    save.click(add,[name,recording,consent],[voice,status])
    generate.click(sample,[voice,text],[audio,timing],concurrency_id='speech')
    accept.click(review,[voice,checked],accepted)
    run.click(chapter,[voice,title,book],[output,report],concurrency_id='speech')
    load.click(queue_book,[book_title,files,detect,voice],[queue_id,chapter_list,selected_book])
    selected_book.change(resume_book,[selected_book,voice],[queue_id,chapter_list])
    def next_result(book_id,voice):
        if not book_id: raise gr.Error('Load or select a saved book first.')
        file,report=next_chapter(book_id,voice)
        return file,file,report,book_status(book_id,voice)
    next_button.click(next_result,[queue_id,voice],[next_audio,next_file,next_report,chapter_list],concurrency_id='speech')
    book_shortcut.click(lambda: gr.Tabs(selected=4),outputs=tabs)
    voice.change(lambda name: saved_voice(name)[1],voice,saved_status)
    voice.change(lambda book_id,name: book_status(book_id,name) if book_id and name else '',[queue_id,voice],chapter_list)
    def initial_voice():
        names=profiles(); selected=names[0] if names else None
        reference,message=saved_voice(selected)
        books=saved_books(); book_id=books[0] if books else None
        progress=book_status(book_id,selected) if book_id and selected else ''
        return gr.Dropdown(choices=names,value=selected),message,gr.Dropdown(choices=books,value=book_id),book_id or '',progress
    app.load(initial_voice,outputs=[voice,saved_status,selected_book,queue_id,chapter_list])
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(); parser.add_argument('--lan',action='store_true'); parser.add_argument('--port',type=int,default=7860); args=parser.parse_args()
    credential=ROOT/'tools/web-login.json'
    if not credential.exists(): credential.write_text(json.dumps({'username':'reader','password':secrets.token_urlsafe(18)}))
    c=json.loads(credential.read_text())
    app.queue(default_concurrency_limit=1).launch(server_name='0.0.0.0' if args.lan else '127.0.0.1',server_port=args.port,share=False,auth=(c['username'],c['password']),allowed_paths=[str(ROOT/'output')])
