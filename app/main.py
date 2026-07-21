"""
main.py — FastAPI Uygulama Giriş Noktası
==========================================
Swagger UI: http://localhost:8080/docs
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import app.baresip as baresip
import app.tts as tts
import app.ivr as ivr


# ─── Uygulama Başlatma ───────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[Main] FastAPI başlatılıyor...")
    asyncio.create_task(baresip.connect_loop(ivr.handle_event))
    yield
    print("[Main] FastAPI durduruluyor.")


app = FastAPI(
    title="Baresip IVR Kontrol API",
    description="Baresip + Piper TTS + FFmpeg ile dinamik IVR sistemi.",
    version="1.0.0",
    lifespan=lifespan,
)


# ─── İstek Şemaları ──────────────────────────────────────────────────────────

class CallRequest(BaseModel):
    """POST /api/v1/call için istek gövdesi."""
    to: str                     # Aranacak SIP adresi
    welcome_text: str = (
        "Hoş geldiniz. Bilgi almak için 1'e, operatör için 2'ye basın."
    )
    voice: str = "fettah"       # Ses anahtar kelimesi — bkz. /api/v1/status


class HangupRequest(BaseModel):
    """POST /api/v1/hangup için istek gövdesi."""
    call_id: str = ""           # Boş = aktif çağrıyı kapat


class PlayRequest(BaseModel):
    """POST /api/v1/play için istek gövdesi."""
    text: str                   # Seslendirilecek metin
    voice: str = "fettah"       # Ses anahtar kelimesi


# ─── Endpoint: Arama Başlat ──────────────────────────────────────────────────

@app.post("/api/v1/call", summary="SIP çağrısı başlat")
async def start_call(req: CallRequest):
    """
    Adımlar:
      1. welcome_text → Piper + FFmpeg → /tmp/welcome.wav
      2. IVR modülüne seçilen sesi bildir
      3. Baresip'e dial komutu gönder
      4. Telefon açılınca IVR otomatik sesi çalar
    """
    if baresip.writer is None:
        raise HTTPException(503, "Baresip bağlı değil. Konteyner loglarını kontrol edin.")

    if req.voice not in tts.MODELS:
        raise HTTPException(400, f"Geçersiz ses: '{req.voice}'. "
                                 f"Geçerli sesler: {list(tts.MODELS.keys())}")

    await tts.text_to_wav(req.welcome_text, "/tmp/welcome.wav", voice=req.voice)
    ivr.set_voice(req.voice)

    basarili = await baresip.send("dial", req.to)
    if not basarili:
        raise HTTPException(500, "Baresip'e dial komutu gönderilemedi.")

    return {"status": "ok", "aranan": req.to, "ses": req.voice}


# ─── Endpoint: Çağrıyı Kapat ─────────────────────────────────────────────────

@app.post("/api/v1/hangup", summary="Aktif çağrıyı kapat")
async def hangup(req: HangupRequest):
    if baresip.writer is None:
        raise HTTPException(503, "Baresip bağlı değil.")
    await baresip.send("hangup", req.call_id)
    return {"status": "ok"}


# ─── Endpoint: Ses Çal ───────────────────────────────────────────────────────

@app.post("/api/v1/play", summary="Aktif çağrıda metin seslendir")
async def play_text(req: PlayRequest):
    """Aktif çağrı sırasında herhangi bir metni anında seslendirir."""
    if baresip.writer is None:
        raise HTTPException(503, "Baresip bağlı değil.")

    if req.voice not in tts.MODELS:
        raise HTTPException(400, f"Geçersiz ses: '{req.voice}'.")

    await tts.text_to_wav(req.text, "/tmp/dynamic.wav", voice=req.voice)
    await baresip.send("ausrc", "aufile,/tmp/dynamic.wav")
    return {"status": "ok", "seslendirildi": req.text, "ses": req.voice}


# ─── Endpoint: Durum ─────────────────────────────────────────────────────────

@app.get("/api/v1/status", summary="Sistem durumu ve mevcut sesler")
async def status():
    """
    Baresip bağlantı durumu + kullanılabilir tüm ses anahtar kelimeleri.
    Ses seçerken bu listeden bir değer alın ve 'voice' alanına yazın.
    """
    return {
        "baresip_bagli": baresip.writer is not None,
        "aktif_ses": ivr.current_voice,
        "mevcut_sesler": [
            {"keyword": k, "dosya": v}
            for k, v in tts.MODELS.items()
        ],
    }
