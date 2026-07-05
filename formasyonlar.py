"""
formasyonlar.py — Tüm Mum Formasyonları + Geometrik Şekiller (Esnek Matematik)
==============================================================================
Botun "gözü" — mumu ve grafik yapısını fuzzy (sigmoid) puanlamayla okur.

ZAMAN DİLİMİ KURALI:
  Ana birim: 1H | Giriş: 15M | Trend: 4H + 1D

FELSEFE (hadi bu.txt):
  "Şekil" değil "davranış". Sert eşik yok, sigmoid ile yumuşak benzerlik.
  Her formasyon 0-100 benzerlik puanı alır (var/yok değil, %kaç benziyor).
  Sigmoid: f(x) = 1 / (1 + e^(-k*(x-a)))

İÇERİK:
  TEKLİ  (7): Hammer, Ters Hammer, Shooting Star, Doji, Pin Bar, Marubozu, Spinning Top
  İKİLİ  (6): Bullish/Bearish Engulfing, Harami, Piercing, Dark Cloud, Tweezer
  ÜÇLÜ   (6): Morning/Evening Star, 3 Asker, 3 Karga, 3 Inside/Outside
  GEO   (10): Üçgenler, Wedge, Kanal, Omuz-Baş-Omuz, Çift/Üçlü Tepe-Dip,
              Bayrak, Flama, Cup&Handle, Likidite Sweep

Kütüphane: sadece math (Python standart).
"""

import math

# Geometrik şekil arama penceresi (mum sayısı)
GEO_PENCERE = 50


# =====================================================================
# TEMEL FUZZY FONKSİYONLAR
# =====================================================================
def sigmoid(x, a, k):
    """x, a'ya yakınsa 0.5; büyükse→1, küçükse→0. k=sertlik."""
    try:
        return 1.0 / (1.0 + math.exp(-k * (x - a)))
    except OverflowError:
        return 0.0 if x < a else 1.0


def ters_sigmoid(x, a, k):
    """x KÜÇÜKSE yüksek puan ('kısa olmalı' durumları)."""
    return 1.0 - sigmoid(x, a, k)


def ucgen(x, dusuk, ideal, yuksek):
    """Üçgen üyelik: ideal'de 1.0, kenarlarda 0.0."""
    if x <= dusuk or x >= yuksek:
        return 0.0
    if x == ideal:
        return 1.0
    if x < ideal:
        return (x - dusuk) / (ideal - dusuk)
    return (yuksek - x) / (yuksek - ideal)


# =====================================================================
# MUM ANATOMİSİ
# =====================================================================
def mum_anatomi(mum):
    """
    Mumu orana çevirir (fiyat ölçeğinden bağımsız).
    mum = [zaman, açılış, yüksek, düşük, kapanış, hacim]
    """
    o = float(mum[1]); h = float(mum[2]); l = float(mum[3]); c = float(mum[4])
    boy = h - l
    if boy <= 0:
        return None
    govde = abs(c - o)
    ust_fitil = h - max(o, c)
    alt_fitil = min(o, c) - l
    payda = govde if govde > boy * 0.02 else boy
    return {
        "govde_oran": govde / boy,
        "alt_fitil_oran": alt_fitil / payda,
        "ust_fitil_oran": ust_fitil / payda,
        "yon": 1 if c > o else (-1 if c < o else 0),
        "kapanis_konum": (c - l) / boy,
        "govde": govde, "boy": boy,
        "o": o, "h": h, "l": l, "c": c,
    }


# =====================================================================
# TEKLİ MUM FORMASYONLARI (7)
# =====================================================================
def hammer(mum, dip_bolgede=False, hacim_yuksek=False):
    """Çekiç: küçük gövde tepede + uzun alt fitil → LONG dönüş."""
    a = mum_anatomi(mum)
    if a is None: return {"puan": 0, "yon": None}
    p_alt = sigmoid(a["alt_fitil_oran"], 2.0, 1.5) * 35
    p_ust = ters_sigmoid(a["ust_fitil_oran"], 0.4, 5.0) * 20
    p_govde = ters_sigmoid(a["govde_oran"], 0.4, 6.0) * 15
    p_kapanis = sigmoid(a["kapanis_konum"], 0.6, 6.0) * 10
    p_dip = 10 if dip_bolgede else 0
    p_hacim = 10 if hacim_yuksek else 0
    return {"puan": round(p_alt+p_ust+p_govde+p_kapanis+p_dip+p_hacim, 1), "yon": "LONG"}


