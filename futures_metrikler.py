"""
futures_metrikler.py — Futures/Order-Flow Metrikleri (Binance)
=====================================================================
Senaryo motorunun ihtiyaç duyduğu, OHLCV'den ÇIKMAYAN metrikler:
  - CVD (Cumulative Volume Delta) — taker alım-satım farkı, birikimli
  - Spot CVD / Future CVD (ayrı)
  - Net Delta — mum bazında taker alım-satım
  - OI (Open Interest) + OI değişim
  - Funding rate
  - Likidite/piyasa değeri oranı
  - Günlük hacim >2M filtresi

VERİ KAYNAĞI: Binance (python-binance). Hazır CVD/OBV YOK — taker verisinden
hesaplanır. Kline'daki taker_buy_base alanı + futures_coin_taker_buy_sell_volume.

NOT: Binance API çağrıları altyapi.py'deki client üzerinden yapılır.
     Bu modül metrik HESAPLAMA mantığını içerir; veri çekme altyapi'ye delege.
"""
import math

# Günlük hacim filtresi eşiği (USDT)
MIN_GUNLUK_HACIM = 2_000_000   # 2M altı coinler elenir


# =====================================================================
# CVD / DELTA — taker alım-satım farkından
# =====================================================================
def net_delta(kline):
    """
    Bir mumun net delta'sı = taker_alım − taker_satım (coin cinsinden).
    kline Binance formatı: [..., volume(5), ..., taker_buy_base(9), ...]
    Toplam hacim - taker_buy = taker_sell.
    """
    toplam = float(kline[5])
    taker_buy = float(kline[9])       # taker (agresif) alıcı hacmi
    taker_sell = toplam - taker_buy   # geri kalan = agresif satıcı
    return taker_buy - taker_sell     # + alım baskın, - satım baskın


PENCERE = 14   # son 14 mum (canlı hariç)

def cvd_serisi(klines, canli_haric=True):
    """
    CVD = net delta'ların birikimli toplamı.
    SON 14 KAPANMIŞ mum üzerinden (canlı/açık mum HARİÇ).
    Pencere başı = referans noktası (0). Mutlak değer değil, eğim okunur.
    """
    # Canlı (son/açık) mumu at
    kapali = klines[:-1] if canli_haric and len(klines) > 0 else klines
    # Son PENCERE kapalı mumu al
    pencere = kapali[-PENCERE:] if len(kapali) >= PENCERE else kapali
    # Pencere başını referans (0) kabul et, oradan birikim
    cvd = [0.0]
    for k in pencere:
        cvd.append(cvd[-1] + net_delta(k))
    return cvd[1:]   # ilk referans 0'ı at


def cvd_egim(klines, canli_haric=True):
    """
    CVD eğimi — son 14 KAPANMIŞ mum penceresinde (canlı hariç).
    Pencere başından sonuna değişim. + yukarı, - aşağı.
    """
    cvd = cvd_serisi(klines, canli_haric)
    if len(cvd) < 2:
        return 0.0
    olcek = (max(cvd) - min(cvd)) or 1
    return (cvd[-1] - cvd[0]) / len(cvd) / olcek   # normalize


def spot_future_cvd(spot_klines, fut_klines):
    """
    Spot CVD ve Future CVD eğimlerini ayrı döndürür.
    Son 14 kapanmış mum (canlı hariç). Yön belirleyici = SPOT CVD.
    """
    return {
        "spot_cvd_egim": cvd_egim(spot_klines),
        "fut_cvd_egim": cvd_egim(fut_klines),
        "net_cvd_egim": cvd_egim(fut_klines),  # net = futures ana akış
        "yon_belirleyici": "spot",
    }


# =====================================================================
# OPEN INTEREST
# =====================================================================
def oi_egim(oi_serisi, bak=10):
    """
    OI değişim eğimi. oi_serisi = [{'timestamp':.., 'sumOpenInterest':..}, ...]
    (Binance futures_open_interest_hist formatı)
    + artıyor (yeni pozisyon), - azalıyor (pozisyon kapanış).
    """
    if len(oi_serisi) < bak:
        return 0.0
    degerler = [float(x["sumOpenInterest"]) for x in oi_serisi[-bak:]]
    ort = sum(degerler)/len(degerler)
    if ort <= 0:
        return 0.0
    return (degerler[-1] - degerler[0]) / bak / ort


