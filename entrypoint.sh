#!/bin/bash
set -e  # Herhangi bir komut başarısız olursa dur

echo "[Entrypoint] Baresip varsayılan ses dosyaları oluşturuluyor..."
ffmpeg -y -f lavfi -i anullsrc=r=8000:cl=mono -t 1 -acodec pcm_s16le /tmp/welcome.wav >/dev/null 2>&1
ffmpeg -y -f lavfi -i anullsrc=r=8000:cl=mono -t 1 -acodec pcm_s16le /tmp/playback.wav >/dev/null 2>&1

# ─────────────────────────────────────────────────────────────
# Baresip'i arka planda (daemon) başlat
# -f: yapılandırma dizini
# -d: daemon modu (arka planda çalış)
# ─────────────────────────────────────────────────────────────
echo "[Entrypoint] Baresip başlatılıyor..."
baresip -f /root/.baresip -d

# Baresip'in TCP kontrol portunu (4444) açması için kısa bekleme
echo "[Entrypoint] Baresip'in başlaması için 2 saniye bekleniyor..."
sleep 2

# ─────────────────────────────────────────────────────────────
# FastAPI uygulamasını ön planda başlat
# Konteyner FastAPI ile ayakta kalır; bu process ölürse konteyner durur
# ─────────────────────────────────────────────────────────────
# Python önbelleğini (__pycache__) temizle ki eski bytecode çalışmasın
find /app/app -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find /app/app -name "*.pyc" -delete 2>/dev/null || true

echo "[Entrypoint] FastAPI başlatılıyor (port: 8080)..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8080 --log-level info --reload
