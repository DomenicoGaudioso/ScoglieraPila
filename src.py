# -*- coding: utf-8 -*-
"""
SCOGLIERA PILA - Modulo di calcolo (src.py)
Dimensionamento del D50 della scogliera (riprap) a protezione di una pila da ponte.
Metodi: Isbash (da velocita') e Shields (da sforzo di fondo).
Versione professionale:
- Calcolo D50 con entrambi i metodi (confronto)
- Gradazione riprap: D15, D85, D100 da D50
- Filtro granulare (criteri di Terzaghi)
- Classe pezzatura EN 13383-1
- Spessore e larghezza apron + volume e massa per metro lineare
- Verifiche normative tabellari
- Tabella passaggi di calcolo estesa
- Generazione report PDF professionale
- Curve di sensitivita D50 vs V (Isbash) e D50 vs y (Shields)
- Validazione e commenti progettuali
"""
from __future__ import annotations

import datetime
import math
from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import pandas as pd

G = 9.81


# ---------------------------------------------------------------------------
# Dataclass input
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DatiScogliera:
    S_s: float              # densita relativa roccia rho_s/rho [-]
    rho: float              # densita acqua [kg/m3]
    metodo: str             # 'Isbash' o 'Shields'
    # Isbash
    V: float = 0.0          # velocita caratteristica [m/s]
    K_isbash: float = 1.7   # coeff. Isbash [-]
    # Shields
    y: float = 0.0          # tirante [m]
    S_idraulica: float = 0.002   # pendenza idraulica [-]
    theta_c: float = 0.047  # parametro critico di Shields [-]
    # Apron
    ys_atteso: float = 2.0  # scalzamento atteso [m]
    fattore_spessore: float = 2.0   # spessore = f_t * D50
    fattore_larghezza: float = 2.0  # larghezza apron = f_L * ys


# ---------------------------------------------------------------------------
# Validazione
# ---------------------------------------------------------------------------

def valida_dati(dati: DatiScogliera) -> List[str]:
    errori: List[str] = []
    if dati.S_s <= 1.0:
        errori.append("La densita relativa S_s deve essere maggiore di 1.0.")
    if dati.rho <= 0:
        errori.append("La densita dell'acqua deve essere positiva.")
    if dati.metodo == "Isbash":
        if dati.V <= 0:
            errori.append("La velocita caratteristica V deve essere positiva (metodo Isbash).")
        if dati.K_isbash <= 0:
            errori.append("Il coefficiente K di Isbash deve essere positivo.")
    elif dati.metodo == "Shields":
        if dati.y <= 0:
            errori.append("Il tirante y deve essere positivo (metodo Shields).")
        if dati.S_idraulica <= 0:
            errori.append("La pendenza idraulica S deve essere positiva (metodo Shields).")
        if dati.theta_c <= 0:
            errori.append("Il parametro critico di Shields theta_c deve essere positivo.")
    else:
        errori.append("Metodo non riconosciuto: scegliere 'Isbash' o 'Shields'.")
    if dati.ys_atteso <= 0:
        errori.append("Lo scalzamento atteso ys deve essere positivo.")
    if dati.fattore_spessore <= 0:
        errori.append("Il fattore spessore deve essere positivo.")
    if dati.fattore_larghezza <= 0:
        errori.append("Il fattore larghezza deve essere positivo.")
    return errori


# ---------------------------------------------------------------------------
# Formule di dimensionamento
# ---------------------------------------------------------------------------

def d50_isbash(V: float, S_s: float, K: float = 1.7) -> float:
    """D50 [m] da formula di Isbash: D = V^2 / (K^2*g*(S_s-1))."""
    if V <= 0 or S_s <= 1 or K <= 0:
        return float("nan")
    return (V * V) / (K * K * G * (S_s - 1.0))


def tau_fondo(y: float, S: float, rho: float = 1000.0) -> float:
    """Sforzo al fondo tau [Pa] = rho*g*y*S (alveo ampio)."""
    if y <= 0 or S <= 0:
        return float("nan")
    return rho * G * y * S


