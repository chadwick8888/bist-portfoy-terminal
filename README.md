# BIST Personal Terminal — gerçek veri motorlu sürüm

Bu sürüm önceki statik HTML değildir. Flask backend `/api/portfolio` üzerinden seçilen BIST veri servisine bağlanır; geçmiş OHLCV'den RSI, SMA20/50/200, MACD, hacim oranı ve momentum hesaplar; ardından AL/BEKLE/SAT skorlarını her yenilemede yeniden hesaplar.

## İnternete yayınlama
Render'a bu klasörü GitHub repo olarak yükleyip Web Service oluştur.
Build: `pip install -r requirements.txt`
Start: `gunicorn app:app`
Environment:
- `BIST_API_URL` = veri servisinin adresi
- `BIST_API_KEY` = veri servisinin anahtarı

Önerilen veri servisi: Armert-Labs/bist-data-service. Servis ~15 dk gecikmeli BIST fiyatı, geçmiş OHLCV ve SSE/REST uçları sunuyor; veri uçları API key ile korunabiliyor.
