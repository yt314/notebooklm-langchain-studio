"""Cloud Run TTS relay: runs ElevenLabs calls outside the filtered network,
stores chunks in GCS, and delivers the concatenated result via Google Drive
(the channel the network filter allows through).

Deploy with `gcloud run deploy` (see README.md in this folder). Never commit
ELEVENLABS_API_KEY or SERVICE_SECRET - they are passed as Cloud Run env vars
at deploy time, not stored in this repo.
"""

import os
import subprocess
import tempfile
from pathlib import Path

import google.auth
from elevenlabs.client import ElevenLabs
from elevenlabs.types import DialogueInput, ModelSettingsResponseModel
from fastapi import FastAPI, Header, HTTPException
from google.cloud import storage
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from pydantic import BaseModel

app = FastAPI()

BUCKET = os.environ["AUDIO_BUCKET"]
SECRET = os.environ["SERVICE_SECRET"]
DRIVE_FOLDER_ID = os.environ["DRIVE_FOLDER_ID"]


def _require_secret(value: str) -> None:
    if value != SECRET:
        raise HTTPException(status_code=403, detail="bad service secret")


class Line(BaseModel):
    text: str
    voice_id: str


class SynthesizeRequest(BaseModel):
    job_id: str
    chunk_index: int
    lines: list[Line]


@app.post("/synthesize")
def synthesize(req: SynthesizeRequest, x_service_secret: str = Header("")):
    _require_secret(x_service_secret)
    client = ElevenLabs()  # ELEVENLABS_API_KEY from env
    audio = client.text_to_dialogue.convert(
        inputs=[DialogueInput(text=l.text, voice_id=l.voice_id) for l in req.lines],
        model_id="eleven_v3",
        settings=ModelSettingsResponseModel(stability=float(os.getenv("TTS_STABILITY", "0.35"))),
    )
    data = b"".join(audio)
    blob = storage.Client().bucket(BUCKET).blob(f"jobs/{req.job_id}/{req.chunk_index:04d}.mp3")
    blob.upload_from_string(data, content_type="audio/mpeg")
    return {"job_id": req.job_id, "chunk_index": req.chunk_index, "bytes": len(data)}


class FinalizeRequest(BaseModel):
    job_id: str
    filename: str


@app.post("/finalize")
def finalize(req: FinalizeRequest, x_service_secret: str = Header("")):
    _require_secret(x_service_secret)
    bucket = storage.Client().bucket(BUCKET)
    blobs = sorted(bucket.list_blobs(prefix=f"jobs/{req.job_id}/"), key=lambda b: b.name)
    if not blobs:
        raise HTTPException(status_code=404, detail="no chunks for this job")

    with tempfile.TemporaryDirectory() as tmp:
        paths = []
        for b in blobs:
            path = Path(tmp) / Path(b.name).name
            b.download_to_filename(path)
            paths.append(path)

        listfile = Path(tmp) / "list.txt"
        listfile.write_text("\n".join(f"file '{p}'" for p in paths))
        out = Path(tmp) / req.filename
        subprocess.run(
            ["ffmpeg", "-f", "concat", "-safe", "0", "-i", str(listfile), "-c", "copy", str(out)],
            check=True,
            capture_output=True,
        )

        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/drive"])
        drive = build("drive", "v3", credentials=creds)
        file = (
            drive.files()
            .create(
                body={"name": req.filename, "parents": [DRIVE_FOLDER_ID]},
                media_body=MediaFileUpload(str(out), mimetype="audio/mpeg"),
                fields="id, webViewLink",
            )
            .execute()
        )

    for b in blobs:
        b.delete()
    return {"url": file["webViewLink"]}
