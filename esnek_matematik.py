"""
esnek_matematik.py — Esnek (Fuzzy) Mum Formasyonu Puanlama Motoru
=====================================================================
"Şekil" değil "davranış". Sert eşik yerine sigmoid ile yumuşak puan.

Felsefe (hadi bu.txt belgesinden):
  - Bir mum "Hammer var/yok" değil, "Hammer benzerliği: %88" olarak ölçülür
  - Sigmoid: f(x) = 1 / (1 + e^(-k*(x-a)))
      x = ölçülen oran (örn. alt fitil / gövde)
      a = ideal seviye (örn. 2.0)
      k = geçiş sertliği (büyük k = keskin, küçük k = yumuşak)
  - Her formasyon, ağırlıklı özelliklerin toplamı olarak 0-100 puan alır

Kütüphane: sadece math (Python standart) — ekstra kurulum yok.
"""

import math


# =====================================================================
# TEMEL FUZZY FONKSİYONLAR
# =====================================================================
def sigmoid(x, a, k):
    """
    Yumuşak geçiş: x, a'ya yakınsa 0.5; büyükse 1'e, küçükse 0'a gider.
    a = ideal nokta, k = sertlik (büyük k = keskin eşik gibi).
    """
    try:
        return 1.0 / (1.0 + math.exp(-k * (x - a)))
    except OverflowError:
        return 0.0 if x < a else 1.0


def ters_sigmoid(x, a, k):
    """
    Ters yumuşak geçiş: x KÜÇÜKSE yüksek puan (örn. 'üst fitil kısa olmalı').
    x < a → 1'e yakın, x > a → 0'a yakın.
    """
    return 1.0 - sigmoid(x, a, k)


def ucgen(x, dusuk, ideal, yuksek):
    """
    Üçgen üyelik: x ideal'de 1.0, kenarlarda 0.0.
    'Şu aralıkta olmalı, ortası en iyi' durumları için.
    """
    if x <= dusuk or x >= yuksek:
        return 0.0
    if x == ideal:
        return 1.0
    if x < ideal:
        return (x - dusuk) / (ideal - dusuk)
    return (yuksek - x) / (yuksek - ideal)


# =====================================================================
# MUM ANATOMİSİ — bir mumun oranlarını çıkar
# =====================================================================
def mum_anatomi(mum):
    """
    Bir mumu oranlara ayırır (fiyat ölçeğinden bağımsız).
    mum = [zaman, açılış, yüksek, düşük, kapanış, hacim]

    Dönüş: sözlük
      govde_oran     : gövde / toplam boy
      alt_fitil_oran : alt fitil / gövde (gövde 0 ise toplam boya göre)
      ust_fitil_oran : üst fitil / gövde
      yon            : +1 yeşil, -1 kırmızı, 0 doji
      kapanis_konum  : kapanışın mumun neresinde (0=dip, 1=tepe)
    """
    o = float(mum[1]); h = float(mum[2]); l = float(mum[3]); c = float(mum[4])
    boy = h - l
    if boy <= 0:
        return None
    govde = abs(c - o)
    ust_fitil = h - max(o, c)
    alt_fitil = min(o, c) - l

    # Gövde çok küçükse fitil oranını toplam boya göre ver (0'a bölme yok)
    payda = govde if govde > boy * 0.02 else boy

    return {
        "govde_oran":     govde / boy,
        "alt_fitil_oran": alt_fitil / payda,
        "ust_fitil_oran": ust_fitil / payda,
        "yon":            1 if c > o else (-1 if c < o else 0),
        "kapanis_konum":  (c - l) / boy,   # 0=dipte kapandı, 1=tepede
        "govde":          govde,
        "boy":            boy,
    }


