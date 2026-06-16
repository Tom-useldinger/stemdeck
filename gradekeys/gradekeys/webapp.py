"""A small FastAPI web UI for the GradeKeys 3-step flow.

    uvicorn gradekeys.webapp:app --port 8000      # or: gradekeys-web

Needs the ``web`` extra (fastapi, uvicorn, python-multipart) plus ``audio`` for
real input. Feasibility uses Demucs when the ``separate`` extra is installed and
otherwise falls back to a no-separation mix analysis, so the app runs with just
``audio`` too.
"""

from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from . import acquire, feasibility, separate, transcribe
from .arrange import render
from .engrave import engrave
from .models import Source, Verdict

app = FastAPI(title="GradeKeys")

_WORK = Path(tempfile.mkdtemp(prefix="gradekeys-web-"))
# job_id -> {audio_path, title, source}
_JOBS: dict[str, dict] = {}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return INDEX_HTML


@app.post("/api/song")
async def api_song(name: str | None = Form(None), file: UploadFile | None = None):
    """Step 1 + Step 2: acquire the audio and report feasibility."""
    job_id = uuid.uuid4().hex[:12]
    job_dir = _WORK / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # --- Step 1: get audio ----------------------------------------------------
    if file is not None and file.filename:
        audio_path = job_dir / file.filename
        with open(audio_path, "wb") as fh:
            shutil.copyfileobj(file.file, fh)
        title = Path(file.filename).stem
    elif name:
        try:
            got = acquire.acquire(name, job_dir)
        except acquire.AcquireError as exc:
            raise HTTPException(400, str(exc)) from exc
        audio_path, title = got.audio_path, got.title
    else:
        raise HTTPException(400, "Provide a song name or upload an audio file.")

    # --- Step 2: feasibility (Demucs if available, else mix analysis) ---------
    try:
        stem_dir = separate.separate(audio_path, job_dir / "stems")
        energies = separate.measure_energies(stem_dir)
        method = "demucs"
    except Exception:
        energies = separate.analyze_mix(audio_path)
        method = "mix-analysis"

    report = feasibility.assess(energies)
    _JOBS[job_id] = {
        "audio_path": audio_path,
        "title": title,
        "source": report.source or Source.VOCAL,
    }
    return {
        "job_id": job_id,
        "title": title,
        "verdict": report.verdict.value,
        "message": report.message,
        "source": report.source.value if report.source else None,
        "can_continue": report.verdict is Verdict.FEASIBLE,
        "method": method,
    }


@app.post("/api/arrange")
async def api_arrange(job_id: str = Form(...), grade: int = Form(...)):
    """Step 3: transcribe, arrange at the chosen grade, engrave to PDF."""
    job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(404, "Unknown job. Start again from step 1.")
    if not 1 <= grade <= 8:
        raise HTTPException(400, "Grade must be 1-8.")

    material = transcribe.transcribe(
        job["audio_path"], job["source"], title=job["title"]
    )
    score = render(material, grade)
    out_base = _WORK / job_id / f"score_g{grade}"
    result = engrave(score, out_base)

    return JSONResponse({
        "events": len(list(score.recurse().notes)),
        "renderer": result.renderer,
        "note": result.note,
        "pdf_url": f"/api/file/{job_id}/{grade}/pdf" if result.pdf_path else None,
        "musicxml_url": f"/api/file/{job_id}/{grade}/musicxml",
    })


@app.get("/api/file/{job_id}/{grade}/{kind}")
def api_file(job_id: str, grade: int, kind: str):
    base = _WORK / job_id / f"score_g{grade}"
    suffix = {"pdf": ".pdf", "musicxml": ".musicxml"}.get(kind)
    if suffix is None:
        raise HTTPException(404, "Unknown file kind.")
    path = base.with_suffix(suffix)
    if not path.exists():
        raise HTTPException(404, "File not found.")
    media = "application/pdf" if kind == "pdf" else "application/vnd.recordare.musicxml+xml"
    return FileResponse(path, media_type=media, filename=path.name)


