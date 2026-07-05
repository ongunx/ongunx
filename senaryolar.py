"""
senaryolar.py — 9 Piyasa Senaryosu Değerlendirme Motoru
=====================================================================
Her senaryo, tüm metrikleri (Fiyat, EMA, Volume, OBV, SMI, CVD,
Spot/Future CVD, OI) birleştirip 0-100 OLASILIK puanı verir.

FELSEFE: Metrik = iz. Davranış = sinyal. Sigmoid ile yumuşak birleşim.
Notasyon:
  σ(Δx)        = yukarı eğilim
  σ(-Δx)       = aşağı eğilim
  1-|2σ(Δx)-1| = yatay/nötr ölçer
  σ(x-alt)-σ(x-üst) = bant içi

GİRDİ (metrik_paketi): önceden hesaplanmış metriklerin sözlüğü:
  fiyat_egim, ema_dizilim, vol_egim, obv_isaret, smi_*, cvd_egim,
  spot_cvd_egim, fut_cvd_egim, oi_egim ... (tümü normalize -1..+1 veya puan)

Senaryolar:
  1 Boğa | 2 Boğa Tuzağı | 3 Akümülasyon | 4 Ayı | 5 Çöküş
  6 Ayı Tuzağı | 7 Yatay | 8 Short Cover | 9 Long Cover (Kâr Al)
"""
import math

def sig(x, a=0.0, k=1.0):
    try: return 1.0/(1.0+math.exp(-k*(x-a)))
    except OverflowError: return 0.0 if x<a else 1.0

def ters_sig(x, a=0.0, k=1.0):
    return 1.0 - sig(x, a, k)

def yatay_olcer(dx, k=5.0):
    """1-|2σ(Δx)-1|: Δx≈0 ise 1 (yatay), uzaklaştıkça 0."""
    return 1.0 - abs(2*sig(dx, 0, k) - 1)


# =====================================================================
# 9 SENARYO — her biri metrik_paketi alır, 0-100 olasılık döndürür
# =====================================================================
def s1_boga(M):
    """Güçlü Sağlıklı Yükseliş: fiyat↑ + EMA dizilim↑ + OI↑ + SpotCVD↑ + FutCVD↑ + OBV↑"""
    return round(sig(
        0.25*M["fiyat_egim"] + 0.20*M["oi_egim"] + 0.20*M["fut_cvd_egim"]
        + 0.20*M["spot_cvd_egim"] + 0.15*M["obv_egim"], 0, 4.0) * 100, 1)

def s2_boga_tuzagi(M):
    """Kaldıraç Yapay Yükseliş: fiyat↑ ama Vol↓ + OBV↓ + SpotCVD~ + FutCVD↑↑ + OI↑↑"""
    fiyat_yuksek = sig(M["fiyat_egim"], 0, 4.0)
    vol_dusuk = ters_sig(M["vol_egim"], 0, 4.0)
    obv_zayif = ters_sig(M["obv_isaret"], 0, 3.0)
    spot_yatay = yatay_olcer(M["spot_cvd_egim"])
    fut_asiri = sig(M["fut_cvd_egim"], 0.3, 4.0)
    oi_asiri = sig(M["oi_egim"], 0.3, 4.0)
    return round(sig(
        0.15*fiyat_yuksek + 0.20*vol_dusuk + 0.15*obv_zayif
        + 0.15*spot_yatay + 0.20*fut_asiri + 0.15*oi_asiri, 0.5, 6.0) * 100, 1)

def s3_akumulasyon(M):
    """Gizli Mal Toplama: fiyat yatay + SpotCVD↑ + OBV↑ + OI yatay + FutCVD yatay/↓"""
    return round(sig(
        0.35*M["spot_cvd_egim"] + 0.30*M["obv_isaret"]
        - 0.20*abs(M["oi_egim"]) - 0.15*abs(M["fut_cvd_egim"]), 0, 5.0) * 100, 1)

def s4_ayi(M):
    """Sağlıklı Düşüş: fiyat↓ + EMA ayı dizilim + Vol↑(düşüşte) + OBV↓ + CVD↓ + OI↑(short)"""
    return round(sig(
        0.25*(-M["fiyat_egim"]) + 0.20*(-M["obv_isaret"]) + 0.20*(-M["cvd_egim"])
        + 0.20*M["oi_egim"] + 0.15*M["vol_egim"], 0, 4.0) * 100, 1)

def s5_cokus(M):
    """Spot Dağıtımlı Çöküş: SpotCVD sert↓ + OI↑ + FutCVD direniyor + EMA ayı"""
    return round(sig(
        0.40*(-M["spot_cvd_egim"]) + 0.30*M["oi_egim"] + 0.30*M["fut_cvd_egim"],
        0, 4.0) * 100, 1)

def s6_ayi_tuzagi(M):
    """Satıcı Tükenmesi/Ayı Tuzağı: wick + reclaim + CVD toparlanma + SMI diverj + climax hacim - spot dağıtım"""
    wick = M.get("wick_reclaim", 0.0)
    cvd_toparlanma = sig(M["cvd_egim"], 0, 4.0)
    mom_diverj = M.get("smi_boga_diverj", 0.0)
    climax = sig(M["vol_egim"], 0.3, 5.0)
    spot_dagitim = ters_sig(M["spot_cvd_egim"], 0, 4.0)
    return round(sig(
        0.30*wick + 0.25*cvd_toparlanma + 0.20*mom_diverj
        + 0.15*climax - 0.20*spot_dagitim, 0.3, 6.0) * 100, 1)

