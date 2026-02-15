# 📈 Méthodologie & Performance des modèles
Cette section détaille le cœur analytique du projet, c'est-à-dire comment l'architecture construite à partir de Python transforme un historique brut en une projection fiable.

## 🎯 Objectifs
- Evaluer dynamiquement chaque point de vente à travers un benchmark de modèles statistiques.
- Mesurer la précision des modèles via l'indicateur WAPE (Weighted Absolute Percentage Error) et conserver le modèle le plus performant par magasin.
- Justifier les choix de modélisation à l'aide d'une méthode documentée et reproductible.

## 🔍 Récupération du dataset & Analyse visuelle de la série temporelle
- Récupération du dataset Walmart disponible librement sur Kaggle.
- Données des colonnes : Store (numéro du magasin), ds (date), y (ventes hebdomadaires du magasin), Holiday_Flag (binaire).

#### Analyse simple de la série temporelle : Consolidation des données historiques et visualisation de la distribution des ventes ci-dessous.
<img width="1238" height="378" alt="image" src="https://github.com/user-attachments/assets/111a0656-9045-4e80-9afa-49805a164c24" />

#### Analyse : D'après la période étudiée (données de début 2010 à fin 2011), l'activité des 45 magasins Walmart est extremement saisonnière, notre distribution prend une forme bimodale (deux modes d'activité), ce qui justifie une approche poussée via Python.

