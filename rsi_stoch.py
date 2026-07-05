"""
rsi_stoch.py — RSI (7/14/24) + StochRSI Analiz Modülü
=====================================================================
RSI: Wilder yumuşatma (TradingView/pandas-ta ile birebir)
  RSI7  → erken uyarı, TP tetik (>85)
  RSI14 → ana tetik
  RSI24 → trend yön belirleyici

StochRSI: 14 periyot, %K = SMA(ham,3), %D = SMA(%K,3)
  (TradingView/pandas-ta varsayılan — EMA değil SMA)

BÖLGELER:
  0-30   : aşırı satım (likidite bitti, alım başlar)
  30-45  : sağlıklı düşüş
  45-55  : nötr kanal (pullback/retest/A/D)
  55-70  : sağlıklı yükseliş
  71-100 : aşırı alım (kar satışı, sahte yükseliş riski)

FELSEFE: Eşiğe değme değil, DAVRANISH (geçiş, dizilim, divergence).
"""

import math

PENCERE = 14


# =====================================================================
# TEMEL
# =====================================================================
def sigmoid(x, a, k):
    try: return 1.0 / (1.0 + math.exp(-k * (x - a)))
    except OverflowError: return 0.0 if x < a else 1.0

def ters_sigmoid(x, a, k):
    return 1.0 - sigmoid(x, a, k)

def yatay_olcer(dx, k=5.0):
    return 1.0 - abs(2 * sigmoid(dx, 0, k) - 1)

def _sma(seri, p):
    if len(seri) < p: return [None] * len(seri)
    out = [None] * (p - 1)
    for i in range(p - 1, len(seri)):
        out.append(sum(seri[i - p + 1:i + 1]) / p)
    return out


# =====================================================================
# RSI — Wilder yumuşatma
# =====================================================================
def _rsi_serisi(kapanislar, periyot):
    """Wilder RSI serisi. kapanislar = float listesi."""
    n = len(kapanislar)
    if n < periyot + 1:
        return [None] * n
    kazanc = []; kayip = []
    for i in range(1, n):
        fark = kapanislar[i] - kapanislar[i - 1]
        kazanc.append(max(fark, 0.0))
        kayip.append(max(-fark, 0.0))

    # İlk ortalama: SMA
    ag = sum(kazanc[:periyot]) / periyot
    ak = sum(kayip[:periyot]) / periyot

    out = [None] * (periyot)
    rs = ag / ak if ak != 0 else float('inf')
    out.append(100 - 100 / (1 + rs))

    for i in range(periyot, len(kazanc)):
        ag = (ag * (periyot - 1) + kazanc[i]) / periyot
        ak = (ak * (periyot - 1) + kayip[i]) / periyot
        rs = ag / ak if ak != 0 else float('inf')
        out.append(100 - 100 / (1 + rs))

    return out


def rsi_hesapla(mumlar):
    """
    RSI7, RSI14, RSI24 serilerini döndürür.
    mum = [zaman, o, h, l, c, v]
    """
    kapanislar = [float(m[4]) for m in mumlar]
    return {
        "rsi7":  _rsi_serisi(kapanislar, 7),
        "rsi14": _rsi_serisi(kapanislar, 14),
        "rsi24": _rsi_serisi(kapanislar, 24),
    }


# =====================================================================
# StochRSI — %K = SMA(ham,3), %D = SMA(%K,3)
# =====================================================================
def stochrsi_hesapla(mumlar, rsi_periyot=14, k_periyot=3, d_periyot=3):
    """
    StochRSI serisi (TradingView varsayılanı).
    ham  = 100 × (RSI - min_RSI14) / (max_RSI14 - min_RSI14)
    %K   = SMA(ham, 3)
    %D   = SMA(%K, 3)
    """
    kapanislar = [float(m[4]) for m in mumlar]
    rsi = _rsi_serisi(kapanislar, rsi_periyot)
    n = len(rsi)
    ham = []
    for i in range(n):
        if rsi[i] is None:
            ham.append(None); continue
        pencere = [r for r in rsi[max(0, i - rsi_periyot + 1):i + 1] if r is not None]
        if len(pencere) < rsi_periyot:
            ham.append(None); continue
        mn = min(pencere); mx = max(pencere)
        if mx == mn:
            ham.append(50.0)
        else:
            ham.append(100 * (rsi[i] - mn) / (mx - mn))

    ham_temiz = [h if h is not None else 0.0 for h in ham]
    k_seri = _sma(ham_temiz, k_periyot)
    k_temiz = [v if v is not None else 0.0 for v in k_seri]
    d_seri = _sma(k_temiz, d_periyot)

    # None'ları geri koy
    for i in range(n):
        if ham[i] is None:
            k_seri[i] = None; d_seri[i] = None

    return {"stoch_k": k_seri, "stoch_d": d_seri, "stoch_ham": ham}