def ters_hammer(mum, dip_bolgede=False, hacim_yuksek=False):
    """Ters Çekiç: küçük gövde dipte + uzun üst fitil → LONG dönüş (dipte)."""
    a = mum_anatomi(mum)
    if a is None: return {"puan": 0, "yon": None}
    p_ust = sigmoid(a["ust_fitil_oran"], 2.0, 1.5) * 35
    p_alt = ters_sigmoid(a["alt_fitil_oran"], 0.4, 5.0) * 20
    p_govde = ters_sigmoid(a["govde_oran"], 0.4, 6.0) * 15
    p_kapanis = ters_sigmoid(a["kapanis_konum"], 0.4, 6.0) * 10
    p_dip = 10 if dip_bolgede else 0
    p_hacim = 10 if hacim_yuksek else 0
    return {"puan": round(p_ust+p_alt+p_govde+p_kapanis+p_dip+p_hacim, 1), "yon": "LONG"}


def shooting_star(mum, tepe_bolgede=False, hacim_yuksek=False):
    """Kayan Yıldız: küçük gövde dipte + uzun üst fitil (tepede) → SHORT dönüş."""
    a = mum_anatomi(mum)
    if a is None: return {"puan": 0, "yon": None}
    p_ust = sigmoid(a["ust_fitil_oran"], 2.0, 1.5) * 35
    p_alt = ters_sigmoid(a["alt_fitil_oran"], 0.4, 5.0) * 20
    p_govde = ters_sigmoid(a["govde_oran"], 0.4, 6.0) * 15
    p_kapanis = ters_sigmoid(a["kapanis_konum"], 0.4, 6.0) * 10
    p_tepe = 10 if tepe_bolgede else 0
    p_hacim = 10 if hacim_yuksek else 0
    return {"puan": round(p_ust+p_alt+p_govde+p_kapanis+p_tepe+p_hacim, 1), "yon": "SHORT"}


def doji(mum):
    """Doji: çok küçük gövde = kararsızlık (bekle sinyali)."""
    a = mum_anatomi(mum)
    if a is None: return {"puan": 0, "yon": None}
    p = ters_sigmoid(a["govde_oran"], 0.1, 15.0) * 100
    return {"puan": round(p, 1), "yon": "NOTR"}


def pin_bar(mum):
    """Pin Bar: uzun tek fitil + küçük gövde. Alt uzunsa LONG, üst uzunsa SHORT."""
    a = mum_anatomi(mum)
    if a is None: return {"puan": 0, "yon": None}
    if a["alt_fitil_oran"] > a["ust_fitil_oran"]:
        yon = "LONG"; baskin = a["alt_fitil_oran"]; diger = a["ust_fitil_oran"]
    else:
        yon = "SHORT"; baskin = a["ust_fitil_oran"]; diger = a["alt_fitil_oran"]
    p_baskin = sigmoid(baskin, 2.0, 1.5) * 50
    p_diger = ters_sigmoid(diger, 0.5, 4.0) * 25
    p_govde = ters_sigmoid(a["govde_oran"], 0.35, 6.0) * 25
    return {"puan": round(p_baskin+p_diger+p_govde, 1), "yon": yon}


def marubozu(mum):
    """Marubozu: fitilsiz büyük gövde = güçlü momentum. Yeşilse LONG, kırmızıysa SHORT."""
    a = mum_anatomi(mum)
    if a is None: return {"puan": 0, "yon": None}
    p_govde = sigmoid(a["govde_oran"], 0.9, 12.0) * 60
    p_ust = ters_sigmoid(a["ust_fitil_oran"], 0.1, 10.0) * 20
    p_alt = ters_sigmoid(a["alt_fitil_oran"], 0.1, 10.0) * 20
    yon = "LONG" if a["yon"] == 1 else "SHORT"
    return {"puan": round(p_govde+p_ust+p_alt, 1), "yon": yon}


def spinning_top(mum):
    """Topaç: küçük gövde + iki yanda fitil = kararsızlık."""
    a = mum_anatomi(mum)
    if a is None: return {"puan": 0, "yon": None}
    p_govde = ters_sigmoid(a["govde_oran"], 0.3, 8.0) * 40
    p_ust = sigmoid(a["ust_fitil_oran"], 0.8, 3.0) * 30
    p_alt = sigmoid(a["alt_fitil_oran"], 0.8, 3.0) * 30
    return {"puan": round(p_govde+p_ust+p_alt, 1), "yon": "NOTR"}


