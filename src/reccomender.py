import os
import re
import unicodedata
import pandas as pd
import polars as pl
import numpy as np
from surprise import dump
from sklearn.linear_model import Ridge

MODEL_PATH = "models/svd_model.pkl"
DATA_PATH = "data/train.parquet" # Assure-toi que cela pointe vers ta BDD complète, pas le sample de 10k lignes
USER_CSV_PATH = "data/ratings.csv"
OUTPUT_TXT_PATH = "recommandations.txt"

ALIAS_TITRES = {
    "city-of-god": ["cidade-de-deus", "la-cité-de-dieu"],
    "black-box": ["black-box-2020"],
    "challenger": ["challengers"]
}

def clean_title(title):
    if pd.isna(title):
        return ""
    title_str = str(title).lower()
    
    # Suppression absolue des accents (é -> e, à -> a, etc.)
    title_str = unicodedata.normalize('NFKD', title_str).encode('ASCII', 'ignore').decode('utf-8')
    
    title_str = title_str.replace('-', ' ')
    title_str = re.sub(r'[^\w\s]', '', title_str)
    title_str = re.sub(r'\s+', ' ', title_str).strip()
    title_str = title_str.replace(' ', '-')
    
    return title_str

def recommander():
    if not os.path.exists(MODEL_PATH) or not os.path.exists(DATA_PATH):
        raise FileNotFoundError("Modèle ou Dataset introuvable.")
    if not os.path.exists(USER_CSV_PATH):
        raise FileNotFoundError(f"Place ton CSV dans : {USER_CSV_PATH}")

    print("1. Chargement du modèle SVD...")
    _, algo = dump.load(MODEL_PATH)
    trainset = algo.trainset
    mu = trainset.global_mean

    print("2. Cartographie de la base de données...")
    movies_df = pl.scan_parquet(DATA_PATH).select(["movie_id", "title"]).unique().collect().to_pandas()
    
    movies_df['title_clean'] = movies_df['title'].apply(clean_title)
    
    title_to_id = dict(zip(movies_df['title_clean'], movies_df['movie_id']))
    id_to_title = dict(zip(movies_df['movie_id'], movies_df['title']))

    print("3. Analyse de tes films...")
    user_df = pd.read_csv(USER_CSV_PATH)
    user_df['title_clean'] = user_df['Name'].apply(clean_title)
    
    titres_vus_etendus = set()
    for _, row in user_df.iterrows():
        t = row['title_clean']
        y = str(row['Year'])
        
        titres_vus_etendus.add(t)
        titres_vus_etendus.add(f"{t}-{y}")
        
        if t in ALIAS_TITRES:
            for alias in ALIAS_TITRES[t]:
                titres_vus_etendus.add(alias)
                titres_vus_etendus.add(f"{alias}-{y}")
                
    user_watched_titles_clean = titres_vus_etendus
    
    watched_inner_ids = set()
    watched_movie_ids = []
    user_ratings = []

    for _, row in user_df.iterrows():
        title_clean = row['title_clean']
        year = str(row['Year'])
        
        titres_a_chercher = [f"{title_clean}-{year}", title_clean]
        if title_clean in ALIAS_TITRES:
            for alias in ALIAS_TITRES[title_clean]:
                titres_a_chercher.extend([f"{alias}-{year}", alias])
            
        m_id = None
        for t_cherche in titres_a_chercher:
            if t_cherche in title_to_id:
                m_id = title_to_id[t_cherche]
                break
                
        if m_id is not None:
            inner_id = None
            try:
                inner_id = trainset.to_inner_iid(m_id)
            except ValueError:
                try:
                    inner_id = trainset.to_inner_iid(int(m_id))
                    m_id = int(m_id)
                except (ValueError, TypeError):
                    try:
                        inner_id = trainset.to_inner_iid(str(m_id))
                        m_id = str(m_id)
                    except ValueError:
                        pass
            
            if inner_id is not None:
                watched_inner_ids.add(inner_id)
                watched_movie_ids.append(m_id)
                user_ratings.append(float(row['Rating']))

    print(f"-> {len(watched_inner_ids)} de tes films ont été formellement cartographiés.")
    
    if len(watched_inner_ids) < 5:
        print("\n[ERREUR] Pas assez de correspondances pour profiler tes goûts.")
        return

    print("4. Projection mathématique de tes goûts...")
    X = []
    y = []
    
    for m_id, r_true in zip(watched_movie_ids, user_ratings):
        inner_id = trainset.to_inner_iid(m_id)
        X.append(algo.qi[inner_id])
        y.append(r_true - mu - algo.bi[inner_id])

    clf = Ridge(alpha=1.5)
    clf.fit(np.array(X), np.array(y))
    
    p_u = clf.coef_
    b_u = clf.intercept_

    print("5. Calcul des prédictions sur les films non vus...")
    predictions = []

    for inner_id in trainset.all_items():
        m_id = trainset.to_raw_iid(inner_id)
        title = id_to_title.get(m_id, str(m_id))
        title_clean = clean_title(title)
        
        if inner_id not in watched_inner_ids and title_clean not in user_watched_titles_clean:
            q_i = algo.qi[inner_id]
            b_i = algo.bi[inner_id]
            
            score_predit = mu + b_u + b_i + np.dot(p_u, q_i)
            score_predit = max(0.5, min(5.0, score_predit))
            
            predictions.append((title, score_predit))

    predictions.sort(key=lambda x: x[1], reverse=True)
    top_100 = predictions[:100]

    print(f"6. Écriture des résultats dans {OUTPUT_TXT_PATH}...")
    with open(OUTPUT_TXT_PATH, "w", encoding="utf-8") as f:
        f.write("="*65 + "\n")
        f.write("TOP 100 DES RECOMMANDATIONS FILMS - PROJECTION COLLABORATIVE SVD\n")
        f.write("="*65 + "\n\n")
        for rank, (title, score) in enumerate(top_100, 1):
            f.write(f"{rank:03d}. {title:<45} | Note estimée : {score:.2f} / 5\n")

    print(f"Terminé. Le fichier '{OUTPUT_TXT_PATH}' a été mis à jour.")

if __name__ == "__main__":
    recommander()