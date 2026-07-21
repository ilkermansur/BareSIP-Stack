# Developer Guide: Baresip + FastAPI + Piper TTS + FFmpeg Pipeline

> Bu döküman sistemin her katmanını derinlemesine açıklar.  
> "Neden?" sorusuna odaklanır; sadece ne yaptığımızı değil, neden o şekilde yaptığımızı anlatır.

---

## 1. Sisteme Genel Bakış

Sistem dört bileşenden oluşur. Her biri bağımsız ama birbirine bağımlı çalışır:

```
Dışarıdan HTTP İsteği
        │
        ▼
 ┌─────────────┐
 │  FastAPI    │  ← Dışarıya açık tek kapı (port 8080)
 │  (main.py)  │
 └──────┬──────┘
        │
        ├──► tts.py ──► Piper ──► FFmpeg ──► /tmp/*.wav
        │
        └──► baresip.py ──► TCP:4444 ──► Baresip (SIP istemcisi)
                                              │
                                         RTP Ses ──► Telefon
```

**Kullanıcının bakış açısından:** Tek bir HTTP isteği atarsınız, karşı tarafın telefonu çalar. Açtığında sesinizi duyar. Tuşa bastığında cevap alır.

**Sistemin içinden bakıldığında:** FastAPI bu isteği alır, sesi üretir, Baresip'e arama komutu gönderir. Baresip gerçek SIP protokolüyle telefonu arar. Telefon açılınca Baresip FastAPI'ye haber verir. FastAPI sesi çalmasını emreder.

---

## 2. Bileşenler ve Sorumlulukları

| Bileşen | Ne İşe Yarar |
|---|---|
| **Baresip** | Gerçek SIP istemcisi. Arama açar/kapatır. Ses paketlerini (RTP) gönderir/alır. |
| **Piper TTS** | Metni 22050Hz WAV'a çevirir. Tamamen offline çalışır. |
| **FFmpeg** | WAV dosyasını Baresip'in istediği formata (8kHz, mono, PCM) çevirir. |
| **FastAPI** | Dışarıdan gelen HTTP isteklerini yönetir. Diğer üçünü koordine eder. |

---

## 3. Konteyner İçinde Ne Çalışıyor?

Konteyner başladığında `entrypoint.sh` iki süreç başlatır:

```
Konteyner
  ├── Süreç 1: baresip -d    (arka planda, daemon modda)
  └── Süreç 2: uvicorn       (ön planda, konteyner bu süreçle yaşar/ölür)
```

FastAPI ve Baresip aynı anda çalışır. Aralarındaki iletişim TCP üzerinden olur:

```
FastAPI (port 8080) ──── TCP 127.0.0.1:4444 ───► Baresip
```

Bu loopback bağlantısı konteyner içi — dışarıya açılmaz, güvenlidir.

---

## 4. Bir HTTP İsteğinin Tam Yolculuğu

### Senaryo: `POST /api/v1/call`

```json
{
  "to": "sip:1001@192.168.1.100",
  "welcome_text": "Merhaba. Bilgi için 1'e basın."
}
```

#### Adım 1 — FastAPI isteği alır (`main.py`)

```
HTTP POST → /api/v1/call
```

FastAPI Pydantic ile isteği doğrular. `to` ve `welcome_text` alanlarını alır.

#### Adım 2 — TTS Pipeline başlar (`tts.py`)

```
"Merhaba. Bilgi için 1'e basın."
         │
         ▼
    piper --model tr-model.onnx
         │
         ▼
   /tmp/_piper_raw.wav   (22050 Hz, mono, WAV)
         │
         ▼
    ffmpeg -ac 1 -ar 8000 -acodec pcm_s16le
         │
         ▼
   /tmp/welcome.wav   (8000 Hz, mono, PCM 16-bit WAV)
```

- **Neden iki adım?** Piper çıktısı Baresip'in istediği formatta değil. FFmpeg zorunlu.
- **Neden `/tmp`?** Konteyner içinde kalıcı yazma alanı olmadığı için geçici dizin kullanıyoruz. Görüşme bitince dosyalar siliniyor.
- **Neden `/tmp/welcome.wav`?** Telefon açıldığında IVR modülü bu sabit ismi arayacak.