def d50_shields(tau: float, S_s: float, rho: float = 1000.0,
                theta_c: float = 0.047) -> float:
    """D50 [m] da Shields: D = tau / (theta_c*(S_s-1)*rho*g)."""
    if tau <= 0 or S_s <= 1 or theta_c <= 0:
        return float("nan")
    return tau / (theta_c * (S_s - 1.0) * rho * G)


def calcola_d50(dati: DatiScogliera) -> float:
    if dati.metodo == "Isbash":
        return d50_isbash(dati.V, dati.S_s, dati.K_isbash)
    tau = tau_fondo(dati.y, dati.S_idraulica, dati.rho)
    return d50_shields(tau, dati.S_s, dati.rho, dati.theta_c)


def spessore_rivestimento(D50: float, fattore: float = 2.0) -> float:
    """Spessore minimo del rivestimento [m] = fattore x D50."""
    if D50 <= 0:
        return float("nan")
    return fattore * D50


def larghezza_apron(ys_atteso: float, fattore: float = 2.0) -> float:
    """Larghezza consigliata dell'apron [m] = fattore x ys."""
    if ys_atteso <= 0 or fattore <= 0:
        return float("nan")
    return fattore * ys_atteso


def massa_masso_tipico(D50: float, S_s: float = 2.65,
                       rho: float = 1000.0) -> dict:
    """Stima massa e volume di un masso sferico equivalente di diametro D50."""
    rho_s = S_s * rho
    V_masso = math.pi * D50 ** 3 / 6.0
    M_masso = rho_s * V_masso
    return {
        "rho_s [kg/m3]": rho_s,
        "volume_masso [m3]": V_masso,
        "massa_masso [kg]": M_masso,
    }


# ---------------------------------------------------------------------------
# Gradazione riprap e filtro Terzaghi
# ---------------------------------------------------------------------------

def gradazione_riprap(D50_m: float) -> dict:
    """
    Gradazione tipica di una scogliera in riprap (curva granulometrica).
    Basato su curve di Fuller modificate e linee guida FHWA HEC-23:
    - D15 ~ 0.40 * D50
    - D85 ~ 2.00 * D50
    - D100 ~ 2.50 * D50 (circa il massimo accettabile)
    Rif.: FHWA HEC-23 (2009), EN 13383-1.
    """
    return {
        "D15 [m]": 0.40 * D50_m,
        "D50 [m]": D50_m,
        "D85 [m]": 2.00 * D50_m,
        "D100 [m]": 2.50 * D50_m,
    }


def progettazione_filtro_terzaghi(D50_riprap_m: float) -> dict:
    """
    Progettazione del filtro granulare di transizione (criteri di Terzaghi).
    Il filtro deve soddisfare:
    1. Anti-piping: D15_filtro / D85_base < 5
       -> D15_filtro < 5 * D85_base = 5 * 2.0 * D50_riprap
    2. Anti-intasamento: D15_filtro / D15_base > 5
       -> D15_filtro > 5 * D15_base = 5 * 0.40 * D50_riprap
    3. Gradazione: D50_filtro < 25 * D50_base

    Per semplificazione (filtro classico a granulometria uniforme):
    D50_filtro ~ 0.25 * D50_riprap (filtro unico su substrato naturale medio)
    Spessore minimo filtro: max(0.15 m, 1.5 * D85_filtro)
    Rif.: Terzaghi (1943); USACE EM 1110-2-1913; FHWA HEC-23.
    """
    grad = gradazione_riprap(D50_riprap_m)
    D85_base = grad["D85 [m]"]
    D15_base = grad["D15 [m]"]
    D15_max = 5.0 * D85_base
    D15_min = 5.0 * D15_base
    # D50 filtro scelto come media geometrica
    D50_filtro = math.sqrt(D15_min * D15_max) if D15_min < D15_max else D15_min
    D85_filtro = 2.0 * D50_filtro
    spessore_filtro = max(0.15, 1.5 * D85_filtro)
    return {
        "D15_filtro_min [m]": round(D15_min, 4),
        "D15_filtro_max [m]": round(D15_max, 4),
        "D50_filtro_adottato [m]": round(D50_filtro, 4),
        "D85_filtro [m]": round(D85_filtro, 4),
        "Spessore_filtro [m]": round(spessore_filtro, 3),
    }


