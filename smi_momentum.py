"""
smi_momentum.py — Stochastic Momentum Index (Momentum metriği)
=====================================================================
Momentum = SMI. Skala -100/+100, 0 merkezli.

BÖLGELER (kullanıcı tanımı):
  LONG:  0→+20 sağlıklı | +20→+80 sürdürülebilir | +80→+100 mayınlı (dönüş riski)
  SHORT: 0→-20 sağlıklı | -20→-80 sürdürülebilir | -80→-100 mayınlı

FELSEFE: Metrik bir izdir; DAVRANIŞ sezilir.
  → Eşiğe DEĞME önemsiz. Eşikten DÖNME (roll-over) sinyaldir.
  → Sinyal = σ(SMI∓80) · σ(∓ΔSMI)  (uç bölgede VE ters dönüş)
  → En güçlü: fiyat-SMI divergence
  → W_ZAYIF = 0.6: alt dönüş sinyali üst dönüşün %60'ı kadar güçlü
"""
import math

def _ema(seri, p):
    if not seri: return []
    k = 2/(p+1)
    out = [seri[0]]
    for x in seri[1:]:
        out.append(x*k + out[-1]*(1-k))
    return out

def smi_hesapla(mumlar, lookback=13, yumusatma=25, sinyal=2):
    """SMI serisi (-100..+100). mum=[t,o,h,l,c,v]"""
    n = len(mumlar)
    if n < lookback + yumusatma:
        return None, None
    highs = [float(m[2]) for m in mumlar]
    lows  = [float(m[3]) for m in mumlar]
    closes= [float(m[4]) for m in mumlar]
    D = []; HL = []
    for i in range(n):
        if i < lookback-1:
            D.append(0.0); HL.append(0.0); continue
        hh = max(highs[i-lookback+1:i+1]); ll = min(lows[i-lookback+1:i+1])
        orta = (hh + ll) / 2
        D.append(closes[i] - orta); HL.append(hh - ll)
    D1 = _ema(D, yumusatma); D2 = _ema(D1, sinyal)
    HL1 = _ema(HL, yumusatma); HL2 = _ema(HL1, sinyal)
    smi = []
    for i in range(n):
        payda = HL2[i]/2
        smi.append(100 * D2[i]/payda if payda != 0 else 0.0)
    return smi, _ema(smi, sinyal)

def sigmoid(x, a, k):
    try: return 1.0/(1.0+math.exp(-k*(x-a)))
    except OverflowError: return 0.0 if x<a else 1.0

def ters_sigmoid(x, a, k):
    return 1.0 - sigmoid(x, a, k)

def smi_davranis(mumlar):
    """SMI davranış analizi — DEĞME değil DÖNME odaklı."""
    smi, sig = smi_hesapla(mumlar)
    if smi is None:
        return {"gecerli": False}
    son = smi[-1]; onceki = smi[-2] if len(smi) > 1 else son
    dSMI = son - onceki
    if son >= 0:
        saglikli = sigmoid(son, 0, 0.3) * ters_sigmoid(son, 20, 0.3)
        surdurulebilir = sigmoid(son, 20, 0.2) * ters_sigmoid(son, 80, 0.2)
        mayinli = sigmoid(son, 80, 0.3)
        taraf = "LONG"
    else:
        saglikli = sigmoid(-son, 0, 0.3) * ters_sigmoid(-son, 20, 0.3)
        surdurulebilir = sigmoid(-son, 20, 0.2) * ters_sigmoid(-son, 80, 0.2)
        mayinli = sigmoid(-son, 80, 0.3)
        taraf = "SHORT"

    W_ZAYIF = 0.6   # alt dönüş üst dönüşün %60'ı kadar güçlü
    ust_donus = sigmoid(son, 80, 0.2) * sigmoid(-dSMI, 0, 0.5)
    alt_donus = sigmoid(-son, 80, 0.2) * sigmoid(dSMI, 0, 0.5) * W_ZAYIF

    return {
        "gecerli": True, "smi": round(son,1), "dSMI": round(dSMI,2),
        "taraf": taraf, "yon": "boğa" if son > 0 else "ayı",
        "bolge": {"saglikli": round(saglikli,2),
                  "surdurulebilir": round(surdurulebilir,2),
                  "mayinli": round(mayinli,2)},
        "ust_donus_sat": round(ust_donus,3),
        "alt_donus_al": round(alt_donus,3),
    }

def smi_divergence(mumlar, bak=20):
    """Fiyat-SMI divergence (en güçlü davranış sinyali)."""
    smi, _ = smi_hesapla(mumlar)
    if smi is None or len(mumlar) < bak:
        return {"boga_diverj": 0, "ayi_diverj": 0}
    m = mumlar[-bak:]; s = smi[-bak:]
    yari = bak//2
    f_dip_son = min(float(x[3]) for x in m[yari:]); f_dip_ilk = min(float(x[3]) for x in m[:yari])
    s_dip_son = min(s[yari:]); s_dip_ilk = min(s[:yari])
    boga = 1.0 if (f_dip_son < f_dip_ilk and s_dip_son > s_dip_ilk) else 0.0
    f_tepe_son = max(float(x[2]) for x in m[yari:]); f_tepe_ilk = max(float(x[2]) for x in m[:yari])
    s_tepe_son = max(s[yari:]); s_tepe_ilk = max(s[:yari])
    ayi = 1.0 if (f_tepe_son > f_tepe_ilk and s_tepe_son < s_tepe_ilk) else 0.0
    return {"boga_diverj": boga, "ayi_diverj": ayi}

if __name__ == "__main__":
    import random; random.seed(3)
    m=[]; f=100
    for i in range(60):
        o=f; c=o+random.uniform(-1,2); m.append([i,o,max(o,c)+0.5,min(o,c)-0.5,c,1000]); f=c
    d = smi_davranis(m)
    print("SMI davranış testi:", d)
    print("Divergence:", smi_divergence(m))
