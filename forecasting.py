import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from statsmodels.tsa.statespace.sarimax import SARIMAX
import itertools
from calendar_utils import construire_variables_calendaires


def estimer_effets_marche(data, colonne, etat, borne_min=0.3, borne_max=3.0):
    sous = data[data["Etat"] == etat].copy()
    sous = sous[sous[colonne] > 0]
    if len(sous) < 8:
        return None
    sous["log_valeur"] = np.log(sous[colonne])
    try:
        modele = smf.ols(
            "log_valeur ~ t + C(mois) + frac_ramadan + is_eid_fitr + is_eid_adha",
            data=sous
        ).fit()
    except Exception:
        return None

    def plafonner(v):
        return min(max(v, borne_min), borne_max)

    effet_mois = {1: 1.0}
    for m in range(2, 13):
        coef = modele.params.get(f"C(mois)[T.{m}]", 0.0)
        effet_mois[m] = plafonner(np.exp(coef))

    return {
        "effet_mois": effet_mois,
        "effet_ramadan": plafonner(np.exp(modele.params.get("frac_ramadan", 0.0))),
        "effet_eid_fitr": plafonner(np.exp(modele.params.get("is_eid_fitr", 0.0))),
        "effet_eid_adha": plafonner(np.exp(modele.params.get("is_eid_adha", 0.0))),
        "modele": modele,
    }


def generer_serie_synthetique(df_brut, banque, code_moyen, variable, etat,
                               n_mois_a_generer, seed=42):
    np.random.seed(seed)

    marche = df_brut[df_brut["Moyen_de_Paiement"] == code_moyen].copy()
    boa = marche[marche["Banque"].str.upper() == banque.upper()].sort_values("Periode").copy()
    if boa.empty:
        return None, "Aucune donnée disponible pour cette combinaison de banque et moyen de paiement."

    sous_boa = boa[boa["Etat"] == etat].copy()
    nb_mois_reels = len(sous_boa)

    if nb_mois_reels < 4:
        return None, "Volume d'historique réel insuffisant pour estimer une tendance linéaire (minimum 4 mois)."

    # --- Préparation des données réelles ---
    cal_reel = construire_variables_calendaires(sous_boa["Periode"].unique())
    df_reel = sous_boa.set_index("Periode")[[variable]].rename(columns={variable: "Valeur"})
    df_reel = df_reel.join(cal_reel)
    df_reel["Type_Donnee"] = "Reel"

    # =========================================================================
    # CONDITION : Si la série a 24 mois ou plus, on garde STRICTEMENT le réel
    # =========================================================================
    if nb_mois_reels >= 24:
        # Pas de génération synthétique requise, la série réelle est assez longue
        return df_reel.sort_index(), None

    # =========================================================================
    # Sinon (< 24 mois) : Génération de la série synthétique
    # =========================================================================
    sous_boa["t"] = (sous_boa["Periode"].dt.to_period("M")
                      - sous_boa["Periode"].dt.to_period("M").min()).apply(lambda x: x.n)
    pente, intercept = np.polyfit(sous_boa["t"], sous_boa[variable], 1)
    ecart_type = (sous_boa[variable] - (pente * sous_boa["t"] + intercept)).std()
    if ecart_type == 0 or np.isnan(ecart_type):
        ecart_type = max(abs(pente), 1.0) * 0.05

    marche_mensuel = marche.groupby(["Periode", "Etat"])[["Nombre", "Montant"]].sum().reset_index()
    cal = construire_variables_calendaires(marche_mensuel["Periode"].unique())
    marche_mensuel = marche_mensuel.merge(cal, on="Periode", how="left")
    marche_mensuel["t"] = (marche_mensuel["Periode"].dt.to_period("M")
                            - marche_mensuel["Periode"].dt.to_period("M").min()).apply(lambda x: x.n)
    marche_mensuel["mois"] = marche_mensuel["Periode"].dt.month

    effets = estimer_effets_marche(marche_mensuel, variable, etat)
    if effets is None:
        return None, "Impossibilité d'estimer la saisonnalité sectorielle de marché."

    derniere_periode = sous_boa["Periode"].max()
    nouvelles_periodes = pd.date_range(derniere_periode + pd.DateOffset(months=1),
                                        periods=n_mois_a_generer, freq="MS")
    cal_futur = construire_variables_calendaires(nouvelles_periodes)
    t_depart = sous_boa["t"].max() + 1

    lignes_sim = []
    for i, periode in enumerate(nouvelles_periodes):
        t = t_depart + i
        mois = periode.month
        fr, fitr, adha = cal_futur.loc[periode]
        effet_mois = effets["effet_mois"][mois]
        effet_lunaire = (effets["effet_ramadan"] ** fr
                          * effets["effet_eid_fitr"] ** fitr
                          * effets["effet_eid_adha"] ** adha)
        tendance = pente * t + intercept
        bruit = np.random.normal(0, ecart_type)
        valeur = max(tendance * effet_mois * effet_lunaire + bruit, 1.0)
        lignes_sim.append({"Periode": periode, "Valeur": valeur, "Type_Donnee": "Simule",
                            "frac_ramadan": fr, "is_eid_fitr": fitr, "is_eid_adha": adha})

    df_sim = pd.DataFrame(lignes_sim).set_index("Periode")

    # Fusion Réel + Synthétique
    serie = pd.concat([df_reel, df_sim]).sort_index()
    return serie, None
    

