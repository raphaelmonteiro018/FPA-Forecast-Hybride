<img width="898" height="683" alt="image" src="https://github.com/user-attachments/assets/e2483f34-5cc6-4989-832b-ad735cc77e80" />

# 🖥️ Présentation & Mise à jour de l'outil

Cette section présente l'outil de pilotage sous Power BI, détaille la procédure de mise à jour du rapport et documente les limites connues de l'architecture actuelle.

---

## 📊 Lecture du dashboard

Le dashboard est organisé autour de **3 niveaux de lecture** :

**Vue synthétique (KPIs en-tête)**
- **CA cumulé à S+8** : Somme du réalisé sur la période sélectionnée et des ventes projetées sur les 8 semaines suivantes.
- **Ventes réalisées sur la période** : CA historique consolidé sur le filtre appliqué.
- **Ventes prévues à S+8** : Projection forward issue du moteur d'arbitrage Python.

**Vue opérationnelle (graphiques)**
- **Évolution des ventes hebdomadaires** : Historique consolidé du réseau avec la zone de prévision en surbrillance. Les bandes jaunes représentent les intervalles de confiance dynamiques — élargis automatiquement lors des semaines de pics calendaires (régime 2).
- **Écarts N-1 par mois** : Comparaison des ventes réalisées vs la même période l'année précédente. Permet d'identifier rapidement les dérives de tendance.
- **Modèles retenus par magasin** : Répartition des modèles champions (Naïf, Holt-Winters, XGBoost) sur l'ensemble du réseau — indicateur de la diversité des comportements locaux capturés par l'arbitrage.

**Filtres disponibles**
- Magasin (vue individuelle ou consolidée réseau)
- Année d'exercice
- Mois d'exercice

---

## 🔄 Procédure de mise à jour

La mise à jour du rapport suit un processus en 3 étapes, conçu pour être exécutable par tout utilisateur sans compétence technique :

**1. Mise à jour du fichier source**
- Ajouter les nouvelles données de ventes dans le fichier `walmart.xlsm` (onglet "Import retravaillé").

**2. Exécution du moteur Python**
- Lancer `ScriptWalmart.py` — le script s'exécute en quelques minutes et génère automatiquement un fichier Excel structuré dans le dossier `PowerBI_Ready/`.
- Renommer ce fichier en `Walmart_Source_PowerBI.xlsx`.

**3. Actualisation Power BI**
- Ouvrir `Walmart Dashboard.pbix` et cliquer sur **Actualiser** — le rapport se met à jour automatiquement depuis le fichier source.

> **💡 Note :** La scission volontaire entre le fichier généré par le script et le fichier source Power BI garantit qu'une nouvelle exécution du script n'écrase jamais le rapport en production. Seul un renommage explicite déclenche la mise à jour.

---

## ⚠️ Limites connues & Pistes d'amélioration

L'architecture actuelle repose sur deux choix de modélisation qui constituent des simplifications assumées. Elles sont documentées ici dans un souci de transparence et d'auditabilité.

---

### Limite 1 — Détection du régime "pics" par flag calendaire fixe

**Ce qui est implémenté :**
La fonction `get_weekly_flags` déclenche le régime "pics" uniquement sur des semaines calendaires prédéfinies :
```python
is_peak = 1 if (month == 11 and week_num in [47, 48]) or 
               (month == 12 and week_num in [51, 52]) else 0
```

Le coefficient d'élargissement `sqrt(hetero_ratio)` s'applique donc de manière **binaire et identique** sur ces 4 semaines pour tous les magasins, indépendamment du niveau de ventes réel du magasin concerné.

**Conséquence observable :**
- Un magasin au comportement erratique (ex : magasin 38, oscillations permanentes en dents de scie) reçoit le même élargissement de bornes en novembre qu'un magasin fortement saisonnier — alors que son risque réel n'est pas plus élevé en fin d'année qu'en milieu d'année.
- À l'inverse, un magasin dont les pics d'activité seraient concentrés sur une autre période (fête locale, événement saisonnier spécifique) ne bénéficierait d'aucun élargissement adapté.

**Piste d'amélioration :**
Calculer un **P90 individuel par magasin** sur sa propre distribution de ventes, et détecter dynamiquement le régime en comparant chaque semaine à ce seuil local :
```python
# Exemple d'implémentation
p90_by_store = df.groupby('Store')['y'].quantile(0.90)

def is_peak_local(store_id, value):
    return 1 if value > p90_by_store[store_id] else 0
```

Cette évolution transformerait la détection de régime en véritable approche **bottom-up**, alignée avec la philosophie d'arbitrage par magasin du reste du moteur.

---

### Limite 2 — Amplitude des bornes : architecture hybride

**Ce qui est implémenté :**
L'architecture actuelle est hybride :
- **Amplitude des bornes → bottom-up** : calculée à partir du WAPE individuel de chaque magasin. Un magasin régulier (WAPE faible) aura des bornes serrées, un magasin volatile (WAPE élevé) aura des bornes larges.
- **Timing de l'élargissement → top-down** : déclenché par le flag calendaire global, identique pour tous les magasins.

**Conséquence observable :**
Le magasin 32 illustre bien cette logique — ses bornes restent très serrées même en novembre car son WAPE est structurellement bas, malgré le déclenchement du coefficient `sqrt(hetero_ratio)`. À l'inverse, le magasin 38 présente des bornes très larges en fin d'année non pas à cause d'une saisonnalité réelle, mais parce que son WAPE élevé (lié à ses oscillations permanentes) est amplifié par le coefficient calendaire.

**Piste d'amélioration :**
Combiner les deux améliorations : P90 local pour le timing + WAPE local pour l'amplitude. Le `hetero_ratio` serait alors recalculé **par magasin** entre son régime baseline local et son régime pics local :
```python
# Exemple d'implémentation
def calc_local_hetero_ratio(store_df, p90_threshold):
    baseline = store_df[store_df['y'] <= p90_threshold]['y']
    peaks = store_df[store_df['y'] > p90_threshold]['y']
    if len(peaks) < 3:  # Pas assez de données pour calculer un ratio fiable
        return global_hetero_ratio  # Fallback sur le ratio global
    return peaks.std() / baseline.std()
```

---

## 📁 Contenu de cette branche
* `Walmart Dashboard.pbix` : Rapport Power BI prêt à l'emploi.
* `Walmart_Source_PowerBI.xlsx` : Fichier source structuré alimentant le rapport (données historiques, prévisions, audit des modèles, synthèse).

---

## ✅ Pour aller plus loin
La structure du moteur est conçue pour être dupliquée sur tout réseau de points de vente disposant d'un historique hebdomadaire. L'intégration de variables externes (météo, inflation, politiques commerciales) est possible sans refondre le moteur — il suffit d'ajouter les régresseurs dans le feature engineering de `ScriptWalmart.py`.

Les deux pistes d'amélioration documentées ci-dessus constituent une évolution naturelle vers un modèle **100% bottom-up**, où chaque magasin disposerait de son propre régime de détection et de son propre ratio d'hétéroscédasticité.