# =====================================================================
# FORMASYON PUANLAYICILARI (0-100, fuzzy)
# =====================================================================
def hammer_puani(mum, dip_bolgede=False, hacim_yuksek=False):
    """
    Çekiç (Hammer) benzerliği — 0-100 fuzzy puan.
    Belgedeki ağırlıklar:
      alt fitil uzun 35 | üst fitil kısa 20 | gövde küçük 15
      dip bölgede 10 | hacim yüksek 10 | güçlü kapanış 10
    """
    a = mum_anatomi(mum)
    if a is None:
        return {"puan": 0, "detay": {}}

    # Alt fitil gövdenin ~2-3 katı olmalı → sigmoid(a=2.0)
    p_alt   = sigmoid(a["alt_fitil_oran"], a=2.0, k=1.5) * 35
    # Üst fitil kısa olmalı → ters sigmoid (küçükse yüksek puan)
    p_ust   = ters_sigmoid(a["ust_fitil_oran"], a=0.4, k=5.0) * 20
    # Gövde küçük olmalı (toplam boyun küçük kısmı)
    p_govde = ters_sigmoid(a["govde_oran"], a=0.4, k=6.0) * 15
    # Kapanış mumun üst kısmında olmalı (dipte iğne, tepede kapanış)
    p_kapanis = sigmoid(a["kapanis_konum"], a=0.6, k=6.0) * 10
    # Bağlamsal (dışarıdan gelir)
    p_dip   = 10 if dip_bolgede else 0
    p_hacim = 10 if hacim_yuksek else 0

    toplam = p_alt + p_ust + p_govde + p_kapanis + p_dip + p_hacim
    return {
        "puan": round(toplam, 1),
        "detay": {
            "alt_fitil": round(p_alt, 1), "ust_fitil": round(p_ust, 1),
            "govde": round(p_govde, 1), "kapanis": round(p_kapanis, 1),
            "dip": p_dip, "hacim": p_hacim,
        }
    }


def engulfing_puani(onceki_mum, mum, hacim_yuksek=False):
    """
    Yutan (Engulfing) formasyonu benzerliği — 0-100.
    Bullish: önceki kırmızı, şimdi yeşil, gövde öncekini sarıyor.
    Bearish: tersi. Yön dönüşü + sarma oranı + hacim.
    """
    a1 = mum_anatomi(onceki_mum); a2 = mum_anatomi(mum)
    if a1 is None or a2 is None:
        return {"puan": 0, "yon": None, "detay": {}}

    o1 = float(onceki_mum[1]); c1 = float(onceki_mum[4])
    o2 = float(mum[1]); c2 = float(mum[4])
    govde1 = abs(c1 - o1); govde2 = abs(c2 - o2)
    if govde1 <= 0:
        return {"puan": 0, "yon": None, "detay": {}}

    sarma = govde2 / govde1   # yeni gövde öncekinin kaç katı

    # Bullish engulfing: önceki kırmızı (-1), şimdi yeşil (+1)
    if a1["yon"] == -1 and a2["yon"] == 1 and c2 > o1 and o2 < c1:
        yon = "LONG"
    elif a1["yon"] == 1 and a2["yon"] == -1 and c2 < o1 and o2 > c1:
        yon = "SHORT"
    else:
        return {"puan": 0, "yon": None, "detay": {"sarma": round(sarma, 2)}}

    # Sarma oranı ~1.0-2.0 arası ideal, sigmoid(a=1.0)
    p_sarma = sigmoid(sarma, a=1.0, k=3.0) * 60
    # Yeni mumun gövdesi güçlü olmalı (fitil değil gövde baskın)
    p_govde = sigmoid(a2["govde_oran"], a=0.6, k=5.0) * 25
    p_hacim = 15 if hacim_yuksek else 0

    toplam = p_sarma + p_govde + p_hacim
    return {
        "puan": round(toplam, 1), "yon": yon,
        "detay": {"sarma": round(p_sarma, 1), "govde": round(p_govde, 1),
                  "hacim": p_hacim, "sarma_orani": round(sarma, 2)}
    }