#### Adım 3 — Baresip'e dial komutu gönderilir (`baresip.py`)

```python
await baresip.send("dial", "sip:1001@192.168.1.100")
```

Bu kod şunu TCP soketine yazar:
```
41:{"command":"dial","params":"sip:1001@192.168.1.100"},
```

Bu format **Netstring** adıyla bilinir:
```
<içerik uzunluğu>:<JSON içerik>,
```

Baresip bu komutu aldığında gerçek SIP `INVITE` paketi göndererek telefonu çaldırmaya başlar.

#### Adım 4 — HTTP isteği burada döner

FastAPI şu anda cevap verir:
```json
{"status": "ok", "aranan": "sip:1001@192.168.1.100"}
```

Ses henüz çalmıyor. Telefon açılmayı bekliyor.

---

## 5. Telefon Açıldığında: Event Sistemi

Baresip arka planda sürekli olayları FastAPI'nin TCP soketine fırlatır.

#### Baresip'in Gönderdiği Örnek Olaylar:

```json
{"event": true, "type": "CALL_RINGING",     "id": "abc123"}
{"event": true, "type": "CALL_ESTABLISHED", "id": "abc123"}
{"event": true, "type": "CALL_DTMF_START",  "id": "abc123", "param": "1"}
{"event": true, "type": "CALL_CLOSED",      "id": "abc123"}
```

#### FastAPI bu olayları nasıl dinliyor?

`baresip.connect_loop()` fonksiyonu başlatma sırasında arka planda çalışır. Sürekli TCP soketini okur:

```
Baresip TCP:4444
      │
      │ (ham byte stream)
      ▼
  _parse_netstrings()
      │
      │ (JSON dict'ler)
      ▼
  ivr.handle_event()
      │
      ├── CALL_ESTABLISHED → welcome.wav çal
      ├── CALL_DTMF_START  → tuşa göre ses üret ve çal
      └── CALL_CLOSED      → geçici dosyaları temizle
```

#### Telefon açıldığında (`CALL_ESTABLISHED`):

```python
await baresip.send("ausrc", "aufile,/tmp/welcome.wav")
```

Bu komut Baresip'e şunu söyler:
> "Ses kaynağını değiştir. Artık mikrofondan değil, bu WAV dosyasından oku."

Baresip `/tmp/welcome.wav`'ı okur ve RTP paketleri halinde karşı tarafa gönderir. Karşı taraftaki kişi sesi duyar.

---

## 6. DTMF: Tuş Takibi

Kullanıcı telefonundan `1` tuşuna bastığında:

1. Karşı SIP sunucusu/Baresip bu RFC 4733 RTP event'ini alır.
2. Baresip TCP soketine şunu yazar:
   ```json
   {"event": true, "type": "CALL_DTMF_START", "param": "1", "id": "abc123"}
   ```
3. FastAPI bu olayı yakalar → `ivr.py/on_dtmf()` çağrılır.
4. `ivr.DTMF_MENU["1"]` metnini alır.
5. Bu metni `tts.text_to_wav()` ile `/tmp/dtmf_1.wav`'a çevirir.
6. Baresip'e `/tmp/dtmf_1.wav`'ı çalmasını emreder.
7. Kullanıcı yeni sesi duyar.

**Yeni bir tuş eklemek için tek yapmanız gereken `ivr.py`'daki `DTMF_MENU` sözlüğüne satır eklemek:**

```python
DTMF_MENU = {
    "1": "Birinci seçenek.",
    "2": "İkinci seçenek.",
    "3": "Yeni eklediğiniz üçüncü seçenek.",  # ← sadece bu kadar
}
```

---

## 7. Ses Dosyası Akışı: Nereye Yazılıyor, Nereden Okunuyor?

