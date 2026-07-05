"""
hacim_tarama.py — Hacim Toplama/Tespit (Aşama 1)
=====================================================================
AMAÇ: MM'nin sessizce likidite/coin topladığı anı ÖNCEDEN tespit etmek.
      Fiyat oynasa da coin alımı (base volume) istikrarlı artıyorsa
      → gizli birikim (absorption/accumulation).

ZAMAN: 1D TF, son 14 mum.
HACİM: Coin miktarı (base volume), USDT değeri DEĞİL.

FELSEFE: Esnek matematik (sigmoid). Sert eşik yok, benzerlik/olasılık puanı.
         Sigmoid: f(x) = 1 / (1 + e^(-k*(x-a)))

İÇERİK:
  ADIM 1: Her muma A/D-ağırlıklı puan (kapanış konumu × hacim), 2x referans, sigmoid.
  ADIM 4: Spot/Futures hacim ilişkisinden MM niyeti değerlendirmesi.
"""

import math

PENCERE = 14          # son 14 mum (1D)
SPIKE_REF = 2.0       # referans eşiği: hacim ortalamanın 2 katı = güçlü


# =====================================================================
# TEMEL FUZZY
# =====================================================================
def sigmoid(x, a, k):
    """x>a → 1'e, x<a → 0'a. Yumuşak geçiş."""
    try:
        return 1.0 / (1.0 + math.exp(-k * (x - a)))
    except OverflowError:
        return 0.0 if x < a else 1.0


# =====================================================================
# ADIM 1 — HER MUMA A/D AĞIRLIKLI PUAN
# =====================================================================
def ad_carpani(mum):
    """
    A/D Line mantığı: kapanış gün içi aralığın neresinde?
    CLV = ((C - L) - (H - C)) / (H - L)   → -1 (dipte) ... +1 (tepede)
    Tepede kapanış = alım baskısı (+), dipte = satış baskısı (-).
    """
    o = float(mum[1]); h = float(mum[2]); l = float(mum[3]); c = float(mum[4])
    boy = h - l
    if boy <= 0:
        return 0.0
    return ((c - l) - (h - c)) / boy   # Close Location Value (-1..+1)


def mum_hacim_puani(mum, ort_hacim):
    """
    Bir mumun birikim puanı:
      - Hacim, ortalamanın kaç katı? (2x referans, sigmoid)
      - Kapanış aralığın neresinde? (A/D çarpanı, -1..+1)
      - İkisi çarpılır: yüksek hacim + tepede kapanış = güçlü birikim (+)
                        yüksek hacim + dipte kapanış = dağıtım (-)
    Dönüş: -100..+100 (negatif = dağıtım/baskı, pozitif = birikim)
    """
    hacim = float(mum[5])
    if ort_hacim <= 0:
        return 0.0
    oran = hacim / ort_hacim                      # 1.0 = ortalama, 2.0 = 2x
    # Hacim gücü: 2x'te 0.5, üstünde 1'e yaklaşır (sigmoid, a=SPIKE_REF)
    hacim_gucu = sigmoid(oran, a=SPIKE_REF, k=2.0)
    ad = ad_carpani(mum)                          # -1..+1
    # Birikim yönü × hacim gücü × 100
    return round(ad * hacim_gucu * 100, 1)


def adim1_birikim(mumlar):
    """
    ADIM 1: Son PENCERE mumun her birine A/D-ağırlıklı puan ver,
    son muma kadar yürü. Coin hacmi bazlı.

    Değerlendirilen:
      - her mumun birikim puanı (A/D × hacim gücü)
      - bu puanların EĞİLİMİ artıyor mu (eskiden yeniye)
      - toplam birikim pozitif mi (dağıtım değil birikim mi)

    Dönüş: sözlük
      mum_puanlari : her mumun -100..+100 puanı
      egim         : puanların artış eğilimi (pozitif = güçlenen birikim)
      toplam       : birikim toplamı (pozitif = net alım)
      birikim_puani: 0-100 genel birikim gücü
    """
    if len(mumlar) < PENCERE:
        return {"gecerli": False, "sebep": "yetersiz mum"}

    m = mumlar[-PENCERE:]
    hacimler = [float(x[5]) for x in m]
    ort_hacim = sum(hacimler) / len(hacimler)

    # Her muma puan
    puanlar = [mum_hacim_puani(x, ort_hacim) for x in m]

    # Eğilim: puanlar eskiden yeniye artıyor mu? (basit doğrusal eğim)
    n = len(puanlar)
    xs = list(range(n))
    mx = sum(xs)/n; my = sum(puanlar)/n
    pay = sum((xs[i]-mx)*(puanlar[i]-my) for i in range(n))
    payda = sum((xs[i]-mx)**2 for i in range(n))
    egim = pay/payda if payda else 0.0

    toplam = sum(puanlar)

    # Genel birikim puanı: eğim pozitif + toplam pozitif → yüksek
    egim_puan = sigmoid(egim, a=0.0, k=0.5) * 50      # artan eğilim
    toplam_puan = sigmoid(toplam, a=0.0, k=0.02) * 50 # net pozitif birikim
    birikim_puani = round(egim_puan + toplam_puan, 1)

    return {
        "gecerli": True,
        "mum_puanlari": puanlar,
        "egim": round(egim, 2),
        "toplam": round(toplam, 1),
        "birikim_puani": birikim_puani,
    }