# =====================================================================
# İKİLİ MUM FORMASYONLARI (6)
# =====================================================================
def engulfing(onceki, mum, hacim_yuksek=False):
    """Yutan: yeni gövde öncekini sarar. Kırmızı→Yeşil LONG, tersi SHORT."""
    a1 = mum_anatomi(onceki); a2 = mum_anatomi(mum)
    if a1 is None or a2 is None: return {"puan": 0, "yon": None}
    o1, c1 = a1["o"], a1["c"]; o2, c2 = a2["o"], a2["c"]
    g1 = abs(c1 - o1)
    if g1 <= 0: return {"puan": 0, "yon": None}
    sarma = abs(c2 - o2) / g1
    if a1["yon"] == -1 and a2["yon"] == 1 and c2 > o1 and o2 < c1:
        yon = "LONG"
    elif a1["yon"] == 1 and a2["yon"] == -1 and c2 < o1 and o2 > c1:
        yon = "SHORT"
    else:
        return {"puan": 0, "yon": None}
    p_sarma = sigmoid(sarma, 1.0, 3.0) * 60
    p_govde = sigmoid(a2["govde_oran"], 0.6, 5.0) * 25
    p_hacim = 15 if hacim_yuksek else 0
    return {"puan": round(p_sarma+p_govde+p_hacim, 1), "yon": yon}


def harami(onceki, mum):
    """Harami: küçük mum önceki büyük mumun içinde = momentum zayıflıyor."""
    a1 = mum_anatomi(onceki); a2 = mum_anatomi(mum)
    if a1 is None or a2 is None: return {"puan": 0, "yon": None}
    g1 = a1["govde"]; g2 = a2["govde"]
    if g1 <= 0: return {"puan": 0, "yon": None}
    ic_oran = g2 / g1  # küçük olmalı
    o1, c1 = a1["o"], a1["c"]; o2, c2 = a2["o"], a2["c"]
    icinde = max(o2, c2) < max(o1, c1) and min(o2, c2) > min(o1, c1)
    if not icinde: return {"puan": 0, "yon": None}
    yon = "SHORT" if a1["yon"] == 1 else "LONG"  # dönüş
    p_ic = ters_sigmoid(ic_oran, 0.5, 5.0) * 60
    p_onceki = sigmoid(a1["govde_oran"], 0.5, 4.0) * 40
    return {"puan": round(p_ic+p_onceki, 1), "yon": yon}


def piercing(onceki, mum):
    """Piercing: kırmızı sonrası yeşil, öncekinin ortasını geçer → LONG."""
    a1 = mum_anatomi(onceki); a2 = mum_anatomi(mum)
    if a1 is None or a2 is None: return {"puan": 0, "yon": None}
    if a1["yon"] != -1 or a2["yon"] != 1: return {"puan": 0, "yon": None}
    orta = (a1["o"] + a1["c"]) / 2
    if a2["c"] <= orta or a2["o"] >= a1["c"]: return {"puan": 0, "yon": None}
    nufuz = (a2["c"] - orta) / (a1["o"] - orta) if (a1["o"] - orta) != 0 else 0
    p = sigmoid(nufuz, 0.5, 3.0) * 100
    return {"puan": round(p, 1), "yon": "LONG"}


def dark_cloud(onceki, mum):
    """Kara Bulut: yeşil sonrası kırmızı, öncekinin ortasını geçer → SHORT."""
    a1 = mum_anatomi(onceki); a2 = mum_anatomi(mum)
    if a1 is None or a2 is None: return {"puan": 0, "yon": None}
    if a1["yon"] != 1 or a2["yon"] != -1: return {"puan": 0, "yon": None}
    orta = (a1["o"] + a1["c"]) / 2
    if a2["c"] >= orta or a2["o"] <= a1["c"]: return {"puan": 0, "yon": None}
    nufuz = (orta - a2["c"]) / (orta - a1["o"]) if (orta - a1["o"]) != 0 else 0
    p = sigmoid(nufuz, 0.5, 3.0) * 100
    return {"puan": round(p, 1), "yon": "SHORT"}


def tweezer(onceki, mum):
    """Cımbız: iki mumun tepe/dibi eşit = dönüş bölgesi."""
    a1 = mum_anatomi(onceki); a2 = mum_anatomi(mum)
    if a1 is None or a2 is None: return {"puan": 0, "yon": None}
    ort = (a1["boy"] + a2["boy"]) / 2
    if ort <= 0: return {"puan": 0, "yon": None}
    dip_fark = abs(a1["l"] - a2["l"]) / ort
    tepe_fark = abs(a1["h"] - a2["h"]) / ort
    if dip_fark < tepe_fark:
        yon = "LONG"; fark = dip_fark
    else:
        yon = "SHORT"; fark = tepe_fark
    p = ters_sigmoid(fark, 0.1, 20.0) * 100
    return {"puan": round(p, 1), "yon": yon}