```
/tmp/
  ├── _piper_raw.wav    → Piper'ın ham çıktısı (geçici, hemen silinir)
  ├── welcome.wav       → Karşılama sesi (telefon açılınca çalınır)
  ├── dtmf_1.wav        → 1 tuşuna basıldığında çalınan ses
  ├── dtmf_2.wav        → 2 tuşuna basıldığında çalınan ses
  └── dynamic.wav       → /api/v1/play endpoint'inden gelen dinamik ses
```

- **Baresip bu dosyaları nasıl okuyor?**  
  `ausrc aufile,/tmp/welcome.wav` komutuyla. Baresip `aufile` modülü ile WAV dosyasını açar, örnekleri okur ve RTP paketlerine çevirir.

- **Dosyalar ne zaman siliniyor?**  
  Görüşme kapandığında (`CALL_CLOSED` olayı) `ivr.py/_on_call_ended()` çağrılır ve `/tmp/*.wav` dosyaları temizlenir.

- **İki eş zamanlı arama olursa ne olur?**  
  Şu anki tasarım tek eş zamanlı arama için optimize edilmiştir. Dosya isimleri sabit olduğu için iki arama çakışırsa üzerine yazılır. Çok eş zamanlı arama gerekirse call_id bazlı dizin yapısı (`/tmp/{call_id}/welcome.wav`) eklenmeli.

---

## 8. Netstring Protokolü: Neden Var?

TCP bir byte akışıdır, mesaj sınırları yoktur. İki JSON mesajı art arda gelebilir ve hepsi tek bir `read()` çağrısında birleşik gelir:

```
37:{"type":"CALL_RINGING"},42:{"type":"CALL_ESTABLISHED"},
```

Netstring bu sorunu çözer: Her mesajın başına uzunluk yazar. Böylece tam olarak nerede biteceğini biliriz. `baresip.py/_parse_netstrings()` fonksiyonu bu ayrıştırmayı yapar.

---

## 9. Platform Desteği: macOS ve Linux

Docker imajı `linux/amd64` (x86_64 sunucular) ve `linux/arm64` (Apple M-serisi) mimarilerini destekler. Piper binary'si Dockerfile içindeki `ARG TARGETARCH` değişkeniyle otomatik seçilir:

```dockerfile
ARG TARGETARCH
RUN if [ "${TARGETARCH}" = "arm64" ]; then \
        PIPER_FILE="piper_linux_aarch64.tar.gz"; \
    else \
        PIPER_FILE="piper_linux_x86_64.tar.gz"; \
    fi && ...
```

- **macOS Intel (x86_64):** `piper_linux_x86_64.tar.gz` indirilir.
- **macOS M1/M2/M3/M4 (ARM64):** `piper_linux_aarch64.tar.gz` indirilir.
- **Linux AMD64:** `piper_linux_x86_64.tar.gz` indirilir.

> **Not:** Docker Desktop (macOS) `linux/arm64` platform bilgisini otomatik iletir. Ayrıca bir şey yapmanıza gerek yoktur.

---

## 10. Baresip Yapılandırması: Kritik Ayarlar

```
audio_source  aufile,/tmp/playback.wav  → başlangıç ses kaynağı (dummy)
audio_player  null,                     → hoparlör yok (headless)
audio_alert   null,                     → zil sesi yok (headless)
ctrl_tcp_listen 127.0.0.1:4444          → sadece lokal erişim
rtp_ports     40000-40100               → ses portları (firewall için belirgin)
```

- **Neden `audio_player null`?** Konteyner içinde ses kartı yok. Gelen sesi dinlememize gerek yok; sadece gönderiyoruz.
- **Neden `ctrl_tcp_listen 127.0.0.1`?** Güvenlik. Dışarıdan doğrudan Baresip'e komut gönderilmesini engeller. Yalnızca aynı konteynerdeki FastAPI erişebilir.

---

## 11. Proje Yapısı

