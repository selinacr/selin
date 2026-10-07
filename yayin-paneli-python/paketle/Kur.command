#!/bin/bash
# macOS kurulum yardımcısı.
#
# İnternetten indirilen ve Apple sertifikasıyla imzalanmamış uygulamalara macOS
# "karantina" bayrağı koyar ve açılmasını engeller. Bu betik o bayrağı kaldırır,
# uygulamayı Uygulamalar klasörüne taşır ve açar. Tek seferlik çalıştırılır.

set -u
cd "$(dirname "$0")" || exit 1

echo "Yayın Paneli — macOS kurulumu"
echo

# Zip'in yanındaki uygulamayı bul (zip içinden çıkan uygulama.zip de açılır).
if [ ! -d "Yayin Paneli.app" ] && [ -f "uygulama.zip" ]; then
  echo "Uygulama arşivi açılıyor..."
  ditto -x -k "uygulama.zip" . || unzip -oq "uygulama.zip"
fi

if [ ! -d "Yayin Paneli.app" ]; then
  echo "HATA: 'Yayin Paneli.app' bu klasörde bulunamadı."
  echo "Bu dosyayı uygulamayla aynı klasöre koyup tekrar çalıştırın."
  read -r -p "Kapatmak için Enter'a basın..."
  exit 1
fi

HEDEF="/Applications/Yayin Paneli.app"
echo "Uygulama Uygulamalar klasörüne taşınıyor..."
rm -rf "$HEDEF" 2>/dev/null
if ! cp -R "Yayin Paneli.app" "$HEDEF" 2>/dev/null; then
  echo "Uygulamalar klasörüne yazılamadı; uygulama bulunduğu yerden açılacak."
  HEDEF="$PWD/Yayin Paneli.app"
fi

echo "Karantina bayrağı kaldırılıyor..."
xattr -dr com.apple.quarantine "$HEDEF" 2>/dev/null
codesign --force --deep --sign - "$HEDEF" 2>/dev/null

echo "Uygulama açılıyor..."
open "$HEDEF"
echo
echo "Tamamdır. Bundan sonra uygulamaya doğrudan çift tıklayabilirsiniz:"
echo "  $HEDEF"
echo
read -r -p "Bu pencereyi kapatmak için Enter'a basın..."
