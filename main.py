"""
YT Transcript API — Backend propio
Usa youtube-transcript-api v1.2.x (jdepoix)

Endpoints:
  GET /                  → health check
  GET /transcript        → transcripción de un video
  GET /languages         → idiomas disponibles para un video
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
    CouldNotRetrieveTranscript,
)
import re

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="YT Transcript API",
    description="API propia para extraer transcripciones de YouTube",
    version="2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

from youtube_transcript_api.proxies import WebshareProxyConfig

# Proxy residencial Webshare — evita el bloqueo de YouTube en servidores cloud
ytt = YouTubeTranscriptApi(
    proxy_config=WebshareProxyConfig(
        proxy_username='bnlubrxv',
        proxy_password='9subtsr8y6cv0',
    )
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_video_id(url_or_id: str) -> str:
    """Acepta URL completa, youtu.be, shorts, o video ID directo."""
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
    """Convierte FetchedTranscript a texto plano limpio."""
    return " ".join(
        snippet.text.replace("\n", " ").strip()
        for snippet in fetched
        if snippet.text.strip()
    )

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
def root():
    return {
        "status": "ok",
        "service": "YT Transcript API",
        "version": "2.0",
        "endpoints": ["/transcript", "/languages"],
    }


@app.get("/transcript", tags=["Transcript"])
def get_transcript(
    url: str = Query(..., description="URL completa o video ID de YouTube"),
    lang: str = Query("es,en", description="Idiomas preferidos separados por coma (ej: es,en,pt)"),
    text_only: bool = Query(True, description="True = texto plano, False = incluye timestamps"),
):
    """
    Extrae la transcripción de un video de YouTube.
    
    - Prefiere transcripciones manuales sobre auto-generadas
    - Intenta los idiomas en orden de preferencia
    - Si ningún idioma está disponible, devuelve el primero que encuentre
    """
    # Extraer video ID
    try:
        video_id = extract_video_id(url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    lang_list = [l.strip() for l in lang.split(",") if l.strip()]

    try:
        # v1.2.x: usar list() para tener control sobre el idioma
        transcript_list = ytt.list(video_id)

        # Buscar transcript en orden de preferencia
        transcript = None

        # 1. Manual en idioma preferido
        try:
            transcript = transcript_list.find_manually_created_transcript(lang_list)
        except NoTranscriptFound:
            pass

        # 2. Auto-generado en idioma preferido
        if not transcript:
            try:
                transcript = transcript_list.find_generated_transcript(lang_list)
            except NoTranscriptFound:
                pass

        # 3. Cualquier transcript disponible (primer resultado)
        if not transcript:
            available = list(transcript_list)
            if available:
                transcript = available[0]

        if not transcript:
            raise HTTPException(
                status_code=404,
                detail="No hay transcripción disponible para este video."
            )

        # Fetchear contenido
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
        raise HTTPException(
            status_code=404,
            detail="Las transcripciones están deshabilitadas para este video."
        )
    except NoTranscriptFound:
        raise HTTPException(
            status_code=404,
            detail=f"No se encontró transcripción en los idiomas: {', '.join(lang_list)}"
        )
    except VideoUnavailable:
        raise HTTPException(
            status_code=404,
            detail="Video no disponible o privado."
        )
    except CouldNotRetrieveTranscript as e:
        error_msg = str(e)
        # YouTube bloquea IPs de servidores cloud — error conocido
        if "blocked" in error_msg.lower() or "ip" in error_msg.lower():
            raise HTTPException(
                status_code=503,
                detail="YouTube bloqueó la request desde este servidor. Intentá de nuevo en unos minutos."
            )
        raise HTTPException(status_code=503, detail=error_msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@app.get("/languages", tags=["Transcript"])
def get_languages(
    url: str = Query(..., description="URL completa o video ID de YouTube"),
):
    """
    Lista todos los idiomas disponibles para la transcripción de un video.
    Útil para saber qué idiomas podés pedir antes de llamar a /transcript.
    """
    try:
        video_id = extract_video_id(url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        transcript_list = ytt.list(video_id)
        languages = [
            {
                "code": t.language_code,
                "name": t.language,
                "is_auto_generated": t.is_generated,
                "is_translatable": t.is_translatable,
            }
            for t in transcript_list
        ]
        return {
            "video_id": video_id,
            "available_languages": languages,
            "count": len(languages),
        }

    except TranscriptsDisabled:
        raise HTTPException(status_code=404, detail="Transcripciones deshabilitadas.")
    except VideoUnavailable:
        raise HTTPException(status_code=404, detail="Video no disponible.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
