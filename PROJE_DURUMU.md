# MM/STOP-AVI TESPİT BOTU — PROJE DURUMU VE AŞAMALAR
> Bu belge, sohbet yenilendiğinde kaldığımız yeri hatırlamak içindir.
> Yeni sohbette bu belgeyi ve 7 .py dosyasını + FORMULLER.md'yi yükle.

---

## PROJE NEDİR (özet)

**Amaç:** MM (market maker) ve stop-avı işlemlerini yakalayıp sağlıklı trend işlemlerine girmek.
**Hedef:** Stop avı/MM likidite toplamasını ÖNCEDEN tespit + sağlıklı yükselen trendleri ERKEN yakalamak.

**Rol dağılımı:**
- **Bot:** İzler + uyarır (İŞLEM AÇMAZ). Tüm metrikleri sürekli hesaplar, davranış değişince Telegram'dan uyarır.
- **Kullanıcı (MusBey):** Sezgi + MM psikolojisi ile KARAR verir, işlemi MANUEL açar. Zaten kazanan trader.
- **Claude:** Yazılım kolu — kullanıcı metriği sözle tanımlar, Claude sigmoid matematiğe çevirir, kaynaklarla doğrular.

**Kurulum:** Windows, C:\Users\MusBey\Desktop\ongun, Türkçe. Binance + CMC. Ücretsiz API.

---

## TEMEL KURALLAR (kalıcı)

1. **Mum verisi:** Tüm ölçümler KAPANMIŞ mum (OHLC) ile. Canlı mumla ölçüme başlanmaz.
2. **En az 14 kapanmış mum** seti (canlı hariç).
3. **Anlık takip istisna:** Canlı mum, geçmiş kapanmış metriklerle KIYASLANABİLİR (bot işlem açmadığı için). Referans=kapanmış mum, anlık mum=kıyas noktası.
4. **B yöntemi uygulandı:** altyapi.py'de `mum_cek_kapali()` canlı mumu atar, tüm indikatörler temiz veri alır. `mum_cek()` ham (canlı dahil, sadece takip).
5. **Zaman:** Ana=1H, Giriş=15M, Trend teyit=4H+1D. İşlem süresi 1-12 gün (swing).
6. **Yön belirleyici:** Spot CVD.
7. **Modüler:** Her parça ayrı dosya + ana motor birleştirir.
8. **Çalışma yöntemi:** Kullanıcı SÖZLE tanımlar → Claude matematiğe çevirir → kaynaklarla doğrular → "senin formülün vs benim önerim" tablo → birlikte karar. Claude "yaz" demeden KOD YAZMAZ. Kod Claude'da tutulur (kullanıcı istedi diye artık verildi).

---

## NOTASYON STANDARDI (kullanıcı tanımı)

