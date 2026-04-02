from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
    CouldNotRetrieveTranscript,
)
from youtube_transcript_api.proxies import GenericProxyConfig
import re
import os

app = FastAPI(title="YT Transcript API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# IPRoyal residential proxy
PROXY_USER = os.environ.get("PROXY_USER", "dbE7DGDQbY8Yhzib")
PROXY_PASS = os.environ.get("PROXY_PASS", "zXzXdQ2EHJbuNCvs")
PROXY_HOST = os.environ.get("PROXY_HOST", "geo.iproyal.com")
PROXY_PORT = os.environ.get("PROXY_PORT", "12321")

PROXY_URL = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"

print(f"[INIT] Proxy configurado: {PROXY_HOST}:{PROXY_PORT}")

def get_ytt():
    return YouTubeTranscriptApi(
        proxy_config=GenericProxyConfig(
            http_url=PROXY_URL,
            https_url=PROXY_URL,
        )
    )

def extract_video_id(url_or_id: str) -> str:
    patterns = [
        r"(?:v=)([a-zA-Z0-9_-]{11})",
        r"(?:youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"(?:embed/)([a-zA-Z0-9_-]{11})",
        r"(?:shorts/)([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    if re.match(r"^[a-zA-Z0-9_-]{11}$", url_or_id):
        return url_or_id
    raise ValueError(f"No se pudo extraer un video ID de: '{url_or_id}'")

def transcript_to_text(fetched) -> str:
    return " ".join(
        snippet.text.replace("\n", " ").strip()
        for snippet in fetched
        if snippet.text.strip()
    )


@app.get("/")
def root():
    return {"status": "ok", "service": "YT Transcript API", "version": "2.0"}


@app.get("/transcript")
def get_transcript(
    url: str = Query(...),
    lang: str = Query("es,en"),
    text_only: bool = Query(True),
):
    try:
        video_id = extract_video_id(url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    lang_list = [l.strip() for l in lang.split(",") if l.strip()]

    try:
        ytt = get_ytt()
        transcript_list = ytt.list(video_id)

        transcript = None

        try:
            transcript = transcript_list.find_manually_created_transcript(lang_list)
        except NoTranscriptFound:
            pass

        if not transcript:
            try:
                transcript = transcript_list.find_generated_transcript(lang_list)
            except NoTranscriptFound:
                pass

        if not transcript:
            available = list(transcript_list)
            if available:
                transcript = available[0]

        if not transcript:
            raise HTTPException(status_code=404, detail="No hay transcripción disponible.")

        fetched = transcript.fetch()

        if text_only:
            content = transcript_to_text(fetched)
        else:
            content = [
                {
                    "text": snippet.text.replace("\n", " ").strip(),
                    "start": round(snippet.start, 2),
                    "duration": round(snippet.duration, 2),
                }
                for snippet in fetched
                if snippet.text.strip()
            ]

        return {
            "video_id": video_id,
            "lang": transcript.language_code,
            "lang_name": transcript.language,
            "is_auto_generated": transcript.is_generated,
            "content": content,
        }

    except HTTPException:
        raise
    except TranscriptsDisabled:
        raise HTTPException(status_code=404, detail="Transcripciones deshabilitadas.")
    except NoTranscriptFound:
        raise HTTPException(status_code=404, detail="Sin transcripción en los idiomas solicitados.")
    except VideoUnavailable:
        raise HTTPException(status_code=404, detail="Video no disponible.")
    except CouldNotRetrieveTranscript as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/languages")
def get_languages(url: str = Query(...)):
    try:
        video_id = extract_video_id(url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        transcript_list = get_ytt().list(video_id)
        return {
            "video_id": video_id,
            "available_languages": [
                {
                    "code": t.language_code,
                    "name": t.language,
                    "is_auto_generated": t.is_generated,
                }
                for t in transcript_list
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