def pinbar_puani(mum):
    """
    Pin Bar benzerliği — 0-100. Uzun tek fitil + küçük gövde.
    Yön: alt fitil uzunsa LONG (reddedilen dip), üst uzunsa SHORT.
    """
    a = mum_anatomi(mum)
    if a is None:
        return {"puan": 0, "yon": None, "detay": {}}

    # Hangi fitil baskın?
    if a["alt_fitil_oran"] > a["ust_fitil_oran"]:
        yon = "LONG"; baskin = a["alt_fitil_oran"]; diger = a["ust_fitil_oran"]
    else:
        yon = "SHORT"; baskin = a["ust_fitil_oran"]; diger = a["alt_fitil_oran"]

    # Baskın fitil uzun (a=2.0), diğer fitil kısa, gövde küçük
    p_baskin = sigmoid(baskin, a=2.0, k=1.5) * 50
    p_diger  = ters_sigmoid(diger, a=0.5, k=4.0) * 25
    p_govde  = ters_sigmoid(a["govde_oran"], a=0.35, k=6.0) * 25

    toplam = p_baskin + p_diger + p_govde
    return {
        "puan": round(toplam, 1), "yon": yon,
        "detay": {"baskin_fitil": round(p_baskin, 1),
                  "diger_fitil": round(p_diger, 1), "govde": round(p_govde, 1)}
    }


def doji_puani(mum):
    """
    Doji benzerliği — 0-100. Çok küçük gövde = kararsızlık.
    Yüksek puan = güçlü doji (işlem AÇMA sinyali, bekle).
    """
    a = mum_anatomi(mum)
    if a is None:
        return {"puan": 0, "detay": {}}
    # Gövde ne kadar küçükse o kadar doji
    p = ters_sigmoid(a["govde_oran"], a=0.1, k=15.0) * 100
    return {"puan": round(p, 1), "detay": {"govde_oran": round(a["govde_oran"], 3)}}


# =====================================================================
# GENEL BENZERLİK — tüm formasyonları puanla
# =====================================================================
def tum_formasyonlar(mumlar, dip_bolgede=False, hacim_yuksek=False):
    """
    Son mum için tüm formasyon benzerlik puanlarını döndürür.
    Belgedeki mantık: "Hammer %88, Engulfing %65, Pin Bar %79..."
    """
    if len(mumlar) < 2:
        return {}
    son = mumlar[-1]; onceki = mumlar[-2]
    return {
        "hammer":    hammer_puani(son, dip_bolgede, hacim_yuksek),
        "engulfing": engulfing_puani(onceki, son, hacim_yuksek),
        "pinbar":    pinbar_puani(son),
        "doji":      doji_puani(son),
    }


# =====================================================================
# HIZLI TEST
# =====================================================================
if __name__ == "__main__":
    print("=" * 55)
    print("  ESNEK MATEMATİK — FORMASYON PUANLAMA TESTİ")
    print("=" * 55)

    # Klasik Hammer: küçük gövde tepede, uzun alt fitil
    # [zaman, açılış, yüksek, düşük, kapanış, hacim]
    hammer = [0, 100.0, 100.5, 96.0, 100.2, 5000]
    print("\n[Klasik Hammer testi]")
    print(f"  Mum: açılış=100, yüksek=100.5, düşük=96, kapanış=100.2")
    r = hammer_puani(hammer, dip_bolgede=True, hacim_yuksek=True)
    print(f"  Hammer puanı: {r['puan']}/100")
    print(f"  Detay: {r['detay']}")

    # Bullish Engulfing
    kirmizi = [0, 100.0, 100.2, 98.0, 98.5, 3000]
    yesil   = [1, 98.3, 101.0, 98.2, 100.8, 6000]
    print("\n[Bullish Engulfing testi]")
    r = engulfing_puani(kirmizi, yesil, hacim_yuksek=True)
    print(f"  Puan: {r['puan']}/100 | Yön: {r['yon']}")
    print(f"  Detay: {r['detay']}")

    # Doji
    doji = [0, 100.0, 100.8, 99.2, 100.02, 4000]
    print("\n[Doji testi]")
    r = doji_puani(doji)
    print(f"  Doji puanı: {r['puan']}/100 (yüksek=kararsızlık, bekle)")