# =====================================================================
# ÜÇLÜ MUM FORMASYONLARI (6)
# =====================================================================
def morning_star(m1, m2, m3):
    """Sabah Yıldızı: kırmızı + küçük + yeşil → LONG dönüş."""
    a1 = mum_anatomi(m1); a2 = mum_anatomi(m2); a3 = mum_anatomi(m3)
    if None in (a1, a2, a3): return {"puan": 0, "yon": None}
    if a1["yon"] != -1 or a3["yon"] != 1: return {"puan": 0, "yon": None}
    p_orta = ters_sigmoid(a2["govde_oran"], 0.3, 6.0) * 40   # orta küçük
    p_ilk = sigmoid(a1["govde_oran"], 0.5, 4.0) * 30          # ilk güçlü kırmızı
    kapanis_geri = (a3["c"] - a1["c"]) / a1["govde"] if a1["govde"] > 0 else 0
    p_son = sigmoid(kapanis_geri, 0.5, 3.0) * 30              # son güçlü toparlanma
    return {"puan": round(p_orta+p_ilk+p_son, 1), "yon": "LONG"}


def evening_star(m1, m2, m3):
    """Akşam Yıldızı: yeşil + küçük + kırmızı → SHORT dönüş."""
    a1 = mum_anatomi(m1); a2 = mum_anatomi(m2); a3 = mum_anatomi(m3)
    if None in (a1, a2, a3): return {"puan": 0, "yon": None}
    if a1["yon"] != 1 or a3["yon"] != -1: return {"puan": 0, "yon": None}
    p_orta = ters_sigmoid(a2["govde_oran"], 0.3, 6.0) * 40
    p_ilk = sigmoid(a1["govde_oran"], 0.5, 4.0) * 30
    kapanis_geri = (a1["c"] - a3["c"]) / a1["govde"] if a1["govde"] > 0 else 0
    p_son = sigmoid(kapanis_geri, 0.5, 3.0) * 30
    return {"puan": round(p_orta+p_ilk+p_son, 1), "yon": "SHORT"}


def uc_asker(m1, m2, m3):
    """3 Beyaz Asker: 3 ardışık güçlü yeşil, yükselen → LONG."""
    a1 = mum_anatomi(m1); a2 = mum_anatomi(m2); a3 = mum_anatomi(m3)
    if None in (a1, a2, a3): return {"puan": 0, "yon": None}
    if not (a1["yon"] == a2["yon"] == a3["yon"] == 1): return {"puan": 0, "yon": None}
    yukselen = a1["c"] < a2["c"] < a3["c"]
    if not yukselen: return {"puan": 0, "yon": None}
    p_govde = (sigmoid(a1["govde_oran"], 0.5, 4.0) +
               sigmoid(a2["govde_oran"], 0.5, 4.0) +
               sigmoid(a3["govde_oran"], 0.5, 4.0)) / 3 * 100
    return {"puan": round(p_govde, 1), "yon": "LONG"}


def uc_karga(m1, m2, m3):
    """3 Kara Karga: 3 ardışık güçlü kırmızı, alçalan → SHORT."""
    a1 = mum_anatomi(m1); a2 = mum_anatomi(m2); a3 = mum_anatomi(m3)
    if None in (a1, a2, a3): return {"puan": 0, "yon": None}
    if not (a1["yon"] == a2["yon"] == a3["yon"] == -1): return {"puan": 0, "yon": None}
    alcalan = a1["c"] > a2["c"] > a3["c"]
    if not alcalan: return {"puan": 0, "yon": None}
    p_govde = (sigmoid(a1["govde_oran"], 0.5, 4.0) +
               sigmoid(a2["govde_oran"], 0.5, 4.0) +
               sigmoid(a3["govde_oran"], 0.5, 4.0)) / 3 * 100
    return {"puan": round(p_govde, 1), "yon": "SHORT"}


def uc_inside(m1, m2, m3):
    """3 Inside Up/Down: harami + teyit mumu → dönüş."""
    a1 = mum_anatomi(m1); a2 = mum_anatomi(m2); a3 = mum_anatomi(m3)
    if None in (a1, a2, a3): return {"puan": 0, "yon": None}
    h = harami(m1, m2)
    if h["puan"] < 40: return {"puan": 0, "yon": None}
    if h["yon"] == "LONG" and a3["yon"] == 1 and a3["c"] > a2["c"]:
        return {"puan": round(h["puan"], 1), "yon": "LONG"}
    if h["yon"] == "SHORT" and a3["yon"] == -1 and a3["c"] < a2["c"]:
        return {"puan": round(h["puan"], 1), "yon": "SHORT"}
    return {"puan": 0, "yon": None}


def uc_outside(m1, m2, m3):
    """3 Outside Up/Down: engulfing + teyit mumu → dönüş."""
    a3 = mum_anatomi(m3)
    if a3 is None: return {"puan": 0, "yon": None}
    e = engulfing(m1, m2)
    if e["puan"] < 40: return {"puan": 0, "yon": None}
    a2 = mum_anatomi(m2)
    if e["yon"] == "LONG" and a3["yon"] == 1 and a3["c"] > a2["c"]:
        return {"puan": round(e["puan"], 1), "yon": "LONG"}
    if e["yon"] == "SHORT" and a3["yon"] == -1 and a3["c"] < a2["c"]:
        return {"puan": round(e["puan"], 1), "yon": "SHORT"}
    return {"puan": 0, "yon": None}


