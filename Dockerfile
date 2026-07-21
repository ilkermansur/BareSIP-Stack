# =============================================================================
# Aşama 1: Derleme (Builder)
# =============================================================================
# Bu aşamada Baresip ve bağımlılığı "libre (re)" kaynak kodundan derlenir.
# Derlenmiş ikili ve kütüphaneler ikinci aşamaya aktarılır.
FROM debian:bookworm-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    libssl-dev \
    zlib1g-dev \
    ca-certificates \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src

# libre (re) kütüphanesini derle — Baresip'in çekirdek bağımlılığı
RUN git clone --depth 1 https://github.com/baresip/re.git && \
    cd re && \
    cmake -B build -DCMAKE_BUILD_TYPE=Release && \
    cmake --build build -j$(nproc) && \
    cmake --install build

# Baresip'i derle
# Yalnızca ihtiyacımız olan modüller: aufile, ctrl_tcp, g711, g722, menu, account
RUN git clone --depth 1 https://github.com/baresip/baresip.git && \
    cd baresip && \
    cmake -B build \
      -DCMAKE_BUILD_TYPE=Release \
      -DMODULES="aufile;ctrl_tcp;g711;g722;menu;account" && \
    cmake --build build -j$(nproc) && \
    cmake --install build


# =============================================================================
# Aşama 2: Çalışma Ortamı (Runtime) — Tamamen Anonim İmaj
# =============================================================================
# Bu aşamada yalnızca araçlar kurulur.
# Hiçbir kullanıcı verisi, yapılandırma veya uygulama kodu bu imaja kopyalanmaz.
# Tüm bunlar docker-compose.yml üzerinden bind mount ile sağlanır.
FROM debian:bookworm-slim

# Sistem araçları: FFmpeg, Python, curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    ca-certificates \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Builder'dan derlenmiş Baresip ikili ve kütüphaneleri kopyala
COPY --from=builder /usr/local /usr/local
RUN ldconfig

# Python sanal ortamı ve FastAPI bağımlılıkları
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir fastapi uvicorn pydantic

# ─── Piper TTS: Platform Bağımsız Kurulum ────────────────────────────────────
# TARGETARCH: Docker'ın derleme sırasında otomatik belirlediği mimari
#   arm64  → Apple M1/M2/M3/M4, AWS Graviton
#   amd64  → Intel/AMD sunucular, Linux makineler
ARG TARGETARCH
WORKDIR /opt

RUN echo "Platform: ${TARGETARCH}" && \
    if [ "${TARGETARCH}" = "arm64" ]; then \
        PIPER_FILE="piper_linux_aarch64.tar.gz"; \
    else \
        PIPER_FILE="piper_linux_x86_64.tar.gz"; \
    fi && \
    curl -L --insecure \
         "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/${PIPER_FILE}" \
         -o piper.tar.gz && \
    tar -xf piper.tar.gz && \
    ln -s /opt/piper/piper /usr/local/bin/piper && \
    rm piper.tar.gz

# ─── Başlatma Betiği ──────────────────────────────────────────────────────────
# entrypoint.sh imaja gömülür çünkü konteynerin nasıl başlayacağını tanımlar.
# İçeriği değiştirmeniz gerekmez; yalnızca araçları sıraya koyar.
WORKDIR /app
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# ─── Beklenen Mount Noktaları (docker-compose tarafından sağlanır) ─────────────
# /app/app/          → Python IVR kodu      (./app)
# /app/voices/       → Piper ses modelleri  (./voices)
# /root/.baresip/config    → Baresip ayarları    (./config)
# /root/.baresip/accounts  → SIP hesap bilgileri (./accounts)
# Hiçbiri bu imaj içinde bulunmaz.

# ─── Port Açıklamaları ────────────────────────────────────────────────────────
# 8080          → FastAPI HTTP API
# 5060/udp+tcp  → SIP Sinyalleşme
# 40000-40100   → RTP Ses (host network modunda geçerli)
EXPOSE 8080 5060/udp 5060/tcp

ENTRYPOINT ["/app/entrypoint.sh"]