# =====================================================================
# RSI DAVRANIŞ ANALİZİ
# =====================================================================
def rsi_bolge(rsi_degeri):
    """RSI değerinin hangi bölgede olduğu + sigmoid puanı."""
    if rsi_degeri is None: return {"bolge": "bilinmiyor", "puan": 0}
    r = rsi_degeri
    if r <= 30:
        return {"bolge": "asiri_satim", "puan": round(ters_sigmoid(r, 30, 0.3) * 100, 1)}
    elif r <= 45:
        return {"bolge": "saglikli_dusus", "puan": round((sigmoid(r, 30, 0.3) - sigmoid(r, 45, 0.3)) * 100, 1)}
    elif r <= 55:
        return {"bolge": "notr_kanal", "puan": round((sigmoid(r, 45, 0.3) - sigmoid(r, 55, 0.3)) * 100, 1)}
    elif r <= 70:
        return {"bolge": "saglikli_yukselis", "puan": round((sigmoid(r, 55, 0.3) - sigmoid(r, 70, 0.3)) * 100, 1)}
    else:
        return {"bolge": "asiri_alim", "puan": round(sigmoid(r, 71, 0.3) * 100, 1)}


def rsi_davranis(mumlar):
    """
    Son kapanmış mumun RSI davranış analizi.

    Dönüş:
      rsi7/14/24     : son değerler
      bolge          : her RSI'nın bölgesi
      dizilim        : yukselis / dusus / karisik
      gecis          : yukselis_baslangic / dusus_baslangic / yok
      tp_tetik       : RSI7 > 85 → TP bölgesi
      wick_uyari     : ani yükseliş uyarısı (yükseliş trendinde)
      short_avi      : ani ters hareket uyarısı (düşüş trendinde)
      dip_donus      : RSI7+RSI14 > 44, RSI24 < 44 + fiyat ≥ son dip
    """
    rsi = rsi_hesapla(mumlar)
    r7  = rsi["rsi7"][-1];  r7p  = rsi["rsi7"][-2]  if len(rsi["rsi7"]) > 1  else r7
    r14 = rsi["rsi14"][-1]; r14p = rsi["rsi14"][-2] if len(rsi["rsi14"]) > 1 else r14
    r24 = rsi["rsi24"][-1]; r24p = rsi["rsi24"][-2] if len(rsi["rsi24"]) > 1 else r24

    if None in (r7, r14, r24):
        return {"gecerli": False}

    # Bölgeler
    b7  = rsi_bolge(r7)
    b14 = rsi_bolge(r14)
    b24 = rsi_bolge(r24)

    # TP tetik: RSI7 > 85
    tp_tetik = round(sigmoid(r7, 85, 0.5) * 100, 1)

    # Dizilim
    yukselis_diz = sigmoid(r7 - r14, 0, 5) * sigmoid(r14 - r24, 0, 5)
    dusus_diz    = sigmoid(r24 - r14, 0, 5) * sigmoid(r14 - r7, 0, 5)
    if yukselis_diz > 0.6:
        dizilim = "yukselis"
    elif dusus_diz > 0.6:
        dizilim = "dusus"
    else:
        dizilim = "karisik"

    # Wick/ani yükseliş uyarısı: 55+ bölge + RSI7≈RSI14 > RSI24
    wick_uyari = round(
        sigmoid(r7 - r24, 0, 3) * yatay_olcer(r7 - r14) * sigmoid(r14, 55, 0.3) * 100, 1
    )

    # Short avı uyarısı: 44- bölge + RSI7≈RSI14 < RSI24
    short_avi = round(
        sigmoid(r24 - r7, 0, 3) * yatay_olcer(r7 - r14) * ters_sigmoid(r14, 44, 0.3) * 100, 1
    )

    # Geçiş: yükseliş başlangıcı (önceki TF ~49, şimdi RSI7+RSI14 > 50)
    yukselis_gecis = round(
        sigmoid(r7 - 50, 0, 2) * sigmoid(r14 - 50, 0, 2) *
        ters_sigmoid(r7p - 50, 0, 2) * 100, 1
    )

    # Geçiş: yükseliş teyidi (RSI24 da 50 geçti)
    yukselis_teyit = round(
        sigmoid(r7 - 50, 0, 2) * sigmoid(r14 - 50, 0, 2) * sigmoid(r24 - 50, 0, 2) * 100, 1
    )

    # Geçiş: düşüş başlangıcı
    dusus_gecis = round(
        ters_sigmoid(r7 - 50, 0, 2) * ters_sigmoid(r14 - 50, 0, 2) *
        sigmoid(r7p - 50, 0, 2) * 100, 1
    )

    # Dip dönüşü: RSI7+RSI14 > 44, RSI24 hâlâ < 44
    dip_donus_rsi = round(
        sigmoid(r7 - 44, 0, 2) * sigmoid(r14 - 44, 0, 2) *
        ters_sigmoid(r24 - 44, 0, 2) * 100, 1
    )

    # Karışık sinyal: RSI7 hareket ediyor, RSI14+RSI24 yatay
    karisik = round(
        yatay_olcer(r14p - r14) * yatay_olcer(r24p - r24) *
        sigmoid(abs(r7 - r7p), 0, 3) * 100, 1
    )

    return {
        "gecerli": True,
        "rsi7": round(r7, 1), "rsi14": round(r14, 1), "rsi24": round(r24, 1),
        "bolge_r7": b7["bolge"], "bolge_r14": b14["bolge"], "bolge_r24": b24["bolge"],
        "dizilim": dizilim,
        "tp_tetik": tp_tetik,
        "wick_uyari": wick_uyari,
        "short_avi": short_avi,
        "yukselis_gecis": yukselis_gecis,
        "yukselis_teyit": yukselis_teyit,
        "dusus_gecis": dusus_gecis,
        "dip_donus_rsi": dip_donus_rsi,
        "karisik_sinyal": karisik,
    }


