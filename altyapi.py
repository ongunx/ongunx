"""
altyapi.py — Binance Veri Çekme Altyapısı
=====================================================================
Tüm modüllere temiz, standart veri sağlar.

KURAL: Tüm indikatörler KAPANMIŞ mum üzerinden çalışır.
  mum_cek_kapali() → canlı (açık) mumu atar, sadece kapanmış döndürür
  mum_cek()        → ham liste (canlı dahil, sadece anlık takip için)

MUM FORMAT: [açılış_zamanı, o, h, l, c, hacim, kapanış_zamanı, quote_hacim,
             işlem_sayısı, taker_buy_base, taker_buy_quote, ignore]
  → Binance standart kline formatı (12 alan)
  → [0]=zaman [1]=o [2]=h [3]=l [4]=c [5]=hacim(coin) [9]=taker_buy_base

KURULUM:
  pip install python-binance
  API anahtarları: Binance → Hesap → API Yönetimi (sadece okuma yeterli)
"""

from binance.client import Client
from binance.exceptions import BinanceAPIException
import time

# =====================================================================
# İSTEĞE BAĞLI — API anahtarı yoksa public endpoint'ler çalışır
# (kline, OI, funding için anahtar gerekmez; hesap işlemleri için gerekir)
# =====================================================================
_client = None

def client_baslat(api_key="", api_secret=""):
    """
    Binance client'ı başlatır. Okuma işlemleri için anahtar zorunlu değil.
    Anahtarlar varsa daha yüksek rate limit sağlar.
    """
    global _client
    _client = Client(api_key, api_secret)
    return _client

def _get_client():
    global _client
    if _client is None:
        _client = Client("", "")
    return _client


# =====================================================================
# ZAMAN DİLİMİ SABİTLERİ
# =====================================================================
TF = {
    "15m": Client.KLINE_INTERVAL_15MINUTE,
    "1h":  Client.KLINE_INTERVAL_1HOUR,
    "4h":  Client.KLINE_INTERVAL_4HOUR,
    "1d":  Client.KLINE_INTERVAL_1DAY,
}

MIN_MUM = 14   # minimum kapanmış mum sayısı


# =====================================================================
# SPOT MUM VERİSİ
# =====================================================================
def mum_cek(sembol, aralik="1h", adet=50):
    """
    Ham kline listesi (canlı mum DAHİL).
    Sadece anlık takip / kıyaslama için kullan.
    sembol: "BTCUSDT", aralik: "15m"/"1h"/"4h"/"1d"
    """
    c = _get_client()
    try:
        klines = c.get_klines(symbol=sembol, interval=TF.get(aralik, aralik), limit=adet)
        return klines
    except BinanceAPIException as e:
        print(f"[altyapi] Spot mum hatası {sembol}: {e}")
        return []


def mum_cek_kapali(sembol, aralik="1h", adet=50):
    """
    Sadece KAPANMIŞ mumlar (canlı/açık mum ATILIR).
    Tüm indikatörler bu fonksiyondan beslenir.
    adet: istenen kapanmış mum sayısı (1 fazla çekilir, son atılır)
    """
    ham = mum_cek(sembol, aralik, adet + 1)
    if len(ham) < 2:
        return []
    return ham[:-1]   # son (açık) mumu at


def spot_veri_hazirla(sembol, ana_tf="1h", giris_tf="15m", trend_tf="4h"):
    """
    Senaryo motoru için 3 zaman diliminde spot veri paketi.
    Döndürür: {ana, giris, trend, gunluk} — hepsi kapanmış mum
    """
    return {
        "ana":    mum_cek_kapali(sembol, ana_tf, 60),      # 1H — sinyal
        "giris":  mum_cek_kapali(sembol, giris_tf, 60),    # 15M — giriş
        "trend":  mum_cek_kapali(sembol, trend_tf, 60),    # 4H — trend teyit
        "gunluk": mum_cek_kapali(sembol, "1d", 30),        # 1D — hacim/OBV
    }


# =====================================================================
# FUTURES MUM VERİSİ
# =====================================================================
def futures_mum_cek(sembol, aralik="1h", adet=50):
    """
    Futures (perp) kline — canlı mum DAHİL.
    CVD hesabı için taker_buy_base (index 9) kullanılır.
    """
    c = _get_client()
    try:
        klines = c.futures_klines(symbol=sembol, interval=TF.get(aralik, aralik), limit=adet)
        return klines
    except BinanceAPIException as e:
        print(f"[altyapi] Futures mum hatası {sembol}: {e}")
        return []


def futures_mum_kapali(sembol, aralik="1h", adet=50):
    """Sadece kapanmış futures mumlar."""
    ham = futures_mum_cek(sembol, aralik, adet + 1)
    if len(ham) < 2:
        return []
    return ham[:-1]


# =====================================================================
# OPEN INTEREST
# =====================================================================
def oi_cek(sembol, aralik="1h", adet=50):
    """
    Futures Open Interest geçmişi.
    Döndürür: [{'timestamp': ms, 'sumOpenInterest': '123.45', ...}, ...]
    Binance: futures_open_interest_hist — 200 kayıt limit.
    """
    c = _get_client()
    periyot_map = {
        "15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d",
    }
    try:
        veri = c.futures_open_interest_hist(
            symbol=sembol,
            period=periyot_map.get(aralik, "1h"),
            limit=adet
        )
        return veri
    except BinanceAPIException as e:
        print(f"[altyapi] OI hatası {sembol}: {e}")
        return []


