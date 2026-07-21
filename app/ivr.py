"""
ivr.py — IVR Akış Yönetimi Modülü
===================================
Baresip'ten gelen olayları dinler ve sesi yönetir.

Desteklenen Olaylar:
  CALL_ESTABLISHED  → Telefon açıldı, karşılama sesini çal
  CALL_DTMF_START   → Kullanıcı tuşa bastı, tuşa göre ses üret ve çal
  CALL_CLOSED       → Görüşme bitti, geçici dosyaları temizle

Yeni DTMF senaryosu eklemek için yalnızca DTMF_MENU sözlüğünü düzenleyin.
"""

import os
import app.baresip as baresip
import app.tts as tts

# ─── Aktif Çağrı Ses Tercihi ──────────────────────────────────────────────────
# Çağrı başlatılırken main.py tarafından set_voice() ile ayarlanır.
current_voice = tts.DEFAULT_VOICE  # Varsayılan ses


def set_voice(voice: str) -> None:
    """Çağrının ses tercihini ayarlar. main.py tarafından çağrılır."""
    global current_voice
    current_voice = voice
    print(f"[IVR] Aktif ses ayarlandı: '{voice}'")


# ─── IVR Menü Tanımları ───────────────────────────────────────────────────────
# Hangi DTMF tuşuna basıldığında ne söyleneceğini buraya ekleyin.
# "voice" alanı boş bırakılırsa çağrının sesi (current_voice) kullanılır.

DTMF_MENU = {
    "1": {"text": "Bir tuşuna bastınız. Bilgi menüsünü seçtiniz.",          "voice": ""},
    "2": {"text": "İki tuşuna bastınız. Operatöre bağlanıyorsunuz.",        "voice": ""},
    "9": {"text": "Dokuz tuşuna bastınız. Ana menüye dönülüyor.",           "voice": ""},
    "#": {"text": "Kare tuşuna bastınız. İşlem tamamlandı. Güle güle.",    "voice": ""},
}

# Menüde olmayan tuş için söylenecek metin
UNKNOWN_KEY = {"text": "Geçersiz tuş. Lütfen menüden bir seçenek seçin.", "voice": ""}

TMP_DIR = "/tmp"


# ─── Olay İşleyici ────────────────────────────────────────────────────────────

async def handle_event(event: dict) -> None:
    """
    Baresip'ten gelen her JSON olayını işler.
    baresip.connect_loop() tarafından her yeni event'te çağrılır.
    """
    # Sadece event=true olan mesajlarla ilgileniyoruz
    if not event.get("event"):
        return

    event_type = event.get("type", "")
    call_id    = event.get("id", "?")
    param      = event.get("param", "")

    print(f"[IVR] Olay: {event_type} | Çağrı: {call_id} | Param: {param}")

    if event_type == "CALL_ESTABLISHED":
        await _on_call_answered(call_id)

    elif event_type == "CALL_DTMF_START":
        await _on_dtmf(call_id, digit=param)

    elif event_type == "CALL_CLOSED":
        _on_call_ended(call_id)


# ─── Senaryo Fonksiyonları ────────────────────────────────────────────────────

async def _on_call_answered(call_id: str) -> None:
    """Telefon açıldığında karşılama sesini çalar."""
    welcome_wav = f"{TMP_DIR}/welcome.wav"

    if not os.path.exists(welcome_wav):
        print("[IVR] Karşılama dosyası bulunamadı.")
        return

    print(f"[IVR] Telefon açıldı ({call_id}). Karşılama sesi çalınıyor.")
    await baresip.send("ausrc", f"aufile,{welcome_wav}")


async def _on_dtmf(call_id: str, digit: str) -> None:
    """Kullanıcı DTMF tuşuna bastığında ilgili sesi üretir ve çalar."""
    print(f"[IVR] DTMF: '{digit}' (Çağrı: {call_id})")

    # Menüde var mı? Yoksa bilinmeyen tuş mesajı
    secenek = DTMF_MENU.get(digit, UNKNOWN_KEY)
    metin   = secenek["text"]
    # Seçenekte özel bir ses belirtilmişse onu, yoksa aktif çağrının sesini kullan
    voice   = secenek["voice"] or current_voice

    ses_dosyasi = f"{TMP_DIR}/dtmf_{digit}.wav"
    await tts.text_to_wav(metin, ses_dosyasi, voice=voice)
    await baresip.send("ausrc", f"aufile,{ses_dosyasi}")


def _on_call_ended(call_id: str) -> None:
    """Görüşme bittiğinde geçici ses dosyalarını siler."""
    print(f"[IVR] Görüşme bitti ({call_id}). Temizlik yapılıyor.")

    temizlenecekler = [
        f"{TMP_DIR}/welcome.wav",
        f"{TMP_DIR}/_piper_raw.wav",
    ]

    # DTMF dosyaları
    for key in list(DTMF_MENU.keys()) + ["unknown", "dynamic"]:
        temizlenecekler.append(f"{TMP_DIR}/dtmf_{key}.wav")

    for path in temizlenecekler:
        if os.path.exists(path):
            try:
                os.remove(path)
                print(f"[IVR] Silindi: {path}")
            except Exception as e:
                print(f"[IVR] Silinemedi {path}: {e}")
