import pandas as pd

RAMADAN_EID = {
    2025: dict(ramadan_debut="2025-03-01", ramadan_fin="2025-03-30",
               eid_fitr="2025-03-30", eid_adha="2025-06-06"),
    2026: dict(ramadan_debut="2026-02-18", ramadan_fin="2026-03-19",
               eid_fitr="2026-03-20", eid_adha="2026-05-27"),
    2027: dict(ramadan_debut="2027-02-08", ramadan_fin="2027-03-09",
               eid_fitr="2027-03-10", eid_adha="2027-05-19"),
    2028: dict(ramadan_debut="2028-01-27", ramadan_fin="2028-02-26",
               eid_fitr="2028-02-27", eid_adha="2028-05-07"),
    2029: dict(ramadan_debut="2029-01-16", ramadan_fin="2029-02-14",
               eid_fitr="2029-02-15", eid_adha="2029-04-26"),
    2030: dict(ramadan_debut="2030-01-05", ramadan_fin="2030-02-03",
               eid_fitr="2030-02-04", eid_adha="2030-04-15"),
}


def variables_calendaires(date_debut_mois, jours_avant=3, jours_apres=3):
    mois_debut = date_debut_mois
    mois_fin = mois_debut + pd.offsets.MonthEnd(0)
    jours_mois = (mois_fin - mois_debut).days + 1
    largeur = jours_avant + jours_apres + 1
    jours_ramadan, jours_fitr, jours_adha = 0, 0, 0
    for info in RAMADAN_EID.values():
        r_debut, r_fin = pd.Timestamp(info["ramadan_debut"]), pd.Timestamp(info["ramadan_fin"])
        ov_debut, ov_fin = max(mois_debut, r_debut), min(mois_fin, r_fin)
        if ov_debut <= ov_fin:
            jours_ramadan += (ov_fin - ov_debut).days + 1
        for cle, acc in [("eid_fitr", "fitr"), ("eid_adha", "adha")]:
            eid_date = pd.Timestamp(info[cle])
            fen_debut = eid_date - pd.Timedelta(days=jours_avant)
            fen_fin = eid_date + pd.Timedelta(days=jours_apres)
            ov_debut, ov_fin = max(mois_debut, fen_debut), min(mois_fin, fen_fin)
            if ov_debut <= ov_fin:
                jours = (ov_fin - ov_debut).days + 1
                if acc == "fitr":
                    jours_fitr += jours
                else:
                    jours_adha += jours
    frac_ramadan = min(jours_ramadan / jours_mois, 1.0)
    is_eid_fitr = min(jours_fitr / largeur, 1.0)
    is_eid_adha = min(jours_adha / largeur, 1.0)
    return frac_ramadan, is_eid_fitr, is_eid_adha


def construire_variables_calendaires(periodes):
    lignes = []
    for p in periodes:
        fr, fitr, adha = variables_calendaires(p)
        lignes.append({"Periode": p, "frac_ramadan": fr,
                        "is_eid_fitr": fitr, "is_eid_adha": adha})
    return pd.DataFrame(lignes).set_index("Periode")