"""
vwap_poc.py — Hedef Bölge Tespiti (Onay Katmanı)
=====================================================================
MİSYON: Fiyat hedefe ulaşmadan önce psikolojik bölgeleri tespit et.

3 HEDEF BÖLGESİ:
  POC   — Son 14 günün en yüksek hacimli fiyat seviyesi
  VPVR  — Major dip/zirve noktaları arası hacim profili (destek/direnç)
  VWAP  — 2 haftalık (14 gün × 1H) hacim ağırlıklı ortalama fiyat

KULLANIM: Bu katman tek başına uyarı üretmez.
  Fiyat bu bölgelere yaklaştığında + diğer metrikler hizalanıyorsa → uyarı.
  Yakınlık eşiği: fiyat, seviyenin ±%0.5 içindeyse "yakın" sayılır.

VERİ: 1D kapanmış mumlar (POC/VPVR) + 1H kapanmış mumlar (VWAP)
"""

import math


# =====================================================================
# YAKINLIK EŞİĞİ
# =====================================================================
YAKIN_ESIK = 0.005   # ±%0.5 (ayarlanabilir)
BINS = 50            # hacim profili çözünürlüğü (fiyat bölme sayısı)


def sigmoid(x, a, k):
    try: return 1.0 / (1.0 + math.exp(-k * (x - a)))
    except OverflowError: return 0.0 if x < a else 1.0


# =====================================================================
# YARDIMCI — hacim profili (bin bazlı)
# =====================================================================
def _hacim_profili(mumlar, bins=BINS):
    """
    Mum listesinden hacim profili üretir.
    Her mumun hacmini H-L aralığına eşit dağıtır.
    Döndürür: [(fiyat_orta, hacim), ...] — yüksekten alçağa sıralı
    """
    if not mumlar:
        return []

    yuksek = max(float(m[2]) for m in mumlar)
    dusuk  = min(float(m[3]) for m in mumlar)
    if yuksek <= dusuk:
        return []

    adim = (yuksek - dusuk) / bins
    bölmeler = [0.0] * bins

    for m in mumlar:
        h = float(m[2]); l = float(m[3]); v = float(m[5])
        aralik = h - l
        if aralik <= 0:
            # Tek noktaya tüm hacmi ver
            idx = min(int((h - dusuk) / adim), bins - 1)
            bölmeler[idx] += v
            continue
        # Hangi bin'lere değiyor?
        idx_alt = max(0, int((l - dusuk) / adim))
        idx_ust = min(bins - 1, int((h - dusuk) / adim))
        sayi = idx_ust - idx_alt + 1
        parca = v / sayi
        for i in range(idx_alt, idx_ust + 1):
            bölmeler[i] += parca

    # (fiyat_orta, hacim) listesi
    profil = []
    for i, h in enumerate(bölmeler):
        fiyat_orta = dusuk + (i + 0.5) * adim
        profil.append((fiyat_orta, h))

    return profil


def _poc_bul(profil):
    """En yüksek hacimli fiyat seviyesini döndürür."""
    if not profil:
        return None
    return max(profil, key=lambda x: x[1])[0]


def _deger_alani(profil, oran=0.70):
    """
    Value Area: toplam hacmin %70'ini içeren fiyat aralığı.
    POC'tan başlayıp yukarı/aşağı genişler.
    Döndürür: (VAL, VAH)
    """
    if not profil:
        return None, None
    toplam = sum(h for _, h in profil)
    hedef = toplam * oran

    poc_idx = max(range(len(profil)), key=lambda i: profil[i][1])
    alt = poc_idx; ust = poc_idx
    birikim = profil[poc_idx][1]

    while birikim < hedef and (alt > 0 or ust < len(profil) - 1):
        alt_ekle = profil[alt - 1][1] if alt > 0 else 0
        ust_ekle = profil[ust + 1][1] if ust < len(profil) - 1 else 0
        if alt_ekle >= ust_ekle and alt > 0:
            alt -= 1; birikim += alt_ekle
        elif ust < len(profil) - 1:
            ust += 1; birikim += ust_ekle
        else:
            break

    return profil[alt][0], profil[ust][0]