def classe_en13383(massa_kg: float) -> str:
    """
    Classe pezzatura secondo EN 13383-1 (armourstone) basata sulla massa del masso tipico.
    Classi approssimate: CP = classi granulometriche per armourstone naturale.
    Rif.: EN 13383-1:2002+A1:2008.
    """
    if massa_kg < 25:
        return "CP 5/25 (< 25 kg, massi leggeri)"
    elif massa_kg < 100:
        return "CP 25/100 (25-100 kg)"
    elif massa_kg < 300:
        return "CP 100/300 (100-300 kg)"
    elif massa_kg < 1000:
        return "CP 300/1000 (300-1000 kg)"
    elif massa_kg < 3000:
        return "CP 1000/3000 (1-3 t)"
    elif massa_kg < 10000:
        return "CP 3000/10000 (3-10 t)"
    else:
        return "Armourstone pesante (> 10 t) - verificare approvvigionamento"


def volume_massa_per_metro(D50_m: float, spessore_m: float,
                           larghezza_apron_m: float,
                           S_s: float = 2.65, rho: float = 1000.0,
                           porosita: float = 0.40) -> dict:
    """
    Stima volume e massa di scogliera per metro lineare di pila.
    Il volume netto di roccia considera la porosita' della scogliera.
    V_totale = larghezza_apron * spessore [m3/m]
    M_roccia = V_totale * (1 - porosita) * rho_s [kg/m]
    Rif.: FHWA HEC-23, linee guida ASCE.
    """
    rho_s = S_s * rho
    V_tot = larghezza_apron_m * spessore_m
    M_tot = V_tot * (1.0 - porosita) * rho_s
    return {
        "V_totale [m3/m]": round(V_tot, 3),
        "V_roccia_netto [m3/m]": round(V_tot * (1.0 - porosita), 3),
        "Massa_roccia [kg/m]": round(M_tot, 1),
        "Massa_roccia [t/m]": round(M_tot / 1000.0, 2),
        "Porosita': [-]": porosita,
    }


# ---------------------------------------------------------------------------
# Verifiche normative
# ---------------------------------------------------------------------------

