"""
ana_motor.py — MM/Stop-Avı Tespit Botu Ana Motoru
=====================================================================
MİMARİ: DATA → FEATURES → SCORES → THRESHOLD → ACTION

MİSYON:
  Fiyat hedefe ulaşmadan önce yüksek olasılıklı psikolojik bölgeleri
  tespit et. Destekleyici metrikler hizalanmaya başladığında uyarı ver.
  Son karar her zaman insanda. Güven yetersizse sus — sessizlik geçerli çıktıdır.

UYARI KOŞULU (üçü aynı anda):
  1. Fiyat hedef bölgeye yakın (POC / VPVR / VWAP ±%0.5)
  2. Zincir hizalanıyor (Sweep → Formasyon → CVD → Delta → OI)
  3. Davranış skoru eşiği geçti (varsayılan: 65/100)
  → Üçü olmadan mesaj üretilmez.

Bot karar vermez, işlem açmaz. Son karar kullanıcıda.
"""

import time
import math
import requests

from altyapi import tam_veri_paketi, gunluk_hacim_usdt
from vwap_poc import onay_katmani
from formasyonlar import (
    tum_formasyonlar, likidite_sweep, engulfing, hammer,
    pin_bar, doji, uc_outside, uc_inside
)
from obv_analiz import obv_durum, divergence_giris, divergence_cikis
from futures_metrikler import (
    cvd_egim, spot_future_cvd, oi_egim, funding_degerlendir,
    net_delta, hacim_filtresi_gecer
)
from rsi_stoch import rsi_stoch_analiz
from smi_momentum import smi_davranis, smi_divergence
from hacim_tarama import hacim_tarama
from senaryolar import tum_senaryolar


# =====================================================================
# AYARLAR
# =====================================================================
TELEGRAM_TOKEN = ""          # buraya bot token
TELEGRAM_CHAT_ID = ""        # buraya chat id
TARAMA_ARALIĞI = 60 * 60     # saniye (varsayılan: 1H = yeni mum kapanınca)
MIN_HACIM = 2_000_000        # 2M USDT filtresi
UYARI_ESIK = 65              # davranış skoru bu değerin üstündeyse uyarı ver