# =====================================================================
# ADIM 4 — SPOT / FUTURES HACİM İLİŞKİSİ (MM NİYETİ)
# =====================================================================
def hacim_egilimi(mumlar):
    """
    Bir seride coin hacminin eğilimini döndürür (normalize).
    +: artıyor, ~0: yatay, -: düşüyor.
    """
    if len(mumlar) < PENCERE:
        return 0.0
    m = mumlar[-PENCERE:]
    hacimler = [float(x[5]) for x in m]
    ort = sum(hacimler)/len(hacimler)
    if ort <= 0:
        return 0.0
    n = len(hacimler)
    xs = list(range(n))
    mx = sum(xs)/n; my = sum(hacimler)/n
    pay = sum((xs[i]-mx)*(hacimler[i]-my) for i in range(n))
    payda = sum((xs[i]-mx)**2 for i in range(n))
    egim = pay/payda if payda else 0.0
    return egim / ort   # ortalamaya göre normalize (fiyat/coin ölçeğinden bağımsız)


def adim4_spot_futures(spot_mumlar, futures_mumlar, spot_satis_ad=None):
    """
    ADIM 4: Spot ve futures coin-hacim ilişkisinden MM niyeti.

    Kurallar (kullanıcı mantığı):
      Spot↑  + Futures↓/=  → MM futures kapatıp spot destekli → OLUMLU
      Spot↑  + Futures↑    → MM çift taraflı işlem → OLUMLU
      Spot yatay + Futures↑ → MM futures kullanıyor, spota dokunmuyor → KABUL
      Spot satış(dağıtım) + Futures↑ → sigmoid oran karar verir
          (oran dışı düşüş zaten - sayı → elenir; içindeyse fiyat baskılama → değerlendir)
      Spot ve Futures durgun/düşüş → İŞLEM YOK

    spot_satis_ad: spot birikim toplamı (adim1'den). Negatifse satış baskısı var.

    Dönüş: sözlük { durum, olumlu, puan, sebep }
    """
    spot_eg = hacim_egilimi(spot_mumlar)
    fut_eg = hacim_egilimi(futures_mumlar)

    # Yatay eşiği (küçük eğim = yatay)
    YATAY = 0.01

    spot_artiyor = spot_eg > YATAY
    spot_yatay = -YATAY <= spot_eg <= YATAY
    spot_dususte = spot_eg < -YATAY
    fut_artiyor = fut_eg > YATAY
    fut_durgun = fut_eg <= YATAY   # düşüyor veya yatay

    # 1) Spot artıyor + futures düşüyor/aynı → futures kapatıp spot destekli
    if spot_artiyor and not fut_artiyor:
        p = sigmoid(spot_eg, a=0.0, k=30.0) * 100
        return {"durum": "spot↑ futures↓/=", "olumlu": True,
                "puan": round(p, 1),
                "sebep": "MM futures kapatıp spot destekli işlem yapıyor"}

    # 2) Spot artıyor + futures artıyor → çift taraflı
    if spot_artiyor and fut_artiyor:
        p = sigmoid((spot_eg + fut_eg)/2, a=0.0, k=30.0) * 100
        return {"durum": "spot↑ futures↑", "olumlu": True,
                "puan": round(p, 1),
                "sebep": "MM her iki alanda işlem açıyor"}

    # 3) Spot yatay + futures artıyor → MM futures kullanıyor, spota dokunmuyor
    if spot_yatay and fut_artiyor:
        p = sigmoid(fut_eg, a=0.0, k=30.0) * 100
        return {"durum": "spot~ futures↑", "olumlu": True,
                "puan": round(p, 1),
                "sebep": "MM futures kullanıyor, spota dokunmuyor"}

    # 4) Spot satışta + futures artıyor → sigmoid oran karar verir
    if spot_dususte and fut_artiyor:
        # Spot satışı ne kadar sert? Oran dışı düşüş zaten negatif puana gider.
        # spot_satis_ad (adim1 toplam) negatifse dağıtım; sigmoid ile ölç.
        baski = spot_satis_ad if spot_satis_ad is not None else spot_eg * 1000
        # baski çok negatifse (gerçek dağıtım) → düşük/negatif puan
        p = (sigmoid(baski, a=-30.0, k=0.05) * 100) - 50  # -50..+50 civarı
        olumlu = p > 0
        return {"durum": "spot↓ futures↑", "olumlu": olumlu,
                "puan": round(p, 1),
                "sebep": ("Fiyat baskılama (oran içinde) → değerlendir" if olumlu
                          else "Gerçek dağıtım (oran dışı düşüş) → elenir")}

    # 5) İkisi de durgun/düşüş → işlem yok
    return {"durum": "spot~/↓ futures~/↓", "olumlu": False, "puan": 0,
            "sebep": "Hareket yok, değerlendirme yapılmaz"}