def rechercher_meilleur_sarima(serie, n_test_min=3, progress_callback=None):
    x = serie[["Valeur"]].copy()
    x["Valeur"] = x["Valeur"].clip(lower=1.0)
    y = np.log(x)
    exog = serie[["frac_ramadan", "is_eid_fitr", "is_eid_adha"]]

    n_test = max(n_test_min, int(len(x) * 0.15))
    y_train, y_test = y.iloc[:-n_test], y.iloc[-n_test:]
    x_test = x.iloc[-n_test:]
    exog_train, exog_test = exog.iloc[:-n_test], exog.iloc[-n_test:]

    grille = list(itertools.product(range(3), range(2), range(3),
                                    range(2), range(2), range(2)))
    candidats = []
    for i, (p_, d_, q_, P_, D_, Q_) in enumerate(grille):
        if progress_callback:
            progress_callback((i + 1) / len(grille))
        try:
            m = SARIMAX(y_train.values, order=(p_, d_, q_), seasonal_order=(P_, D_, Q_, 12),
                        exog=exog_train.values, enforce_stationarity=True, enforce_invertibility=True)
            r = m.fit(disp=False, maxiter=300, method="lbfgs")
            if not r.mle_retvals.get("converged", False):
                continue
        except Exception:
            continue

        y_pred_c = r.get_forecast(len(y_test), exog=exog_test.values)
        x_pred_c = np.asarray(np.exp(y_pred_c.predicted_mean)).flatten()
        if not np.all(np.isfinite(x_pred_c)) or x_pred_c.max() > 20 * x["Valeur"].max():
            continue

        smape_c = (200 * np.abs(x_pred_c - x_test["Valeur"].values)
                   / (np.abs(x_pred_c) + np.abs(x_test["Valeur"].values))).mean()
        mape_c = (np.abs(1 - x_pred_c / x_test["Valeur"].values)).mean() * 100
        candidats.append({
            "ordre": f"({p_},{d_},{q_})({P_},{D_},{Q_})12", "AIC": round(r.aic, 2),
            "sMAPE_%": round(smape_c, 2), "MAPE_%": round(mape_c, 2),
            "model": r, "order_tuple": (p_, d_, q_), "seasonal_tuple": (P_, D_, Q_, 12),
        })

    if not candidats:
        return None, None, "Aucun modèle candidate n'a convergé avec stabilité."

    candidats_tries = sorted(candidats, key=lambda c: c["sMAPE_%"])
    return candidats_tries, (x, y, exog, x_test, y_test, exog_test, n_test), None