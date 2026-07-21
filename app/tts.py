"""
tts.py — Piper TTS + FFmpeg Ses Üretme Modülü
==============================================
Metin → Piper (ham WAV) → FFmpeg (Baresip uyumlu WAV) pipeline'ı.

API'ye gelen isteklerde ses seçimi için "voice" anahtar kelimesi kullanılır.
Mevcut sesler ve anahtar kelimeleri → developer_guide.md bölüm 13.

Baresip'in aufile modülü şu formatı bekler:
  Codec:     PCM 16-bit signed little-endian
  Örnekleme: 8000 Hz
  Kanal:     Mono
  Kapsayıcı: WAV
"""

import asyncio
import os

# ─── Model Tablosu ────────────────────────────────────────────────────────────
# Anahtar : API'ye gönderilecek "voice" değeri (string)
# Değer   : /app/voices/ altındaki .onnx dosya adı
#
# Yeni model eklemek:
#  1. download_voices.sh içine indirme adımı ekle
#  2. Aşağıya yeni satır ekle
#  3. Ses dosyasını /voices/ dizinine koy (konteyner bind mount ile okur)

MODELS = {
    # ── Türkçe ──────────────────────────────────────────────────────────────
    # Fettah — speaches-ai/piper-tr_TR-fettah-medium
    "fettah":    "/app/voices/tr-fettah.onnx",

    # Eren — 99eren99/piper-turkish-tts
    "eren":      "/app/voices/tr-eren.onnx",

    # Cem — dcx514ai/piper_tts_turkish_high (gated repo, ayrıca indirin)
    # Gated modeli indiremezseniz aşağıdaki satırı "tr-eren.onnx" ile değiştirin
    "cem":       "/app/voices/tr-cem.onnx",

    # ── İngilizce ───────────────────────────────────────────────────────────
    # HFC Male — rhasspy/piper-voices hfc_male medium
    "hfc_male":  "/app/voices/en-hfc-male.onnx",

    # HFC Female — rhasspy/piper-voices hfc_female medium
    "hfc_female":"/app/voices/en-hfc-female.onnx",
}

# Ses belirtilmezse kullanılacak varsayılan
DEFAULT_VOICE = "fettah"

# Piper çıktısının geçici yazıldığı dosya
TEMP_WAV = "/tmp/_piper_raw.wav"


# ─── Ana Fonksiyon ────────────────────────────────────────────────────────────

async def text_to_wav(text: str, output_path: str, voice: str = DEFAULT_VOICE) -> None:
    """
    Metni sesli WAV dosyasına çevirir.

    Parametreler:
      text        → Seslendirilecek metin
      output_path → Üretilen WAV'ın kaydedileceği tam yol
      voice       → Ses anahtar kelimesi (bkz. MODELS tablosu)
                    Örnek: "fettah", "eren", "cem", "hfc_male", "hfc_female"

    Kullanım:
      await tts.text_to_wav("Merhaba dünya", "/tmp/ses.wav", voice="eren")
      await tts.text_to_wav("Hello world",   "/tmp/ses.wav", voice="hfc_female")
    """
    model_path = _get_model(voice)
    await _run_piper(text, TEMP_WAV, model_path)
    await _run_ffmpeg(TEMP_WAV, output_path)

    # Geçici Piper çıktısını temizle
    if os.path.exists(TEMP_WAV):
        os.remove(TEMP_WAV)


# ─── Model Seçimi ─────────────────────────────────────────────────────────────

def _get_model(voice: str) -> str:
    """
    Ses adına göre model dosyası yolunu döner.
    Bilinmeyen bir ses adı gelirse varsayılana düşer.
    """
    model = MODELS.get(voice)

    if model is None:
        fallback = MODELS[DEFAULT_VOICE]
        print(f"[TTS] UYARI: '{voice}' sesi tanınmıyor. "
              f"Varsayılan kullanılıyor: {DEFAULT_VOICE} → {fallback}")
        return fallback

    print(f"[TTS] Ses seçildi: '{voice}' → {model}")
    return model


# ─── Piper ────────────────────────────────────────────────────────────────────

async def _run_piper(text: str, output_wav: str, model_path: str) -> None:
    """Piper TTS çalıştırır. Metin stdin'den girilir, ses dosyaya yazılır."""
    print(f"[TTS] Piper: '{text[:50]}...' → {output_wav}")

    process = await asyncio.create_subprocess_exec(
        "piper",
        "--model", model_path,
        "--output_file", output_wav,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    _, stderr = await process.communicate(input=text.encode("utf-8"))

    if process.returncode != 0:
        hata = stderr.decode("utf-8")
        print(f"[TTS] Piper HATA: {hata}")
        raise RuntimeError(f"Piper başarısız: {hata}")

    print(f"[TTS] Piper tamamlandı → {output_wav}")


# ─── FFmpeg ───────────────────────────────────────────────────────────────────

async def _run_ffmpeg(input_wav: str, output_wav: str) -> None:
    """
    FFmpeg ile ses formatını Baresip uyumlu hale getirir:
      -ac 1              → Mono
      -ar 8000           → 8000 Hz
      -acodec pcm_s16le  → 16-bit PCM
      -y                 → Varsa üzerine yaz
    """
    print(f"[TTS] FFmpeg: {input_wav} → {output_wav}")

    process = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y",
        "-i", input_wav,
        "-ac", "1",
        "-ar", "8000",
        "-acodec", "pcm_s16le",
        output_wav,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    _, stderr = await process.communicate()

    if process.returncode != 0:
        hata = stderr.decode("utf-8")
        print(f"[TTS] FFmpeg HATA: {hata}")
        raise RuntimeError(f"FFmpeg başarısız: {hata}")

    print(f"[TTS] FFmpeg tamamlandı → {output_wav}")
