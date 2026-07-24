import numpy as np


def interpreter_comparaison(dates_futures, emis_prev, recus_prev, variable_nom="Montant"):
    """
    Analyse financière approfondie et institutionnelle de la trajectoire prévisionnelle
    Flux Émis vs Flux Reçus.
    """
    emis_arr = np.asarray(emis_prev)
    recus_arr = np.asarray(recus_prev)
    diff = emis_arr - recus_arr
    solde_moyen = np.mean(diff)
    solde_cumule = np.sum(diff)
    
    vol_emis_total = np.sum(emis_arr)
    vol_recus_total = np.sum(recus_arr)
    ratio_couverture = (vol_recus_total / vol_emis_total * 100) if vol_emis_total > 0 else 0
    
    dominant_initial = "Flux Émis" if diff[0] > 0 else "Flux Reçus"
    dominant_final = "Flux Émis" if diff[-1] > 0 else "Flux Reçus"
    
    croisements = []
    signe_courant = np.sign(diff[0])
    for i in range(1, len(diff)):
        signe = np.sign(diff[i])
        if signe != 0 and signe != signe_courant:
            nouveau_dominant = "Flux Émis" if signe > 0 else "Flux Reçus"
            croisements.append((dates_futures[i], nouveau_dominant, abs(diff[i])))
            signe_courant = signe

    unit_str = "MAD" if variable_nom.lower() == "montant" else "unités"
    
    si = f"### Synthèse Executive du Solde Prévisionnel ({variable_nom})\n\n"
    if solde_moyen > 0:
        si += f"- **Position Nette Structurelle** : Profil **débitrice/émetteur net**, affichant un exode moyen des flux Émis de **{solde_moyen:,.0f} {unit_str}/mois** (Solde net cumulé projeté : **+{solde_cumule:,.0f} {unit_str}**).\n"
    else:
        si += f"- **Position Nette Structurelle** : Profil **créditrice/récepteur net**, affichant un surplus moyen des flux Reçus de **{abs(solde_moyen):,.0f} {unit_str}/mois** (Solde net cumulé projeté : **{solde_cumule:,.0f} {unit_str}**).\n"
    
    si += f"- **Ratio de Couverture (Reçus / Émis)** : **{ratio_couverture:.1f}%** sur l'horizon de projection.\n\n"

    si += "### Dynanique Temporelle & Points de Croisement\n\n"
    if not croisements:
        si += f"- **Maintien de Tendance** : Aucune inversion de polarité n'est anticipée. Les **{dominant_initial}** maintiennent une prédominance continue du début à la fin de la période.\n"
    else:
        si += f"- **Inflexion Décelée** : Transition observée depuis une dominance initiale des **{dominant_initial}** vers une prédominance finale des **{dominant_final}**.\n"
        si += f"- **Inflexions Clés ({len(croisements)})** :\n"
        for dt, nov, am in croisements:
            si += f"  * **{dt.strftime('%B %Y')}** : Pivotage en faveur des **{nov}** (Écart estimé : {am:,.0f} {unit_str}).\n"
    
    si += "\n### Orientations de Gestion de Trésorerie\n\n"
    if abs(solde_moyen) / (vol_emis_total / len(emis_arr)) < 0.1:
        si += "- **Équilibre Flux Quasi-Parfait** : Alignement étroit entre flux entrants et sortants, limitant l'exposition aux impasses nettes de liquidités.\n"
    elif solde_moyen > 0:
        si += "- **Couverture des Sorties de Caisse** : La prédominance continue des émissions exige un calibrage préventif des réserves de liquidité compensatoires.\n"
    else:
        si += "- **Optimisation des Excédents Entrants** : La prédominance des encaissements offre des opportunités d'arbitrage et de placement à court terme.\n"

    return si, croisements