# =====================================================================
# TELEGRAM
# =====================================================================
def telegram_gonder(mesaj):
    """Telegram mesajı gönderir. Token/chat_id boşsa yazdırır."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"\n[TELEGRAM]\n{mesaj}\n")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": mesaj}, timeout=10)
    except Exception as e:
        print(f"[Telegram hata] {e}")


# =====================================================================
# TEMEL FUZZY
# =====================================================================
def sig(x, a=0.0, k=1.0):
    try: return 1.0 / (1.0 + math.exp(-k * (x - a)))
    except OverflowError: return 0.0 if x < a else 1.0

def ters_sig(x, a=0.0, k=1.0):
    return 1.0 - sig(x, a, k)

def yatay(dx, k=5.0):
    return 1.0 - abs(2 * sig(dx, 0, k) - 1)


# =====================================================================
# FEATURES — metrik paketini hazırla
# =====================================================================
def features_uret(veri):
    """
    Tüm modülleri çağırır, normalize edilmiş metrik sözlüğü döndürür.
    senaryolar.py'nin beklediği format + ek metrikler.
    """
    spot_ana    = veri["spot_ana"]
    spot_trend  = veri["spot_trend"]
    spot_gunluk = veri["spot_gunluk"]
    fut_ana     = veri["fut_ana"]
    fut_gunluk  = veri["fut_gunluk"]
    oi_veri     = veri["oi"]
    funding     = veri["funding"]

    if len(spot_ana) < 14 or len(fut_ana) < 14:
        return None

    # --- OBV ---
    obv = obv_durum(spot_ana)
    obv_isaret  = obv.get("isaret", 0) if obv.get("gecerli") else 0
    obv_egim_v  = (obv.get("puan", 0) / 100) if obv.get("gecerli") else 0

    # --- CVD ---
    cvd = spot_future_cvd(spot_ana, fut_ana)
    spot_cvd = cvd["spot_cvd_egim"]
    fut_cvd  = cvd["fut_cvd_egim"]
    cvd_net  = cvd["net_cvd_egim"]

    # --- Son mum net delta ---
    son_delta = net_delta(fut_ana[-1]) if fut_ana else 0
    delta_norm = sig(son_delta, 0, 0.0001)  # 0→0.5, pozitif→1

    # --- OI ---
    oi_eg = oi_egim(oi_veri)

    # --- Funding ---
    fund = funding_degerlendir(funding)

    # --- Fiyat eğimi (son 5 kapanmış mum) ---
    kapanislar = [float(m[4]) for m in spot_ana[-6:]]
    fiyat_eg = (kapanislar[-1] - kapanislar[0]) / kapanislar[0] if kapanislar[0] else 0
    fiyat_eg_n = sig(fiyat_eg, 0, 20)  # -1→0, 0→0.5, +1→1 normalize

    # --- Hacim eğimi ---
    hacimler = [float(m[5]) for m in spot_ana[-6:]]
    ort_h = sum(hacimler) / len(hacimler)
    vol_eg = (hacimler[-1] - hacimler[0]) / ort_h if ort_h else 0

    # --- EMA21 / EMA50 dizilim ---
    def ema_hesapla(seri, p):
        k = 2 / (p + 1)
        e = seri[0]
        for x in seri[1:]:
            e = x * k + e * (1 - k)
        return e

    kapanislar_tam = [float(m[4]) for m in spot_ana]
    ema21 = ema_hesapla(kapanislar_tam, 21) if len(kapanislar_tam) >= 21 else None
    ema50 = ema_hesapla(kapanislar_tam, 50) if len(kapanislar_tam) >= 50 else None
    son_fiyat = kapanislar_tam[-1]
    ema_dizilim = 0.0
    if ema21 and ema50:
        ema_dizilim = sig(ema21 - ema50, 0, 0.5)  # ema21>ema50 → boğa

    # --- RSI + StochRSI ---
    rsi_analiz = rsi_stoch_analiz(spot_ana)
    rsi14 = rsi_analiz["rsi"]["rsi14"] if rsi_analiz.get("gecerli") else 50
    stoch_k = rsi_analiz["stochrsi"]["stoch_k"] if rsi_analiz.get("gecerli") else 50

    # --- SMI ---
    smi = smi_davranis(spot_ana)
    smi_deger = smi.get("smi", 0) if smi.get("gecerli") else 0
    smi_ust_donus = smi.get("ust_donus_sat", 0) if smi.get("gecerli") else 0

    # --- SMI Divergence ---
    smi_div = smi_divergence(spot_ana)
    smi_boga_diverj = smi_div.get("boga_diverj", 0)

    # Senaryo motoru için paket
    return {
        # Temel
        "fiyat_egim":     fiyat_eg_n - 0.5,   # -0.5..+0.5
        "ema_dizilim":    ema_dizilim - 0.5,
        "vol_egim":       vol_eg,
        "obv_isaret":     obv_isaret,
        "obv_egim":       obv_egim_v - 0.5,
        "cvd_egim":       cvd_net,
        "spot_cvd_egim":  spot_cvd,
        "fut_cvd_egim":   fut_cvd,
        "oi_egim":        oi_eg,
        # Ek
        "delta_norm":     delta_norm - 0.5,
        "rsi14":          rsi14,
        "stoch_k":        stoch_k,
        "smi":            smi_deger,
        "smi_ust_donus":  smi_ust_donus,
        "smi_boga_diverj": smi_boga_diverj,
        "funding_asiri_pozitif": 1.0 if fund["asiri_pozitif"] else 0.0,
        "funding_asiri_negatif": 1.0 if fund["asiri_negatif"] else 0.0,
        "ema21":          ema21,
        "ema50":          ema50,
        "son_fiyat":      son_fiyat,
        # Ham veriler (formasyon/sweep kontrolü için)
        "_spot_ana":      spot_ana,
        "_fut_ana":       fut_ana,
        "_rsi_analiz":    rsi_analiz,
        "_smi":           smi,
        "_obv":           obv,
    }


# =====================================================================
# SCORES — davranış puanları
# =====================================================================
def scores_hesapla(M, veri):
    """
    5 davranış puanı: manipülasyon, short squeeze, long trap, trend devam, dönüş.
    Her biri 0-100.
    """
    spot_cvd  = M["spot_cvd_egim"]
    fut_cvd   = M["fut_cvd_egim"]
    oi_eg     = M["oi_egim"]
    obv       = M["obv_isaret"]
    vol       = M["vol_egim"]
    delta     = M["delta_norm"]
    fiyat     = M["fiyat_egim"]
    smi_d     = M["smi_ust_donus"]
    fund_pos  = M["funding_asiri_pozitif"]
    fund_neg  = M["funding_asiri_negatif"]

    # Likidite sweep son 30 mumda var mı?
    spot_ana = M["_spot_ana"]
    sweep_son30 = 0.0
    if len(spot_ana) >= 10:
        sw = likidite_sweep(spot_ana[-30:] if len(spot_ana) >= 30 else spot_ana)
        sweep_son30 = sw.get("puan", 0) / 100

    # --- Manipülasyon puanı ---
    # Sweep + OI sapması + SpotCVD uyumsuzluğu (fiyat↑ ama spot CVD yatay/↓)
    spot_cvd_uyumsuz = yatay(spot_cvd) if fiyat > 0.1 else 0
    manipulasyon = round(sig(
        0.35 * sweep_son30 + 0.30 * sig(abs(oi_eg), 0, 3) + 0.35 * spot_cvd_uyumsuz,
        0.4, 5.0) * 100, 1)

    # --- Short squeeze ihtimali ---
    # OI↓ + FutCVD↑ + funding aşırı negatif
    short_squeeze = round(sig(
        0.40 * ters_sig(oi_eg, 0, 3) + 0.35 * sig(fut_cvd, 0, 4) + 0.25 * fund_neg,
        0.4, 5.0) * 100, 1)

    # --- Long trap ihtimali ---
    # Fiyat↑ + SpotCVD yatay/↓ + OI aşırı↑ + funding aşırı pozitif
    long_trap = round(sig(
        0.30 * sig(fiyat, 0.1, 5) + 0.30 * ters_sig(spot_cvd, 0, 4) +
        0.25 * sig(oi_eg, 0.3, 4) + 0.15 * fund_pos,
        0.4, 5.0) * 100, 1)

    # --- Trend devam olasılığı ---
    # Fiyat↑ + EMA boğa + OBV↑ + SpotCVD↑ + hacim sağlıklı
    trend_devam = round(sig(
        0.25 * sig(fiyat, 0.1, 5) + 0.20 * sig(M["ema_dizilim"], 0, 3) +
        0.20 * sig(obv, 0, 2) + 0.20 * sig(spot_cvd, 0, 4) +
        0.15 * sig(vol, 0.1, 3),
        0.4, 5.0) * 100, 1)

    # --- Dönüş olasılığı ---
    # Sweep + formasyon + CVD toparlanma + SMI dönüş
    rsi_analiz = M["_rsi_analiz"]
    dip_donus_rsi = rsi_analiz["rsi"].get("dip_donus_rsi", 0) / 100 if rsi_analiz.get("gecerli") else 0
    donus = round(sig(
        0.30 * sweep_son30 + 0.25 * sig(spot_cvd, 0, 4) +
        0.25 * dip_donus_rsi + 0.20 * sig(delta, 0, 3),
        0.4, 5.0) * 100, 1)

    return {
        "manipulasyon":   manipulasyon,
        "short_squeeze":  short_squeeze,
        "long_trap":      long_trap,
        "trend_devam":    trend_devam,
        "donus":          donus,
    }


# =====================================================================
# ZİNCİR KONTROLÜ — formasyon + filtreler
# =====================================================================
def zincir_kontrol(M, veri):
    """
    Likidite Sweep → Formasyon → SpotCVD → Delta → OI → UYARI zinciri.
    Her halka sigmoid puanıyla değerlendirilir.
    Döndürür: {tetik, zincir_puani, formasyon, detay}
    """
    spot_ana = M["_spot_ana"]
    if len(spot_ana) < 10:
        return {"tetik": False, "zincir_puani": 0}

    # 1) Likidite Sweep (son 30 mum)
    pencere = spot_ana[-30:] if len(spot_ana) >= 30 else spot_ana
    sw = likidite_sweep(pencere)
    sweep_puan = sw.get("puan", 0) / 100
    sweep_yon  = sw.get("yon")   # "LONG" / "SHORT" / None

    # 2) Formasyon (son 3 mum)
    form = tum_formasyonlar(spot_ana[-5:] if len(spot_ana) >= 5 else spot_ana,
                            dip_bolgede=(M["rsi14"] < 40),
                            tepe_bolgede=(M["rsi14"] > 65),
                            hacim_yuksek=(M["vol_egim"] > 0.5))
    # En güçlü formasyon
    en_guclu = max(form.items(), key=lambda x: x[1].get("puan", 0)) if form else (None, {"puan": 0})
    form_adi  = en_guclu[0]
    form_puan = en_guclu[1].get("puan", 0) / 100
    form_yon  = en_guclu[1].get("yon")

    # 3) SpotCVD alıma döndü mü?
    spot_cvd_alim = sig(M["spot_cvd_egim"], 0, 4)

    # 4) Delta pozitif mi?
    delta_pozitif = sig(M["delta_norm"], 0, 3)

    # 5) OI beklenen yönde mi?
    # LONG için: OI yatay veya hafif↑ (taze long) ya da↓ (short kapanıyor)
    oi_uygun = sig(abs(M["oi_egim"]), 0.05, 5)  # çok yatay değil (hareket var)

    # Zincir puanı
    zincir = round(
        (0.25 * sweep_puan + 0.25 * form_puan +
         0.20 * spot_cvd_alim + 0.15 * delta_pozitif + 0.15 * oi_uygun) * 100, 1)

    # EMA21 trend filtresi
    ema21 = M.get("ema21"); ema50 = M.get("ema50"); fiyat = M.get("son_fiyat", 0)
    trend_yukari = (ema21 and ema50 and ema21 > ema50) if (ema21 and ema50) else None

    tetik = zincir >= UYARI_ESIK

    return {
        "tetik":        tetik,
        "zincir_puani": zincir,
        "sweep":        {"puan": round(sweep_puan * 100), "yon": sweep_yon},
        "formasyon":    {"ad": form_adi, "puan": round(form_puan * 100), "yon": form_yon},
        "spot_cvd_alim": round(spot_cvd_alim * 100, 1),
        "delta_pozitif": round(delta_pozitif * 100, 1),
        "oi_uygun":      round(oi_uygun * 100, 1),
        "trend_yukari":  trend_yukari,
    }


# =====================================================================
# DAVRANISH DİLİ — mesaj üret
# =====================================================================
def mesaj_uret(sembol, senaryo, scores, zincir, onay, M):
    """
    Sayı yağdırmaz, davranışı özetler.
    """
    baskin = senaryo["baskin"].replace("_", " ").upper()
    baskin_puan = senaryo["baskin_puan"]

    satirlar = [f"📊 {sembol} — {baskin} ({baskin_puan:.0f}/100)"]

    # Hedef bölge bilgisi
    y = onay.get("yakinlik", {})
    if y.get("yakin_herhangi"):
        en = y.get("en_yakin", "?")
        uzak = y.get("en_yakin_uzaklik", "?")
        satirlar.append(f"🎯 Hedef bölge: {en} (%{uzak} uzakta)")

    # Davranış puanları — sadece yüksek olanları yaz
    p = scores
    if p["manipulasyon"] >= 60:
        satirlar.append(f"⚠️ Manipülasyon sinyali: {p['manipulasyon']}/100")
    if p["short_squeeze"] >= 60:
        satirlar.append(f"🔥 Short squeeze ihtimali: {p['short_squeeze']}/100")
    if p["long_trap"] >= 60:
        satirlar.append(f"🪤 Long trap riski: {p['long_trap']}/100")
    if p["trend_devam"] >= 65:
        satirlar.append(f"📈 Trend devam: {p['trend_devam']}/100")
    if p["donus"] >= 60:
        satirlar.append(f"🔄 Dönüş olasılığı: {p['donus']}/100")

    # Zincir tetiklendi mi?
    if zincir["tetik"]:
        zp = zincir["zincir_puani"]
        satirlar.append(f"\n⛓ Zincir tetiklendi ({zp}/100):")
        if zincir["sweep"]["puan"] > 40:
            satirlar.append(f"  Likidite sweep: {zincir['sweep']['yon']} ({zincir['sweep']['puan']})")
        if zincir["formasyon"]["ad"]:
            satirlar.append(f"  Formasyon: {zincir['formasyon']['ad']} ({zincir['formasyon']['puan']})")

    # Metrik özeti (kısa)
    spot_cvd = M["spot_cvd_egim"]
    oi_eg    = M["oi_egim"]
    smi_d    = M["smi"]
    rsi14    = M["rsi14"]

    cvd_yazi = "artıyor" if spot_cvd > 0.05 else ("azalıyor" if spot_cvd < -0.05 else "yatay")
    oi_yazi  = "artıyor" if oi_eg > 0.05 else ("azalıyor" if oi_eg < -0.05 else "yatay")

    satirlar.append(f"\nSpot CVD {cvd_yazi} | OI {oi_yazi} | SMI: {smi_d:.0f} | RSI14: {rsi14:.0f}")

    # Trend durumu
    if zincir.get("trend_yukari") is True:
        satirlar.append("EMA21 > EMA50 — yükseliş trendi")
    elif zincir.get("trend_yukari") is False:
        satirlar.append("EMA21 < EMA50 — düşüş trendi")

    return "\n".join(satirlar)


# =====================================================================
# TEK COİN ANALİZİ
# =====================================================================
def coin_analiz(sembol, onceki_durum=None):
    """
    Bir coin için tam analiz döngüsü.
    onceki_durum: önceki çalışmada tespit edilen baskın senaryo (değişim kontrolü için)
    Döndürür: {senaryo, scores, zincir, mesaj, uyari_gerekli}
    """
    veri = tam_veri_paketi(sembol)
    if not veri["gecerli"]:
        return None

    # Hacim filtresi
    if not hacim_filtresi_gecer(veri["gunluk_hacim"]):
        return None

    M = features_uret(veri)
    if M is None:
        return None

    senaryo  = tum_senaryolar(M)
    scores   = scores_hesapla(M, veri)
    zincir   = zincir_kontrol(M, veri)

    # Onay katmanı: fiyat hedef bölgeye yakın mı?
    fiyat = M.get("son_fiyat", 0)
    onay  = onay_katmani(veri["spot_gunluk"], veri["spot_ana"], fiyat)

    # ─── MİSYON: UYARI KOŞULU — ÜÇÜ AYNI ANDA ───
    # 1. Fiyat hedef bölgede (POC/VPVR/VWAP yakını)
    hedef_bolgede = onay["onay"]
    # 2. Zincir hizalanıyor
    zincir_tetik = zincir["tetik"]
    # 3. Davranış skoru eşiği
    kritik_skor = any(v >= UYARI_ESIK for v in scores.values())

    # Üçü de olmadan mesaj üretilmez — sessizlik geçerli çıktıdır
    uyari = hedef_bolgede and zincir_tetik and kritik_skor

    # Senaryo değişim uyarısı (ek, bölge şartı aranmaz — durum bildirimi)
    senaryo_degisti = (onceki_durum and onceki_durum != senaryo["baskin"])

    mesaj = None
    if uyari or senaryo_degisti:
        mesaj = mesaj_uret(sembol, senaryo, scores, zincir, onay, M)

    return {
        "sembol":         sembol,
        "senaryo":        senaryo,
        "scores":         scores,
        "zincir":         zincir,
        "onay":           onay,
        "mesaj":          mesaj,
        "uyari_gerekli":  bool(uyari or senaryo_degisti),
        "baskin":         senaryo["baskin"],
    }


# =====================================================================
# ANA DÖNGÜ
# =====================================================================
def calistir(semboller, aralik=TARAMA_ARALIĞI):
    """
    Sembol listesini sürekli tarar, davranış değişiminde Telegram uyarısı gönderir.
    semboller: ["BTCUSDT", "ETHUSDT", ...]
    aralik: saniye cinsinden tarama aralığı (varsayılan 1H)
    """
    print(f"[Ana Motor] {len(semboller)} coin izleniyor. Aralık: {aralik}s")
    onceki = {}   # sembol → baskın senaryo

    while True:
        for sembol in semboller:
            try:
                sonuc = coin_analiz(sembol, onceki.get(sembol))
                if sonuc is None:
                    continue
                if sonuc["uyari_gerekli"] and sonuc["mesaj"]:
                    telegram_gonder(sonuc["mesaj"])
                onceki[sembol] = sonuc["baskin"]
                time.sleep(0.3)   # rate limit
            except Exception as e:
                print(f"[{sembol}] Hata: {e}")
                time.sleep(1)

        print(f"[Ana Motor] Tur tamamlandı. {aralik}s bekleniyor...")
        time.sleep(aralik)


# =====================================================================
# TEST (tek coin, Telegram'sız)
# =====================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  ANA MOTOR TESTİ — BTCUSDT")
    print("=" * 60)

    sonuc = coin_analiz("BTCUSDT")  # gerçek API çağrısı yapar
    if sonuc is None:
        print("Veri yetersiz veya hacim filtresi geçmedi.")
    else:
        print(f"\nBaskın senaryo: {sonuc['senaryo']['baskin']} ({sonuc['senaryo']['baskin_puan']})")
        print(f"\nDavranış puanları:")
        for k, v in sonuc["scores"].items():
            print(f"  {k}: {v}/100")
        print(f"\nZincir puanı: {sonuc['zincir']['zincir_puani']} — Tetik: {sonuc['zincir']['tetik']}")
        if sonuc["mesaj"]:
            print(f"\n--- MESAJ ---\n{sonuc['mesaj']}")
        else:
            print("\n(Uyarı eşiği geçilmedi, mesaj üretilmedi)")