def s7_yatay(M):
    """Kararsızlık/Yatay: 3 CVD yatay + OI yatay + hacim düşük"""
    spot_yatay = yatay_olcer(M["spot_cvd_egim"])
    oi_yatay = yatay_olcer(M["oi_egim"])
    hacim_dusuk = ters_sig(M["vol_egim"], 0, 4.0)
    return round(spot_yatay * oi_yatay * hacim_dusuk * 100, 1)

def s8_short_cover(M):
    """Short Cover Yükselişi: fiyat↑ + FutCVD↑↑ + OI↓↓ + SpotCVD yatay(inanmıyor)"""
    fut_up = sig(M["fut_cvd_egim"], 0, 4.0)
    oi_dusus = ters_sig(M["oi_egim"], 0, 4.0)   # OI düşüyor
    spot_inanmiyor = yatay_olcer(M["spot_cvd_egim"])
    return round(sig(
        0.40*fut_up + 0.35*oi_dusus + 0.25*spot_inanmiyor, 0.5, 6.0) * 100, 1)

def s9_long_cover(M):
    """Long Cover/Kâr Al: fiyat↓ + FutCVD↓ + OI↓ ama SpotCVD SAĞLAM(yatay)"""
    fut_dusus = ters_sig(M["fut_cvd_egim"], 0, 4.0)
    oi_dusus = ters_sig(M["oi_egim"], 0, 4.0)
    spot_saglam = yatay_olcer(M["spot_cvd_egim"])  # spot panik satmıyor
    smi_donus = M.get("smi_ust_donus", 0.0)         # zirveden dönüş
    return round(sig(
        0.30*fut_dusus + 0.25*oi_dusus + 0.30*spot_saglam + 0.15*smi_donus,
        0.5, 6.0) * 100, 1)


def tum_senaryolar(M):
    """9 senaryonun olasılık puanlarını döndürür, en yükseği işaretler."""
    s = {
        "1_boga": s1_boga(M), "2_boga_tuzagi": s2_boga_tuzagi(M),
        "3_akumulasyon": s3_akumulasyon(M), "4_ayi": s4_ayi(M),
        "5_cokus": s5_cokus(M), "6_ayi_tuzagi": s6_ayi_tuzagi(M),
        "7_yatay": s7_yatay(M), "8_short_cover": s8_short_cover(M),
        "9_long_cover": s9_long_cover(M),
    }
    en = max(s.items(), key=lambda x: x[1])
    return {"puanlar": s, "baskin": en[0], "baskin_puan": en[1]}


if __name__ == "__main__":
    # Test: güçlü boğa metrik paketi
    print("="*55)
    print("  9 SENARYO MOTORU TESTİ")
    print("="*55)

    boga = {"fiyat_egim":0.8,"ema_dizilim":0.9,"vol_egim":0.6,"obv_isaret":0.8,
            "obv_egim":0.7,"cvd_egim":0.7,"spot_cvd_egim":0.8,"fut_cvd_egim":0.6,"oi_egim":0.7}
    r = tum_senaryolar(boga)
    print(f"\n[Güçlü boğa girdisi]")
    print(f"  Baskın senaryo: {r['baskin']} ({r['baskin_puan']})")
    for k,v in sorted(r['puanlar'].items(), key=lambda x:-x[1])[:3]:
        print(f"    {k}: {v}")

    # Test: boğa tuzağı (fiyat↑ ama spot yok, fut+OI aşırı)
    tuzak = {"fiyat_egim":0.7,"ema_dizilim":0.8,"vol_egim":-0.5,"obv_isaret":-0.3,
             "obv_egim":-0.2,"cvd_egim":-0.3,"spot_cvd_egim":0.0,"fut_cvd_egim":0.9,"oi_egim":0.9}
    r2 = tum_senaryolar(tuzak)
    print(f"\n[Boğa tuzağı girdisi]")
    print(f"  Baskın senaryo: {r2['baskin']} ({r2['baskin_puan']})")
    for k,v in sorted(r2['puanlar'].items(), key=lambda x:-x[1])[:3]:
        print(f"    {k}: {v}")

    # Test: akümülasyon (fiyat yatay, spot+OBV↑, OI+fut yatay)
    akum = {"fiyat_egim":0.0,"ema_dizilim":0.0,"vol_egim":0.1,"obv_isaret":0.7,
            "obv_egim":0.7,"cvd_egim":0.5,"spot_cvd_egim":0.8,"fut_cvd_egim":0.0,"oi_egim":0.0}
    r3 = tum_senaryolar(akum)
    print(f"\n[Akümülasyon girdisi]")
    print(f"  Baskın senaryo: {r3['baskin']} ({r3['baskin_puan']})")
    for k,v in sorted(r3['puanlar'].items(), key=lambda x:-x[1])[:3]:
        print(f"    {k}: {v}")