# =====================================================================
# StochRSI DAVRANIŞ ANALİZİ
# =====================================================================
def stochrsi_davranis(mumlar):
    """
    StochRSI davranış analizi.

    Alım tetik  : %K < 20 + %D < 20 + %K > %D (yukarı kesişim) + %D ≥ 18
    Satış tetik : %K > 80 + %D > 70 + %K < %D (aşağı kesişim)
    Satış teyit : %K < 50 + %D ≤ 50 (düşüş sağlıklı devam)
    Yükseliş tr : %K ≥ 80 + %D ≥ 70
    """
    sr = stochrsi_hesapla(mumlar)
    k = sr["stoch_k"][-1]; kp = sr["stoch_k"][-2] if len(sr["stoch_k"]) > 1 else k
    d = sr["stoch_d"][-1]; dp = sr["stoch_d"][-2] if len(sr["stoch_d"]) > 1 else d

    if None in (k, d, kp, dp):
        return {"gecerli": False}

    # Alım tetik: %K < 20, %D < 20, %K > %D (yukarı keser), %D ≥ 18 ivme
    alim_tetik = round(
        ters_sigmoid(k, 20, 0.5) *
        ters_sigmoid(d, 20, 0.5) *
        sigmoid(k - d, 0, 3) *
        sigmoid(d - 18, 0, 2) * 100, 1
    )

    # %D ivmesi (yukarı eğim)
    d_ivme = round(sigmoid(d - dp, 0, 5) * 100, 1)

    # Satış tetik: %K > 80, %D > 70, %K < %D (aşağı keser)
    satis_tetik = round(
        sigmoid(k, 80, 0.5) *
        sigmoid(d - 70, 0, 3) *
        sigmoid(d - k, 0, 3) * 100, 1
    )

    # Satış teyit: %K < 50, %D ≤ 50
    satis_teyit = round(
        ters_sigmoid(k - 50, 0, 2) *
        ters_sigmoid(d - 50, 0, 2) * 100, 1
    )

    # Yükseliş trendi: %K ≥ 80, %D ≥ 70
    yukselis_trend = round(
        sigmoid(k, 80, 0.3) * sigmoid(d, 70, 0.3) * 100, 1
    )

    return {
        "gecerli": True,
        "stoch_k": round(k, 1), "stoch_d": round(d, 1),
        "alim_tetik": alim_tetik,
        "d_ivme": d_ivme,
        "satis_tetik": satis_tetik,
        "satis_teyit": satis_teyit,
        "yukselis_trend": yukselis_trend,
    }