# =====================================================================
# GEOMETRİK ŞEKİLLER (10) — pivot tabanlı
# =====================================================================
def pivotlar(mumlar, sol=2, sag=2):
    """
    Tepe (high) ve dip (low) pivot noktalarını bulur.
    sol/sag: bir pivotun kaç mum solunda/sağında en uç olması gerektiği.
    Dönüş: (tepeler, dipler) — her biri [(idx, fiyat), ...]
    """
    tepeler = []; dipler = []
    n = len(mumlar)
    for i in range(sol, n - sag):
        h = float(mumlar[i][2]); l = float(mumlar[i][3])
        sol_h = all(float(mumlar[i-j][2]) <= h for j in range(1, sol+1))
        sag_h = all(float(mumlar[i+j][2]) <= h for j in range(1, sag+1))
        if sol_h and sag_h:
            tepeler.append((i, h))
        sol_l = all(float(mumlar[i-j][3]) >= l for j in range(1, sol+1))
        sag_l = all(float(mumlar[i+j][3]) >= l for j in range(1, sag+1))
        if sol_l and sag_l:
            dipler.append((i, l))
    return tepeler, dipler


def _egim(noktalar):
    """Nokta listesinin doğrusal eğimi (basit)."""
    n = len(noktalar)
    if n < 2: return 0.0
    xs = [p[0] for p in noktalar]; ys = [p[1] for p in noktalar]
    mx = sum(xs)/n; my = sum(ys)/n
    pay = sum((xs[i]-mx)*(ys[i]-my) for i in range(n))
    payda = sum((xs[i]-mx)**2 for i in range(n))
    return pay/payda if payda != 0 else 0.0


def ucgen_sekil(mumlar):
    """
    Üçgen: yükselen (dipler yükselir, tepeler yatay), alçalan (tersi),
    simetrik (ikisi de daralır). Fuzzy puan + tip.
    """
    m = mumlar[-GEO_PENCERE:] if len(mumlar) > GEO_PENCERE else mumlar
    tepeler, dipler = pivotlar(m)
    if len(tepeler) < 2 or len(dipler) < 2:
        return {"puan": 0, "yon": None, "tip": None}
    te = _egim(tepeler); de = _egim(dipler)
    # normalize (fiyat ölçeğine göre)
    ort_fiyat = sum(p[1] for p in tepeler) / len(tepeler)
    te_n = te / ort_fiyat * 100; de_n = de / ort_fiyat * 100
    # Yükselen üçgen: tepe ~yatay, dip yükseliyor → LONG
    if abs(te_n) < 0.1 and de_n > 0.1:
        p = sigmoid(de_n, 0.2, 5.0) * 100
        return {"puan": round(p, 1), "yon": "LONG", "tip": "yükselen üçgen"}
    # Alçalan üçgen: dip ~yatay, tepe düşüyor → SHORT
    if abs(de_n) < 0.1 and te_n < -0.1:
        p = sigmoid(-te_n, 0.2, 5.0) * 100
        return {"puan": round(p, 1), "yon": "SHORT", "tip": "alçalan üçgen"}
    # Simetrik: tepe düşer + dip yükselir (daralma) → kırılım bekle
    if te_n < -0.05 and de_n > 0.05:
        p = sigmoid((abs(te_n)+de_n)/2, 0.15, 5.0) * 100
        return {"puan": round(p, 1), "yon": "NOTR", "tip": "simetrik üçgen"}
    return {"puan": 0, "yon": None, "tip": None}


def wedge(mumlar):
    """Kama: her iki çizgi aynı yöne eğimli ama daralıyor. Yükselen kama→SHORT, alçalan→LONG."""
    m = mumlar[-GEO_PENCERE:] if len(mumlar) > GEO_PENCERE else mumlar
    tepeler, dipler = pivotlar(m)
    if len(tepeler) < 2 or len(dipler) < 2:
        return {"puan": 0, "yon": None, "tip": None}
    te = _egim(tepeler); de = _egim(dipler)
    ort = sum(p[1] for p in tepeler)/len(tepeler)
    te_n = te/ort*100; de_n = de/ort*100
    # Yükselen kama: ikisi de pozitif, dip daha dik (daralıyor) → SHORT
    if te_n > 0.05 and de_n > 0.05 and de_n > te_n:
        p = sigmoid(de_n - te_n, 0.1, 8.0) * 100
        return {"puan": round(p, 1), "yon": "SHORT", "tip": "yükselen kama"}
    # Alçalan kama: ikisi de negatif, tepe daha dik → LONG
    if te_n < -0.05 and de_n < -0.05 and te_n < de_n:
        p = sigmoid(de_n - te_n, 0.1, 8.0) * 100
        return {"puan": round(p, 1), "yon": "LONG", "tip": "alçalan kama"}
    return {"puan": 0, "yon": None, "tip": None}