```
bareSIP/
  ├── Dockerfile            → İmaj tanımı (araçlar burada; kullanıcı verisi YOK)
  ├── docker-compose.yml    → Servis çalıştırma + bind mount tanımları
  ├── entrypoint.sh         → Baresip + FastAPI başlatma sırası
  ├── download_voices.sh    → Ses modellerini host'a indiren betik
  ├── config                → Baresip yapılandırması   ← bind mount
  ├── accounts              → SIP hesap bilgileri      ← bind mount
  ├── voices/               → Piper ses modelleri      ← bind mount
  │     ├── tr-model.onnx
  │     └── tr-model.onnx.json
  └── app/                  → Python kodu              ← bind mount
        ├── __init__.py
        ├── main.py         → FastAPI endpoint'leri
        ├── baresip.py      → TCP soket + komut gönderme
        ├── tts.py          → Piper + FFmpeg pipeline
        └── ivr.py          → IVR menü ve event mantığı
```

**Nereye ne eklerim?**

| Yapmak İstediğim | Değiştireceğim Dosya |
|---|---|
| Yeni DTMF tuşu eklemek | `app/ivr.py` → `DTMF_MENU` sözlüğü |
| Yeni API endpoint'i açmak | `app/main.py` |
| Ses formatını değiştirmek | `app/tts.py` → `_run_ffmpeg()` argümanları |
| Farklı TTS modeli kullanmak | `app/tts.py` → `VOICE_MODEL` sabiti |
| Baresip'e farklı komut göndermek | `app/baresip.py` → `send()` fonksiyonu |
| Yeni Baresip olayı işlemek | `app/ivr.py` → `handle_event()` |
| Yeni ses modeli eklemek | `./download_voices.sh` içine URL ekle |

---

## 12. Anonim İmaj Mimarisi

Bu projenin en önemli tasarım kararlarından biridir.

### Felsefe

> **Container içinde hiçbir kullanıcı verisi bulunmaz.**

İmajı build ettikten sonra ona bir daha dokunmazsınız. Konfigürasyonunuz, kodunuz, ses modelleriniz, SIP kimlik bilgileriniz — hepsi **host makinenizde** durur ve Docker Compose aracılığıyla konteynere **salt okunur (`:ro`)** olarak bağlanır.

### Ne İmajın İçindedir, Ne Dışındadır?

| İmaj İçinde (Sabit) | Host'ta (Değişken) |
|---|---|
| Baresip ikili dosyası | `app/` Python kodu |
| Piper ikili dosyası | `voices/` ses modelleri |
| FFmpeg | `config` Baresip ayarları |
| Python + venv + FastAPI | `accounts` SIP bilgileri |
| `entrypoint.sh` | — |

### Avantajları

**Kararlılık:** İmaj build edildikten sonra değişmez. Yanlışlıkla container içinde bir şeyleri bozma riski yoktur.

**Güvenlik — Anonimlik:** İmajı birisine verseydiniz ya da bir registry'ye itseydiniz, içinde SIP şifreniz, hesap bilgileriniz veya özel IVR mantığınız **bulunmaz**. İmaj sadece genel amaçlı araçlardan oluşur.

**Esneklik:** Kodu değiştirmek için `docker-compose restart` yeterlidir; `docker-compose build` gerekmez. Kodu düzenleyin → konteyneri yeniden başlatın → değişiklikler aktif olur.

**Taşınabilirlik:** İmajı her ortamda kullanabilirsiniz. Farklı SIP sunucusu, farklı IVR menüsü, farklı ses modeli — hepsi sadece mount edilen dosyalarda yapılan değişiklikle sağlanır.

### Değişiklik → Etki Tablosu

| Ne Değiştirdiniz? | Ne Yapmanız Gerekiyor? |
|---|---|
| `app/ivr.py` (DTMF menüsü) | `docker-compose restart` |
| `app/tts.py` (ses ayarları) | `docker-compose restart` |
| `config` (Baresip ayarları) | `docker-compose restart` |
| `accounts` (SIP bilgileri) | `docker-compose restart` |
| `voices/` (yeni ses modeli) | `docker-compose restart` |
| `Dockerfile` veya `entrypoint.sh` | `docker-compose build && docker-compose up -d` |

---

## 13. Ses Anahtar Kelimeleri (Voice Keywords)

API'ye gelen her istekte hangi sesin kullanılacağı `voice` alanıyla belirtilir.
Bu tablo, sisteme yüklü tüm sesleri ve anahtar kelimelerini gösterir.

