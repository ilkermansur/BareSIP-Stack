#!/bin/bash
# =============================================================================
# download_voices.sh — Piper TTS Ses Modellerini Host'a İndir
# =============================================================================
# Ses modelleri konteyner dışında host makinenize indirilir.
# İndirilen modeller docker-compose üzerinden /app/voices/ olarak mount edilir.
#
# Kullanım:
#   chmod +x download_voices.sh
#   ./download_voices.sh
# =============================================================================

set -e

VOICES_DIR="./voices"
HF_BASE="https://huggingface.co"
mkdir -p "$VOICES_DIR"

echo ""
echo "╔═══════════════════════════════════════════════════╗"
echo "║        Piper TTS Ses Modeli İndirici              ║"
echo "╚═══════════════════════════════════════════════════╝"
echo ""

# ─── Yardımcı Fonksiyon ──────────────────────────────────────────────────────
download_if_missing() {
    local url="$1"
    local dest="$2"
    local label="$3"

    if [ -f "$dest" ]; then
        echo "  ✓ $label zaten mevcut, atlanıyor."
    else
        echo "  ↓ $label indiriliyor..."
        curl -L --progress-bar "$url" -o "$dest"
        echo "  ✓ $label indirildi."
    fi
}

# ─── 1. Fettah (Türkçe Erkek) ────────────────────────────────────────────────
# keyword: "fettah"
# Kaynak : speaches-ai/piper-tr_TR-fettah-medium
echo "▶ [1/5] Fettah — Türkçe Erkek  (keyword: fettah)"
FETTAH_BASE="${HF_BASE}/speaches-ai/piper-tr_TR-fettah-medium/resolve/main"
download_if_missing "${FETTAH_BASE}/model.onnx"   "$VOICES_DIR/tr-fettah.onnx"      "tr-fettah.onnx"
download_if_missing "${FETTAH_BASE}/config.json"  "$VOICES_DIR/tr-fettah.onnx.json" "tr-fettah.onnx.json"
echo ""

# ─── 2. Eren (Türkçe Erkek) ──────────────────────────────────────────────────
# keyword: "eren"
# Kaynak : 99eren99/piper-turkish-tts
echo "▶ [2/5] Eren — Türkçe Erkek  (keyword: eren)"
EREN_BASE="${HF_BASE}/99eren99/piper-turkish-tts/resolve/main"
download_if_missing "${EREN_BASE}/model.onnx"   "$VOICES_DIR/tr-eren.onnx"      "tr-eren.onnx"
download_if_missing "${EREN_BASE}/config.json"  "$VOICES_DIR/tr-eren.onnx.json" "tr-eren.onnx.json"
echo ""

# ─── 3. Cem (Türkçe Erkek) ───────────────────────────────────────────────────
# keyword: "cem"
# Kaynak : dcx514ai/piper_tts_turkish_high  (GATED REPO — manuel giriş gerektirir)
#
# Bu model Hugging Face'te erişim izni gerektiriyor.
# İndirmek için:
#   1. https://huggingface.co/dcx514ai/piper_tts_turkish_high adresine gidin
#   2. Modeli kabul edin
#   3. "huggingface-cli login" ile giriş yapın
#   4. Dosyaları manuel indirin:
#      curl -H "Authorization: Bearer HF_TOKEN" \
#           "https://huggingface.co/dcx514ai/piper_tts_turkish_high/resolve/main/last.onnx" \
#           -o voices/tr-cem.onnx
#
# Şimdilik Cem için Fettah modeli kopyalanıyor (geçici fallback):
echo "▶ [3/5] Cem — Türkçe Erkek  (keyword: cem)  [Gated Repo — Fallback: Fettah]"
if [ -f "$VOICES_DIR/tr-cem.onnx" ]; then
    echo "  ✓ tr-cem.onnx zaten mevcut, atlanıyor."
else
    if [ -f "$VOICES_DIR/tr-fettah.onnx" ]; then
        cp "$VOICES_DIR/tr-fettah.onnx"      "$VOICES_DIR/tr-cem.onnx"
        cp "$VOICES_DIR/tr-fettah.onnx.json" "$VOICES_DIR/tr-cem.onnx.json"
        echo "  ⚠ Gerçek Cem modeli gated. Fettah kopyalandı (geçici fallback)."
        echo "  ℹ Gerçek modeli indirdikten sonra tr-cem.onnx ile değiştirin."
    else
        echo "  ✗ Fettah henüz indirilmedi. Önce Fettah adımını tamamlayın."
    fi
fi
echo ""

# ─── 4. HFC Male (İngilizce Erkek) ───────────────────────────────────────────
# keyword: "hfc_male"
# Kaynak : rhasspy/piper-voices (HFC — Hi-Fi Captain dataset)
echo "▶ [4/5] HFC Male — İngilizce Erkek  (keyword: hfc_male)"
HFC_MALE_BASE="${HF_BASE}/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/hfc_male/medium"
download_if_missing "${HFC_MALE_BASE}/en_US-hfc_male-medium.onnx"      "$VOICES_DIR/en-hfc-male.onnx"      "en-hfc-male.onnx"
download_if_missing "${HFC_MALE_BASE}/en_US-hfc_male-medium.onnx.json" "$VOICES_DIR/en-hfc-male.onnx.json" "en-hfc-male.onnx.json"
echo ""

# ─── 5. HFC Female (İngilizce Kadın) ─────────────────────────────────────────
# keyword: "hfc_female"
# Kaynak : rhasspy/piper-voices (HFC — Hi-Fi Captain dataset)
echo "▶ [5/5] HFC Female — İngilizce Kadın  (keyword: hfc_female)"
HFC_FEMALE_BASE="${HF_BASE}/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/hfc_female/medium"
download_if_missing "${HFC_FEMALE_BASE}/en_US-hfc_female-medium.onnx"      "$VOICES_DIR/en-hfc-female.onnx"      "en-hfc-female.onnx"
download_if_missing "${HFC_FEMALE_BASE}/en_US-hfc_female-medium.onnx.json" "$VOICES_DIR/en-hfc-female.onnx.json" "en-hfc-female.onnx.json"
echo ""

# ─── Özet ────────────────────────────────────────────────────────────────────
echo "════════════════════════════════════════════════════"
echo "✅ İndirme tamamlandı! voices/ dizini:"
ls -lh "$VOICES_DIR"
echo ""
echo "API'de kullanım:"
echo "  POST /api/v1/call  →  { \"voice\": \"fettah\" }"
echo "  POST /api/v1/call  →  { \"voice\": \"eren\" }"
echo "  POST /api/v1/call  →  { \"voice\": \"cem\" }"
echo "  POST /api/v1/call  →  { \"voice\": \"hfc_male\" }"
echo "  POST /api/v1/call  →  { \"voice\": \"hfc_female\" }"
echo ""
