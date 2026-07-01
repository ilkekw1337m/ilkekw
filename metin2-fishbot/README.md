# Metin2 Balık Botu (Gelişmiş)

Görüntü işleme tabanlı, **sadece ekran görüntüsü** kullanan gelişmiş bir Metin2
balık botu. Oyun belleğine **dokunmaz** (enjeksiyon/hafıza okuma yok), bu yüzden
sunucudan bağımsız ve anti-cheat riski düşüktür. Hem **eski "at-bekle-vur"
sistemini** hem de **yeni yapboz (jigsaw) minigame'ini** destekler; istenmeyen
balıkları otomatik **yaktırabilir/atabilir** ve admin/şüpheli mesajlarına
**yapay zekâ (Claude API)** ile insansı yanıt verebilir.

> ⚠️ **Uyarı (ToS / eğitim):** Oyun botu kullanmak çoğu oyunun kullanım
> koşullarını ihlal eder ve hesap yasağına yol açabilir. Bu proje
> **eğitim/araştırma** amaçlıdır; kullanımı tamamen sizin sorumluluğunuzdadır.

## Özellikler

- **Görüntü işleme** (OpenCV `matchTemplate` + HSV) ile tespit — bellek okuma yok.
- **Pencere yakalama**: Windows'ta Win32 `BitBlt` (arka plandaki pencereyi bile
  yakalar), Linux/test için `mss`. Arayüz arkasına soyutlanmıştır.
- **İki balık sistemi**: eski strike döngüsü + yeni jigsaw çözücü (greedy, delik
  minimize eden heuristik).
- **İnsansı girdi**: `pydirectinput` (DirectX uyumlu) + gaussian gecikme/jitter,
  rastgele tık noktası, anti-spam cooldown.
- **Güvenlik**: F6 acil durdurma, maks süre/eylem limiti, periyodik mola,
  detect-before-action, **kuru çalışma (dry-run)** modu.
- **Balık seçimi + yaktırma**: web'den indirilen balık ikon kataloğu; GUI'den
  her balık için *tut/yaktır* seçimi; yapılandırılabilir imha eylemi.
- **Sohbet AI aracı**: sohbet bölgesini OCR ile okur, GM/whisper mesajını
  algılar, Claude API ile kısa/insansı yanıt üretip yazar (opsiyonel, kapalı).
- **Telegram uzaktan kontrol + bildirim**: telefondan `/start /stop /pause /resume
  /status /screenshot /dryrun` komutları; captcha / GM mesajı / bot-durdu-hata
  bildirimleri. Yalnız yetkili `chat_id`'ler komut verebilir (opsiyonel, kapalı).
- **Captcha tespiti**: kalibre edilmiş captcha şablonu varsa bot duraklar ve
  (Telegram açıksa) size ekran görüntüsüyle haber verir; siz çözüp `/resume` dersiniz.
- **CustomTkinter GUI**: sekmeli arayüz + canlı log + sürükle-bırak kalibrasyon.

## Kurulum

```bash
pip install -r requirements.txt
```

Ek gereksinimler:

- **Tesseract-OCR** (sohbet AI'nin OCR'ı için): Windows için
  [UB-Mannheim derlemesi](https://github.com/UB-Mannheim/tesseract/wiki);
  Linux: `apt install tesseract-ocr`.
- **GUI** için Tkinter: Linux'ta `apt install python3-tk` (Windows'ta Python ile
  birlikte gelir).