### Mevcut Sesler

| Keyword | Dil | Cinsiyet | Sesçi / Model | Dosya (voices/) |
|---|---|---|---|---|
| `fettah` | Türkçe | Erkek | Fettah — speaches-ai/piper-tr_TR-fettah-medium | `tr-fettah.onnx` |
| `eren` | Türkçe | Erkek | Eren — 99eren99/piper-turkish-tts | `tr-eren.onnx` |
| `cem` | Türkçe | Erkek | Cem — dcx514ai/piper_tts_turkish_high ¹ | `tr-cem.onnx` |
| `hfc_male` | İngilizce | Erkek | HFC Male — rhasspy/piper-voices hfc_male medium | `en-hfc-male.onnx` |
| `hfc_female` | İngilizce | Kadın | HFC Female — rhasspy/piper-voices hfc_female medium | `en-hfc-female.onnx` |

> ¹ **Cem modeli gated repo'dadır.** `download_voices.sh` çalıştırıldığında geçici
> olarak Fettah kopyalanır. Gerçek modeli indirmek için HuggingFace hesabıyla
> `dcx514ai/piper_tts_turkish_high` reposuna erişim izni almanız gerekir.

### API Kullanım Örnekleri

**Çağrı başlatmak:**
```bash
# Türkçe Erkek - Fettah
curl -X POST http://localhost:8080/api/v1/call \
  -H "Content-Type: application/json" \
  -d '{"to": "sip:1001@192.168.1.1", "welcome_text": "Merhaba!", "voice": "fettah"}'

# Türkçe Erkek - Eren
curl -X POST http://localhost:8080/api/v1/call \
  -d '{"to": "sip:1001@192.168.1.1", "welcome_text": "Merhaba!", "voice": "eren"}' \
  -H "Content-Type: application/json"

# İngilizce Kadın - HFC Female
curl -X POST http://localhost:8080/api/v1/call \
  -H "Content-Type: application/json" \
  -d '{"to": "sip:1001@192.168.1.1", "welcome_text": "Hello!", "voice": "hfc_female"}'
```

**Aktif çağrıda metin seslendirmek:**
```bash
curl -X POST http://localhost:8080/api/v1/play \
  -H "Content-Type: application/json" \
  -d '{"text": "Your appointment is confirmed.", "voice": "hfc_male"}'
```

**Mevcut sesleri listelemek:**
```bash
curl http://localhost:8080/api/v1/status
# Dönen yanıt:
# {
#   "baresip_bagli": true,
#   "aktif_ses": "fettah",
#   "mevcut_sesler": [
#     {"keyword": "fettah",     "dosya": "/app/voices/tr-fettah.onnx"},
#     {"keyword": "eren",       "dosya": "/app/voices/tr-eren.onnx"},
#     {"keyword": "cem",        "dosya": "/app/voices/tr-cem.onnx"},
#     {"keyword": "hfc_male",   "dosya": "/app/voices/en-hfc-male.onnx"},
#     {"keyword": "hfc_female", "dosya": "/app/voices/en-hfc-female.onnx"}
#   ]
# }
```

### Yeni Ses Eklemek

1. **Ses modelini indirin** (`voices/` dizinine `.onnx` ve `.onnx.json` dosyaları)
2. **`app/tts.py`** içindeki `MODELS` sözlüğüne yeni satır ekleyin:
   ```python
   "yeni_ses": "/app/voices/yeni-model.onnx",
   ```
3. **`docker-compose restart`** — rebuild gerekmez.

### DTMF Seçeneğine Özel Ses Atamak

`app/ivr.py` içindeki `DTMF_MENU` sözlüğünde her tuşa farklı bir ses atayabilirsiniz:

```python
DTMF_MENU = {
    "1": {"text": "Türkçe yanıt.",        "voice": "eren"},       # Bu tuşta Eren konuşur
    "2": {"text": "English response.",    "voice": "hfc_female"}, # Bu tuşta HFC Female konuşur
    "9": {"text": "Ana menü.",            "voice": ""},           # Boş = çağrının sesi kullanılır
}
```

