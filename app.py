import io
import warnings
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

warnings.filterwarnings("ignore")

from analytics import interpreter_comparaison
from calendar_utils import construire_variables_calendaires
from config import (
    COLOR_BORDER,
    COLOR_CARD_BG,
    COLOR_EMIS_HIST,
    COLOR_EMIS_PREV,
    COLOR_GOLD,
    COLOR_LIGHT_BG,
    COLOR_NAVY,
    COLOR_NAVY_BG,
    COLOR_RECUS_HIST,
    COLOR_RECUS_PREV,
    COLOR_SUBTEXT,
    COLOR_TEXT,
    CSS_APPLICATION,
    FONT_STACK,
    RADIUS_CARD,
    render_banner,
    render_divider,
    render_section_header,
)
from forecasting import generer_serie_synthetique, rechercher_meilleur_sarima
from report_generator import generer_rapport_word

# ==============================================================================
# CONFIGURATION STREAMLIT & STYLE PLOTLY
# ==============================================================================
st.set_page_config(
    page_title="Institutional Payment Analytics - Bank of Africa",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Injection du CSS — Thème Bleu Ardoise (Option 2) avec Cadre Doré
CUSTOM_CSS = """
<style>
    /* 1. Fond général Bleu Ardoise */
    .stApp, [data-testid="stSidebar"] {
        background-color: #0F172A !important;
        color: #F8FAFC !important;
    }

    /* 2. BANDEAU D'EN-TÊTE (Cadre Ardoise + Bordure Dorée) */
    .platform-banner {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%) !important;
        border: 1px solid #C59B27 !important; /* Bordure dorée */
        border-radius: 10px !important;
        padding: 24px 32px !important;
        margin-bottom: 24px !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4) !important;
    }

    .platform-kicker {
        color: #C59B27 !important; /* "BANK OF AFRICA" en doré */
        font-family: 'Segoe UI', sans-serif !important;
        font-size: 0.82rem !important;
        font-weight: 700 !important;
        letter-spacing: 2.5px !important;
        text-transform: uppercase !important;
        margin-bottom: 6px !important;
    }

    .platform-title {
        color: #F8FAFC !important;
        font-family: 'Segoe UI', sans-serif !important;
        font-size: 1.6rem !important;
        font-weight: 700 !important;
        margin: 0 0 6px 0 !important;
    }

    .platform-subtitle {
        color: #94A3B8 !important;
        font-family: 'Segoe UI', sans-serif !important;
        font-size: 0.92rem !important;
        margin: 0 !important;
    }

    .platform-divider {
        border: none !important;
        border-top: 1px solid #C59B27 !important; /* Séparateur doré */
        opacity: 0.5 !important;
        margin-top: 16px !important;
        margin-bottom: 0 !important;
    }

    /* 3. Style des cartes en Ardoise */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #1E293B !important;
        border: 1px solid #334155 !important;
        border-radius: 10px !important;
    }

    /* 4. Métriques */
    div[data-testid="stMetric"] {
        background-color: #334155 !important;
        border: 1px solid #475569 !important;
        border-radius: 8px !important;
    }

    div[data-testid="stMetricLabel"] {
        color: #94A3B8 !important;
        font-size: 0.8rem !important;
        text-transform: uppercase;
    }

    div[data-testid="stMetricValue"] {
        color: #38BDF8 !important;
        font-size: 1.05rem !important;
        white-space: nowrap !important;
    }

    h1, h2, h3, h4, h5, h6, p, label, .stMarkdown {
        color: #F8FAFC !important;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def style_plotly_figure(fig, title_text):
    fig.update_layout(
        title=dict(
            text=title_text,
            font=dict(size=13, color=COLOR_TEXT, family="Segoe UI"),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=COLOR_CARD_BG,
        font=dict(color=COLOR_SUBTEXT, family="Segoe UI"),
        margin=dict(l=30, r=30, t=40, b=30),
        hovermode="closest",
        legend=dict(
            bgcolor="rgba(17, 34, 64, 0.8)",
            bordercolor="#233554",
            borderwidth=1,
            font=dict(color=COLOR_TEXT),
        ),
        xaxis=dict(
            showgrid=True,
            gridcolor="#1D2D50",
            gridwidth=0.5,
            zeroline=False,
            linecolor="#233554",
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#1D2D50",
            gridwidth=0.5,
            zeroline=False,
            linecolor="#233554",
        ),
    )
    return fig


# ---- BANDEAU D'EN-TÊTE ----
render_banner(
    titre="Plateforme de Modélisation et Prévision des Moyens de Paiement",
    sous_titre="Global Transition Banking  - Bank of Africa",
)

# ==============================================================================
# SIDEBAR : INPUTS & CONFIGURATION
# ==============================================================================
with st.sidebar:
    st.header("Configuration")

    # 1. Chargement de la base de données
    st.subheader("1. Base de Données")
    fichier = st.file_uploader(
        "Fichier Excel source (.xlsx)",
        type=["xlsx"],
        label_visibility="collapsed",
    )

    if fichier is not None:
        df_uploaded = pd.read_excel(fichier)
        colonnes_attendues = {
            "Periode",
            "Banque",
            "Etat",
            "Moyen_de_Paiement",
            "Nombre",
            "Montant",
        }
        if not colonnes_attendues.issubset(df_uploaded.columns):
            st.error(
                f"Structure non conforme. Colonnes requises : {colonnes_attendues}"
            )
            st.stop()

        df_uploaded["Moyen_de_Paiement"] = (
            df_uploaded["Moyen_de_Paiement"].astype(str).str.zfill(3)
        )
        df_uploaded["Periode"] = pd.to_datetime(df_uploaded["Periode"])
        st.session_state["df"] = df_uploaded
        st.success("Fichier chargé avec succès !")

    # 2. Sélections des paramètres
    if "df" in st.session_state:
        df = st.session_state["df"]
        st.divider()
        st.subheader("2. Paramètres du Modèle")

        banque = st.selectbox("Établissement", sorted(df["Banque"].unique()))
        moyen = st.selectbox(
            "Moyen de Paiement", sorted(df["Moyen_de_Paiement"].unique())
        )
        variable = st.selectbox("Indicateur Cible", ["Montant", "Nombre"])
        horizon_annees = st.slider("Horizon de Projection (Années)", 1, 5, 2)

        st.divider()
        lancer_analyse = st.button(
            "Lancer l'Analyse", type="primary", use_container_width=True
        )
    else:
        st.info("Veuillez charger un fichier Excel pour continuer.")


# ==============================================================================
# TRAITEMENT ÉCONOMÉTRIQUE (LANCEMENT)
# ==============================================================================
if "lancer_analyse" in locals() and lancer_analyse:
    resultats_par_etat = {}
    progress_status = st.empty()
    progress_bar = st.progress(0)

    for idx, etat in enumerate(["Emis", "Recus"]):
        nom_affichage = "Flux Émis" if etat == "Emis" else "Flux Reçus"
        progress_status.info(
            f"Traitement économétrique en cours : **{nom_affichage}**..."
        )

        serie, erreur = generer_serie_synthetique(
            df, banque, moyen, variable, etat, horizon_annees * 12
        )
        if erreur:
            resultats_par_etat[etat] = {"erreur": erreur}
            st.error(f"{nom_affichage} : {erreur}")
            continue

        def maj_barre(frac):
            base_frac = 0.0 if etat == "Emis" else 0.5
            progress_bar.progress(
                base_frac + (frac * 0.5),
                text=f"Optimisation {nom_affichage} ({int(frac*100)}%)",
            )

        candidats, contexte_serie, erreur2 = rechercher_meilleur_sarima(
            serie, progress_callback=maj_barre
        )

        if erreur2:
            resultats_par_etat[etat] = {"erreur": erreur2}
            st.error(f"{nom_affichage} : {erreur2}")
            continue

        resultats_par_etat[etat] = {
            "meilleur": candidats[0],
            "candidats": candidats,
            "nb_candidats": len(candidats),
            "serie": serie,
            "contexte_serie": contexte_serie,
        }

    progress_bar.progress(1.0)
    progress_status.success("Analyse économétrique achevée avec succès !")

    st.session_state["resultats_par_etat"] = resultats_par_etat
    st.session_state["contexte"] = {
        "banque": banque,
        "moyen": moyen,
        "variable": variable,
        "horizon_annees": horizon_annees,
    }


# ==============================================================================
# LIGNE 1 : CÔTE À CÔTE (MÉTRIQUES GLOBALES & GRAPHIQUE ANNÉES)
# ==============================================================================
if "df" in st.session_state:
    df = st.session_state["df"]

    moyen_courant = (
        st.session_state.get("contexte", {}).get("moyen")
        or sorted(df["Moyen_de_Paiement"].unique())[0]
    )
    var_courante = (
        st.session_state.get("contexte", {}).get("variable") or "Montant"
    )

    df_moyen = df[df["Moyen_de_Paiement"] == moyen_courant].copy()
    df_moyen = df_moyen.dropna(subset=[var_courante])

    col_gauche, col_droite = st.columns([1, 1.8], gap="large")

    # --- PARTIE 1 : MÉTRIQUES GLOBALES ---
    with col_gauche:
        with st.container(border=True):
            render_section_header("1", "Métriques Globales")

            nb_enregistrements = len(df_moyen)
            nb_banques = df_moyen["Banque"].nunique()

            if not df_moyen.empty:
                periode_min = df_moyen["Periode"].min().strftime("%m/%Y")
                periode_max = df_moyen["Periode"].max().strftime("%m/%Y")
            else:
                periode_min, periode_max = "N/A", "N/A"

            st.metric(
                "Enregistrements (Moyen sélectionné)",
                f"{nb_enregistrements:,}".replace(",", " "),
            )
            st.metric("Établissements Actifs", f"{nb_banques}")
            st.metric("Période Couverte", f"{periode_min} — {periode_max}")

            with st.expander(" Aperçu des Variables Exogènes"):
                apercu_cal = construire_variables_calendaires(
                    df["Periode"].unique()
                ).reset_index()
                st.dataframe(
                    apercu_cal.sort_values("Periode"),
                    use_container_width=True,
                    height=140,
                )

    # --- SECTION A : ÉVOLUTION ANNUELLE (TOP 5 BANQUES AVECS FILTRE FLUX) ---
    with col_droite:
        with st.container(border=True):
            # En-tête + Bouton de sélection (Émis / Reçus) côte à côte
            col_titre, col_switch = st.columns([2.5, 1])

            with col_titre:
                render_section_header(
                    "A",
                    f"Évol. Annuelle — Moyen {moyen_courant}",
                    caption="X = Volume | Y = Top 5 Établissements",
                )

            with col_switch:
                # Bouton de choix pour le flux
                flux_choisi = st.radio(
                    "Flux à afficher",
                    options=["Emis", "Recus"],
                    format_func=lambda x: "Flux Émis"
                    if x == "Emis"
                    else "Flux Reçus",
                    horizontal=True,
                    label_visibility="collapsed",
                    key="switch_flux_top5",
                )

            if df_moyen.empty:
                st.info("Aucune donnée disponible pour ce moyen de paiement.")
            else:
                # 1. Filtrage sur le flux sélectionné par l'utilisateur
                df_flux = df_moyen[df_moyen["Etat"] == flux_choisi].copy()

                if df_flux.empty:
                    st.warning(
                        f"Aucune donnée pour les flux {flux_choisi} sur ce moyen."
                    )
                else:
                    df_flux["Annee"] = df_flux["Periode"].dt.year.astype(str)

                    # 2. Extraction STRICTE du Top 5 des banques pour CE flux précis
                    top_5_banques = (
                        df_flux.groupby("Banque")[var_courante]
                        .sum()
                        .nlargest(5)
                        .index.tolist()
                    )

                    df_top = df_flux[df_flux["Banque"].isin(top_5_banques)]

                    # 3. Agrégation par Année et par Banque
                    agg_annee = (
                        df_top.groupby(["Annee", "Banque"])[
                            ["Montant", "Nombre"]
                        ]
                        .sum()
                        .reset_index()
                    )

                    fig_annee = go.Figure()
                    annees_uniques = sorted(agg_annee["Annee"].unique())

                    # Couleurs selon le flux sélectionné (Thème cohérent)
                    if flux_choisi == "Emis":
                        couleurs_annees = [
                            "#3DA5F5",
                            "#64FFDA",
                            "#1E88E5",
                            "#00ATC4",
                            "#90CAF9",
                        ]
                    else:
                        couleurs_annees = [
                            "#FF8C42",
                            "#FFD166",
                            "#F57C00",
                            "#FFB74D",
                            "#FFE082",
                        ]

                    # 4. Construction des barres horizontales
                    for i, ann in enumerate(annees_uniques):
                        sous_ann = agg_annee[agg_annee["Annee"] == ann]

                        hover_text = [
                            f"<b>{row['Banque']}</b><br>"
                            f"Année : {row['Annee']}<br>"
                            f"Flux : {flux_choisi}<br>"
                            f"Montant : {row['Montant']:,.2f} DH<br>"
                            f"Transactions : {int(row['Nombre']):,}"
                            for _, row in sous_ann.iterrows()
                        ]

                        fig_annee.add_trace(
                            go.Bar(
                                y=sous_ann["Banque"],
                                x=sous_ann[var_courante],
                                name=f"Année {ann}",
                                orientation="h",
                                marker_color=couleurs_annees[
                                    i % len(couleurs_annees)
                                ],
                                hovertext=hover_text,
                                hoverinfo="text",
                            )
                        )

                    fig_annee.update_layout(
                        barmode="stack",
                        xaxis_title=f"Total {var_courante} ({flux_choisi})",
                        yaxis_title="Établissements (Top 5)",
                        yaxis=dict(
                            autorange="reversed"
                        ),  # Le 1er est en haut
                        hoverlabel=dict(
                            bgcolor="#112240",
                            font_size=11,
                            font_family="Segoe UI",
                        ),
                        height=380,
                    )

                    nom_flux_complet = (
                        "Flux Émis" if flux_choisi == "Emis" else "Flux Reçus"
                    )
                    fig_annee = style_plotly_figure(
                        fig_annee,
                        f"Top 5 Banques — {nom_flux_complet} ({var_courante})",
                    )
                    st.plotly_chart(fig_annee, use_container_width=True)

    # ==========================================================================
    # LIGNE 2 : PARTIE 2 EN PLEINE LARGEUR (SOUS LES DEUX PREMIERS BLOCS)
    # ==========================================================================
    with st.container(border=True):
        render_section_header("2", "Modèles Retenus")

        if "resultats_par_etat" in st.session_state:
            resultats = st.session_state["resultats_par_etat"]
            col_m_emis, col_m_recus = st.columns(2, gap="medium")

            for etat, col_target in [("Emis", col_m_emis), ("Recus", col_m_recus)]:
                with col_target:
                    res = resultats.get(etat, {})
                    nom_etat = "Flux Émis (Sortants)" if etat == "Emis" else "Flux Reçus (Entrants)"
                    st.markdown(f"#### {nom_etat}")

                    if res.get("erreur"):
                        st.error(res["erreur"])
                    elif "meilleur" in res:
                        meilleur = res["meilleur"]
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Ordre SARIMA", f"{meilleur['ordre']}")
                        c2.metric("sMAPE Test", f"{meilleur['sMAPE_%']}%")
                        c3.metric("Critère AIC", f"{meilleur['AIC']:.1f}")

                        with st.expander(f"Consulter le classement des candidats ({etat})"):
                            df_cand = pd.DataFrame(res["candidats"])[
                                ["ordre", "AIC", "sMAPE_%", "MAPE_%"]
                            ]
                            st.dataframe(
                                df_cand.head(5), use_container_width=True
                            )
        else:
            st.info(
                "Lancez l'analyse depuis la barre latérale pour afficher la synthèse des modèles retenus."
            )


# ==============================================================================
# LIGNE 3 : TRAJECTOIRES DE PRÉDICTION (PLEINE LARGEUR)
# ==============================================================================
if "resultats_par_etat" in st.session_state:
    render_divider()
    resultats = st.session_state["resultats_par_etat"]
    contexte = st.session_state["contexte"]
    horizon_mois = contexte["horizon_annees"] * 12
    previsions = {}

    render_section_header("3", "Trajectoires de Prédiction Individuelles")

    for etat, couleur_reel, couleur_prev in [
        ("Emis", COLOR_EMIS_HIST, COLOR_EMIS_PREV),
        ("Recus", COLOR_RECUS_HIST, COLOR_RECUS_PREV),
    ]:
        res = resultats.get(etat, {})
        nom_etat = "Flux Émis" if etat == "Emis" else "Flux Reçus"
        if res.get("erreur") or "meilleur" not in res:
            continue

        with st.container(border=True):
            meilleur = res["meilleur"]
            x, y, exog, x_test, y_test, exog_test, n_test = res[
                "contexte_serie"
            ]
            model = meilleur["model"]

            dates_futures = pd.date_range(
                x.index[-1] + pd.DateOffset(months=1),
                periods=horizon_mois,
                freq="MS",
            )
            exog_futures = construire_variables_calendaires(
                dates_futures
            ).reindex(dates_futures)
            prevision = model.get_forecast(
                horizon_mois, exog=exog_futures.values
            )
            x_prev = np.exp(prevision.predicted_mean)
            ci = np.asarray(prevision.conf_int(alpha=0.05))
            previsions[etat] = {
                "dates": dates_futures,
                "valeurs": np.asarray(x_prev),
                "x_historique": x,
                "ci": ci,
            }

            dates_futures_str = dates_futures.strftime("%Y-%m-%d").tolist()
            x_index_str = x.index.strftime("%Y-%m-%d").tolist()

            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=dates_futures_str + dates_futures_str[::-1],
                    y=list(np.exp(ci[:, 1])) + list(np.exp(ci[:, 0]))[::-1],
                    fill="toself",
                    fillcolor=(
                        "rgba(100, 255, 218, 0.10)"
                        if etat == "Emis"
                        else "rgba(255, 209, 102, 0.10)"
                    ),
                    line=dict(color="rgba(255,255,255,0)"),
                    hoverinfo="skip",
                    name="IC 95%",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=x_index_str,
                    y=x["Valeur"],
                    mode="lines",
                    name=f"{nom_etat} (Historique)",
                    line=dict(color=couleur_reel, width=2.5),
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=dates_futures_str,
                    y=x_prev,
                    mode="lines+markers",
                    name=f"{nom_etat} (Projection)",
                    line=dict(color=couleur_prev, width=2.5, dash="dash"),
                    marker=dict(size=5),
                )
            )

            fig = style_plotly_figure(
                fig,
                f"Projection {nom_etat} ({contexte['variable']}) — {contexte['banque']}",
            )
            st.plotly_chart(fig, use_container_width=True)

            try:
                img_bytes = fig.to_image(
                    format="png", width=1000, height=400, scale=2
                )
                resultats[etat]["figure_bytes"] = img_bytes
            except Exception:
                resultats[etat]["figure_bytes"] = None

    # Graphique comparatif Combiné
    if "Emis" in previsions and "Recus" in previsions:
        with st.container(border=True):
            render_section_header("4", "Analyse Comparative : Émis vs Reçus")

            fig_comb = go.Figure()
            emis_hist_dates = (
                previsions["Emis"]["x_historique"]
                .index.strftime("%Y-%m-%d")
                .tolist()
            )
            emis_prev_dates = (
                previsions["Emis"]["dates"].strftime("%Y-%m-%d").tolist()
            )
            recus_hist_dates = (
                previsions["Recus"]["x_historique"]
                .index.strftime("%Y-%m-%d")
                .tolist()
            )
            recus_prev_dates = (
                previsions["Recus"]["dates"].strftime("%Y-%m-%d").tolist()
            )

            fig_comb.add_trace(
                go.Scatter(
                    x=emis_hist_dates,
                    y=previsions["Emis"]["x_historique"]["Valeur"],
                    mode="lines",
                    name="Flux Émis (Hist)",
                    line=dict(color=COLOR_EMIS_HIST, width=2),
                )
            )
            fig_comb.add_trace(
                go.Scatter(
                    x=emis_prev_dates,
                    y=previsions["Emis"]["valeurs"],
                    mode="lines+markers",
                    name="Flux Émis (Proj)",
                    line=dict(color=COLOR_EMIS_PREV, width=2, dash="dash"),
                )
            )
            fig_comb.add_trace(
                go.Scatter(
                    x=recus_hist_dates,
                    y=previsions["Recus"]["x_historique"]["Valeur"],
                    mode="lines",
                    name="Flux Reçus (Hist)",
                    line=dict(color=COLOR_RECUS_HIST, width=2),
                )
            )
            fig_comb.add_trace(
                go.Scatter(
                    x=recus_prev_dates,
                    y=previsions["Recus"]["valeurs"],
                    mode="lines+markers",
                    name="Flux Reçus (Proj)",
                    line=dict(color=COLOR_RECUS_PREV, width=2, dash="dash"),
                )
            )

            date_sep_str = (
                previsions["Emis"]["x_historique"]
                .index[-1]
                .strftime("%Y-%m-%d")
            )
            fig_comb.add_vline(
                x=date_sep_str,
                line_width=1,
                line_dash="dot",
                line_color=COLOR_SUBTEXT,
            )
            fig_comb = style_plotly_figure(
                fig_comb,
                f"Profil Comparatif des Trajectoires — {contexte['variable']}",
            )
            st.plotly_chart(fig_comb, use_container_width=True)

            try:
                st.session_state["figure_combinee_bytes"] = fig_comb.to_image(
                    format="png", width=1200, height=500, scale=2
                )
            except Exception:
                st.session_state["figure_combinee_bytes"] = None

            texte_interp, croisements = interpreter_comparaison(
                previsions["Emis"]["dates"],
                previsions["Emis"]["valeurs"],
                previsions["Recus"]["valeurs"],
                variable_nom=contexte["variable"],
            )
            st.info(texte_interp)
            st.session_state["texte_interpretation"] = texte_interp

# ==============================================================================
# PIED DE PAGE : EXPORTATION DU RAPPORT WORD
# ==============================================================================
if "resultats_par_etat" in st.session_state:
    render_divider()
    with st.container(border=True):
        render_section_header("5", "Exportation du Rapport Institutionnel")
        col_exp1, col_exp2 = st.columns([3, 1])

        with col_exp1:
            st.write(
                "Générez un document Word exécutif synthétisant l'ensemble des modélisations, "
                "des graphiques de projection et du diagnostic financier."
            )

        with col_exp2:
            rapport = generer_rapport_word(
                st.session_state["contexte"],
                st.session_state["resultats_par_etat"],
                st.session_state.get("texte_interpretation"),
                st.session_state.get("figure_combinee_bytes"),
            )
            st.download_button(
                label="Télécharger le Rapport (.docx)",
                data=rapport,
                file_name=f"Rapport_Prevision_{st.session_state['contexte']['moyen']}_{st.session_state['contexte']['banque'].replace(' ', '_')}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                type="primary",
                use_container_width=True,
            )