# =====================================================================
# BİRLEŞİK — Aşama 1 hacim taraması
# =====================================================================
def hacim_tarama(spot_mumlar, futures_mumlar):
    """
    Aşama 1'in tam çıktısı: Adım 1 (birikim) + Adım 4 (spot/futures niyeti).
    """
    a1 = adim1_birikim(spot_mumlar)
    if not a1.get("gecerli"):
        return {"gecerli": False, "sebep": a1.get("sebep")}

    a4 = adim4_spot_futures(spot_mumlar, futures_mumlar,
                            spot_satis_ad=a1["toplam"])

    return {
        "gecerli": True,
        "adim1_birikim": a1,
        "adim4_niyet": a4,
        # Genel: birikim var VE MM niyeti olumlu ise güçlü sinyal
        "hacim_sinyali": a4["olumlu"] and a1["birikim_puani"] > 50,
    }


# =====================================================================
# TEST
# =====================================================================
if __name__ == "__main__":
    import random
    random.seed(1)

    def uret(n, hacim_artan=True, kapanis_ust=True, taban=1000):
        """Test mumları: [zaman, o, h, l, c, hacim(coin)]"""
        m = []; fiyat = 100
        for i in range(n):
            o = fiyat + random.uniform(-1, 1)
            h = o + random.uniform(0.5, 2)
            l = o - random.uniform(0.5, 2)
            # kapanış üst bölgede mi?
            if kapanis_ust:
                c = l + (h - l) * random.uniform(0.65, 0.95)
            else:
                c = l + (h - l) * random.uniform(0.05, 0.35)
            # hacim artan mı?
            hacim = taban * (1 + i * 0.08) if hacim_artan else taban * random.uniform(0.8, 1.2)
            m.append([i, o, h, l, c, hacim])
            fiyat = c
        return m

    print("=" * 60)
    print("  HACİM TARAMA TESTİ (Aşama 1)")
    print("=" * 60)

    # Senaryo A: birikim var (hacim artan + kapanış üstte) + spot↑ futures↑
    spot = uret(14, hacim_artan=True, kapanis_ust=True, taban=1000)
    fut  = uret(14, hacim_artan=True, kapanis_ust=True, taban=800)
    r = hacim_tarama(spot, fut)
    print("\n[Senaryo A: birikim + spot↑ futures↑]")
    print(f"  Birikim puanı: {r['adim1_birikim']['birikim_puani']}")
    print(f"  Eğim: {r['adim1_birikim']['egim']} | Toplam: {r['adim1_birikim']['toplam']}")
    print(f"  Niyet: {r['adim4_niyet']['durum']} → {r['adim4_niyet']['sebep']}")
    print(f"  Niyet puanı: {r['adim4_niyet']['puan']} | Olumlu: {r['adim4_niyet']['olumlu']}")
    print(f"  ➤ HACİM SİNYALİ: {r['hacim_sinyali']}")

    # Senaryo B: dağıtım (kapanış dipte) 
    spot2 = uret(14, hacim_artan=True, kapanis_ust=False, taban=1000)
    fut2  = uret(14, hacim_artan=False, taban=800)
    r2 = hacim_tarama(spot2, fut2)
    print("\n[Senaryo B: kapanış dipte = dağıtım]")
    print(f"  Birikim puanı: {r2['adim1_birikim']['birikim_puani']}")
    print(f"  Toplam: {r2['adim1_birikim']['toplam']} (negatif = dağıtım)")
    print(f"  ➤ HACİM SİNYALİ: {r2['hacim_sinyali']}")

    # Senaryo C: ikisi de durgun
    spot3 = uret(14, hacim_artan=False, taban=1000)
    fut3  = uret(14, hacim_artan=False, taban=800)
    r3 = hacim_tarama(spot3, fut3)
    print("\n[Senaryo C: ikisi de durgun]")
    print(f"  Niyet: {r3['adim4_niyet']['sebep']}")
    print(f"  ➤ HACİM SİNYALİ: {r3['hacim_sinyali']}")