#### Conséquence : L'intensité de l'activité est représentée par deux régimes distincts (baseline / pics) pour lesquels les intervalles de confiance doivent être adaptés dynamiquement pour refléter la différence de tailles des erreurs (hétéroscédasticité) entre les deux régimes.
- La vérification de la taille des erreurs (hétéroscédasticité), représentée ici par le WAPE (Weighted Absolute Percentage Error) permet de prouver que plus le montant des ventes augmente, plus l'écart entre la prévision et la donnée réelle tend à etre élevée.
- Exemple : En scénario stable les déviations à la moyenne (écart-type, unité qui mesure l'intensité de la dispersion des données autour de leur moyenne) vont etre beaucoup plus faibles que sur les scénarios de pics d'activité. Plus simplement, la série a tendance à rompre sa moyenne momentanément, ces moments doivent faire l'objet d'une attention particulière.

## 📊 Statistiques Descriptives

### 1. Comparaison des régimes d'activité
> **💡 Diagnostic :**
> - La segmentation de l'activité a été réalisée par le choix du 90ème Percentile des ventes hebdomadaires consolidées.
> - Le point de bascule du régime "baseline" au régime "pics" a été statisquement quantifié à 49.88 M$ (voir tableau ci-dessous). Dans 90% du temps, le montant total des ventes est situé sous ce seuil.
> - Ce choix permet d'isoler mathématiquement la "Queue de distribution" (Tail Risk), c'est-à-dire les 10% d'événements "extremes".

| Métrique | REGIME 1 (Baseline) | REGIME 2 (Pics) |
| :--- | :--- | :--- |
| **Nb. Semaines** | 128 (90%) | 15 (10%) |
| **CA Moyen (μ)** | **45,767,633 $** | **58,597,458 $** |
| **Écart-type (σ)** | 2,132,545 $ | **10,075,269 $** |
| **Volatilité (CV)** | **4.66 %** | **17.19 %** |
| **Amplitude CA** | [39.6M$ - 49.7M$] | [49.9M$ - 80.9M$] |

> **💡 Diagnostic :**
> - L'écart-type est multiplié par **4.7** lors du passage de l'activité "normale" aux pics. Cette explosion de la volatilité des ventes prouve l'**hétéroscédasticité** de la série (l'erreur de prévision n'est pas constante).
> - Cette approche est supérieure à une moyenne qui aurait simplement surestimé la volatilité des ventes futures dans un scénario de baseline et sous-estimé celle des pics d'activité.

---

### 2. Analyse de l'incertitude

| Indicateur | Valeur | Impact Stratégique |
| :--- | :--- | :--- |
| **Ratio d'incertitude** | **4.72x** | Le risque de rupture est 4.7 fois plus élevé lors des pics d'activité saisonniers |
| **Incertitude Baseline** | **3.88 %** | Précision de 96.12% dans 90% de l'année (optimisation du BFR). |
| **Incertitude Pics** | **18.31 %** | Marge de sécurité nécessaire pour couvrir la volatilité des pics et assurer les ventes sans passer par la rupture de stocks. |
| **Valeur du point de WAPE** | **~471 k$** | Pour chaque point d'incertitude réduit, le BFR peut-etre optisé en réduisant les dépenses liées aux stocks|

> **💡 Diagnostic :** En isolant le régime "pics" le chiffre d'affaires est sécurisé. On accepte une incertitude de 18.31% sur les 10% des semaines avec les plus fortes ventes pour garantir un taux de service maximal, tout en maintenant une gestion tendue le reste de l'année (incertitude de 3.88% pour la baseline).


## 🛠️ Conception & Explication du Benchmark
- Le script "ScriptWalmart.py" présent en pièce-jointe fait concourir **3 approches** sur une période de validation étendue, puis sélectionne dynamiquement la plus performante pour chaque magasin.
- Le modèle est évalué et entrainé sur un horizon de 26 points de données hebdomadaires consolidées **soit 26 semaines (~6 mois)**.

---

### 1. Benchmark Naïf
* **Logique** : Projection des ventes de l'année précédente ($y = y_{t-52}$). On reprend tout simplement la valeur de l'année précédente à la meme période.
* **Rôle** : Sert de garde-fou. Si un modèle complexe ne bat pas le Naïf, il est rejeté, la complexité d'un modèle doit etre justifiée par un gain de performance notable.
*  **Inconvénient** : Ce modèle capture parfaitement la saisonnalité pure mais ignore les tendances et relations complexes.

### 2. Holt-Winters (Triple Lissage Exponentiel)
* **Logique** : Modèle statistique classique décomposant la série via 3 approches (Niveau + Tendance + Saisonnalité).
* **Fonctionnement** : Le Niveau représente la valeur de base lissée (EMA : exponential moving average), la Tendance capture la direction des fluctuations et la Saisonnalité isole les cycles répétitifs.
* **Force** : Très efficace sur les magasins ayant des cycles saisonniers très réguliers et peu de bruit aléatoire.

### 3. XGBoost (Machine Learning)
* **Logique** : Algorithme de Machine Learning utilisant des régresseurs spécifiés (exemples : Lags tels que $y-52$, Moyennes Mobiles/EMA, Flag des jours fériés et pics saisonniers).
* **Méthode Itérative** : Le modèle prédit $y+1$, intègre cette valeur dans son historique, recalcule les régresseurs (comme les moyennes mobiles), puis prédit $y+2$. Cette boucle se répète jusqu'à l'horizon $y+N$.
* **Force** : Capacité unique à capturer les ruptures de régime (ex: pics brutaux de Thanksgiving et Noël) et les relations non-linéaires complexes entre les données.
* **Inconvénient** : Le fonctionnement se rapproche d'une "black-box" par rapport aux méthodes traditionnelles (Holt-Winters), limitant l'auditabilité totale du calcul interne, bien que le choix des variables d'entrée reste totalement transparent.

---

## 🛡️ Sécurisation des Prévisions
Plutôt que d'appliquer des bornes fixes, le modèle adapte ses intervalles de confiance en fonction du régime d'activité identifié lors de l'audit statistique.

| Régime Détecté | Logique d'Incertitude | WAPE Cible | Stratégie de Stock |
| :--- | :--- | :--- | :--- |
| **Baseline** | Activité standard (< 49.88 M$) | **3.88 %** | **Flux tendus** : Réduction maximale de l'immobilisation financière. |
| **Extreme Peaks** | Pics saisonniers (> 49.88 M$) | **18.31 %** | **Marge de sécurité** : Élargissement du tunnel pour couvrir la volatilité (Risk-Off). |

> **💡 Note :** Le passage du WAPE de 3.88% à 18.31% n'est pas une perte de performance, mais une **calibration sur le risque réel**. En multipliant les bornes de confiance par **4.72** lors des pics, le modèle garantit un taux de service optimal là où un modèle standard et l'utilisation d'une moyenne provoquerait des ruptures massives.

---

## 📊 Performance des modèles
L'intérêt majeur de ma méthode réside dans la **mise en compétition systématique** des modèles. Au lieu d'appliquer une méthode unique à l'ensemble du réseau, l'algorithme sélectionne dynamiquement le modèle le plus performant pour chaque point de vente. Créer 3 approches et ajouter de la complexité a pour unique vocation de servir l'opérationnel de la manière la plus fiable possible, et non démontrer une performance purement technique.

| Méthode de prévision | Score WAPE (Erreur pondérée) |
| :--- | :--- |
| **Benchmark Naïf** (Référence $y-52$) | 8,20 % |
| **Benchmark Holt-Winters** (Statistique) | 4,39 % |
| **Benchmark XGBoost** (Machine Learning) | 5,12 % |
| **Sélection Automatique (Best Model per Store)** | **3,88 %** |

> [!IMPORTANT]
> **Lecture du résultat** : En ne retenant que le meilleur modèle par magasin (celui ayant la plus faible erreur historique), nous atteignons une précision réseau de **96,12 %** (soit un WAPE de 3,88 %).
> → **Gain de précision de ~53 %** par rapport à la méthode naïve, divisant ainsi l'incertitude par deux, la complexité des approches est donc mathématiquement justifiée.

---

## 🔍 Éléments pris en compte dans les modèles
Pour surpasser le modèle Naïf, les modèles Holt-Winters et XGBoost intègrent des variables clés :
* **Calendrier commercial** : Impact des jours fériés US et du **Black Friday** (Variable binaire "Holiday").
* **Indicateurs de tendance** : Ventes décalées (**Lags** de 1, 4 et 52 semaines) pour capter la dynamique récente et annuelle.
* **Lissage de données** : Moyennes mobiles sur 4 semaines pour filtrer le bruit court terme.
* **Saisonnalité** : Codage du numéro de semaine pour anticiper les récurrences annuelles.

---

## ✅ Points forts de la méthodologie
* **Arbitrage de précision** : Choix du modèle (Naïf, HW ou XGB) optimisé magasin par magasin selon les spécificités locales.
* **Approche Business-Oriented** : Utilisation du **WAPE** pour pondérer l'erreur par le chiffre d'affaires ; une erreur sur un magasin "Top Performer" est plus pénalisante qu'une erreur sur un petit point de vente.
* **Auditabilité totale** : Contrairement aux solutions "boîte noire", le fichier Excel généré permet de justifier chaque prévision, avec le détail des scores et les bandes d'incertitude (quantiles).
* **Efficience opérationnelle** : Le moteur Python remplace des heures de retraitement manuel par un calcul automatisé, robuste et répétable.

---
## 📁 Contenu de cette branche
* `ScriptWalmart.py` : Moteur d'analyse complet (Traitement, Benchmark, Forecast).
* `Walmart_Source_PowerBI.xlsx` : Fichier source utilisé pour Power BI (j'ai volontairement scindé l'Excel généré par le script, du fichier source alimentant mon rapport afin d'en faciliter la mise à jour).
* `Walmart Dashboard.pbix` : Répertoire de sortie contenant les données structurées pour la visualisation (Historiques, Audit des erreurs, Synthèse consolidée).

## ➡️ Prochaine étape
L'étape 2 permet de découvrir l'outil de pilotage sous **Power BI**.

