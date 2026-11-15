# LaterBoxd

Système de recommandation personnalisé de films basé sur vos notes Letterboxd, utilisant le filtrage collaboratif par décomposition en valeurs singulières (SVD) et une régression Ridge pour projeter les goûts de l'utilisateur dans l'espace latent des films.

## Fonctionnalités

- **Filtrage collaboratif SVD** entraîné sur un large ensemble de données de notation de films (`scikit-surprise`).
- **Personnalisation Ridge** : projection rapide de vos notes Letterboxd sans devoir ré-entraîner tout le modèle SVD.
- **Normalisation des titres** : gestion des titres multilingues, alias et suppressions des accents/caractères spéciaux.
- **Export automatique** : génération d'un rapport `recommandations.txt` listant le Top 100 des films recommandés avec notes estimées.

## Structure du Projet

```text
LaterBoxd/
├── data/
│   ├── ratings.csv          # Export de vos notes Letterboxd
│   └── train.parquet        # Dataset complet d'entraînement (ignoré par Git)
├── models/
│   └── svd_model.pkl        # Modèle SVD sérialisé (ignoré par Git)
├── src/
│   ├── nettoyage.py         # Chargement et filtrage des données avec Polars
│   ├── train.py             # Entraînement et sauvegarde du modèle SVD
│   └── reccomender.py       # Génération des recommandations personnalisées
├── recommandations.txt      # Résultats des recommandations
├── requirements.txt         # Dépendances Python
└── README.md
```

## Installation

1. Clonez le dépôt :
   ```bash
   git clone https://github.com/444Atlas/LaterBoxd.git
   cd LaterBoxd
   ```

2. Créez et activez un environnement virtuel (Python 3.12 recommandé) :
   ```bash
   conda create -n laterboxd python=3.12 -y
   conda activate laterboxd
   ```

3. Installez les dépendances :
   ```bash
   pip install -r requirements.txt
   ```

## Utilisation

1. **Données d'entraînement & Modèle** :
   - Placez votre fichier d'entraînement `train.parquet` dans le dossier `data/`.
   - Entraînez le modèle (si `svd_model.pkl` n'est pas déjà présent) :
     ```bash
     python src/train.py
     ```

2. **Générer des recommandations** :
   - Exportez vos données depuis Letterboxd et placez votre fichier `ratings.csv` dans le dossier `data/`.
   - Lancez le script de recommandation :
     ```bash
     python src/reccomender.py
     ```
   - Consultez vos recommandations dans `recommandations.txt` !