# =====================================================================
# FUNDING RATE
# =====================================================================
def funding_cek(sembol):
    """
    Güncel funding rate.
    Döndürür: float (örn. 0.0001 = %0.01)
    """
    c = _get_client()
    try:
        veri = c.futures_funding_rate(symbol=sembol, limit=1)
        if veri:
            return float(veri[-1]["fundingRate"])
        return 0.0
    except BinanceAPIException as e:
        print(f"[altyapi] Funding hatası {sembol}: {e}")
        return 0.0


# =====================================================================
# PİYASA DEĞERİ / HACİM FİLTRESİ
# =====================================================================
def gunluk_hacim_usdt(sembol):
    """
    24 saatlik işlem hacmi (USDT cinsinden).
    >2M filtresi için kullanılır (hacim_tarama.py).
    """
    c = _get_client()
    try:
        ticker = c.get_ticker(symbol=sembol)
        return float(ticker["quoteVolume"])   # USDT hacmi
    except BinanceAPIException as e:
        print(f"[altyapi] Hacim hatası {sembol}: {e}")
        return 0.0


# =====================================================================
# TAM VERİ PAKETİ — senaryo motoru için
# =====================================================================
def tam_veri_paketi(sembol, ana_tf="1h"):
    """
    Tek çağrıyla tüm metriklerin ihtiyaç duyduğu veriyi toplar.

    Döndürür:
      spot_ana      : 1H kapanmış spot mumlar (sinyal katmanı)
      spot_giris    : 15M kapanmış spot mumlar (giriş katmanı)
      spot_trend    : 4H kapanmış spot mumlar (trend teyit)
      spot_gunluk   : 1D kapanmış spot mumlar (hacim/OBV/birikim)
      fut_ana       : 1H kapanmış futures mumlar (CVD)
      fut_gunluk    : 1D kapanmış futures mumlar
      oi            : OI geçmişi (1H)
      funding       : anlık funding rate (float)
      gunluk_hacim  : 24H USDT hacmi (filtre için)
      gecerli       : False ise yetersiz veri
    """
    spot_ana    = mum_cek_kapali(sembol, ana_tf, 60)
    spot_giris  = mum_cek_kapali(sembol, "15m", 60)
    spot_trend  = mum_cek_kapali(sembol, "4h", 60)
    spot_gunluk = mum_cek_kapali(sembol, "1d", 30)
    fut_ana     = futures_mum_kapali(sembol, ana_tf, 60)
    fut_gunluk  = futures_mum_kapali(sembol, "1d", 30)
    oi          = oi_cek(sembol, ana_tf, 30)
    funding     = funding_cek(sembol)
    hacim       = gunluk_hacim_usdt(sembol)

    gecerli = (
        len(spot_ana) >= MIN_MUM and
        len(fut_ana) >= MIN_MUM and
        len(oi) >= 5
    )

    return {
        "sembol":       sembol,
        "spot_ana":     spot_ana,
        "spot_giris":   spot_giris,
        "spot_trend":   spot_trend,
        "spot_gunluk":  spot_gunluk,
        "fut_ana":      fut_ana,
        "fut_gunluk":   fut_gunluk,
        "oi":           oi,
        "funding":      funding,
        "gunluk_hacim": hacim,
        "gecerli":      gecerli,
    }


# =====================================================================
# ÇOKLU SEMBOl TARAMA (liste)
# =====================================================================
def sembol_listesi_filtrele(semboller, min_hacim=2_000_000, bekleme=0.2):
    """
    Sembol listesinden günlük hacim <2M olanları eler.
    bekleme: her API çağrısı arasında saniye (rate limit koruması).
    Döndürür: geçen semboller listesi
    """
    gecenler = []
    for s in semboller:
        hacim = gunluk_hacim_usdt(s)
        if hacim >= min_hacim:
            gecenler.append(s)
        time.sleep(bekleme)
    return gecenler


# =====================================================================
# TEST
# =====================================================================
if __name__ == "__main__":
    print("=" * 55)
    print("  ALTYAPI TEST (gerçek API çağrısı)")
    print("=" * 55)

    # API anahtarı olmadan public endpoint test
    client_baslat()   # anahtarsız

    sembol = "BTCUSDT"

    print(f"\n[Spot kapanmış mumlar — 1H, son 5]")
    mumlar = mum_cek_kapali(sembol, "1h", 10)
    print(f"  Adet: {len(mumlar)}")
    if mumlar:
        son = mumlar[-1]
        print(f"  Son mum: o={son[1]} h={son[2]} l={son[3]} c={son[4]} v={son[5]}")

    print(f"\n[Futures kapanmış mumlar — 1H, son 5]")
    fut = futures_mum_kapali(sembol, "1h", 10)
    print(f"  Adet: {len(fut)}")

    print(f"\n[OI geçmişi — son 5]")
    oi = oi_cek(sembol, "1h", 10)
    print(f"  Adet: {len(oi)}")
    if oi:
        print(f"  Son OI: {oi[-1].get('sumOpenInterest')}")

    print(f"\n[Funding rate]")
    f = funding_cek(sembol)
    print(f"  {sembol}: {f:.6f}")

    print(f"\n[24H hacim filtresi]")
    h = gunluk_hacim_usdt(sembol)
    print(f"  {sembol}: ${h:,.0f} — {'GEÇTİ' if h >= 2_000_000 else 'ELENDİ'}")