# =====================================================================
# DIVERGENCE (StochRSI öncü, RSI teyit)
# =====================================================================
def divergence_tespit(mumlar, bak=20):
    """
    Fiyat-StochRSI divergence (öncü).
    Fiyat-RSI14 divergence (teyit, +ağırlık).

    Dönüş: 4 tip + confluence ağırlığı
      duzgun_boga  : fiyat LL + gösterge HL → dönüş alım
      duzgun_ayi   : fiyat HH + gösterge LH → dönüş satım
      gizli_boga   : fiyat HL + gösterge LL → trend devam ↑
      gizli_ayi    : fiyat LH + gösterge HL → trend devam ↓
    """
    if len(mumlar) < bak:
        return {"gecerli": False}

    m = mumlar[-bak:]
    yari = bak // 2

    # Fiyat tepe/dip
    f_dip_son  = min(float(x[3]) for x in m[yari:])
    f_dip_ilk  = min(float(x[3]) for x in m[:yari])
    f_tepe_son = max(float(x[2]) for x in m[yari:])
    f_tepe_ilk = max(float(x[2]) for x in m[:yari])

    # StochRSI tepe/dip
    sr = stochrsi_hesapla(m)
    k_seri = [v for v in sr["stoch_k"] if v is not None]
    if len(k_seri) < bak // 2:
        return {"gecerli": False}
    yari_k = len(k_seri) // 2
    sk_dip_son  = min(k_seri[yari_k:])
    sk_dip_ilk  = min(k_seri[:yari_k])
    sk_tepe_son = max(k_seri[yari_k:])
    sk_tepe_ilk = max(k_seri[:yari_k])

    # RSI14 tepe/dip (teyit)
    rsi = rsi_hesapla(m)
    r14 = [v for v in rsi["rsi14"] if v is not None]
    if len(r14) >= yari:
        yari_r = len(r14) // 2
        r14_dip_son  = min(r14[yari_r:])
        r14_dip_ilk  = min(r14[:yari_r])
        r14_tepe_son = max(r14[yari_r:])
        r14_tepe_ilk = max(r14[:yari_r])
        rsi_teyit_boga = 0.3 if (f_dip_son < f_dip_ilk and r14_dip_son > r14_dip_ilk) else 0.0
        rsi_teyit_ayi  = 0.3 if (f_tepe_son > f_tepe_ilk and r14_tepe_son < r14_tepe_ilk) else 0.0
    else:
        rsi_teyit_boga = rsi_teyit_ayi = 0.0

    # 4 divergence tipi
    duzgun_boga = 1.0 if (f_dip_son < f_dip_ilk and sk_dip_son > sk_dip_ilk) else 0.0
    duzgun_ayi  = 1.0 if (f_tepe_son > f_tepe_ilk and sk_tepe_son < sk_tepe_ilk) else 0.0
    gizli_boga  = 1.0 if (f_dip_son > f_dip_ilk and sk_dip_son < sk_dip_ilk) else 0.0
    gizli_ayi   = 1.0 if (f_tepe_son < f_tepe_ilk and sk_tepe_son > sk_tepe_ilk) else 0.0

    return {
        "gecerli": True,
        "duzgun_boga": duzgun_boga,   # dönüş alım
        "duzgun_ayi":  duzgun_ayi,    # dönüş satım
        "gizli_boga":  gizli_boga,    # trend devam ↑
        "gizli_ayi":   gizli_ayi,     # trend devam ↓
        "rsi_teyit_boga": rsi_teyit_boga,  # +0.3 ek ağırlık
        "rsi_teyit_ayi":  rsi_teyit_ayi,   # +0.3 ek ağırlık
    }


