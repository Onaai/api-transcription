from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from youtube_transcript_api import YouTubeTranscriptApi
import re

app = FastAPI(title="YT Transcript API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# v1.2.x requiere instancia, no métodos estáticos
ytt = YouTubeTranscriptApi()

def extract_video_id(url_or_id: str) -> str:
    match = re.search(r"(?:v=|youtu\.be/|embed/|shorts/)([a-zA-Z0-9_-]{11})", url_or_id)
    if match:
        return match.group(1)
    if re.match(r"^[a-zA-Z0-9_-]{11}$", url_or_id):
        return url_or_id
    raise ValueError(f"No se pudo extraer un video ID de: {url_or_id}")


@app.get("/")
def root():
    return {"status": "ok", "service": "YT Transcript API"}


@app.get("/transcript")
def get_transcript(
    url: str = Query(...),
    lang: str = Query("es,en"),
):
    try:
        video_id = extract_video_id(url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    lang_list = [l.strip() for l in lang.split(",") if l.strip()]

    try:
        transcript_list = ytt.list_transcripts(video_id)

        transcript = None

        # Manual primero
        for l in lang_list:
            try:
                transcript = transcript_list.find_manually_created_transcript([l])
                break
            except Exception:
                pass

        # Auto-generada
        if not transcript:
            for l in lang_list:
                try:
                    transcript = transcript_list.find_generated_transcript([l])
                    break
                except Exception:
                    pass

        # Cualquiera disponible
        if not transcript:
            available = list(transcript_list)
            if available:
                transcript = available[0]

        if not transcript:
            raise HTTPException(status_code=404, detail="No hay transcripción disponible.")

        fetched = transcript.fetch()
        full_text = " ".join(
            snippet.text.replace("\n", " ").strip()
            for snippet in fetched
            if snippet.text.strip()
        )

        return {
            "video_id": video_id,
            "lang": transcript.language_code,
            "lang_name": transcript.language,
            "is_auto_generated": transcript.is_generated,
            "content": full_text,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