- **Claude API anahtarı** (sohbet AI için): [console.anthropic.com](https://console.anthropic.com)
  → `ANTHROPIC_API_KEY` env değişkenine koyun ya da GUI'deki gizli alana girin.

## Çalıştırma

```bash
# GUI
python -m metin2fishbot.main

# Belirli bir kalibrasyon profiliyle
python -m metin2fishbot.main --profile my_server

# Başsız kuru-çalışma (tespit/karar zincirini loglar, girdi göndermez)
python -m metin2fishbot.main --no-gui
```

(`src/` dizini `PYTHONPATH`'te olmalı ya da `pip install -e .` ile paketi kurun.)

## Hızlı Başlangıç

1. Oyunu **pencereli** modda, sabit çözünürlükte açın; olta yemini ve balık
   becerisini hotkey'lere atayın (varsayılan: yem `2`, atış `1`).
2. Balık ikonlarını indirin ve kataloğu oluşturun:
   ```bash
   python tools/fetch_fish_images.py
   ```
   (Ağ engelliyse `--no-download` ile sadece katalog JSON'u yazılır; ikonları
   sonra elle ekleyebilirsiniz.)
3. GUI'yi açın → **Kalibrasyon** sekmesinde `board / bite / inventory / chat`
   bölgelerini ekrana sürükleyerek seçin → **Profili Kaydet**.
4. Şablon görüntülerini yakalayın (strike işareti, minigame saati vb.):
   ```bash
   python tools/template_capture.py --region 400 250 48 48 \
       --out assets/templates/strike.png
   ```
5. **Balık** sekmesinde sistemi seçin, önce **kuru çalışma** ile test edin,
   sonra kapatıp gerçek modda kısa bir oturum deneyin. **F6** her an durdurur.

## Proje Yapısı

```
src/metin2fishbot/
  core/        capture, input_controller, vision, config, events
  detection/   bite_detector, puzzle_detector, state_detector
  solver/      pieces, puzzle_solver  (greedy jigsaw çözücü)
  fish/        catalog, recognizer, disposer, manager
  chat/        chat_detector(OCR), ai_responder(Claude), chat_writer, watcher
  bot/         state_machine, fishing_bot
  remote/      controller (yaşam döngüsü), telegram (uzaktan kontrol/bildirim)
  safety/      guards (acil durdurma, limitler, molalar)
  gui/         app, fish_picker, chat_panel, telegram_panel, calibration, widgets
tools/         fetch_fish_images.py, template_capture.py
tests/         pytest (solver, vision, fish, chat, bot)
config/        default_config.yaml + profiles/
```

## Yapılandırma

Tüm ayarlar `config/default_config.yaml` içinde; sunucu/çözünürlük başına
`config/profiles/<ad>.yaml` ile üzerine yazılır. Önemli anahtarlar:

- `runtime.dry_run` — `true` iken hiçbir girdi gönderilmez (güvenli test).
- `fishing.system` — `auto | old | new`.
- `regions.*` — kalibrasyondan gelen `[x, y, w, h]` bölgeler.
- `fish.enabled`, `fish.dispose_action` — yaktırma (`log` varsayılan = güvenli).
- `chat_ai.enabled`, `chat_ai.model`, `chat_ai.persona` — sohbet AI aracı.

## Sohbet AI Aracı Hakkında

Admin/GM veya başka biri whisper attığında, bot sohbet bölgesini OCR ile okur,
mesajı Claude API'ye gönderir ve oyuncu kimliğine bürünen kısa bir yanıt yazar.
Maliyet/aşırı kullanım için yanıt cooldown'u ve sayı limiti vardır; varsayılan
olarak **kapalıdır** ve yalnızca siz API anahtarı sağlayıp etkinleştirirseniz
çalışır.

## Telegram Uzaktan Kontrol

Botu telefonunuzdan izleyip yönetmek için:

1. Telegram'da **@BotFather**'a `/newbot` yazıp bir bot oluşturun, verilen
   **token**'ı alın.
2. GUI → **Telegram** sekmesi: token'ı girin (veya `TELEGRAM_BOT_TOKEN` env
   değişkenine koyun), etkinleştirin, **Uygula**.
3. Oluşturduğunuz bota Telegram'dan `/start` yazın. Yetkili değilseniz bot size
   `chat_id`'nizi döndürür; bu id'yi **Yetkili chat_id'ler** alanına ekleyip tekrar
   **Uygula** deyin. (Yalnız bu id'ler komut verebilir — güvenlik için zorunlu.)
4. Botu **Başlat**. Artık telefondan:
   `/status` (durum+istatistik), `/screenshot`, `/pause`, `/resume`, `/stop`,
   `/dryrun on|off`, `/help`.

**Bildirimler:** captcha algılanınca (ekran görüntüsüyle), GM/whisper mesajı
gelince (+AI yanıtı) ve bot durunca/hata olunca telefonunuza düşer. Hangi
bildirimlerin gönderileceğini Telegram sekmesinden seçebilirsiniz.

**GUI olmadan (headless):** `telegram.enabled: true` ve token/chat_id ayarlıyken
`python -m metin2fishbot.main --no-gui` botu Telegram köprüsüyle başlatır; her şeyi
telefondan yönetirsiniz.

> Ağır bir kütüphane kullanılmaz — Telegram Bot HTTP API'si doğrudan `requests` ile
> (long-polling) çağrılır.

## Testler

```bash
pytest
```

Testler Linux'ta başsız çalışır: çözücü mantığı, görüntü tespiti (fixture'lı),
balık tanıma/yaktırma kararı ve sohbet AI çağrı yapısı (mock client) doğrulanır;
gerçek API çağrısı veya ekran gerekmez.