# =====================================================================
# POC — Son 14 Günün Point of Control
# =====================================================================
def poc_hesapla(gunluk_mumlar):
    """
    Son 14 günlük 1D kapanmış mumlardan POC hesaplar.
    Döndürür: {poc, val, vah, profil}
    """
    mumlar = gunluk_mumlar[-14:] if len(gunluk_mumlar) >= 14 else gunluk_mumlar
    if len(mumlar) < 3:
        return {"gecerli": False}

    profil = _hacim_profili(mumlar)
    poc    = _poc_bul(profil)
    val, vah = _deger_alani(profil)

    return {
        "gecerli": True,
        "poc":  round(poc, 4) if poc else None,
        "val":  round(val, 4) if val else None,   # Value Area Low
        "vah":  round(vah, 4) if vah else None,   # Value Area High
    }


# =====================================================================
# VPVR — Major Dip/Zirve Arası Hacim Profili
# =====================================================================
def _pivotlar(mumlar, sol=3, sag=3):
    """Swing high/low pivot noktaları."""
    tepeler = []; dipler = []
    n = len(mumlar)
    for i in range(sol, n - sag):
        h = float(mumlar[i][2]); l = float(mumlar[i][3])
        if all(float(mumlar[i-j][2]) <= h for j in range(1, sol+1)) and \
           all(float(mumlar[i+j][2]) <= h for j in range(1, sag+1)):
            tepeler.append((i, h))
        if all(float(mumlar[i-j][3]) >= l for j in range(1, sol+1)) and \
           all(float(mumlar[i+j][3]) >= l for j in range(1, sag+1)):
            dipler.append((i, l))
    return tepeler, dipler


def vpvr_hesapla(gunluk_mumlar):
    """
    Major dip ve zirve arasındaki hacim profili.
    Yüksek hacimli bölgeler (HVN) destek/direnç, düşük hacimli (LVN) geçiş bölgesi.
    Döndürür: {poc, val, vah, hvn_listesi, lvn_listesi}
    """
    if len(gunluk_mumlar) < 10:
        return {"gecerli": False}

    tepeler, dipler = _pivotlar(gunluk_mumlar)

    # En son major tepe ve dip
    if not tepeler or not dipler:
        # Pivot bulunamazsa tüm seriyi kullan
        alt_idx = 0; ust_idx = len(gunluk_mumlar) - 1
    else:
        son_tepe_idx = tepeler[-1][0]
        son_dip_idx  = dipler[-1][0]
        alt_idx = min(son_tepe_idx, son_dip_idx)
        ust_idx = max(son_tepe_idx, son_dip_idx)

    pencere = gunluk_mumlar[alt_idx:ust_idx + 1]
    if len(pencere) < 3:
        pencere = gunluk_mumlar

    profil = _hacim_profili(pencere)
    if not profil:
        return {"gecerli": False}

    poc   = _poc_bul(profil)
    val, vah = _deger_alani(profil)

    # HVN / LVN tespiti
    ort_hacim = sum(h for _, h in profil) / len(profil)
    hvn = [round(f, 4) for f, h in profil if h > ort_hacim * 1.5]   # yüksek hacimli node
    lvn = [round(f, 4) for f, h in profil if h < ort_hacim * 0.5]   # düşük hacimli node

    return {
        "gecerli": True,
        "poc":  round(poc, 4) if poc else None,
        "val":  round(val, 4) if val else None,
        "vah":  round(vah, 4) if vah else None,
        "hvn":  hvn,   # güçlü destek/direnç seviyeleri
        "lvn":  lvn,   # hızlı geçiş bölgeleri (zayıf direnç)
    }