- `σ(Δx)` = yukarı artan eğilim
- `σ(−Δx)` = aşağı eğilim
- `σ(Δx)≈0.5` = yatay
- `1/(1+e^(−(x−μ)))` = ortalama ÜSTÜNDE (1'e tırmanır)
- `1/(1+e^(+(x−μ)))` = ortalama ALTINDA (0'a süzülür)
- `σ(x−alt)−σ(x−üst)` = bant içi
- `1−|2σ(Δx)−1|` = yatay/nötr ölçer
- Sigmoid: `σ(x,a,k)=1/(1+e^(−k(x−a)))` — scipy.expit ile birebir doğrulandı

---

## TAMAMLANAN AŞAMALAR (sırayla)

### AŞAMA 0 — Çerçeve ve felsefe ✅
- Belge: hadi_bu.txt (fuzzy matematik felsefesi: "şekil değil davranış", sigmoid benzerlik puanı)
- Mimari: DATA → FEATURES → SCORES → THRESHOLD → ACTION
- Karar: Binance ücretsiz API yeterli (OBV/CVD/OI/funding hesaplanabilir). TradingView gereksiz.

### AŞAMA 1 — Esnek matematik temeli ✅
- Dosya: **esnek_matematik.py**
- sigmoid, ters_sigmoid, ucgen, mum_anatomi + Hammer/Engulfing/PinBar/Doji fuzzy puanlama
- scipy ile birebir doğrulandı (fark 0.0)

### AŞAMA 2 — Formasyonlar ✅
- Dosya: **formasyonlar.py**
- Tekli (7): Hammer, TersHammer, ShootingStar, Doji, PinBar, Marubozu, SpinningTop
- İkili (6): Engulfing, Harami, Piercing, DarkCloud, Tweezer
- Üçlü (6): Morning/EveningStar, 3Asker, 3Karga, 3Inside/Outside
- Geo (10): üçgen, wedge, kanal, OBO, çift/üçlü tepe-dip, bayrak, cup&handle, likidite sweep
- Hepsi 0-100 fuzzy puan. Pencere=50 mum.

### AŞAMA 3 — Hacim Taraması ✅
- Dosya: **hacim_tarama.py**
- 1D TF, son 14 mum, COIN miktarı (base volume, USDT değil)
- Adım 1: Her muma A/D-ağırlıklı puan (CLV × hacim gücü sigmoid, 2x referans)
- Adım 4: Spot/Futures MM niyeti — Spot↑Fut↓=futures kapatıp spot destekli(olumlu); Spot↑Fut↑=çift taraflı(olumlu); Spot yatay+Fut↑=futures kullanıyor(kabul); Spot satış+Fut↑=sigmoid oran karar(oran dışı düşüş negatif=elenir); ikisi durgun=işlem yok
- Doğrulandı: A/D ağırlıklandırma + 2x referans profesyonel pratikle uyumlu

### AŞAMA 4 — OBV ✅
- Dosya: **obv_analiz.py**
- OBV = KLASİK/TradingView (kapanış-bazlı: C>önceki→+V, C<önceki→−V). pandas-ta ile birebir (fark 0.0)
- EMA7/MA7 = OBV serisinin kendi 7-EMA ve 7-SMA'sı (fiyat EMA'sı DEĞİL)
- Hız: OBV ışını(öncü) > EMA7 > MA7
- 6 durum tablosu: OBV>EMA7>MA7(kuvvetli alım) ... OBV<EMA7<MA7(en güçlü satış)
- Giriş divergence: fiyat yatay+OBV↑=gizli alım
- Çıkış uyarısı: fiyat↑+OBV ışını≤EMA7/MA7 → 4H teyit ederse KAPATMA UYARISI
- Not: OBV yüksek TF'de sağlıklı. >2M hacim filtresi OBV'yi de korur.

### AŞAMA 5 — CVD kuralları (5 madde) ✅
- MADDE 1 (CVD+Fiyat, 3 kural): dip+CVD yüksek dip→emilim; CVD sert↓+fiyat yatay→yükselecek; fiyat↓+CVD↓→düşecek
- MADDE 2 (Spot+Fut CVD+Fiyat, 7 kural): sağlıklı yükseliş, short squeeze, dip alımı, bear trap, long squeeze vb.
- MADDE 3 (Net CVD+Fiyat+Vol+OBV+Momentum, 7 kural): long sonlandır, düşüş/yükseliş başlıyor, gizli alım, alım başlangıç(5vs6 farkı=Volume)
- MADDE 4 (yeni): CVD+OI — CVD trend+OI↑=yeni pozisyon; +OI↓=unwind
- MADDE 5 (yeni): CVD+Funding — bearish diverg+aşırı+funding=güçlü satış
- CVD referans noktasından (pivot/son 14 mum) ölçülür, mutlak değer değil, eğim+divergence
- Yön belirleyici = SPOT CVD

### AŞAMA 6 — Momentum = SMI ✅
- Dosya: **smi_momentum.py**
- SMI (Stochastic Momentum Index), −100/+100, 0 merkezli
- Bölgeler: 0-20 sağlıklı | 20-80 sürdürülebilir | 80-100 mayınlı (long); simetrik short
- DAVRANIŞ odaklı: DEĞME önemsiz, DÖNME (roll-over) sinyal
- Üst dönüş(sat): σ(SMI−80)·σ(−ΔSMI) | Alt dönüş(al,zayıf): ters_sigmoid(SMI+80)·σ(ΔSMI)·w_zayıf
- En güçlü: fiyat-SMI divergence

### AŞAMA 7 — 9 Senaryo Motoru ✅
- Dosya: **senaryolar.py** + **FORMULLER.md** (tam formül referansı)
- 9 senaryo: 1)Boğa 2)Boğa Tuzağı 3)Akümülasyon 4)Ayı 5)Çöküş 6)Ayı Tuzağı 7)Yatay 8)Short Cover 9)Long Cover
- Her senaryo 8 metrik + birleşik sigmoid skoru
- Kontrol+düzeltmeler: S1/S3/S5/S6/S7 birleşik formül eklendi, S3/S5 EMA düzeltildi, S6 OI eklendi, S9 spot CVD ayrıldı
- S8 vs S9 ayrımı (OI ikisinde↓ ama CVD yönü ayırır), S5 vs S9 ayrımı (spot çöküyor mu yatay mı)