# =====================================================================
# FUNDING RATE
# =====================================================================
def funding_degerlendir(funding_orani):
    """
    Funding rate yorumu.
    Aşırı pozitif = longlar kalabalık (satış riski).
    Aşırı negatif = shortlar kalabalık (squeeze riski).
    """
    # Tipik funding ±0.01% (0.0001). Aşırı = ±0.05%+
    return {
        "oran": funding_orani,
        "asiri_pozitif": funding_orani > 0.0005,   # longlar aşırı
        "asiri_negatif": funding_orani < -0.0005,  # shortlar aşırı
    }


# =====================================================================
# LİKİDİTE / PİYASA DEĞERİ + HACİM FİLTRESİ
# =====================================================================
def hacim_filtresi_gecer(gunluk_hacim_usdt):
    """Günlük hacim >2M mi? BLESS gibi düşük likiditeli coinleri eler."""
    return gunluk_hacim_usdt >= MIN_GUNLUK_HACIM


def likidite_orani(gunluk_hacim_usdt, piyasa_degeri):
    """
    Likidite/piyasa değeri oranı. Yüksek = sağlıklı likidite.
    Düşük = manipüle edilebilir (ince piyasa).
    """
    if piyasa_degeri <= 0:
        return 0.0
    return gunluk_hacim_usdt / piyasa_degeri


# =====================================================================
# METRİK PAKETİ — senaryo motoru için hazırla
# =====================================================================
def metrik_paketi_futures(spot_klines, fut_klines, oi_serisi, funding):
    """
    Senaryo motorunun beklediği futures metriklerini toplar.
    (Fiyat/EMA/OBV/SMI ayrı modüllerden gelir, burada order-flow kısmı.)
    """
    cvd = spot_future_cvd(spot_klines, fut_klines)
    return {
        "cvd_egim": cvd["net_cvd_egim"],
        "spot_cvd_egim": cvd["spot_cvd_egim"],
        "fut_cvd_egim": cvd["fut_cvd_egim"],
        "oi_egim": oi_egim(oi_serisi),
        "funding": funding_degerlendir(funding),
    }


if __name__ == "__main__":
    print("="*55)
    print("  FUTURES METRİKLER TESTİ")
    print("="*55)

    # Sahte kline: [t,o,h,l,c,v,ct,qv,n,taker_buy_base,tbq,ig]
    def kline(v, taker_buy):
        return [0,100,101,99,100.5, v, 0,0,0, taker_buy, 0,0]

    # Alım baskın seri (taker_buy > yarı)
    alim = [kline(1000, 700) for _ in range(15)]   # her mumda +400 delta
    print("\n[Alım baskın CVD]")
    print(f"  Net delta (tek mum): {net_delta(alim[0])}")
    print(f"  CVD eğim: {cvd_egim(alim):.3f} (+ = alım)")

    # Satım baskın
    satim = [kline(1000, 300) for _ in range(15)]  # her mumda -400 delta
    print("\n[Satım baskın CVD]")
    print(f"  Net delta: {net_delta(satim[0])}")
    print(f"  CVD eğim: {cvd_egim(satim):.3f} (- = satım)")

    # OI test
    oi = [{"sumOpenInterest": str(1000+i*50)} for i in range(15)]
    print(f"\n[OI artıyor]  eğim: {oi_egim(oi):.3f}")

    # Funding
    print(f"\n[Funding aşırı pozitif]  {funding_degerlendir(0.0008)}")

    # Hacim filtresi
    print(f"\n[Hacim filtresi]")
    print(f"  3M hacim geçer mi: {hacim_filtresi_gecer(3_000_000)}")
    print(f"  0.5M hacim geçer mi: {hacim_filtresi_gecer(500_000)} (BLESS gibi elenir)")
