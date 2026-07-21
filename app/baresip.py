"""
baresip.py — Baresip TCP Kontrol Soketi Modülü
===============================================
Bu modül Baresip'in ctrl_tcp arayüzüne bağlanır.

Baresip, komutları ve olayları "netstring" formatında iletir.
Netstring formatı şudur:  <uzunluk>:<JSON içerik>,
Örnek: 37:{"command":"dial","params":"sip:1@x"},

Bu modül:
  - Bağlantıyı kurar ve kopunca otomatik yeniden bağlanır
  - Gelen mesajları netstring'den JSON'a çözer
  - Komutları JSON'dan netstring'e çevirip Baresip'e yollar
  - Gelen olayları (event) dışarıya aktarmak için bir callback alır
"""

import asyncio
import json

# ─── Ayarlar ────────────────────────────────────────────────────────────────

BARESIP_HOST = "127.0.0.1"
BARESIP_PORT = 4444
RECONNECT_DELAY_SEC = 2  # Bağlantı koparsa kaç saniye bekle


# ─── Durum ──────────────────────────────────────────────────────────────────

# writer: asyncio akış nesnesi — komut göndermek için kullanılır
# None ise Baresip'e henüz bağlanılmamış demektir
writer = None


# ─── Komut Gönderme ─────────────────────────────────────────────────────────

async def send(command: str, params: str = "") -> bool:
    """
    Baresip'e bir komut gönderir.
    Kullanım:
      await baresip.send("dial", "sip:1001@192.168.1.1")
      await baresip.send("ausrc", "aufile,/tmp/ses.wav")
      await baresip.send("hangup")
    """
    global writer

    if writer is None:
        print("[Baresip] HATA: Soket bağlı değil, komut gönderilemedi.")
        return False

    # JSON payload oluştur
    payload = json.dumps({"command": command, "params": params})

    # Netstring formatına çevir: <uzunluk>:<payload>,
    netstring = f"{len(payload)}:{payload},"

    try:
        writer.write(netstring.encode("utf-8"))
        await writer.drain()
        print(f"[Baresip] >> Komut gönderildi: {payload}")
        return True
    except Exception as e:
        print(f"[Baresip] HATA: Komut gönderilemedi: {e}")
        return False


# ─── Netstring Çözücü ───────────────────────────────────────────────────────

def _parse_netstrings(buffer: bytes) -> tuple[list[str], bytes]:
    """
    Ham byte buffer'ından netstring mesajlarını çıkarır.
    Eksik veri varsa buffer'da bırakır, bir sonraki okumada birleşir.

    Dönüş: (tamamlanan mesajlar listesi, kalan buffer)
    """
    messages = []

    while b":" in buffer:
        # Baştaki sayıyı bul (mesajın uzunluğu)
        colon_idx = buffer.index(b":")

        try:
            length = int(buffer[:colon_idx].decode("ascii"))
        except ValueError:
            # Bozuk veri — buffer'ı temizle
            print("[Baresip] Netstring bozuk, buffer temizlendi.")
            buffer = b""
            break

        # Toplam ihtiyaç: uzunluk_sayısı + ':' + içerik + ','
        total_needed = colon_idx + 1 + length + 1
        if len(buffer) < total_needed:
            break  # Henüz tam mesaj gelmedi, bekle

        # İçeriği çıkar
        content = buffer[colon_idx + 1 : colon_idx + 1 + length]
        trailer = buffer[colon_idx + 1 + length : colon_idx + 1 + length + 1]

        if trailer == b",":
            messages.append(content.decode("utf-8"))

        # Buffer'ı ilerlet
        buffer = buffer[total_needed:]

    return messages, buffer


# ─── TCP Bağlantı Döngüsü ───────────────────────────────────────────────────

async def connect_loop(on_event_callback):
    """
    Baresip'in TCP kontrol portuna sürekli bağlı kalmaya çalışır.
    Bağlantı koparsa otomatik yeniden bağlanır.

    on_event_callback(event: dict) — her yeni olay için çağrılır.
    """
    global writer

    while True:
        try:
            print(f"[Baresip] Bağlanılıyor {BARESIP_HOST}:{BARESIP_PORT}...")
            reader, writer = await asyncio.open_connection(BARESIP_HOST, BARESIP_PORT)
            print("[Baresip] Bağlantı kuruldu!")

            buffer = b""

            # Okuma döngüsü
            while True:
                data = await reader.read(4096)

                if not data:
                    print("[Baresip] Soket kapandı.")
                    break

                buffer += data
                messages, buffer = _parse_netstrings(buffer)

                for msg in messages:
                    try:
                        event = json.loads(msg)
                        await on_event_callback(event)
                    except json.JSONDecodeError:
                        print(f"[Baresip] JSON çözülemedi: {msg}")

        except Exception as e:
            print(f"[Baresip] Bağlantı hatası: {e}")

        # Bağlantı koptu — sıfırla ve yeniden dene
        writer = None
        print(f"[Baresip] {RECONNECT_DELAY_SEC} saniye sonra yeniden denenecek...")
        await asyncio.sleep(RECONNECT_DELAY_SEC)