# =====================================================================
# VWAP — 2 Haftalık (14 Gün × 1H)
# =====================================================================
def vwap_hesapla(saatlik_mumlar):
    """
    2 haftalık rolling VWAP.
    Tipik fiyat = (H + L + C) / 3
    VWAP = Σ(tipik_fiyat × hacim) / Σ(hacim)

    saatlik_mumlar: 1H kapanmış mumlar (son 14×24 = 336 mum)
    Döndürür: {vwap, ust_band, alt_band}  (±1 standart sapma bantları)
    """
    pencere = saatlik_mumlar[-(14 * 24):] if len(saatlik_mumlar) >= 14 * 24 else saatlik_mumlar
    if len(pencere) < 24:
        return {"gecerli": False}

    toplam_pv = 0.0
    toplam_v  = 0.0
    tp_listesi = []

    for m in pencere:
        h = float(m[2]); l = float(m[3]); c = float(m[4]); v = float(m[5])
        tp = (h + l + c) / 3
        toplam_pv += tp * v
        toplam_v  += v
        tp_listesi.append(tp)

    if toplam_v <= 0:
        return {"gecerli": False}

    vwap = toplam_pv / toplam_v

    # Standart sapma bantları
    ort = sum(tp_listesi) / len(tp_listesi)
    varyans = sum((tp - ort) ** 2 for tp in tp_listesi) / len(tp_listesi)
    std = math.sqrt(varyans)

    return {
        "gecerli":  True,
        "vwap":     round(vwap, 4),
        "ust_band": round(vwap + std, 4),   # direnç bölgesi
        "alt_band": round(vwap - std, 4),   # destek bölgesi
        "std":      round(std, 4),
    }


# =====================================================================
# YAKINLIK KONTROLÜ — fiyat hedef bölgeye yakın mı?
# =====================================================================
def yakinlik_kontrol(fiyat, poc_v, vpvr_v, vwap_v, esik=YAKIN_ESIK):
    """
    Fiyatın 3 hedef bölgeye yakınlığını ölçer.
    Yakınlık = fark / fiyat < esik (±%0.5)
    Döndürür: {poc_yakin, vwap_yakin, hvn_yakin, en_yakin_seviye, yakin_herhangi}
    """
    sonuc = {
        "poc_yakin":  False,
        "vwap_yakin": False,
        "hvn_yakin":  False,
        "val_yakin":  False,
        "vah_yakin":  False,
        "en_yakin":   None,
        "en_yakin_uzaklik": None,
        "yakin_herhangi": False,
    }

    seviyeleri = {}

    if poc_v.get("gecerli") and poc_v.get("poc"):
        seviyeleri["poc"] = poc_v["poc"]
        if poc_v.get("val"): seviyeleri["val"] = poc_v["val"]
        if poc_v.get("vah"): seviyeleri["vah"] = poc_v["vah"]

    if vpvr_v.get("gecerli"):
        for hvn in vpvr_v.get("hvn", []):
            seviyeleri[f"hvn_{hvn}"] = hvn

    if vwap_v.get("gecerli"):
        seviyeleri["vwap"]     = vwap_v["vwap"]
        seviyeleri["vwap_ust"] = vwap_v["ust_band"]
        seviyeleri["vwap_alt"] = vwap_v["alt_band"]

    en_yakin_uzaklik = float("inf")
    en_yakin_ad = None

    for ad, seviye in seviyeleri.items():
        uzaklik = abs(fiyat - seviye) / fiyat if fiyat > 0 else 1
        if uzaklik < en_yakin_uzaklik:
            en_yakin_uzaklik = uzaklik
            en_yakin_ad = ad
        yakin = uzaklik <= esik
        if ad == "poc":         sonuc["poc_yakin"]  = yakin
        elif ad == "vwap":      sonuc["vwap_yakin"] = yakin
        elif ad == "val":       sonuc["val_yakin"]  = yakin
        elif ad == "vah":       sonuc["vah_yakin"]  = yakin
        elif ad.startswith("hvn") and yakin: sonuc["hvn_yakin"] = True

    sonuc["en_yakin"]         = en_yakin_ad
    sonuc["en_yakin_uzaklik"] = round(en_yakin_uzaklik * 100, 3)  # %
    sonuc["yakin_herhangi"]   = any([
        sonuc["poc_yakin"], sonuc["vwap_yakin"],
        sonuc["hvn_yakin"], sonuc["val_yakin"], sonuc["vah_yakin"]
    ])

    return sonuc


