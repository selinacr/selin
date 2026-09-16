# Yayın Paneli — masaüstü uygulaması

Claude'da barındırılan yayın panelini kendi penceresinde açan küçük bir Electron
uygulaması. Veriler panelde (Claude tarafında) durduğu için masaüstü sürümü ile
tarayıcı sürümü aynı veriyi gösterir; link paylaşımı da bozulmaz.

## Hazır .exe indirmek (kurulum gerektirmeyen yol)

1. GitHub'da bu deponun **Actions** sekmesini açın.
2. "Masaüstü uygulaması (Windows)" iş akışının en son başarılı çalışmasına girin.
3. Sayfanın altındaki **YayinPaneli-windows** dosyasını indirin, zip'i açın.
4. İçinden çıkan iki dosyadan birini kullanın:
   - `YayinPaneli-tasinabilir-1.0.0.exe` — kurulum yok, çift tıklayınca açılır.
   - `Yayin Paneli Setup 1.0.0.exe` — kurar ve masaüstüne kısayol ekler.

İlk açılışta Claude hesabınıza bir kez giriş yaparsınız; oturum saklandığı için
sonraki açılışlarda doğrudan panel gelir.

## Kaynaktan çalıştırmak (geliştirme)

Node.js 20+ gerekir:

    cd yayin-paneli-masaustu
    npm install
    npm start

Windows kurulum dosyalarını yerel olarak üretmek için: `npm run dist`
(çıktı `dist/` klasörüne yazılır).

## Panel adresi değişirse

`main.js` içindeki `PANEL_ADRESI` sabitini güncelleyin ya da uygulamayı
`YAYIN_PANELI_URL` ortam değişkeni ile çalıştırın.
