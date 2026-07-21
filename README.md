# BareSIP Stack — Dockerized Baresip, FastAPI, FFmpeg & Piper TTS IVR Platform

![Docker](https://img.shields.io/badge/Docker-Multi--stage-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-1.0.0-green)
![Baresip](https://img.shields.io/badge/Baresip-SIP-red)
![Piper TTS](https://img.shields.io/badge/Piper-TTS-orange)
![FFmpeg](https://img.shields.io/badge/FFmpeg-Audio-sharp)

**BareSIP Stack**, **Baresip** (SIP client), **Piper TTS** (offline text-to-speech engine), **FFmpeg** (audio converter), and **FastAPI** (REST API & controller) components into a production-ready, highly modular, and dynamic IVR (Interactive Voice Response) system.

---

## 🌟 Key Features

* **Static & Anonymous Container Architecture**: The Docker image contains *only* runtime tools (Baresip, Piper, FFmpeg, Python venv). Your application code (`app/`), configurations (`config`, `accounts`), and voice models (`voices/`) are bind-mounted read-only (`:ro`). Zero user credentials or application logic are baked into the container.
* **Pre-built Docker Hub Image**: Ready-to-use multi-arch image (`imansur/baresip-ivr:latest`) available for instant 5-second deployments without compiling from source.
* **Modular Python Application**: Cleanly separated into specialized modules (`baresip.py`, `tts.py`, `ivr.py`, `main.py`).
* **Multi-Voice TTS Support**: Pre-configured with named voice models (`fettah`, `eren`, `cem`, `hfc_male`, `hfc_female`) supporting both Turkish and English, with per-call or per-DTMF voice selection.
* **Real-time DTMF & Event Handling**: Listens to Baresip's local TCP netstring control interface (`ctrl_tcp_listen`) to handle call establishment, DTMF keypresses, and call hangup events in real time.
* **Cross-Platform**: Automatically builds and runs seamlessly on both **macOS (ARM64 / Apple Silicon)** and **Linux (AMD64)** architectures.

---

## 📁 Repository Structure

```text
bareSIP/
├── Dockerfile            # Multi-stage, platform-aware container build
├── docker-compose.yml    # Build from source code composition
├── single_image.yml      # Run pre-built Docker Hub image (imansur/baresip-ivr:latest)
├── entrypoint.sh         # Container startup script (Baresip daemon + FastAPI)
├── download_voices.sh    # Script to download Piper TTS voice models to host
├── config                # Headless Baresip configuration (bind-mounted)
├── accounts              # SIP account credentials (bind-mounted)
├── developer_guide.md    # In-depth architectural documentation
├── voices/               # Piper ONNX voice models directory (bind-mounted)
└── app/                  # Modular FastAPI application (bind-mounted)
    ├── __init__.py
    ├── main.py           # REST API endpoints & lifecycle management
    ├── baresip.py        # Async TCP socket client & netstring parser
    ├── tts.py            # Piper TTS + FFmpeg conversion pipeline & model dictionary
    └── ivr.py            # IVR state management & DTMF key handlers
```

---

## 🚀 Quick Start Guide

### 1. Download Voice Models
Execute the helper script to download the required Piper TTS ONNX models directly to your host's `./voices` directory:

```bash
chmod +x download_voices.sh
./download_voices.sh
```

### 2. Configure SIP Credentials
Edit the `accounts` file with your SIP provider or local PBX credentials:

```text
<sip:EXTENSION@SIP_SERVER_IP>;auth_pass=YOUR_PASSWORD;transport=udp
```
*Example:* `<sip:1001@192.168.1.100>;auth_pass=MySecretPass;transport=udp`

---

### 3. Launch Container

Choose **Option A** (Instant pre-built image) or **Option B** (Build from source code):

#### 🔹 Option A: Use Pre-built Docker Hub Image (Recommended — 5 Seconds)
Uses the official pre-compiled multi-arch image `imansur/baresip-ivr:latest`:

```bash
docker compose -f single_image.yml up -d
```

#### 🔸 Option B: Build from Source Code
Compiles Baresip and builds the container locally on your machine:

```bash
docker compose build
docker compose up -d
```

---

### 4. Monitor Logs
Verify that Baresip connected to your SIP server and FastAPI started:

```bash
docker compose logs -f
```

---

## 📡 API Reference

FastAPI runs on port **`8080`**. Interactive Swagger UI documentation is available at `http://localhost:8080/docs`.

### 1. Trigger an Outbound SIP Call

* **Endpoint**: `POST /api/v1/call`
* **Content-Type**: `application/json`
* **Body**:
```json
{
  "to": "sip:1002@192.168.1.100",
  "welcome_text": "Hoş geldiniz. Bilgi almak için 1'e, operatör için 2'ye basın.",
  "voice": "fettah"
}
```

* **cURL Example**:
```bash
curl -X POST "http://localhost:8080/api/v1/call" \
     -H "Content-Type: application/json" \
     -d '{
       "to": "sip:1002@192.168.1.100",
       "welcome_text": "Hoş geldiniz. Bilgi için bir, operatör için iki tuşuna basın.",
       "voice": "fettah"
     }'
```

### 2. Play Dynamic Audio During an Active Call

* **Endpoint**: `POST /api/v1/play`
* **Body**:
```json
{
  "text": "Your appointment is confirmed for tomorrow.",
  "voice": "hfc_female"
}
```

### 3. End Active Call

* **Endpoint**: `POST /api/v1/hangup`
* **Body**: `{"call_id": ""}`

### 4. System Status & Available Voices

* **Endpoint**: `GET /api/v1/status`
* **Response**:
```json
{
  "baresip_bagli": true,
  "aktif_ses": "fettah",
  "mevcut_sesler": [
    {"keyword": "fettah", "dosya": "/app/voices/tr-fettah.onnx"},
    {"keyword": "eren", "dosya": "/app/voices/tr-eren.onnx"},
    {"keyword": "cem", "dosya": "/app/voices/tr-cem.onnx"},
    {"keyword": "hfc_male", "dosya": "/app/voices/en-hfc-male.onnx"},
    {"keyword": "hfc_female", "dosya": "/app/voices/en-hfc-female.onnx"}
  ]
}
```

---

## 🎙️ Available Voice Keywords

| Keyword | Language | Gender | Source / Model | File |
|---|---|---|---|---|
| `fettah` | Turkish | Male | `speaches-ai/piper-tr_TR-fettah-medium` | `tr-fettah.onnx` |
| `eren` | Turkish | Male | `99eren99/piper-turkish-tts` | `tr-eren.onnx` |
| `cem` | Turkish | Male | `dcx514ai/piper_tts_turkish_high` | `tr-cem.onnx` |
| `hfc_male` | English | Male | `rhasspy/piper-voices hfc_male` | `en-hfc-male.onnx` |
| `hfc_female` | English | Female | `rhasspy/piper-voices hfc_female` | `en-hfc-female.onnx` |

---

## 🔄 IVR Flow Customization

To customize the DTMF keypad actions, simply modify `DTMF_MENU` in `app/ivr.py`:

```python
DTMF_MENU = {
    "1": {"text": "Bir tuşuna bastınız. Bilgi menüsü.", "voice": "eren"},
    "2": {"text": "You selected option two.",          "voice": "hfc_female"},
    "9": {"text": "Ana menüye dönülüyor.",             "voice": ""},
}
```

Since application files are bind-mounted, simply run `docker compose restart` to apply code or IVR changes — **no image rebuild required!**

---

## 📖 Deep-Dive Documentation

For exhaustive technical details regarding:
- Netstring socket protocol specifications
- Piper to FFmpeg conversion pipeline (8kHz 16-bit Mono PCM normalization)
- Event dispatching lifecycle
- Static container design philosophy

Please read the [Developer Guide](developer_guide.md).

---

## 🛡️ License

MIT License. Free for personal and commercial use.