def kanal(mumlar):
    """Kanal: tepe ve dip çizgileri paralel. Yükselen/alçalan/yatay."""
    m = mumlar[-GEO_PENCERE:] if len(mumlar) > GEO_PENCERE else mumlar
    tepeler, dipler = pivotlar(m)
    if len(tepeler) < 2 or len(dipler) < 2:
        return {"puan": 0, "yon": None, "tip": None}
    te = _egim(tepeler); de = _egim(dipler)
    ort = sum(p[1] for p in tepeler)/len(tepeler)
    te_n = te/ort*100; de_n = de/ort*100
    paralel = ters_sigmoid(abs(te_n - de_n), 0.1, 10.0)  # eğimler yakınsa yüksek
    if paralel < 0.4: return {"puan": 0, "yon": None, "tip": None}
    ort_egim = (te_n + de_n) / 2
    if ort_egim > 0.1:
        tip, yon = "yükselen kanal", "LONG"
    elif ort_egim < -0.1:
        tip, yon = "alçalan kanal", "SHORT"
    else:
        tip, yon = "yatay kanal", "NOTR"
    return {"puan": round(paralel*100, 1), "yon": yon, "tip": tip}


def omuz_bas_omuz(mumlar):
    """Omuz-Baş-Omuz: 3 tepe, ortası yüksek → SHORT. Ters OBO → LONG."""
    m = mumlar[-GEO_PENCERE:] if len(mumlar) > GEO_PENCERE else mumlar
    tepeler, dipler = pivotlar(m)
    # Normal OBO: 3 tepe
    if len(tepeler) >= 3:
        son3 = tepeler[-3:]
        sol, bas, sag = son3[0][1], son3[1][1], son3[2][1]
        if bas > sol and bas > sag:
            omuz_denge = ters_sigmoid(abs(sol - sag) / bas, 0.05, 15.0)
            bas_yukseklik = sigmoid((bas - max(sol, sag)) / bas, 0.02, 20.0)
            p = (omuz_denge * 0.5 + bas_yukseklik * 0.5) * 100
            if p > 40:
                return {"puan": round(p, 1), "yon": "SHORT", "tip": "omuz-baş-omuz"}
    # Ters OBO: 3 dip
    if len(dipler) >= 3:
        son3 = dipler[-3:]
        sol, bas, sag = son3[0][1], son3[1][1], son3[2][1]
        if bas < sol and bas < sag:
            omuz_denge = ters_sigmoid(abs(sol - sag) / bas, 0.05, 15.0)
            bas_derinlik = sigmoid((min(sol, sag) - bas) / bas, 0.02, 20.0)
            p = (omuz_denge * 0.5 + bas_derinlik * 0.5) * 100
            if p > 40:
                return {"puan": round(p, 1), "yon": "LONG", "tip": "ters omuz-baş-omuz"}
    return {"puan": 0, "yon": None, "tip": None}


def cift_tepe_dip(mumlar):
    """Çift Tepe (M) → SHORT. Çift Dip (W) → LONG."""
    m = mumlar[-GEO_PENCERE:] if len(mumlar) > GEO_PENCERE else mumlar
    tepeler, dipler = pivotlar(m)
    if len(tepeler) >= 2:
        t1, t2 = tepeler[-2][1], tepeler[-1][1]
        ort = (t1 + t2) / 2
        esitlik = ters_sigmoid(abs(t1 - t2) / ort, 0.03, 20.0)
        if esitlik > 0.5:
            return {"puan": round(esitlik*100, 1), "yon": "SHORT", "tip": "çift tepe"}
    if len(dipler) >= 2:
        d1, d2 = dipler[-2][1], dipler[-1][1]
        ort = (d1 + d2) / 2
        esitlik = ters_sigmoid(abs(d1 - d2) / ort, 0.03, 20.0)
        if esitlik > 0.5:
            return {"puan": round(esitlik*100, 1), "yon": "LONG", "tip": "çift dip"}
    return {"puan": 0, "yon": None, "tip": None}


def uclu_tepe_dip(mumlar):
    """Üçlü Tepe → SHORT. Üçlü Dip → LONG."""
    m = mumlar[-GEO_PENCERE:] if len(mumlar) > GEO_PENCERE else mumlar
    tepeler, dipler = pivotlar(m)
    if len(tepeler) >= 3:
        son3 = [t[1] for t in tepeler[-3:]]
        ort = sum(son3)/3
        esitlik = ters_sigmoid(max(son3)-min(son3), 0.0, 1.0) if ort == 0 else \
                  ters_sigmoid((max(son3)-min(son3))/ort, 0.03, 20.0)
        if esitlik > 0.5:
            return {"puan": round(esitlik*100, 1), "yon": "SHORT", "tip": "üçlü tepe"}
    if len(dipler) >= 3:
        son3 = [d[1] for d in dipler[-3:]]
        ort = sum(son3)/3
        esitlik = ters_sigmoid((max(son3)-min(son3))/ort, 0.03, 20.0) if ort else 0
        if esitlik > 0.5:
            return {"puan": round(esitlik*100, 1), "yon": "LONG", "tip": "üçlü dip"}
    return {"puan": 0, "yon": None, "tip": None}


