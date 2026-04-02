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
import random

app = FastAPI(title="YT Transcript API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Webshare free plan usa proxy.webshare.io como endpoint central
# Las IPs de la lista son los exit nodes pero la autenticación va al gateway
PROXY_USER = "bnlubrxv"
PROXY_PASS = "9subtsr8y6cv0"

# Gateway central de Webshare con rotación automática
WEBSHARE_PROXY = f"http://{PROXY_USER}:{PROXY_PASS}@p.webshare.io:80"

def get_ytt():
    return YouTubeTranscriptApi(
        proxy_config=GenericProxyConfig(
            http_url=WEBSHARE_PROXY,
            https_url=WEBSHARE_PROXY,
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
        raise HTTPException(status_code=404, detail="Transcripciones deshabilitadas para este video.")
    except NoTranscriptFound:
        raise HTTPException(status_code=404, detail=f"No se encontró transcripción en: {', '.join(lang_list)}")
    except VideoUnavailable:
        raise HTTPException(status_code=404, detail="Video no disponible o privado.")
    except CouldNotRetrieveTranscript as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@app.get("/languages")
def get_languages(url: str = Query(...)):
    try:
        video_id = extract_video_id(url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        transcript_list = get_ytt().list(video_id)
        languages = [
            {
                "code": t.language_code,
                "name": t.language,
                "is_auto_generated": t.is_generated,
            }
            for t in transcript_list
        ]
        return {"video_id": video_id, "available_languages": languages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
