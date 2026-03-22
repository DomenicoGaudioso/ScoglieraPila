# -*- coding: utf-8 -*-
import json
import streamlit as st
import plotly.express as px
from src import (DatiScogliera, valida_dati, calcola_d50, calcola_report,
                 spessore_rivestimento, larghezza_apron, massa_masso_tipico,
                 curva_d50_vs_V, curva_d50_vs_y, tabella_passaggi,
                 genera_pdf, commenti_progettuali,
                 verifiche_scogliera, gradazione_riprap,
                 progettazione_filtro_terzaghi, volume_massa_per_metro,
                 classe_en13383)

st.set_page_config(page_title="Scogliera - Protezione Pila", layout="wide")
st.title("Scogliera (riprap) a protezione della pila da ponte")
st.caption("Software professionale: Isbash + Shields, gradazione EN 13383-1, filtro Terzaghi, volume/massa per metro, verifiche normative, report PDF.")

# ---------------------------------------------------------------------------
# Defaults e session state
# ---------------------------------------------------------------------------
_DEFAULTS = {
    "scpila_metodo": "Isbash",
    "scpila_Ss": 2.65, "scpila_rho": 1000.0,
    "scpila_ys": 2.0, "scpila_ft": 2.0, "scpila_fL": 2.0,
    "scpila_V": 2.5, "scpila_K": 1.7,
    "scpila_y": 2.5, "scpila_S": 0.002, "scpila_thetac": 0.047,
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ---------------------------------------------------------------------------
# Sidebar - Input
# ---------------------------------------------------------------------------
with st.sidebar:
    with st.expander("Salva / Carica parametri", expanded=False):
        uploaded = st.file_uploader("Carica parametri (JSON)", type=["json"],
                                    key="scpila_upload")
        if uploaded is not None:
            try:
                loaded = json.loads(uploaded.read())
                if st.button("Applica parametri caricati", key="scpila_apply"):
                    for k in _DEFAULTS:
                        if k in loaded:
                            st.session_state[k] = loaded[k]
                    st.rerun()
                st.caption(f"File: {uploaded.name}")
            except Exception:
                st.error("File JSON non valido.")

        params_json = json.dumps(
            {k: st.session_state[k] for k in _DEFAULTS}, indent=2
        ).encode()
        st.download_button("Scarica parametri JSON", params_json,
                           "scogliera_pila_parametri.json", "application/json")

    st.divider()
    st.header("Parametri generali")
    metodo = st.selectbox("Metodo di dimensionamento", ["Isbash", "Shields"],
                          index=["Isbash", "Shields"].index(st.session_state["scpila_metodo"]),
                          key="scpila_metodo")
    S_s = st.number_input("Densit\u00e0 relativa roccia S_s = \u03c1_s/\u03c1",
                          min_value=1.1, max_value=3.5, step=0.05, key="scpila_Ss")
    rho = st.number_input("Densit\u00e0 acqua \u03c1 [kg/m\u00b3]",
                          min_value=900.0, max_value=1100.0, step=10.0, key="scpila_rho")

    st.subheader("Scalzamento atteso e apron")
    ys_atteso = st.number_input("ys atteso [m] (da app Scalzamento)",
                                min_value=0.1, step=0.1, key="scpila_ys")
    fattore_spessore = st.number_input("Fattore spessore f_t (spess = f_t\u00b7D50)",
                                       min_value=1.0, max_value=4.0, step=0.1, key="scpila_ft")
    fattore_larghezza = st.number_input("Fattore larghezza f_L (L_apron = f_L\u00b7ys)",
                                        min_value=1.0, max_value=5.0, step=0.1, key="scpila_fL")

    V = 0.0
    K_isbash = 1.7
    y_shields = 0.0
    S_idraulica = 0.002
    theta_c = 0.047

    if metodo == "Isbash":
        st.header("Parametri Isbash")
        V = st.number_input("Velocit\u00e0 caratteristica V [m/s]",
                            min_value=0.1, step=0.05, key="scpila_V")
        K_isbash = st.number_input("Coefficiente K Isbash (1.5\u00f71.7)",
                                   min_value=1.0, max_value=2.5, step=0.05, key="scpila_K")
        st.caption("K=1.7: masso annegato/fondo  |  K=1.5: masso esposto")
    else:
        st.header("Parametri Shields")
        y_shields = st.number_input("Tirante y [m]",
                                    min_value=0.05, step=0.05, key="scpila_y")
        S_idraulica = st.number_input("Pendenza idraulica S [-]",
                                      min_value=0.00001, step=0.0001, format="%.5f",
                                      key="scpila_S")
        theta_c = st.number_input("Shields critico \u03b8_c",
                                  min_value=0.02, max_value=0.1, step=0.001,
                                  key="scpila_thetac")
        st.caption("\u03b8_c \u2248 0.047 (Shields 1936); 0.030 per materiale angoloso")

# ---------------------------------------------------------------------------
# Calcolo
# ---------------------------------------------------------------------------
dati = DatiScogliera(
    S_s=S_s, rho=rho, metodo=metodo,
    V=V, K_isbash=K_isbash,
    y=y_shields, S_idraulica=S_idraulica, theta_c=theta_c,
    ys_atteso=ys_atteso,
    fattore_spessore=fattore_spessore, fattore_larghezza=fattore_larghezza,
)
errori = valida_dati(dati)
if errori:
    for e in errori:
        st.error(e)
    st.stop()

D50 = calcola_d50(dati)
spess = spessore_rivestimento(D50, fattore_spessore)
L_ap = larghezza_apron(ys_atteso, fattore_larghezza)
massa = massa_masso_tipico(D50, S_s, rho)
grad = gradazione_riprap(D50)
filtro = progettazione_filtro_terzaghi(D50)
vol_m = volume_massa_per_metro(D50, spess, L_ap, S_s, rho)
df_report = calcola_report(dati)
df_pass = tabella_passaggi(dati)
df_ver = verifiche_scogliera(dati, D50)
note = commenti_progettuali(dati, D50)

if metodo == "Isbash":
    df_sens = curva_d50_vs_V(S_s, K_isbash, max(0.1, V * 0.4), V * 2.5)
else:
    df_sens = curva_d50_vs_y(S_idraulica, S_s, rho, theta_c,
                             max(0.1, y_shields * 0.4), y_shields * 2.5)

# ---------------------------------------------------------------------------
# Indicatori sintetici
# ---------------------------------------------------------------------------
n_ok  = (df_ver["Esito"] == "OK").sum()
n_att = (df_ver["Esito"] == "ATTENZIONE").sum()
n_no  = (df_ver["Esito"] == "NON OK").sum()

col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("D50 stimato [m]", f"{D50:.3f}")
col2.metric("Spessore min [m]", f"{spess:.3f}")
col3.metric("Larghezza apron [m]", f"{L_ap:.2f}")
col4.metric("Massa masso tipico [kg]", f"{massa['massa_masso [kg]']:.0f}")
col5.metric("Massa scogliera [t/m]", f"{vol_m['Massa_roccia [t/m]']:.2f}")
col6.metric("Verif. OK / WARN / NO", f"{n_ok} / {n_att} / {n_no}", delta_color="off")

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(["Risultati", "Grafici", "Verifiche avanzate", "Note tecniche"])

with tab1:
    st.subheader("Passaggi di calcolo (passo per passo)")
    st.dataframe(df_pass, use_container_width=True, hide_index=True)

    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Dimensionamento pezzatura**")
        st.markdown(f"- Metodo: **{metodo}**")
        st.markdown(f"- D50 = **{D50:.4f} m**")
        st.markdown(f"- Classe EN 13383-1: *{classe_en13383(massa['massa_masso [kg]'])}*")
        st.markdown(f"- Gradazione: D15={grad['D15 [m]']:.3f} / D50={grad['D50 [m]']:.3f} / D85={grad['D85 [m]']:.3f} / D100={grad['D100 [m]']:.3f} m")
        st.markdown(f"- Massa masso tipico: **{massa['massa_masso [kg]']:.0f} kg**")
    with col_b:
        st.markdown("**Apron e filtro**")
        st.markdown(f"- Spessore rivestimento: **{spess:.3f} m**")
        st.markdown(f"- Larghezza apron: **{L_ap:.3f} m**")
        st.markdown(f"- Filtro Terzaghi D50: **{filtro['D50_filtro_adottato [m]']:.4f} m**")
        st.markdown(f"- Spessore filtro: **{filtro['Spessore_filtro [m]']:.3f} m**")
        st.markdown(f"- Massa scogliera per metro lineare: **{vol_m['Massa_roccia [t/m]']:.2f} t/m**")

    st.divider()
    st.subheader("Riepilogo dimensionamento scogliera")
    st.dataframe(df_report, use_container_width=True, hide_index=True)

    st.divider()
    col_dl1, col_dl2, col_dl3, col_dl4 = st.columns(4)
    with col_dl1:
        st.download_button("Scarica passaggi CSV",
                           df_pass.to_csv(index=False).encode("utf-8"),
                           "scogliera_pila_passaggi.csv", "text/csv")
    with col_dl2:
        st.download_button("Scarica risultati CSV",
                           df_report.to_csv(index=False).encode("utf-8"),
                           "scogliera_pila_risultati.csv", "text/csv")
    with col_dl3:
        st.download_button("Scarica sensitivit\u00e0 CSV",
                           df_sens.to_csv(index=False).encode("utf-8"),
                           "scogliera_pila_sensitivita.csv", "text/csv")
    with col_dl4:
        try:
            pdf_bytes = bytes(genera_pdf(dati, D50, note))
            st.download_button("Scarica Report PDF", pdf_bytes,
                               "scogliera_pila_report.pdf", "application/pdf")
        except ImportError:
            st.warning("fpdf2 non installato. Eseguire: pip install fpdf2")

with tab2:
    if metodo == "Isbash":
        st.subheader("D50 Isbash in funzione della velocit\u00e0 caratteristica")
        fig = px.line(df_sens, x="V [m/s]", y="D50 Isbash [m]",
                      title="Sensitivit\u00e0 D50 (Isbash) rispetto alla velocit\u00e0")
        fig.add_vline(x=V, line_dash="dash", line_color="red",
                      annotation_text=f"V={V:.2f} m/s", annotation_position="top right")
        fig.add_hline(y=D50, line_dash="dot", line_color="orange",
                      annotation_text=f"D50={D50:.3f} m", annotation_position="bottom right")
        fig.update_layout(xaxis_title="V [m/s]", yaxis_title="D50 [m]")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.subheader("D50 Shields in funzione del tirante")
        fig = px.line(df_sens, x="y [m]", y="D50 Shields [m]",
                      title="Sensitivit\u00e0 D50 (Shields) rispetto al tirante")
        fig.add_vline(x=y_shields, line_dash="dash", line_color="red",
                      annotation_text=f"y={y_shields:.2f} m", annotation_position="top right")
        fig.add_hline(y=D50, line_dash="dot", line_color="orange",
                      annotation_text=f"D50={D50:.3f} m", annotation_position="bottom right")
        fig.update_layout(xaxis_title="y [m]", yaxis_title="D50 [m]")
        st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.subheader("Verifiche normative")
    _colori = {"OK": "background-color: #d4edda",
               "ATTENZIONE": "background-color: #fff3cd",
               "NON OK": "background-color: #f8d7da",
               "INFO": "background-color: #d1ecf1"}

    def _colora(row):
        c = _colori.get(row["Esito"], "")
        return [c] * len(row)

    styled = df_ver.style.apply(_colora, axis=1)
    st.dataframe(styled, use_container_width=True, hide_index=True)

    st.divider()
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.subheader("Gradazione riprap")
        st.markdown(f"- D15 = **{grad['D15 [m]']:.4f} m**")
        st.markdown(f"- D50 = **{grad['D50 [m]']:.4f} m**")
        st.markdown(f"- D85 = **{grad['D85 [m]']:.4f} m**")
        st.markdown(f"- D100 = **{grad['D100 [m]']:.4f} m**")
        st.markdown(f"- Classe EN 13383-1: *{classe_en13383(massa['massa_masso [kg]'])}*")
        st.caption("Rif.: FHWA HEC-23 (2009), EN 13383-1:2002+A1:2008")
    with col_g2:
        st.subheader("Filtro granulare (Terzaghi)")
        st.markdown(f"- D15 filtro min: **{filtro['D15_filtro_min [m]']:.4f} m**")
        st.markdown(f"- D15 filtro max: **{filtro['D15_filtro_max [m]']:.4f} m**")
        st.markdown(f"- D50 filtro adottato: **{filtro['D50_filtro_adottato [m]']:.4f} m**")
        st.markdown(f"- D85 filtro: **{filtro['D85_filtro [m]']:.4f} m**")
        st.markdown(f"- Spessore strato filtro: **{filtro['Spessore_filtro [m]']:.3f} m**")
        st.caption("Rif.: Terzaghi (1943); USACE EM 1110-2-1913")

    st.divider()
    st.subheader("Volume e massa per metro lineare di pila")
    st.markdown(f"- Volume totale (L_apron \u00d7 spessore): **{vol_m['V_totale [m3/m]']:.3f} m\u00b3/m**")
    _por = vol_m["Porosita': [-]"]
    st.markdown(f"- Volume roccia netto (porosit\u00e0 = {_por:.0%}): **{vol_m['V_roccia_netto [m3/m]']:.3f} m\u00b3/m**")
    st.markdown(f"- **Massa roccia: {vol_m['Massa_roccia [t/m]']:.2f} t/m lineare**")
    st.caption("La porosita' della scogliera posata e' stimata al 40% (valore tipico).")

    st.divider()
    st.download_button("Scarica verifiche CSV",
                       df_ver.to_csv(index=False).encode("utf-8"),
                       "scogliera_pila_verifiche.csv", "text/csv")

with tab4:
    st.subheader("Note tecniche e commenti di progetto")
    for item in note:
        st.markdown(f"- {item}")
    with st.expander("Descrizione dei metodi e riferimenti normativi"):
        st.markdown("""
**Metodo Isbash:**
D50 = V\u00b2 / (K\u00b2 \u00b7 g \u00b7 (Ss-1))
- K = 1.7: masso annegato o parzialmente interrato nel fondo
- K = 1.5: masso posato sul fondo in corrente

**Metodo Shields:**
\u03c4 = \u03c1 \u00b7 g \u00b7 y \u00b7 S  (sforzo al fondo, alveo ampio)
D50 = \u03c4 / (\u03b8_c \u00b7 (Ss-1) \u00b7 \u03c1 \u00b7 g)
- \u03b8_c \u2248 0.047: valore critico di Shields (materiale subsferico)
- \u03b8_c \u2248 0.030: materiale angoloso, approccio conservativo

**Gradazione riprap (FHWA HEC-23):**
D15 \u2248 0.40 \u00b7 D50  |  D85 \u2248 2.00 \u00b7 D50  |  D100 \u2248 2.50 \u00b7 D50

**Filtro granulare (Terzaghi):**
Anti-piping: D15_filtro < 5 \u00b7 D85_base
Anti-intasamento: D15_filtro > 5 \u00b7 D15_base

**Riferimenti normativi:**
- FHWA HEC-23 (2009): Design of Riprap Revetment
- EN 13383-1:2002+A1:2008: Armourstone
- USACE EM 1110-2-1913: Design and Construction of Levees
- Isbash (1936), Shields (1936)
        """)