### AŞAMA 8 — Futures Metrikleri ✅
- Dosya: **futures_metrikler.py**
- CVD (taker alım−satım, son 14 kapanmış mum, canlı hariç, referanstan eğim)
- Spot CVD + Future CVD (ayrı), Net Delta, OI+değişim, Funding
- Likidite/piyasa değeri oranı, günlük hacim >2M filtresi (BLESS gibi coinleri eler)
- Binance kütüphanesinde tüm metotlar mevcut (doğrulandı)

### AŞAMA 9 — Doğrulama raporu ✅
- Sigmoid: scipy.expit ile birebir (fark 0.0)
- OBV/EMA: pandas-ta ile birebir (fark 0.0)
- Fuzzy formasyon: akademik/GitHub'da geçerli yöntem
- Binance: CVD/OI/funding/likidasyon tüm metotlar var
- Kritik hata YOK

---

## SIRADAKİ ADIMLAR (yeni sohbette devam)

### HENÜZ YAPILMADI:
1. **"HAREKET TARZI" bölümü** — kullanıcı bu bölüme geçmek istiyordu (son bölüm). İçeriği kullanıcıdan alınacak.
2. **Ana Motor (orkestratör)** — tüm modülleri birleştiren, her coin için tüm metrikleri hesaplayıp senaryo + davranış uyarısı üreten katman. Telegram uyarıları (manipülasyon puanı, squeeze ihtimali, davranış dili).
3. **altyapi.py'ye veri çekme fonksiyonları** — CVD/OI/funding çekme (Binance). mum_cek_kapali() eklendi ama futures metrik çekme fonksiyonları eklenecek.
4. **Kalan metrik kuralları:** RSI, StochRSI, VWAP kendi davranış kuralları (henüz senaryo dışında tek tek tanımlanmadı)
5. **w (ağırlık) kalibrasyonu:** Senaryolardaki w₁,w₂... ağırlıkları şu an makul varsayılan. Gerçek veriyle ayarlanacak.
6. **SMI w_zayıf değeri** netleşmedi (~0.6 öneri)

### AÇIK NETLEŞTİRMELER:
- Senaryolardaki `t/T` = olayın başından geçen KAPANMIŞ mum / pencere (canlı değil) — teyit edildi
- CVD pivot referansı: şu an son 14 mum penceresi. İleride swing-pivot bazlı olabilir.

---

## DOSYA LİSTESİ (bu pakette)

**Yeni bot (MM tespit) — 7 modül:**
1. esnek_matematik.py — fuzzy temel + formasyonlar
2. formasyonlar.py — tüm mum + geo şekiller
3. hacim_tarama.py — hacim toplama (A/D, spot/futures)
4. obv_analiz.py — OBV (klasik, EMA7/MA7, divergence)
5. smi_momentum.py — SMI momentum
6. senaryolar.py — 9 senaryo motoru
7. futures_metrikler.py — CVD/OI/funding/delta

**Referans belgeleri:**
- FORMULLER.md — 9 senaryo tam formül referansı
- PROJE_DURUMU.md — bu belge

**Not:** esnek_matematik.py ve formasyonlar.py bir ara "yaz demeden" erken yazılmıştı, sonra kullanıcı onayladı ve kullanımda.

---

## ÖNEMLİ HATIRLATMALAR (Claude için)

- Kullanıcı 10 parmak yazıyor, bazen yanlış Enter'a basıyor → "bekle" deyince BEKLE, hemen yazma.
- "Yaz/ver" komutu OLMADAN kod yazma.
- Kullanıcının cümlesini TAM oku, satır atlama, erken yorumlama yapma.
- Gereksiz "A mı B mi" sorusuyla oyalama — tanım netse birebir uygula.
- Metrik SÖZLE tanımlanır → matematiğe çevrilir → kaynakla doğrulanır → tablo → karar.
- Kullanıcı zaten kazanan trader; bot onun GÖZÜ (kaçırmasın diye), yerine karar vermez.
