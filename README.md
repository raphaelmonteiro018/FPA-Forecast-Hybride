## 🏢 Contexte
Ce projet a pour but de fournir une vision fiable et robuste de la trajectoire commerciale d'un réseau de 45 magasins. Il permet également de transformer un historique de ventes brutes en un outil de pilotage de la performance, notamment concernant la gestion des stocks et donc du BFR.

## 🎯 Objectifs
- Anticiper la trajectoire des ventes : Projeter les revenus du réseau sur un horizon de 8 semaines afin de s'adapter aux variations de l'activité.
- Superviser la performance : Fournir un outil d'arbitrage permettant de trouver le juste équilibre entre la sécurité des stocks (éviter les ruptures) et l'optimisation de la trésorerie (éviter le surplus).
- Fiabiliser les chiffres et auditer le traitement de la donnée : Proposer un code auditable et une méthodologie documentée, permettant de justifier les chiffres affichés.
- Optimiser le reporting : Automatiser la consolidation des données et la création d'un Excel directement exploitable sous Power BI.

## 🚀 Résultats
- Fiabilité des projections : 94% de précision en scénario "baseline" et 87% de précision en scénario "extreme" (scores incluant un buffer conservateur de x1.5 sur les bornes de confiance).
- Réduction du cash immobilisé : Le BFR est désormais optimisé car chaque point de précision gagné équivaut à 377K $ débloqués pour le réseau. Le passage d'une méthode naive (qui consiste à faire y-52) à ma méthode d'arbitrage permet de gagner 4,32 points de précision soit environ 1,630M $ de cash immédiatement disponible par semaine.
- Validation des modèles : Entrainement et test du benchmark sur un historique de 26 semaines (~6 mois) avant toute tentative de projection (split train/test out of sample).
- Aide à la décision : Réduction de l'incertitude globale grâce à un arbitrage entre plusieurs modèles permettant de ne garder que le plus performant et à l'application d'un intervalle de confiance dynamique.
- Gain de productivité : Automatisation complète du reporting (du calcul Python à la visualisation sous Power BI), garantissant une mise à jour rapide.

## 🔁 Workflow
1. Récupération du dataset Walmart (donnée open-source sur le site Kaggle) et préparation du fichier source.
2. Déploiement d'un moteur d'analyse sous Python : 3 approches de modélisation sont mises en compétition sur les séries temporelles de chaque magasin.
3. Génération automatisée d'un fichier structuré, éliminant les processus manuels et les risques d'erreurs de saisie.
4. Import des données sous Power BI et visualisation dynamique des résultats.

## 🏗️ Outils utilisés
- Power BI : DAX
- Excel
- Python : librairies Pandas, NumPy, Statsmodels, XGBoost (algorithme de machine learning)

## 📁 Contenu du projet
- Etape 1 : Méthodologie & Revue des modèles.
- Etape 2 : Présentation & Mise à jour de l'outil.

## Navigation
Pour naviguer entre les différentes étapes du processus veuillez sélectionner les sous-branches nommées dans l'ordre d'exécution.
<img width="1852" height="542" alt="image" src="https://github.com/user-attachments/assets/33f30c23-07e8-4ded-9889-c6039f5d3725" />
