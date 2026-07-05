# MM/STOP-AVI TESPİT BOTU — FORMÜL REFERANSI

## TEMEL KURALLAR

**Mum verisi:**
- Tüm değer ölçümleri **kapanmış mum** (O.H.L.C) ile yapılır
- Hiçbir metrik canlı mumla **ölçüme başlamaz** (başlangıç/referans değeri kapanmış mumdan)
- En az **14 kapanmış mum** seti kullanılır (canlı hariç)
- **Anlık takip istisna:** Canlı mum, geçmiş kapanmış metrik verileriyle **kıyaslanabilir** (bot işlem açmaz, izler/uyarır)
- Referans = kapanmış mum (zemin) | Anlık mum = onunla kıyaslanan takip

**Zaman dilimi:** Ana=1H | Giriş=15M | Trend teyit=4H+1D | İşlem süresi 1-12 gün

**Yön belirleyici:** Spot CVD

---

## NOTASYON STANDARDI

| Gösterim | Anlam |
|---|---|
| `σ(Δx)` | Yukarı artan eğilim (Δx>0 → 1'e) |
| `σ(−Δx)` | Aşağı eğilim (azalış) |
| `σ(Δx) ≈ 0.5` | Yatay |
| `1/(1+e^(−(x−μ)))` | Ortalama ÜSTÜNDE (sapma büyüdükçe 1'e tırmanır) |
| `1/(1+e^(+(x−μ)))` | Ortalama ALTINDA (sapma derinleştikçe 0'a süzülür) |
| `σ(x−alt) − σ(x−üst)` | Bant içi (iki eşik arası) |
| `1 − \|2σ(Δx)−1\|` | Yatay/nötr ölçer (0.5'e yakınsa 1) |

**Sigmoid:** `σ(x,a,k) = 1/(1+e^(−k(x−a)))` — scipy.expit ile birebir doğrulandı.

---

## 9 PİYASA SENARYOSU

### SENARYO 1 — Güçlü Sağlıklı Yükseliş (Boğa)

| Metrik | Davranış | Formül |
|---|---|---|
| Fiyat | HH + HL | `σ((Hₜ−Hₜ₋₁)+(Lₜ−Lₜ₋₁))` |
| EMA | Fiyat>EMA21>EMA50>EMA200 | `σ(Δx)` dizilim yukarı |
| Volume | Ortalama üstü, geri çekilmede düşer | `σ(x−alt) − σ(x−üst)` |
| OBV | Yükselen tepe/dip | `σ(w₁·Δx + w₂·(Hₜ−Hₜ₋₁) + w₃·(Lₜ−Lₜ₋₁))` |
| Momentum (SMI) | Yukarı eğim | `σ(Δx)` |
| CVD | Yukarı eğim | `σ(Δx)` |
| Spot CVD | Yukarı | `σ(Δx)` |
| Future CVD | Yukarı | `σ(Δx)` |
| OI | Yukarı artan | `σ(Δx)` |
| **BİRLEŞİK** | Taze long, spot onaylı, sağlıklı trend | **`σ(w₁·ΔFiyat + w₂·ΔOI + w₃·ΔFutCVD + w₄·ΔSpotCVD + w₅·ΔOBV)`** |

### SENARYO 2 — Kaldıraç Yapay Yükseliş (Boğa Tuzağı / Long Squeeze)

| Metrik | Davranış | Formül |
|---|---|---|
| Fiyat | Yeni zirveler | `σ(w₁·Δx + w₂·(Hₜ−Hₜ₋₁) + w₃·(Lₜ−Lₜ₋₁))` |
| EMA | EMA21>EMA50>EMA200 yukarı | `σ(Δx)` |
| Volume | Fiyat↑ ama hacim küçülür | `σ(−Δx)` |
| OBV | Yatay/alçalan (negatif uyumsuzluk) | `σ(...)` düşen |
| Momentum | Zayıflayarak aşağı eğim | `σ(−Δx)` |
| Spot CVD | Yatay/aşağı (akıllı para spotta almıyor) | `σ(Δx) ≈ 0.5` |
| Future CVD | Agresif dik yukarı | `σ(Δx)` |
| OI | Sert dikey yukarı | `σ(Δx)` |
| **BİRLEŞİK** | Spot=0, OI+FutCVD aşırı, kırılgan → long squeeze | **`1 − σ(Δx · Mₜ/Mₒᵣₜ − Aşırı_Alım)`** |

### SENARYO 3 — Gizli Mal Toplama (Akümülasyon)

| Metrik | Davranış | Formül |
|---|---|---|
| Fiyat | Dip bantta sıkışık/hafif aşağı | `σ(x−alt) − σ(x−üst)` |
| EMA | EMA21≤EMA50≤EMA200 yaklaşmış, fiyat EMA21-50 etrafında yatay | `ters_sigmoid(STDSAPMA(ema21,ema50,ema200))` |
| Volume | Düşük, tabanda küçük artış | `σ(x−alt) − σ(x−üst)` |
| OBV | Dipten istikrarlı yükseliş | `σ(Δx)` |
| Momentum | Negatiften merkeze ivme | `σ(Δx)` |
| Spot CVD | Fiyattan bağımsız net yukarı | `σ(Δx)` |
| Future CVD | Yatay/aşağı (short açıyor) | `σ(Δx)≈0.5` veya `σ(−Δx)` |
| OI | Yatay/hafif düşüş | `1 − \|2σ(ΔOI)−1\|` |
| **BİRLEŞİK** | Vadeli sakin, spot+OBV↑ = balina spottan topluyor | **`σ(w₁·ΔSpotCVD + w₂·ΔOBV − w₃·\|ΔOI\| − w₄·\|ΔFutCVD\|)`** |

### SENARYO 4 — Sağlıklı Güçlü Düşüş (Ayı)

| Metrik | Davranış | Formül |
|---|---|---|
| Fiyat | LH + LL | `σ(w₁·Δx + w₂·(Hₜ−Hₜ₋₁) + w₃·(Lₜ−Lₜ₋₁))` |
| EMA | EMA21<EMA50<EMA200 (ayı dizilim) | `σ(Δx)` dizilim aşağı |
| Volume | Düşüşte büyür, tepkide ~0 | `σ(−k·Δx)` |
| OBV | Alçalan, sert aşağı | `σ(...)` düşen |
| Momentum | Merkeze yaklaşır, satış hızlanır | `σ(−Δx)` |
| CVD/Spot/Future | Üçü eş zamanlı aşağı | `σ(−k·Δx)` |
| OI | Fiyat↓ iken OI↑ (taze short) | `σ((−Δx)·ΔM_satış·t/T)` |
| **BİRLEŞİK** | Taze short + spot satış → güçlü ayı devamı | **`σ(1/(σ_vol+ε)) · e^(−(ΔM−μ_düşüş)²/2ω²)`** |

### SENARYO 5 — Spot Dağıtımlı Çöküş

| Metrik | Davranış | Formül |
|---|---|---|
| Fiyat | Hafif aşağı / vadeli tepki yatay tutuyor | `σ(−Δx)` |
| EMA | Fiyat<EMA21<EMA50<EMA200 çok altında (ayı piyasası) | `σ(k·((EMA50−EMA21)+(EMA200−EMA50)))` + `σ(EMA200−Fiyat)` |
| Volume | Ortalama biraz üstü, dengesiz | `σ(x−alt) − σ(x−üst)` |
| OBV | Fiyat yatay görünse de dik aşağı | `σ(−k·Δx)` |
| Momentum | Merkez altında kararsız, düşer | `σ(−k·Δx)` |
| Spot CVD | Sert istikrarlı aşağı (MM dağıtıyor) | `σ(−k·Δx)` |
| Future CVD | Yatay/yukarı tepki (dip longları) | `σ(Δx)≈0.5` |
| OI | Fiyat yatay/↓ iken istikrarlı↑ | `σ((−Δx_spot)·ΔM_futures·t/T)` |
| **BİRLEŞİK** | Spot çakılıyor, OI+FutCVD direniyor → derin çöküş | **`σ(w₁·(−ΔSpotCVD) + w₂·ΔOI + w₃·ΔFutCVD_direnç)`** |

### SENARYO 6 — Satıcı Tükenmesi / Ayı Tuzağı (Dip Dönüş)

| Metrik | Davranış | Formül |
|---|---|---|
| Fiyat | Sert aşağı iğne (wick), EMA21'den çok uzak, aşırı satım | `1/(1+e^(x−hedef))` + reclaim: `σ(sweep_derinlik)·σ(reclaim_gücü−0.5)` |
| EMA | EMA21<EMA50<EMA200, fiyat çok altında | `1/(1+e^(x−hedef))` |
| Volume | Panik, hacim tavan (climax) | `1/(1+e^(−(x−μ)))` |
| OBV | Yataylaşır/yukarı | `σ(Δx)` |
| Momentum | Daha yüksek dip (pozitif diverjans) | `σ(Δx)` |
| CVD/Spot/Future | İğnede sert düşüş, sonra hızla toparlar | `σ(Δx·t/T + w·(xₜ−x_min))` |
| OI | İğnede sert çakılır, dönerken yataylaşır/hafif↑ (U/V dönüşü) | `σ(Δx·t/T + w·(xₜ−x_min))` |
| **BİRLEŞİK** | Wick+reclaim+CVD toparlanma+momentum diverjans+climax → bear trap | **`σ(w₁·Wick + w₂·CVD_toparlanma + w₃·Mom_diverj + w₄·Climax − w₅·spot_dağıtım)`** |

> Not: `t/T` = olayın başından beri geçen KAPANMIŞ mum / toplam pencere. `x_min` = iğne dibi (kapanmış mum Low). Canlı mum sadece anlık takip için, referansla kıyaslanır.

### SENARYO 7 — Kararsızlık / Likidite Kuruması (Yatay)

| Metrik | Davranış | Formül |
|---|---|---|
| Fiyat | Destek-direnç arası sıkışık | `σ(x−alt) − σ(x−üst)` |
| EMA | EMA21/50 dolanmış, yatay | `σ(ΔOrt / (STDSAPMA(x₁,x₂,x₃)+ε) · t/T)` |
| Volume | Küçük, ortalama altı | `1/(1+e^(x−μ))` |
| OBV | Testere dişi, net yön yok | `σ(x−alt) − σ(x−üst)` |
| Momentum | 0'a yapışık, nötr | `1 − \|2σ(Δx)−1\|` |
| CVD/Spot/Future | Üçü yatay | `1 − \|2σ(Δx)−1\|` |
| OI | Yeni pozisyon yok, yatay | `1 − \|2σ(ΔOI)−1\|` |
| **BİRLEŞİK** | 3 CVD + OI yatay + düşük hacim → kurumsal kırılım bekliyor | **`(1−\|2σ(ΔSpotCVD)−1\|)·(1−\|2σ(ΔOI)−1\|)·ters_sigmoid(hacim)`** |

### SENARYO 8 — Short Cover Yükselişi (Yalancı Yükseliş / Bull Trap)

| Metrik | Davranış | Formül |
|---|---|---|
| Fiyat | Düşüş sonrası ani sert yeşil mum (tepki) | `σ((−ΔM_eski)·a_yeni·(1−t/T))` |
| EMA | Fiyat>EMA21 ama EMA21<EMA50<EMA200 (dirençler altında) | `σ(Δx)` kısa vadeli üstte, dizilim ayı |
| Volume | Anlık tavan (yeşil hacim barı) | `1/(1+e^(−(x−μ)))` |
| OBV | Kapanan mumda OBV ışını çizgileri sert keser | `σ((−ΔM_eski)·a_yeni·(1−t/T))` |
| Momentum | Negatiften hızla 0'a | `σ(Δx·t/T + w·(xₜ−x_min))` |
| Spot CVD | Yatay/çok az↑ (inanmıyor) | `1 − \|2σ(Δx)−1\|` |
| Future CVD | Sert yukarı fırlar | `σ((−ΔM_eski)·a_yeni·(1−t/T))` |
| OI | Fiyat↑ iken OI sert↓ (short kapanıyor) | `σ(−(ΔM_eski·a_yeni·(1−t/T)))` |
| **BİRLEŞİK** | Fiyat+FutCVD↑ ama OI↓ + spot inanmıyor → geçici, kalıcı değil | **`σ(w₁·ΔFutCVD + w₂·(−ΔOI) − w₃·ΔSpotCVD)`** |

> Not: `(1−t/T)` = tepki yükselişi zamanla sönümlenir (t=başlangıç güçlü, t→T zayıflar). "Anlık/yeni mum" = kapanınca teyit edilir (bull trap), canlı takip referansla kıyaslanır.

### SENARYO 9 — Long Cover Düşüşü (Kâr Al)

| Metrik | Davranış | Formül |
|---|---|---|
| Fiyat | Yükseliş sonrası ani kırmızı, EMA21'e çekilir | `1 − σ(Δx·Mₜ/Mₒᵣₜ − Aşırı_Alım)` |
| EMA | Fiyat>EMA21>EMA50>EMA200 (trend boğa, geri çekilme) | `σ(Δx)` dizilim boğa, fiyat geri |
| Volume | Anlık kırmızı bar (negatif uyumsuzluk) | `σ((−Δx)·ΔM_satış·t/T)` |
| OBV | Önceki kapanış altına düşer | `1 − σ(Δx·Mₜ/Mₒᵣₜ − Aşırı_Alım)` |
| Momentum | Zirveden (80+ mayınlı) sert aşağı dönüş | `σ(SMI−80)·σ(−ΔSMI)` |
| **Spot CVD** | **Yatay/çok az↓ (panik satış YOK)** ← S5'ten ayıran | **`1 − \|2σ(Δx)−1\|`** |
| Future CVD | Sert aşağı kırılır | `1 − σ(Δx·Mₜ/Mₒᵣₜ − Aşırı_Alım)` |
| OI | Fiyat↓ iken OI sert↓ (long kapanıyor) | `1 − σ(Δx·Mₜ/Mₒᵣₜ − Aşırı_Alım)` |
| **BİRLEŞİK** | Fiyat+FutCVD↓ + OI↓ ama Spot sağlam → kâr alma, kaldıraç hafifletme | **`σ(w₁·((xₜ−μₓ)/σᵥₒₗ) + w₂·ΔM_inflow − w₃·ΔCVD_spot)·t/T`** |

---

## S8 vs S9 AYRIMI (kritik)

İkisinde de **OI düşer**, ama:
- **S8 (Short Cover):** FutCVD↑ + fiyat↑ → yukarı yalancı yükseliş (short kapanışı iter)
- **S9 (Long Cover):** FutCVD↓ + fiyat↓ + **Spot sağlam** → aşağı geçici düzeltme (kâr al)

Spot CVD ve FutCVD yönü ikisini ayırır.

## S5 vs S9 AYRIMI (kritik)

İkisinde de fiyat düşer, ama:
- **S5 (Gerçek Çöküş):** Spot CVD **sert aşağı** (balina dağıtıyor) → derin çöküş
- **S9 (Kâr Al):** Spot CVD **yatay** (spot sağlam) → geçici düzeltme

Spot CVD'nin yatay mı çöküyor mu olması ikisini ayırır.

---

## MOMENTUM = SMI (Stochastic Momentum Index)

- Skala: −100 / +100, 0 merkezli
- **Bölgeler:** 0-20 sağlıklı | 20-80 sürdürülebilir | 80-100 mayınlı (long); simetrik short
- **Davranış odaklı:** DEĞME önemsiz, DÖNME (roll-over) sinyal
- Üst dönüş (sat): `σ(SMI−80)·σ(−ΔSMI)` | Alt dönüş (al, zayıf): `ters_sigmoid(SMI+80)·σ(ΔSMI)·w_zayıf`
- En güçlü: fiyat-SMI divergence
