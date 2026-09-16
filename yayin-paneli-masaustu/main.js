const { app, BrowserWindow, Menu, shell } = require("electron");

// Panelin adresi. Panel başka bir artifact'a taşınırsa burayı ya da
// YAYIN_PANELI_URL ortam değişkenini güncellemek yeterli.
const PANEL_ADRESI =
  process.env.YAYIN_PANELI_URL || "https://claude.ai/artifact/3k8D6RZzcr8Ca2rB6kt4PW";

// Oturumun kalıcı olması için ayrı bir partition: bir kez giriş yapınca
// uygulama her açıldığında oturum açık gelir.
const BOLUM = "persist:yayin-paneli";

function pencereAc() {
  const pencere = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 420,
    minHeight: 560,
    title: "Yayın Paneli",
    backgroundColor: "#0f172a",
    autoHideMenuBar: true,
    webPreferences: {
      partition: BOLUM,
      contextIsolation: true,
      nodeIntegration: false,
      spellcheck: false,
    },
  });

  pencere.loadURL(PANEL_ADRESI);

  // Dış bağlantılar (yardım sayfaları, WoS vb.) varsayılan tarayıcıda açılsın;
  // Claude'un kendi alan adı uygulama içinde kalsın.
  const iceride = (adres) => {
    try {
      const alan = new URL(adres).hostname;
      return alan === "claude.ai" || alan.endsWith(".claude.ai") ||
        alan.endsWith(".anthropic.com") || alan === "accounts.google.com";
    } catch {
      return false;
    }
  };

  pencere.webContents.setWindowOpenHandler(({ url }) => {
    if (iceride(url)) return { action: "allow" };
    shell.openExternal(url);
    return { action: "deny" };
  });

  pencere.webContents.on("will-navigate", (olay, url) => {
    if (!iceride(url)) {
      olay.preventDefault();
      shell.openExternal(url);
    }
  });

  // Bağlantı kopukluğunda boş beyaz ekran yerine yeniden dene butonu.
  pencere.webContents.on("did-fail-load", (_olay, kod, aciklama, adres, anaCerceve) => {
    if (!anaCerceve || kod === -3) return;
    const metin = `Panele ulaşılamadı (${aciklama || kod}). İnternet bağlantınızı kontrol edip tekrar deneyin.`;
    pencere.webContents.loadURL(
      "data:text/html;charset=utf-8," +
        encodeURIComponent(
          `<!doctype html><meta charset="utf-8"><body style="margin:0;display:flex;align-items:center;justify-content:center;height:100vh;background:#0f172a;color:#e2e8f0;font:16px system-ui,sans-serif;text-align:center"><div><p style="max-width:34rem;line-height:1.6">${metin}</p><p style="font-size:13px;color:#94a3b8">${adres || PANEL_ADRESI}</p><button onclick="location.href='${PANEL_ADRESI}'" style="margin-top:12px;padding:10px 20px;border:0;border-radius:8px;background:#38bdf8;color:#0f172a;font-weight:600;cursor:pointer">Yeniden dene</button></div></body>`
        )
    );
  });

  return pencere;
}

function menuKur() {
  const menu = Menu.buildFromTemplate([
    {
      label: "Panel",
      submenu: [
        {
          label: "Yenile",
          accelerator: "CmdOrCtrl+R",
          click: (_o, pencere) => pencere && pencere.reload(),
        },
        {
          label: "Başlangıç sayfasına dön",
          click: (_o, pencere) => pencere && pencere.loadURL(PANEL_ADRESI),
        },
        { type: "separator" },
        { role: "zoomIn", label: "Yakınlaştır" },
        { role: "zoomOut", label: "Uzaklaştır" },
        { role: "resetZoom", label: "Normal boyut" },
        { type: "separator" },
        { role: "togglefullscreen", label: "Tam ekran" },
        { role: "quit", label: "Çıkış" },
      ],
    },
    {
      label: "Düzen",
      submenu: [
        { role: "undo", label: "Geri al" },
        { role: "redo", label: "Yinele" },
        { type: "separator" },
        { role: "cut", label: "Kes" },
        { role: "copy", label: "Kopyala" },
        { role: "paste", label: "Yapıştır" },
        { role: "selectAll", label: "Tümünü seç" },
      ],
    },
  ]);
  Menu.setApplicationMenu(menu);
}

// Tek örnek: ikinci kez çalıştırılınca yeni pencere yerine mevcut pencere öne gelir.
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  let anaPencere = null;

  app.on("second-instance", () => {
    if (!anaPencere) return;
    if (anaPencere.isMinimized()) anaPencere.restore();
    anaPencere.focus();
  });

  app.whenReady().then(() => {
    menuKur();
    anaPencere = pencereAc();

    app.on("activate", () => {
      if (BrowserWindow.getAllWindows().length === 0) anaPencere = pencereAc();
    });
  });

  app.on("window-all-closed", () => {
    if (process.platform !== "darwin") app.quit();
  });
}