# =====================================================================
# BİRLEŞİK — RSI + StochRSI
# =====================================================================
def rsi_stoch_analiz(mumlar):
    """
    Tam RSI + StochRSI analizi.
    Her iki gösterge aynı yönde → teyit (güvenilir sinyal).
    """
    if len(mumlar) < 30:
        return {"gecerli": False, "sebep": "yetersiz mum"}

    rsi_d  = rsi_davranis(mumlar)
    sr_d   = stochrsi_davranis(mumlar)
    div    = divergence_tespit(mumlar)

    if not rsi_d.get("gecerli") or not sr_d.get("gecerli"):
        return {"gecerli": False, "sebep": "hesaplama yetersiz"}

    # Birleşik alım teyidi: RSI dip dönüşü + StochRSI alım tetik
    alim_teyit = round(
        (rsi_d["dip_donus_rsi"] / 100) * (sr_d["alim_tetik"] / 100) * 100, 1
    )

    # Birleşik satış teyidi: RSI aşırı alım + StochRSI satış tetik
    satis_teyit = round(
        (rsi_d["tp_tetik"] / 100) * (sr_d["satis_tetik"] / 100) * 100, 1
    )

    # Yükseliş başlangıcı teyidi
    yukselis_teyit = round(
        (rsi_d["yukselis_gecis"] / 100) * (sr_d["yukselis_trend"] / 100) * 100, 1
    )

    return {
        "gecerli": True,
        "rsi": rsi_d,
        "stochrsi": sr_d,
        "divergence": div,
        "alim_teyit": alim_teyit,
        "satis_teyit": satis_teyit,
        "yukselis_teyit": yukselis_teyit,
    }


# =====================================================================
# TEST
# =====================================================================
if __name__ == "__main__":
    import random
    random.seed(42)

    def uret(n, yukselis=True, taban=100):
        m = []; f = taban
        for i in range(n):
            o = f + random.uniform(-1, 1)
            h = o + random.uniform(0.5, 2)
            l = o - random.uniform(0.5, 2)
            c = l + (h - l) * (random.uniform(0.6, 0.9) if yukselis else random.uniform(0.1, 0.4))
            m.append([i, o, h, l, c, random.uniform(1000, 5000)])
            f = c
        return m

    print("=" * 60)
    print("  RSI + StochRSI DAVRANIŞ TESTİ")
    print("=" * 60)

    # Yükseliş senaryosu
    yukselis_mumlar = uret(60, yukselis=True)
    r = rsi_stoch_analiz(yukselis_mumlar)
    print("\n[Yükseliş senaryosu]")
    print(f"  RSI7={r['rsi']['rsi7']} | RSI14={r['rsi']['rsi14']} | RSI24={r['rsi']['rsi24']}")
    print(f"  Bölge: {r['rsi']['bolge_r14']} | Dizilim: {r['rsi']['dizilim']}")
    print(f"  StochK={r['stochrsi']['stoch_k']} | StochD={r['stochrsi']['stoch_d']}")
    print(f"  Alım teyit: {r['alim_teyit']} | Satış teyit: {r['satis_teyit']}")
    print(f"  Yükseliş geçiş: {r['rsi']['yukselis_gecis']} | Teyit: {r['rsi']['yukselis_teyit']}")
    print(f"  TP tetik: {r['rsi']['tp_tetik']} | Wick uyarı: {r['rsi']['wick_uyari']}")
    print(f"  Divergence: {r['divergence']}")

    # Düşüş senaryosu
    dusus_mumlar = uret(60, yukselis=False)
    r2 = rsi_stoch_analiz(dusus_mumlar)
    print("\n[Düşüş senaryosu]")
    print(f"  RSI7={r2['rsi']['rsi7']} | RSI14={r2['rsi']['rsi14']} | RSI24={r2['rsi']['rsi24']}")
    print(f"  Bölge: {r2['rsi']['bolge_r14']} | Dizilim: {r2['rsi']['dizilim']}")
    print(f"  Short avı uyarısı: {r2['rsi']['short_avi']} | Dip dönüşü: {r2['rsi']['dip_donus_rsi']}")
    print(f"  StochRSI satış teyit: {r2['stochrsi']['satis_teyit']}")
