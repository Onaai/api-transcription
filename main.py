# main.py — YT Transcript API
# Usa youtube-transcript-api (jdepoix) — la misma librería que usan
# la mayoría de servicios de transcripción de YouTube.

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

app = FastAPI(title="YT Transcript API", version="1.0")

# Permitir llamadas desde la extensión de Chrome
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción podés restringir a tu extensión
    allow_methods=["GET"],
    allow_headers=["*"],
)

def extract_video_id(url_or_id: str) -> str:
    """Extrae el video ID de una URL de YouTube o lo devuelve tal cual."""
    patterns = [
        r"(?:v=|youtu\.be/|embed/|shorts/)([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    # Si ya es un ID (11 chars alfanuméricos)
    if re.match(r"^[a-zA-Z0-9_-]{11}$", url_or_id):
        return url_or_id
    raise ValueError(f"No se pudo extraer un video ID de: {url_or_id}")


@app.get("/")
def root():
    return {"status": "ok", "service": "YT Transcript API"}


@app.get("/transcript")
def get_transcript(
    url: str = Query(..., description="URL o video ID de YouTube"),
    lang: str = Query("es,en", description="Idiomas preferidos, separados por coma"),
):
    """
    Devuelve la transcripción de un video de YouTube.
    
    Parámetros:
    - url: URL completa o video ID (ej: dQw4w9WgXcQ)
    - lang: idiomas preferidos en orden (ej: es,en)
    
    Respuesta:
    {
        "video_id": "...",
        "lang": "es",
        "lang_name": "Español",
        "is_auto_generated": true,
        "content": "texto completo de la transcripción..."
    }
    """
    try:
        video_id = extract_video_id(url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    lang_list = [l.strip() for l in lang.split(",") if l.strip()]

    try:
        # Listar transcripciones disponibles
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # Intentar encontrar en los idiomas preferidos
        transcript = None
        
        # Primero buscar manuales (más precisas)
        for l in lang_list:
            try:
                transcript = transcript_list.find_manually_created_transcript([l])
                break
            except Exception:
                pass
        
        # Si no hay manuales, buscar auto-generadas
        if not transcript:
            for l in lang_list:
                try:
                    transcript = transcript_list.find_generated_transcript([l])
                    break
                except Exception:
                    pass
        
        # Si tampoco, tomar cualquiera disponible
        if not transcript:
            # Intentar traducir la primera disponible al español
            try:
                available = list(transcript_list)
                if available:
                    first = available[0]
                    # Intentar traducir a español si está disponible
                    if "es" in lang_list:
                        try:
                            transcript = first.translate("es")
                        except Exception:
                            transcript = first
                    else:
                        transcript = first
            except Exception:
                pass
        
        if not transcript:
            raise HTTPException(
                status_code=404,
                detail="No hay transcripción disponible para este video."
            )

        # Fetchear el contenido
        entries = transcript.fetch()
        
        # Unir todo el texto
        full_text = " ".join(
            entry.text.replace("\n", " ").strip()
            for entry in entries
            if entry.text.strip()
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
    except TranscriptsDisabled:
        raise HTTPException(status_code=404, detail="Las transcripciones están deshabilitadas para este video.")
    except NoTranscriptFound:
        raise HTTPException(status_code=404, detail="No se encontró transcripción en los idiomas solicitados.")
    except VideoUnavailable:
        raise HTTPException(status_code=404, detail="Video no disponible o no existe.")
    except CouldNotRetrieveTranscript as e:
        raise HTTPException(status_code=503, detail=f"No se pudo obtener la transcripción: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
