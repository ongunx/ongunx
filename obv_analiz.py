"""
obv_analiz.py — OBV Işını + EMA7/MA7 Analizi (Aşama 1 devamı)
=====================================================================
OBV = TradingView/klasik tanım (kapanış-bazlı, doğrulandı):
  kapanış > önceki → OBV += hacim
  kapanış < önceki → OBV -= hacim
  kapanış = önceki → OBV değişmez

EMA7 = OBV serisinin 7-EMA'sı | MA7 = OBV serisinin 7-SMA'sı
Hız: OBV ışını (öncü) > EMA7 (orta) > MA7 (yavaş)

Zaman: 1D alım tespiti → 1H giriş/devam → 4H+1D teyit
Esnek matematik: sigmoid ile açıklık/güç puanlaması.
"""
import math

def sigmoid(x, a, k):
    try: return 1.0/(1.0+math.exp(-k*(x-a)))
    except OverflowError: return 0.0 if x<a else 1.0

def obv_serisi(mumlar):
    """Klasik OBV (TradingView formülü). mum=[t,o,h,l,c,v]"""
    obv = [0.0]
    for i in range(1, len(mumlar)):
        c = float(mumlar[i][4]); onceki_c = float(mumlar[i-1][4])
        v = float(mumlar[i][5])
        if c > onceki_c:   obv.append(obv[-1] + v)
        elif c < onceki_c: obv.append(obv[-1] - v)
        else:              obv.append(obv[-1])
    return obv

def sma(seri, p):
    if len(seri) < p: return [None]*len(seri)
    out = [None]*(p-1)
    for i in range(p-1, len(seri)):
        out.append(sum(seri[i-p+1:i+1])/p)
    return out

def ema(seri, p):
    if len(seri) < p: return [None]*len(seri)
    k = 2/(p+1)
    out = [None]*(p-1)
    ilk = sum(seri[:p])/p
    out.append(ilk)
    for i in range(p, len(seri)):
        out.append(seri[i]*k + out[-1]*(1-k))
    return out

def obv_durum(mumlar):
    """
    OBV ışını, EMA7, MA7 sıralamasından 6 durumlu değerlendirme.
    Açıklık sigmoid ile güce çevrilir. Dönüş: durum + puan (-100..+100).
    """
    if len(mumlar) < 10:
        return {"gecerli": False}
    obv = obv_serisi(mumlar)
    e7 = ema(obv, 7); m7 = sma(obv, 7)
    isin = obv[-1]; E = e7[-1]; M = m7[-1]
    if E is None or M is None:
        return {"gecerli": False}

    # Açıklık: OBV-EMA7 farkı, OBV ölçeğine göre normalize
    olcek = (max(obv[-14:]) - min(obv[-14:])) or 1
    acik = (isin - E) / olcek     # + alım tarafı, - satış tarafı
    guc = sigmoid(abs(acik), a=0.1, k=8.0) * 100  # açıklık büyükse güçlü

    # 6 durum (senin tablon)
    if isin > E > M:
        durum, isaret = "OBV>EMA7>MA7: kuvvetli ALIM", +1
    elif isin > E and E >= M:
        durum, isaret = "OBV>EMA7≥MA7: ALIM zayıf", +1
    elif abs(acik) < 0.02:
        durum, isaret = "OBV≈EMA7≈MA7: NÖTR", 0
    elif isin < E and E <= M:
        durum, isaret = "OBV<EMA7≤MA7: satış baskın, düşüş eğilimli", -1
    elif isin < M < E:
        durum, isaret = "OBV<MA7<EMA7: satış artarak devam", -1
    elif isin < E < M:
        durum, isaret = "OBV<EMA7<MA7: satış baskın, alım yok", -1
    else:
        durum, isaret = "belirsiz", 0

    return {"gecerli": True, "durum": durum, "isaret": isaret,
            "puan": round(guc*isaret, 1), "obv": round(isin,1),
            "ema7": round(E,1), "ma7": round(M,1), "acik": round(acik,4)}

def obv_egim(mumlar, bak=5):
    """OBV ışınının son 'bak' mumdaki eğimi (yukarı/aşağı)."""
    obv = obv_serisi(mumlar)
    if len(obv) < bak: return 0.0
    son = obv[-bak:]
    olcek = (max(obv[-14:]) - min(obv[-14:])) or 1
    return (son[-1] - son[0]) / bak / olcek

# Fiyat oynaklığı (yatay mı?) — divergence için
def fiyat_oynaklik(mumlar, bak=5):
    m = mumlar[-bak:]
    kapanislar = [float(x[4]) for x in m]
    ort = sum(kapanislar)/len(kapanislar)
    if ort <= 0: return 0.0
    return (max(kapanislar)-min(kapanislar))/ort  # küçük=yatay

def divergence_giris(mumlar):
    """GİRİŞ: fiyat yatay/baskılı + OBV yükseliyor → gizli alım."""
    oyn = fiyat_oynaklik(mumlar)
    eg = obv_egim(mumlar)
    yatay = sigmoid(0.03 - oyn, a=0.0, k=100.0)  # oynaklık küçükse yüksek
    obv_yukari = sigmoid(eg, a=0.0, k=50.0)
    p = yatay * obv_yukari * 100
    return {"gizli_alim_puani": round(p,1), "fiyat_yatay": round(oyn,4),
            "obv_egim": round(eg,4)}

def divergence_cikis(mumlar, ust_tf_mumlar=None):
    """
    ÇIKIŞ UYARISI: fiyat yükseliyor + OBV ışını ≤ EMA7/MA7.
    4H (ust_tf) teyit ederse kapatma uyarısı; etmezse uyarı yok.
    """
    d = obv_durum(mumlar)
    if not d.get("gecerli"): return {"uyari": False}
    # fiyat yükseliyor mu?
    kapanislar = [float(x[4]) for x in mumlar[-5:]]
    fiyat_yukari = kapanislar[-1] > kapanislar[0]
    obv_zayif = d["isaret"] < 0  # OBV satış tarafında
    kendi_tf_uyari = fiyat_yukari and obv_zayif
    if not kendi_tf_uyari:
        return {"uyari": False, "sebep": "kendi TF sağlıklı"}
    # 4H teyidi
    if ust_tf_mumlar:
        d4 = obv_durum(ust_tf_mumlar)
        teyit = d4.get("gecerli") and d4["isaret"] <= 0
        if teyit:
            return {"uyari": True, "sebep": f"Fiyat↑ ama OBV satış + 4H teyit → KAPATMA UYARISI",
                    "kendi": d["durum"], "ust_tf": d4["durum"]}
        return {"uyari": False, "sebep": "4H teyit etmedi, uyarı yok"}
    return {"uyari": None, "sebep": "4H verisi bekleniyor"}