def verifiche_scogliera(dati: "DatiScogliera", D50: float) -> pd.DataFrame:
    """
    Tabella verifiche normative per scogliera di protezione pila.
    Colonne: N., Verifica, Valore calcolato, Limite/soglia, Esito, Riferimento normativo
    """
    spess = spessore_rivestimento(D50, dati.fattore_spessore)
    L_ap = larghezza_apron(dati.ys_atteso, dati.fattore_larghezza)
    massa = massa_masso_tipico(D50, dati.S_s, dati.rho)
    grad = gradazione_riprap(D50)
    filtro = progettazione_filtro_terzaghi(D50)

    rows: List[dict] = []

    # 1. D50 dimensionale
    if D50 < 0.10:
        esito_d50, note_d50 = "ATTENZIONE", "massi piccoli: rischio trascinamento, valutare gabbioni"
    elif D50 > 1.5:
        esito_d50, note_d50 = "ATTENZIONE", "massi molto grandi: verificare approvvigionamento"
    else:
        esito_d50, note_d50 = "OK", "pezzatura nella norma"
    rows.append({
        "N.": 1, "Verifica": "D50 pezzatura",
        "Valore calcolato": f"{D50:.4f} m",
        "Limite/soglia": "0.10 - 1.50 m (campo tipico)",
        "Esito": esito_d50,
        "Riferimento normativo": f"FHWA HEC-23; {note_d50}",
    })

    # 2. Spessore rivestimento
    t_min = max(0.30, 2.0 * D50)
    if spess >= t_min:
        esito_t = "OK"
    else:
        esito_t = "NON OK"
    rows.append({
        "N.": 2, "Verifica": "Spessore rivestimento",
        "Valore calcolato": f"{spess:.3f} m",
        "Limite/soglia": f">= {t_min:.3f} m (max(0.30, 2*D50))",
        "Esito": esito_t,
        "Riferimento normativo": "FHWA HEC-23, Sec. 10; CNR-UNI",
    })

    # 3. Larghezza apron
    L_min = 2.0 * dati.ys_atteso
    if L_ap >= L_min:
        esito_L = "OK"
    else:
        esito_L = "NON OK"
    rows.append({
        "N.": 3, "Verifica": "Larghezza apron",
        "Valore calcolato": f"{L_ap:.3f} m",
        "Limite/soglia": f">= {L_min:.3f} m (2 * ys_atteso)",
        "Esito": esito_L,
        "Riferimento normativo": "FHWA HEC-23; Richardson & Davis HEC-18",
    })

    # 4. Massa masso tipico
    M = massa["massa_masso [kg]"]
    if M < 25:
        esito_M = "NON OK"
    elif M < 100:
        esito_M = "ATTENZIONE"
    else:
        esito_M = "OK"
    rows.append({
        "N.": 4, "Verifica": "Massa masso tipico",
        "Valore calcolato": f"{M:.1f} kg",
        "Limite/soglia": "> 100 kg (maneggiabilita')",
        "Esito": esito_M,
        "Riferimento normativo": f"EN 13383-1; {classe_en13383(M)}",
    })

    # 5. Rapporto D85/D15 (uniformita' granulometrica)
    D85 = grad["D85 [m]"]
    D15 = grad["D15 [m]"]
    rapporto = D85 / D15 if D15 > 0 else float("nan")
    if rapporto <= 6.0:
        esito_grad = "OK"
    else:
        esito_grad = "ATTENZIONE"
    rows.append({
        "N.": 5, "Verifica": "Uniformita' granulometrica D85/D15",
        "Valore calcolato": f"{rapporto:.2f}",
        "Limite/soglia": "<= 6 (granulometria continua)",
        "Esito": esito_grad,
        "Riferimento normativo": "FHWA HEC-23; EN 13383-1",
    })

    # 6. Filtro Terzaghi - rispetto criteri
    rows.append({
        "N.": 6, "Verifica": "Filtro Terzaghi - D50 filtro",
        "Valore calcolato": f"{filtro['D50_filtro_adottato [m]']:.4f} m",
        "Limite/soglia": f"{filtro['D15_filtro_min [m]']:.4f} - {filtro['D15_filtro_max [m]']:.4f} m (D15)",
        "Esito": "INFO",
        "Riferimento normativo": "Terzaghi (1943); USACE EM 1110-2-1913",
    })

    # 7. Velocita' (solo se Isbash)
    if dati.metodo == "Isbash" and dati.V > 0:
        if dati.V <= 3.0:
            esito_v = "OK"
        elif dati.V <= 5.0:
            esito_v = "ATTENZIONE"
        else:
            esito_v = "NON OK"
        rows.append({
            "N.": 7, "Verifica": "Velocita' caratteristica (Isbash)",
            "Valore calcolato": f"{dati.V:.3f} m/s",
            "Limite/soglia": "<= 3.0 m/s (normale); <= 5.0 m/s (alto)",
            "Esito": esito_v,
            "Riferimento normativo": "HEC-23; linea guida progettuale",
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Report tabellare
# ---------------------------------------------------------------------------

def calcola_report(dati: DatiScogliera) -> pd.DataFrame:
    D50_calc = calcola_d50(dati)
    spess = spessore_rivestimento(D50_calc, dati.fattore_spessore)
    L_ap = larghezza_apron(dati.ys_atteso, dati.fattore_larghezza)
    massa = massa_masso_tipico(D50_calc, dati.S_s, dati.rho)

    D50_isbash_val = (d50_isbash(dati.V, dati.S_s, dati.K_isbash)
                     if dati.V > 0 else None)
    tau = tau_fondo(dati.y, dati.S_idraulica, dati.rho) if dati.y > 0 else None
    D50_shields_val = (d50_shields(tau, dati.S_s, dati.rho, dati.theta_c)
                      if tau is not None else None)

    rows = [
        {"Parametro": "Metodo selezionato",
         "Valore": dati.metodo},
        {"Parametro": "D50 Isbash [m]",
         "Valore": f"{D50_isbash_val:.3f}" if D50_isbash_val else "-"},
        {"Parametro": "D50 Shields [m]",
         "Valore": f"{D50_shields_val:.3f}" if D50_shields_val else "-"},
        {"Parametro": f"D50 (metodo {dati.metodo}) [m]",
         "Valore": f"{D50_calc:.3f}"},
        {"Parametro": f"Spessore rivestimento [m]  (= {dati.fattore_spessore:.1f}*D50)",
         "Valore": f"{spess:.3f}"},
        {"Parametro": f"Larghezza apron [m]  (= {dati.fattore_larghezza:.1f}*ys)",
         "Valore": f"{L_ap:.2f}"},
        {"Parametro": "Massa masso tipico [kg]",
         "Valore": f"{massa['massa_masso [kg]']:.1f}"},
        {"Parametro": "Densita roccia rho_s [kg/m3]",
         "Valore": f"{massa['rho_s [kg/m3]']:.0f}"},
    ]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Tabella passaggi di calcolo
# ---------------------------------------------------------------------------

def tabella_passaggi(dati: DatiScogliera) -> pd.DataFrame:
    """
    Tabella con tutti i passaggi intermedi del calcolo D50.
    Include: calcolo D50, gradazione, filtro Terzaghi, massa, volume per metro.
    Colonne: Passo, Grandezza, Simbolo, Formula, Valore, Unita
    """
    rho_s = dati.S_s * dati.rho
    D50 = calcola_d50(dati)
    spess = spessore_rivestimento(D50, dati.fattore_spessore)
    L_ap = larghezza_apron(dati.ys_atteso, dati.fattore_larghezza)
    V_masso = math.pi * D50 ** 3 / 6.0
    M_masso = rho_s * V_masso
    grad = gradazione_riprap(D50)
    filtro = progettazione_filtro_terzaghi(D50)
    vol_m = volume_massa_per_metro(D50, spess, L_ap, dati.S_s, dati.rho)

    if dati.metodo == "Isbash":
        K2 = dati.K_isbash ** 2
        denom_isbash = K2 * G * (dati.S_s - 1.0)
        base_rows = [
            (1, "Densita' roccia",     "rho_s",  "S_s * rho",         f"{rho_s:.1f}",          "kg/m3",
             "Densita' del materiale lapideo (granito~2650, calcare~2700 kg/m3)"),
            (2, "Coefficiente K^2",    "K^2",    "K_isbash^2",        f"{K2:.4f}",              "-",
             "K^2 dalla formula di Isbash: K=1.7 annegato, K=1.5 esposto"),
            (3, "Fattore (S_s - 1)",   "S_s-1",  "S_s - 1",           f"{dati.S_s - 1.0:.4f}", "-",
             "Peso immerso relativo del materiale: motore della resistenza idrodinamica"),
            (4, "Denominatore Isbash", "denom",  "K^2 * g * (S_s-1)", f"{denom_isbash:.5f}",   "m/s^2",
             "Denominatore della formula di Isbash"),
            (5, "D50 Isbash",          "D50",    "V^2 / denom",       f"{D50:.5f}",             "m",
             "Diametro mediano necessario per resistere alla velocita' V (Isbash)"),
        ]
    else:
        tau = tau_fondo(dati.y, dati.S_idraulica, dati.rho)
        denom_sh = dati.theta_c * (dati.S_s - 1.0) * dati.rho * G
        base_rows = [
            (1, "Densita' roccia",      "rho_s",  "S_s * rho",               f"{rho_s:.1f}",          "kg/m3",
             "Densita' del materiale lapideo (granito~2650 kg/m3)"),
            (2, "Fattore (S_s - 1)",    "S_s-1",  "S_s - 1",                 f"{dati.S_s - 1.0:.4f}", "-",
             "Peso immerso relativo: ingresso nella formula di Shields"),
            (3, "Sforzo al fondo tau",  "tau",    "rho * g * y * S",         f"{tau:.4f}",            "Pa",
             "Sforzo tangenziale al fondo per alveo largo in moto uniforme"),
            (4, "Denominatore Shields", "denom",  "theta_c*(S_s-1)*rho*g",   f"{denom_sh:.4f}",       "N/m3",
             "Denominatore della formula di Shields (resistenza al moto)"),
            (5, "D50 Shields",          "D50",    "tau / denom",             f"{D50:.5f}",            "m",
             "Diametro mediano necessario per resistere allo sforzo tau (Shields)"),
        ]

    extra_rows = [
        (6,  "Spessore rivestimento",  "t",      f"f_t*D50={dati.fattore_spessore:.1f}*D50",
             f"{spess:.5f}",                   "m",      "Spessore minimo della scogliera: deve contenere almeno 2 strati di massi"),
        (7,  "Larghezza apron",        "L_ap",   f"f_L*ys={dati.fattore_larghezza:.1f}*ys",
             f"{L_ap:.4f}",                    "m",      "Estensione laterale dell'apron oltre la pila: protegge dai filetti di bordo"),
        (8,  "Volume masso (sferico)", "V_m",    "pi * D50^3 / 6",
             f"{V_masso:.6f}",                 "m^3",    "Volume del singolo masso assimilato a sfera di diametro D50"),
        (9,  "Massa masso tipico",     "M_m",    "rho_s * V_m",
             f"{M_masso:.2f}",                 "kg",     "Massa indicativa del singolo masso: confronto con classi EN 13383-1"),
        (10, "D15 gradazione riprap",  "D15",    "0.40 * D50",
             f"{grad['D15 [m]']:.4f}",         "m",      "Percentile 15 della curva granulometrica del riprap (FHWA HEC-23)"),
        (11, "D85 gradazione riprap",  "D85",    "2.00 * D50",
             f"{grad['D85 [m]']:.4f}",         "m",      "Percentile 85: usato per il criterio anti-piping del filtro di Terzaghi"),
        (12, "D100 gradazione riprap", "D100",   "2.50 * D50",
             f"{grad['D100 [m]']:.4f}",        "m",      "Dimensione massima ammissibile della granulometria del riprap"),
        (13, "D50 filtro Terzaghi",    "D50_f",  "sqrt(D15min*D15max)",
             f"{filtro['D50_filtro_adottato [m]']:.4f}", "m",
             "Dimensione del filtro granulare tra substrato e scogliera (criteri Terzaghi)"),
        (14, "Spessore filtro",        "t_f",    "max(0.15, 1.5*D85_f)",
             f"{filtro['Spessore_filtro [m]']:.4f}",    "m",
             "Spessore minimo dello strato filtro: garantisce la funzione di transizione"),
        (15, "Volume scogliera/metro", "V/m",    "L_ap * t",
             f"{vol_m['V_totale [m3/m]']:.3f}", "m^3/m",
             "Volume totale della scogliera per metro lineare di pila"),
        (16, "Massa scogliera/metro",  "M/m",    "V*(1-n)*rho_s",
             f"{vol_m['Massa_roccia [t/m]']:.2f}", "t/m",
             "Massa netta di roccia per metro lineare (detratto il volume dei vuoti)"),
    ]

    rows = base_rows + extra_rows
    return pd.DataFrame(rows, columns=["Passo", "Grandezza", "Simbolo",
                                       "Formula", "Valore", "Unita", "Descrizione"])


# ---------------------------------------------------------------------------
# Curve di sensitivita
# ---------------------------------------------------------------------------

def curva_d50_vs_V(S_s: float, K: float,
                   V_min: float, V_max: float,
                   n_punti: int = 50) -> pd.DataFrame:
    """D50 Isbash al variare della velocita caratteristica."""
    records = []
    for V in np.linspace(V_min, V_max, n_punti):
        records.append({
            "V [m/s]": round(float(V), 3),
            "D50 Isbash [m]": round(d50_isbash(float(V), S_s, K), 4),
        })
    return pd.DataFrame(records)


def curva_d50_vs_y(S_idraulica: float, S_s: float, rho: float,
                   theta_c: float, y_min: float, y_max: float,
                   n_punti: int = 50) -> pd.DataFrame:
    """D50 Shields al variare del tirante y."""
    records = []
    for y in np.linspace(y_min, y_max, n_punti):
        tau = tau_fondo(float(y), S_idraulica, rho)
        records.append({
            "y [m]": round(float(y), 3),
            "D50 Shields [m]": round(d50_shields(tau, S_s, rho, theta_c), 4),
        })
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Generazione report PDF
# ---------------------------------------------------------------------------

def _pdf_sezione(pdf, titolo: str) -> None:
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_fill_color(41, 98, 155)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 7, titolo, ln=True, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(1)


def _pdf_riga_kv(pdf, chiave: str, valore: str) -> None:
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(70, 5, chiave + ":", border="B")
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(0, 5, valore, border="B", ln=True)


def _pdf_tabella(pdf, df: pd.DataFrame) -> None:
    cols = list(df.columns)
    larghezze = {
        "Passo": 9, "Grandezza": 35, "Simbolo": 18,
        "Formula": 45, "Valore": 24, "Unita": 14, "Descrizione": 45,
        "Parametro": 110, "Valore": 70,
    }
    default_w = 30
    row_h = 5

    pdf.set_font("Helvetica", "B", 7)
    pdf.set_fill_color(210, 225, 245)
    for col in cols:
        w = larghezze.get(col, default_w)
        pdf.cell(w, row_h + 1, col, border=1, align="C", fill=True)
    pdf.ln()

    pdf.set_font("Helvetica", "", 7)
    for _, row in df.iterrows():
        for col in cols:
            w = larghezze.get(col, default_w)
            txt = str(row[col])
            align = "C" if col in ("Passo", "Simbolo", "Valore", "Unita") else "L"
            max_c = max(4, int(w / 2.0))
            if len(txt) > max_c:
                txt = txt[: max_c - 2] + ".."
            pdf.cell(w, row_h, txt, border=1, align=align)
        pdf.ln()


def genera_pdf(dati: "DatiScogliera", D50: float, note: List[str]) -> bytes:
    """Genera un report PDF completo e restituisce i bytes."""
    from fpdf import FPDF

    df_pass = tabella_passaggi(dati)
    df_report = calcola_report(dati)
    df_ver = verifiche_scogliera(dati, D50)
    spess = spessore_rivestimento(D50, dati.fattore_spessore)
    L_ap = larghezza_apron(dati.ys_atteso, dati.fattore_larghezza)
    massa = massa_masso_tipico(D50, dati.S_s, dati.rho)
    grad = gradazione_riprap(D50)
    filtro = progettazione_filtro_terzaghi(D50)
    vol_m = volume_massa_per_metro(D50, spess, L_ap, dati.S_s, dati.rho)

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 14)
    pdf.set_fill_color(20, 60, 120)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 12, "Report - Scogliera Protezione Pila (D50 Riprap)",
             ln=True, align="C", fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(0, 6, f"Generato il {datetime.date.today().strftime('%d/%m/%Y')}  |  "
             f"Metodo: {dati.metodo}  |  EN 13383-1, FHWA HEC-23",
             ln=True, align="C")
    pdf.ln(4)

    _pdf_sezione(pdf, "1. Parametri di input")
    _pdf_riga_kv(pdf, "Metodo", dati.metodo)
    _pdf_riga_kv(pdf, "Densita' relativa roccia S_s", f"{dati.S_s:.3f}")
    _pdf_riga_kv(pdf, "Densita' acqua rho", f"{dati.rho:.1f} kg/m3")
    if dati.metodo == "Isbash":
        _pdf_riga_kv(pdf, "Velocita' caratteristica V", f"{dati.V:.3f} m/s")
        _pdf_riga_kv(pdf, "Coefficiente K Isbash", f"{dati.K_isbash:.3f}")
    else:
        _pdf_riga_kv(pdf, "Tirante y", f"{dati.y:.3f} m")
        _pdf_riga_kv(pdf, "Pendenza idraulica S", f"{dati.S_idraulica:.5f}")
        _pdf_riga_kv(pdf, "Shields critico theta_c", f"{dati.theta_c:.4f}")
    _pdf_riga_kv(pdf, "Scalzamento atteso ys", f"{dati.ys_atteso:.2f} m")
    _pdf_riga_kv(pdf, "Fattore spessore f_t", f"{dati.fattore_spessore:.2f}")
    _pdf_riga_kv(pdf, "Fattore larghezza f_L", f"{dati.fattore_larghezza:.2f}")
    pdf.ln(4)

    _pdf_sezione(pdf, "2. Risultati principali")
    _pdf_riga_kv(pdf, "D50 pezzatura", f"{D50:.4f} m")
    _pdf_riga_kv(pdf, "Classe EN 13383-1", classe_en13383(massa["massa_masso [kg]"]))
    _pdf_riga_kv(pdf, "Gradazione: D15 / D50 / D85 / D100",
                 f"{grad['D15 [m]']:.3f} / {grad['D50 [m]']:.3f} / {grad['D85 [m]']:.3f} / {grad['D100 [m]']:.3f} m")
    _pdf_riga_kv(pdf, "Spessore rivestimento", f"{spess:.4f} m")
    _pdf_riga_kv(pdf, "Larghezza apron", f"{L_ap:.3f} m")
    _pdf_riga_kv(pdf, "Massa masso tipico", f"{massa['massa_masso [kg]']:.1f} kg")
    _pdf_riga_kv(pdf, "Filtro Terzaghi - D50 filtro", f"{filtro['D50_filtro_adottato [m]']:.4f} m")
    _pdf_riga_kv(pdf, "Filtro Terzaghi - spessore", f"{filtro['Spessore_filtro [m]']:.3f} m")
    _pdf_riga_kv(pdf, "Massa scogliera per metro lineare", f"{vol_m['Massa_roccia [t/m]']:.2f} t/m")
    pdf.ln(4)

    _pdf_sezione(pdf, "3. Passaggi di calcolo (passo per passo)")
    _pdf_tabella(pdf, df_pass)
    pdf.ln(4)

    pdf.add_page()
    _pdf_sezione(pdf, "4. Riepilogo dimensionamento scogliera")
    _pdf_tabella(pdf, df_report)
    pdf.ln(4)

    _pdf_sezione(pdf, "5. Verifiche normative")
    _pdf_tabella(pdf, df_ver)
    pdf.ln(4)

    pdf.add_page()
    _pdf_sezione(pdf, "6. Note tecniche e commenti progettuali")
    pdf.set_font("Helvetica", "", 8)
    for item in note:
        txt = "- " + item.encode("latin-1", "replace").decode("latin-1")
        pdf.multi_cell(0, 5, txt)
        pdf.ln(1)

    return pdf.output()


# ---------------------------------------------------------------------------
# Commenti progettuali automatici
# ---------------------------------------------------------------------------

def commenti_progettuali(dati: DatiScogliera, D50: float) -> List[str]:
    note: List[str] = []

    if D50 > 1.5:
        note.append(
            f"Il D50 stimato ({D50:.3f} m) e' molto elevato: verificare se la protezione "
            "a scogliera sia praticabile (logistica massi, peso, approvvigionamento). "
            "Valutare soluzioni alternative o complementari."
        )
    elif D50 < 0.05:
        note.append(
            f"Il D50 stimato ({D50:.3f} m) e' molto ridotto: considerare l'uso di materiale "
            "legato (gabbioni, calcestruzzo) o geotessili, dato il peso ridotto dei massi."
        )

    if dati.metodo == "Isbash" and dati.V > 4.0:
        note.append(
            f"La velocita caratteristica ({dati.V:.1f} m/s) e' molto elevata: "
            "la scogliera potrebbe non essere sufficiente da sola. "
            "Considerare soluzioni complementari (pali, cassoni)."
        )
    if dati.metodo == "Shields" and dati.theta_c < 0.03:
        note.append(
            "Il valore critico di Shields theta_c < 0.03 e' molto conservativo: "
            "verificare la letteratura per il materiale di progetto."
        )

    spess = spessore_rivestimento(D50, dati.fattore_spessore)
    L_ap = larghezza_apron(dati.ys_atteso, dati.fattore_larghezza)
    note.append(
        f"Spessore minimo consigliato: {spess:.3f} m (= {dati.fattore_spessore:.1f}*D50). "
        f"Larghezza apron: {L_ap:.2f} m (= {dati.fattore_larghezza:.1f}*ys_atteso)."
    )
    note.append(
        "Predisporre sempre uno strato filtro granulare o geotessile sotto la scogliera "
        "per prevenire la migrazione del materiale fine del substrato."
    )
    note.append(
        "I valori di spessore e larghezza sono indicazioni di linea guida: "
        "adattare alle norme locali (es. FHWA HEC-23, CNR UNI) e alla morfologia del sito."
    )
    return note
