# Yayın Paneli — masaüstü uygulaması

Yerel panel servisini (`python -m yayin_paneli.servis`) kendi penceresinde açan küçük
bir Electron uygulaması. Tarayıcı sekmesi yerine ayrı bir uygulama penceresi ister
diye var; veriler aynı yerde durduğu için iki yol da aynı paneli gösterir.

**Önce servis çalışmalı.** Uygulama <http://127.0.0.1:8787/> adresine bağlanır:
`yayin-paneli-python` klasöründe `baslat_panel.command` (macOS) ya da
`baslat_panel.bat` (Windows). Servis kapalıyken uygulama "bağlanılamadı" ekranı
gösterir ve **Yeniden dene** düğmesi sunar.

## Hazır dosyayı indirmek

1. GitHub'da bu deponun **Actions** sekmesini açın.
2. "Masaüstü uygulaması (Windows + macOS)" iş akışının en son başarılı çalışmasına girin.
3. Sayfanın altındaki artifact'lardan işletim sisteminize uyanı indirin:
   - **YayinPaneli-macos** → `YayinPaneli-1.0.0-mac.dmg` (Intel + Apple Silicon ortak)
   - **YayinPaneli-windows** → taşınabilir `.exe` ya da kurulumlu `Setup .exe`

### macOS'ta ilk açılış

Uygulama Apple geliştirici sertifikasıyla imzalanmadığı için macOS ilk açılışta
engeller. Tek seferlik:

1. `.dmg` dosyasını açın, **Yayin Paneli** uygulamasını `Applications` klasörüne sürükleyin.
2. Uygulamaya **sağ tık → Aç**, çıkan uyarıda yine **Aç** deyin.
   (Çift tıklamak bu ilk seferde çalışmaz; sonraki açılışlarda çalışır.)
3. Sistem Ayarları → Gizlilik ve Güvenlik altında "yine de aç" seçeneği de çıkabilir.

## Kaynaktan çalıştırmak

Node.js 20+ gerekir:

```
cd yayin-paneli-masaustu
npm install
npm start
```

Paket üretmek: Windows için `npm run dist`, macOS için `npm run dist:mac`
(çıktı `dist/` klasörüne yazılır). macOS paketi yalnızca bir Mac'te üretilebilir.

## Panel adresi değişirse

`main.js` içindeki `PANEL_ADRESI` sabitini güncelleyin ya da uygulamayı
`YAYIN_PANELI_URL` ortam değişkeni ile çalıştırın:

```
YAYIN_PANELI_URL=http://127.0.0.1:9000/ npm start
```
