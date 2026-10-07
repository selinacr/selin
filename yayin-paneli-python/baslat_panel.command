#!/bin/bash
# macOS / Linux başlatıcı: yerel servisi çalıştırır ve paneli varsayılan tarayıcıda açar.
# Finder'da çift tıklanarak çalıştırılır (ilk kullanımdan önce: chmod +x baslat_panel.command).

set -u
cd "$(dirname "$0")" || exit 1

bul_python() {
  # Anaconda/Miniconda önce; sonra sistemdeki python3. macOS'ta "python" komutu
  # bulunmayabilir, bu yüzden python3 aranır.
  local aday
  for aday in \
    "${CONDA_PREFIX:-}/bin/python" \
    "$HOME/anaconda3/bin/python" \
    "$HOME/miniconda3/bin/python" \
    "$HOME/miniforge3/bin/python" \
    "/opt/homebrew/anaconda3/bin/python" \
    "/opt/anaconda3/bin/python" \
    "/opt/homebrew/bin/python3" \
    "/usr/local/bin/python3"
  do
    [ -x "$aday" ] && { printf '%s' "$aday"; return 0; }
  done
  command -v python3 2>/dev/null && return 0
  return 1
}

PY="$(bul_python)" || {
  echo "Python bulunamadı."
  echo "Kurulum: https://www.anaconda.com/download ya da 'brew install python'"
  read -r -p "Kapatmak için Enter'a basın..."
  exit 1
}

echo "Python: $PY"
echo "Gerekli paketler denetleniyor..."
"$PY" -m pip install -q -r requirements.txt || {
  echo "Paket kurulumu başarısız. Şunu deneyin:"
  echo "    $PY -m pip install --user -r requirements.txt"
  read -r -p "Kapatmak için Enter'a basın..."
  exit 1
}

# Servis açılır açılmaz tarayıcıyı aç; servis ön planda kalsın ki Ctrl+C ile durdurulabilsin.
( sleep 3
  if command -v open >/dev/null 2>&1; then open "http://127.0.0.1:8787/"
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "http://127.0.0.1:8787/"
  fi ) &

echo "Panel açılıyor: http://127.0.0.1:8787/  (durdurmak için Ctrl+C)"
exec "$PY" -m yayin_paneli.servis