# =====================================================================
# BİRLEŞİK — tam onay katmanı
# =====================================================================
def onay_katmani(gunluk_mumlar, saatlik_mumlar, fiyat):
    """
    3 hedef bölgeyi hesaplar + fiyatın yakınlığını kontrol eder.
    ana_motor.py bu fonksiyonu çağırır.

    Döndürür:
      poc, vpvr, vwap   : her birinin seviyeleri
      yakinlik          : fiyatın hangi seviyelere yakın olduğu
      onay              : True = fiyat hedef bölgede, uyarı için hazır
    """
    poc_v  = poc_hesapla(gunluk_mumlar)
    vpvr_v = vpvr_hesapla(gunluk_mumlar)
    vwap_v = vwap_hesapla(saatlik_mumlar)

    yakinlik = yakinlik_kontrol(fiyat, poc_v, vpvr_v, vwap_v)

    return {
        "gecerli": poc_v.get("gecerli") or vwap_v.get("gecerli"),
        "poc":     poc_v,
        "vpvr":    vpvr_v,
        "vwap":    vwap_v,
        "yakinlik": yakinlik,
        "onay":    yakinlik["yakin_herhangi"],   # uyarı kapısı
    }


# =====================================================================
# TEST
# =====================================================================
if __name__ == "__main__":
    import random
    random.seed(7)

    def uret_gunluk(n, baslangic=100):
        m = []; f = baslangic
        for i in range(n):
            o = f + random.uniform(-2, 2)
            h = o + random.uniform(1, 5)
            l = o - random.uniform(1, 5)
            c = random.uniform(l, h)
            v = random.uniform(500, 2000)
            m.append([i * 86400000, o, h, l, c, v])
            f = c
        return m

    def uret_saatlik(n, baslangic=100):
        m = []; f = baslangic
        for i in range(n):
            o = f + random.uniform(-0.5, 0.5)
            h = o + random.uniform(0.2, 1)
            l = o - random.uniform(0.2, 1)
            c = random.uniform(l, h)
            v = random.uniform(50, 300)
            m.append([i * 3600000, o, h, l, c, v])
            f = c
        return m

    print("=" * 60)
    print("  VWAP / POC / VPVR HEDEF BÖLGELERİ TESTİ")
    print("=" * 60)

    gunluk  = uret_gunluk(20, baslangic=100)
    saatlik = uret_saatlik(350, baslangic=100)
    fiyat   = float(gunluk[-1][4])

    sonuc = onay_katmani(gunluk, saatlik, fiyat)

    print(f"\nGüncel fiyat: {fiyat:.2f}")
    if sonuc["poc"]["gecerli"]:
        print(f"POC (14G):  {sonuc['poc']['poc']}  |  VAL: {sonuc['poc']['val']}  |  VAH: {sonuc['poc']['vah']}")
    if sonuc["vpvr"]["gecerli"]:
        print(f"VPVR POC:   {sonuc['vpvr']['poc']}")
        print(f"HVN seviyeleri: {sonuc['vpvr']['hvn'][:5]}")
    if sonuc["vwap"]["gecerli"]:
        print(f"VWAP (2H):  {sonuc['vwap']['vwap']}  |  Üst: {sonuc['vwap']['ust_band']}  |  Alt: {sonuc['vwap']['alt_band']}")

    y = sonuc["yakinlik"]
    print(f"\nYakınlık kontrolü:")
    print(f"  POC yakın:  {y['poc_yakin']}")
    print(f"  VWAP yakın: {y['vwap_yakin']}")
    print(f"  HVN yakın:  {y['hvn_yakin']}")
    print(f"  En yakın:   {y['en_yakin']} (%{y['en_yakin_uzaklik']} uzakta)")
    print(f"\n  ONAY: {'✅ Fiyat hedef bölgede' if sonuc['onay'] else '❌ Henüz hedef bölgede değil'}")