def _serve() -> None:  # console-script entry point
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>GradeKeys</title>
<style>
  :root { color-scheme: light dark; }
  body { font: 16px/1.5 system-ui, sans-serif; max-width: 760px; margin: 2rem auto; padding: 0 1rem; }
  h1 { margin-bottom: .2rem; }
  .sub { opacity:.7; margin-top:0; }
  .card { border:1px solid #8884; border-radius:12px; padding:1.2rem; margin:1rem 0; }
  .step-num { display:inline-block; width:1.6rem; height:1.6rem; line-height:1.6rem; text-align:center;
              border-radius:50%; background:#52c65f; color:#fff; font-weight:700; margin-right:.5rem; }
  input[type=text]{ width:100%; padding:.6rem; border-radius:8px; border:1px solid #8886; box-sizing:border-box; }
  button{ padding:.6rem 1rem; border:0; border-radius:8px; background:#52c65f; color:#fff; font-weight:600; cursor:pointer; }
  button:disabled{ opacity:.5; cursor:default; }
  .hidden{ display:none; }
  .msg{ padding:.7rem 1rem; border-radius:8px; margin:.6rem 0; }
  .ok{ background:#52c65f22; } .bad{ background:#e5533422; } .lock{ background:#e0a82022; }
  .grades{ display:flex; flex-wrap:wrap; gap:.4rem; margin:.6rem 0; }
  .grades button{ background:#4d9dde; }
  .grades button.sel{ outline:3px solid #1c5; }
  iframe{ width:100%; height:520px; border:1px solid #8884; border-radius:8px; margin-top:.6rem; }
  small{ opacity:.7; }
</style>
</head>
<body>
  <h1>🎹 GradeKeys</h1>
  <p class="sub">Turn any song into a learnable, grade-adjustable piano score.</p>

  <div class="card">
    <p><span class="step-num">1</span><b>Pick a song</b></p>
    <p><input id="name" type="text" placeholder="Song name or URL (e.g. let it be)"></p>
    <p><small>…or upload audio:</small> <input id="file" type="file" accept="audio/*"></p>
    <button id="check">Check song</button>
    <span id="busy1" class="hidden">⏳ analyzing…</span>
  </div>

  <div id="step2" class="card hidden">
    <p><span class="step-num">2</span><b>Feasibility</b></p>
    <div id="verdict" class="msg"></div>
  </div>

  <div id="step3" class="card hidden">
    <p><span class="step-num">3</span><b>Choose a grade</b></p>
    <div class="grades" id="grades"></div>
    <button id="make" disabled>Create score</button>
    <span id="busy3" class="hidden">⏳ arranging & engraving…</span>
    <div id="result"></div>
  </div>

<script>
let job=null, grade=null;
const $=id=>document.getElementById(id);

$('check').onclick=async()=>{
  const fd=new FormData();
  const f=$('file').files[0];
  if(f) fd.append('file',f); else if($('name').value.trim()) fd.append('name',$('name').value.trim());
  else { alert('Enter a song name or pick a file.'); return; }
  $('busy1').classList.remove('hidden'); $('check').disabled=true;
  try{
    const r=await fetch('/api/song',{method:'POST',body:fd});
    const d=await r.json();
    if(!r.ok){ throw new Error(d.detail||'error'); }
    job=d.job_id;
    $('step2').classList.remove('hidden');
    const v=$('verdict');
    v.textContent=d.message+'  ('+d.method+')';
    v.className='msg '+(d.verdict==='feasible'?'ok':d.verdict==='locked_solo_piano'?'lock':'bad');
    if(d.can_continue){ buildGrades(); $('step3').classList.remove('hidden'); }
    else { $('step3').classList.add('hidden'); }
  }catch(e){ alert(e.message); }
  finally{ $('busy1').classList.add('hidden'); $('check').disabled=false; }
};

function buildGrades(){
  const g=$('grades'); g.innerHTML=''; grade=null; $('make').disabled=true; $('result').innerHTML='';
  for(let i=1;i<=8;i++){ const b=document.createElement('button'); b.textContent='Grade '+i;
    b.onclick=()=>{ grade=i; $('make').disabled=false; [...g.children].forEach(c=>c.classList.remove('sel')); b.classList.add('sel'); };
    g.appendChild(b);
  }
}

$('make').onclick=async()=>{
  if(!job||!grade) return;
  const fd=new FormData(); fd.append('job_id',job); fd.append('grade',grade);
  $('busy3').classList.remove('hidden'); $('make').disabled=true;
  try{
    const r=await fetch('/api/arrange',{method:'POST',body:fd});
    const d=await r.json();
    if(!r.ok){ throw new Error(d.detail||'error'); }
    let html='<p class="msg ok">Done — '+d.events+' notes/chords, grade '+grade+'.</p><p>';
    if(d.pdf_url) html+='<a href="'+d.pdf_url+'" target="_blank">⬇ PDF</a> &nbsp; ';
    html+='<a href="'+d.musicxml_url+'">⬇ MusicXML</a></p>';
    if(!d.pdf_url) html+='<p><small>'+d.note+'</small></p>';
    if(d.pdf_url) html+='<iframe src="'+d.pdf_url+'"></iframe>';
    $('result').innerHTML=html;
  }catch(e){ alert(e.message); }
  finally{ $('busy3').classList.add('hidden'); $('make').disabled=false; }
};
</script>
</body>
</html>"""
