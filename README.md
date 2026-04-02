<<<<<<< HEAD
# YT Transcript API

API propia para extraer transcripciones de YouTube. Usa `youtube-transcript-api` de Python.

## Endpoints

### GET /transcript
```
GET /transcript?url=https://www.youtube.com/watch?v=VIDEO_ID&lang=es,en
```

Respuesta:
```json
{
  "video_id": "...",
  "lang": "es",
  "lang_name": "Español (generado automáticamente)",
  "is_auto_generated": true,
  "content": "texto completo..."
}
```

## Deploy en Render

1. Subí este repo a GitHub
2. Entrá a render.com → New → Web Service → conectá tu repo
3. Runtime: Python, Build: `pip install -r requirements.txt`
4. Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Plan: Free
6. Deploy → copiá la URL (ej: https://yt-transcript-api.onrender.com)
=======
# api-transcription
Api para acceder a la transcripción de videos de youtube. Funciona en coop con la extensión...
>>>>>>> ef70b9ee445e48ddea1438a6b60f28361dfd1938
