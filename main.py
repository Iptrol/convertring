import os
import uuid
import asyncio
import tempfile
import subprocess
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ConvertRing API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

JOBS: dict[str, dict] = {}
OUTPUT_DIR = Path("/tmp/ringcut")
OUTPUT_DIR.mkdir(exist_ok=True)

MAX_DURATION = 40
MAX_FILE_MB  = 50

def make_job() -> str:
    jid = str(uuid.uuid4())
    JOBS[jid] = {"status": "pending", "file_path": None, "message": ""}
    return jid

def run_ffmpeg(args: list) -> tuple[bool, str]:
    result = subprocess.run(
        ["ffmpeg", "-y", *args],
        capture_output=True, text=True
    )
    return result.returncode == 0, result.stderr

def convert_to_m4r(src: str, dst: str, start: int, end: int) -> bool:
    duration = min(end - start, MAX_DURATION)
    logger.info(f"Converting: {src} → {dst}, start={start}, duration={duration}")
    ok, stderr = run_ffmpeg([
        "-i", src,
        "-ss", str(start),
        "-t", str(duration),
        "-vn",
        "-acodec", "aac",
        "-b:a", "128k",
        "-f", "ipod",
        dst
    ])
    if not ok:
        logger.error(f"ffmpeg failed: {stderr}")
    else:
        logger.info(f"ffmpeg success, file exists: {Path(dst).exists()}")
    return ok

async def download_url(url: str, out_dir: str) -> Optional[str]:
    """Завантажує відео/аудіо через yt-dlp"""
    opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(out_dir, "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "max_filesize": MAX_FILE_MB * 1024 * 1024,
        "retries": 10,
        "fragment_retries": 10,
        "socket_timeout": 30,
        "http_chunk_size": 1048576,
        "extractor_args": {"youtube": {"player_client": ["ios"]}},
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            base = Path(ydl.prepare_filename(info)).stem
            for f in Path(out_dir).iterdir():
                if f.stem == base:
                    return str(f)
    except Exception as e:
        logger.error(f"yt-dlp error: {e}")
    return None

async def process_file_job(job_id: str, tmp_path: str, start: int, end: int):
    out = str(OUTPUT_DIR / f"{job_id}.m4r")
    try:
        logger.info(f"Job {job_id}: converting file {tmp_path}")
        ok = convert_to_m4r(tmp_path, out, start, end)
        if ok and Path(out).exists():
            logger.info(f"Job {job_id}: done!")
            JOBS[job_id] = {"status": "done", "file_path": out, "message": ""}
        else:
            logger.error(f"Job {job_id}: failed")
            JOBS[job_id] = {"status": "error", "file_path": None, "message": "Конвертація не вдалася"}
    except Exception as e:
        logger.error(f"Job {job_id}: exception: {e}")
        JOBS[job_id] = {"status": "error", "file_path": None, "message": str(e)}
    finally:
        try: os.remove(tmp_path)
        except: pass

async def process_url_job(job_id: str, url: str, start: int, end: int):
    with tempfile.TemporaryDirectory() as tmp:
        JOBS[job_id]["status"] = "downloading"
        logger.info(f"Job {job_id}: downloading via yt-dlp")
        dl = await download_url(url, tmp)

        if not dl:
            JOBS[job_id] = {"status": "error", "file_path": None, "message": "Не вдалося завантажити відео"}
            return

        out = str(OUTPUT_DIR / f"{job_id}.m4r")
        JOBS[job_id]["status"] = "converting"
        ok = convert_to_m4r(dl, out, start, end)
        if ok and Path(out).exists():
            JOBS[job_id] = {"status": "done", "file_path": out, "message": ""}
        else:
            JOBS[job_id] = {"status": "error", "file_path": None, "message": "Помилка конвертації"}

@app.get("/")
def root():
    return {"service": "ConvertRing API", "status": "ok"}

@app.post("/convert/file")
async def convert_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    start: int = Form(0),
    end: int = Form(30)
):
    if file.size and file.size > MAX_FILE_MB * 1024 * 1024:
        raise HTTPException(400, f"Файл занадто великий (макс {MAX_FILE_MB} МБ)")
    if end - start > MAX_DURATION:
        raise HTTPException(400, f"Максимальна тривалість {MAX_DURATION} секунд")

    job_id = make_job()
    suffix = Path(file.filename).suffix or ".mp4"
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(tmp_fd, 'wb') as f:
        content = await file.read()
        f.write(content)

    JOBS[job_id]["status"] = "converting"
    background_tasks.add_task(process_file_job, job_id, tmp_path, start, end)
    return {"job_id": job_id}

class UrlRequest(BaseModel):
    url: str
    start: int = 0
    end: int = 30

@app.post("/convert/url")
async def convert_url(req: UrlRequest, background_tasks: BackgroundTasks):
    if req.end - req.start > MAX_DURATION:
        raise HTTPException(400, f"Максимальна тривалість {MAX_DURATION} секунд")
    job_id = make_job()
    JOBS[job_id]["status"] = "downloading"
    background_tasks.add_task(process_url_job, job_id, req.url, req.start, req.end)
    return {"job_id": job_id}

@app.get("/status/{job_id}")
def get_status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return {"status": job["status"], "message": job.get("message", "")}

@app.get("/download/{job_id}")
def download(job_id: str):
    job = JOBS.get(job_id)
    if not job or job["status"] != "done":
        raise HTTPException(404, "Файл не знайдено або ще не готовий")
    path = job["file_path"]
    if not path or not Path(path).exists():
        raise HTTPException(404, "Файл видалено")
    return FileResponse(
        path,
        media_type="audio/x-m4r",
        filename="ringtone.m4r",
        headers={"Content-Disposition": "attachment; filename=ringtone.m4r"}
    )