def bayrak_flama(mumlar):
    """Bayrak/Flama: güçlü hareket (direk) + kısa konsolidasyon → devam."""
    if len(mumlar) < 15:
        return {"puan": 0, "yon": None, "tip": None}
    m = mumlar[-20:]
    # Direk: ilk kısımda güçlü hareket
    ilk = m[:8]; son = m[8:]
    ilk_hareket = (float(ilk[-1][4]) - float(ilk[0][1])) / float(ilk[0][1])
    # Konsolidasyon: son kısımda dar aralık
    son_yuksek = max(float(x[2]) for x in son)
    son_dusuk = min(float(x[3]) for x in son)
    son_aralik = (son_yuksek - son_dusuk) / float(son[0][1])
    p_direk = sigmoid(abs(ilk_hareket), 0.03, 50.0) * 50
    p_konsol = ters_sigmoid(son_aralik, 0.02, 60.0) * 50
    yon = "LONG" if ilk_hareket > 0 else "SHORT"
    p = p_direk + p_konsol
    if p < 40: return {"puan": 0, "yon": None, "tip": None}
    return {"puan": round(p, 1), "yon": yon, "tip": "bayrak/flama"}


def cup_handle(mumlar):
    """Fincan-Kulp: U şeklinde dip + küçük geri çekilme → LONG."""
    if len(mumlar) < 30:
        return {"puan": 0, "yon": None, "tip": None}
    m = mumlar[-GEO_PENCERE:] if len(mumlar) > GEO_PENCERE else mumlar
    n = len(m)
    sol_kenar = float(m[0][2])
    dip = min(float(x[3]) for x in m)
    dip_idx = min(range(n), key=lambda i: float(m[i][3]))
    sag_kenar = float(m[-1][2])
    # U simetrisi: dip ortada, iki kenar benzer yükseklikte
    if not (n*0.3 < dip_idx < n*0.7):
        return {"puan": 0, "yon": None, "tip": None}
    kenar_denge = ters_sigmoid(abs(sol_kenar - sag_kenar) / sol_kenar, 0.05, 15.0)
    derinlik = sigmoid((sol_kenar - dip) / sol_kenar, 0.1, 8.0)
    p = (kenar_denge * 0.5 + derinlik * 0.5) * 100
    if p < 40: return {"puan": 0, "yon": None, "tip": None}
    return {"puan": round(p, 1), "yon": "LONG", "tip": "fincan-kulp"}


def likidite_sweep(mumlar):
    """
    Likidite Süpürmesi: son N mumun tepe/dibini iğneyle aşıp geri döner.
    Senin belgede vurguladığın MM davranışı. Uzun fitil + geri kapanış.
    """
    if len(mumlar) < 10:
        return {"puan": 0, "yon": None, "tip": None}
    onceki = mumlar[-11:-1]
    son = mumlar[-1]
    a = mum_anatomi(son)
    if a is None: return {"puan": 0, "yon": None, "tip": None}
    onceki_dip = min(float(x[3]) for x in onceki)
    onceki_tepe = max(float(x[2]) for x in onceki)
    # Alt sweep: dibi kırdı ama gövde geri kapandı → LONG (stop avı)
    if a["l"] < onceki_dip and a["c"] > onceki_dip:
        gecis = (onceki_dip - a["l"]) / a["boy"]
        p_gecis = sigmoid(gecis, 0.2, 6.0) * 50
        p_geri = sigmoid(a["kapanis_konum"], 0.6, 5.0) * 50
        p = p_gecis + p_geri
        if p > 40:
            return {"puan": round(p, 1), "yon": "LONG", "tip": "alt likidite sweep"}
    # Üst sweep: tepeyi kırdı ama gövde geri kapandı → SHORT
    if a["h"] > onceki_tepe and a["c"] < onceki_tepe:
        gecis = (a["h"] - onceki_tepe) / a["boy"]
        p_gecis = sigmoid(gecis, 0.2, 6.0) * 50
        p_geri = ters_sigmoid(a["kapanis_konum"], 0.4, 5.0) * 50
        p = p_gecis + p_geri
        if p > 40:
            return {"puan": round(p, 1), "yon": "SHORT", "tip": "üst likidite sweep"}
    return {"puan": 0, "yon": None, "tip": None}


# =====================================================================
# GENEL TARAMA — tüm formasyonları + şekilleri puanla
# =====================================================================
def tum_formasyonlar(mumlar, dip_bolgede=False, tepe_bolgede=False, hacim_yuksek=False):
    """
    Tüm formasyon ve şekilleri tarar, benzerlik puanlarını döndürür.
    Belgedeki mantık: "Hammer %88, Engulfing %65, Wedge %72..."
    """
    if len(mumlar) < 3:
        return {}
    son = mumlar[-1]; onceki = mumlar[-2]
    m1, m2, m3 = mumlar[-3], mumlar[-2], mumlar[-1]

    sonuc = {
        # Tekli
        "hammer":        hammer(son, dip_bolgede, hacim_yuksek),
        "ters_hammer":   ters_hammer(son, dip_bolgede, hacim_yuksek),
        "shooting_star": shooting_star(son, tepe_bolgede, hacim_yuksek),
        "doji":          doji(son),
        "pin_bar":       pin_bar(son),
        "marubozu":      marubozu(son),
        "spinning_top":  spinning_top(son),
        # İkili
        "engulfing":     engulfing(onceki, son, hacim_yuksek),
        "harami":        harami(onceki, son),
        "piercing":      piercing(onceki, son),
        "dark_cloud":    dark_cloud(onceki, son),
        "tweezer":       tweezer(onceki, son),
        # Üçlü
        "morning_star":  morning_star(m1, m2, m3),
        "evening_star":  evening_star(m1, m2, m3),
        "uc_asker":      uc_asker(m1, m2, m3),
        "uc_karga":      uc_karga(m1, m2, m3),
        "uc_inside":     uc_inside(m1, m2, m3),
        "uc_outside":    uc_outside(m1, m2, m3),
        # Geometrik
        "ucgen":         ucgen_sekil(mumlar),
        "wedge":         wedge(mumlar),
        "kanal":         kanal(mumlar),
        "obo":           omuz_bas_omuz(mumlar),
        "cift_tepe_dip": cift_tepe_dip(mumlar),
        "uclu_tepe_dip": uclu_tepe_dip(mumlar),
        "bayrak_flama":  bayrak_flama(mumlar),
        "cup_handle":    cup_handle(mumlar),
        "likidite_sweep": likidite_sweep(mumlar),
    }
    return sonuc


def en_guclu_formasyonlar(mumlar, esik=60, **kwargs):
    """Puanı eşiği geçen formasyonları güçten sıralı döndürür."""
    tum = tum_formasyonlar(mumlar, **kwargs)
    guclu = [(ad, r) for ad, r in tum.items() if r.get("puan", 0) >= esik]
    guclu.sort(key=lambda x: x[1]["puan"], reverse=True)
    return guclu


# =====================================================================
# HIZLI TEST
# =====================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  FORMASYONLAR — TEKLİ+İKİLİ+ÜÇLÜ+GEO (Esnek Matematik)")
    print("=" * 60)

    # Hammer
    hammer_mum = [0, 100.0, 100.5, 96.0, 100.2, 5000]
    print(f"\n[Hammer]  {hammer(hammer_mum, dip_bolgede=True, hacim_yuksek=True)}")

    # Engulfing
    print(f"[Engulfing]  {engulfing([0,100,100.2,98,98.5,3000],[1,98.3,101,98.2,100.8,6000], hacim_yuksek=True)}")

    # 3 Karga
    k1=[0,100,100.2,98,98.2,3000]; k2=[1,98.2,98.5,96,96.3,3500]; k3=[2,96.3,96.5,94,94.2,4000]
    print(f"[3 Karga]  {uc_karga(k1,k2,k3)}")

    # Geometrik: üçgen için trend verisi üret
    import random; random.seed(1)
    m=[]; f=100
    for i in range(60):
        # daralan simetrik üçgen benzeri
        genislik = max(0.5, 5 - i*0.07)
        h = f + random.uniform(0, genislik); l = f - random.uniform(0, genislik)
        c = random.uniform(l, h); o = random.uniform(l, h)
        m.append([i, o, h, l, c, random.uniform(2000,5000)]); f = c
    print(f"\n[Üçgen]  {ucgen_sekil(m)}")
    print(f"[Kanal]  {kanal(m)}")
    print(f"[Likidite Sweep]  {likidite_sweep(m)}")

    print(f"\n[En güçlü formasyonlar (hammer mumuyla)]")
    mumlar_test = [[i,100,101,99,100.5,3000] for i in range(58)] + \
                  [[58,100,100.2,98,98.5,3000],[59,98.3,101,98.2,100.8,6000]]
    for ad, r in en_guclu_formasyonlar(mumlar_test, esik=50):
        print(f"    {ad}: {r['puan']} ({r.get('yon')})")
