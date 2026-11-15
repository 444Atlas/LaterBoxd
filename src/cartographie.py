import os
import re
import json
import time
import unicodedata
import numpy as np
import pandas as pd
import polars as pl
from surprise import dump
from sklearn.linear_model import Ridge
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
import umap

MODEL_PATH = "models/svd_model.pkl"
DATA_PATH = "data/train.parquet"
USER_CSV_PATH = "data/ratings.csv"
OUTPUT_JSON_PATH = "data/movies_map.json"

ALIAS_TITRES = {
    "city-of-god": ["cidade-de-deus", "la-cité-de-dieu"],
    "black-box": ["black-box-2020"],
    "challenger": ["challengers"]
}

def clean_title(title):
    if pd.isna(title):
        return ""
    title_str = str(title).lower()
    title_str = unicodedata.normalize('NFKD', title_str).encode('ASCII', 'ignore').decode('utf-8')
    title_str = title_str.replace('-', ' ')
    title_str = re.sub(r'[^\w\s]', '', title_str)
    title_str = re.sub(r'\s+', ' ', title_str).strip()
    return title_str.replace(' ', '-')

def build_cartographie():
    print("=== DÉMARRAGE DE LA CARTOGRAPHIE ET DU CLUSTERING SVD ===")
    
    print("\n1. Chargement du modèle SVD...")
    _, algo = dump.load(MODEL_PATH)
    trainset = algo.trainset
    mu = trainset.global_mean
    n_items = trainset.n_items
    qi = algo.qi
    print(f"-> {n_items} films dans l'espace latent (dimension {qi.shape[1]}).")

    print("\n2. Chargement des correspondances titres depuis train.parquet...")
    movies_df = pl.scan_parquet(DATA_PATH).select(["movie_id", "title"]).unique().collect().to_pandas()
    movies_df['title_clean'] = movies_df['title'].apply(clean_title)
    title_to_id = dict(zip(movies_df['title_clean'], movies_df['movie_id']))
    id_to_title = dict(zip(movies_df['movie_id'], movies_df['title']))

    print("\n3. Chargement des métadonnées (genres et titres formels)...")
    meta_dict = {}
    if os.path.exists("filters/movies.csv") and os.path.exists("filters/genres.csv"):
        try:
            print("   Lecture de filters/genres.csv...")
            genres_df = pd.read_csv("filters/genres.csv")
            id_genres = genres_df.groupby("id")["genre"].apply(lambda g: ", ".join(list(g)[:3])).to_dict()
            
            print("   Lecture de filters/movies.csv...")
            movies_meta = pd.read_csv("filters/movies.csv", usecols=["id", "name", "date", "rating"])
            movies_meta["clean_name"] = movies_meta["name"].apply(clean_title)
            
            for _, row in movies_meta.iterrows():
                c_name = row["clean_name"]
                if c_name not in meta_dict:
                    meta_dict[c_name] = {
                        "name": row["name"],
                        "year": int(row["date"]) if pd.notna(row["date"]) else None,
                        "rating": float(row["rating"]) if pd.notna(row["rating"]) else None,
                        "genres": id_genres.get(row["id"], "")
                    }
            print(f"-> {len(meta_dict):,} films enrichis avec métadonnées.")
        except Exception as e:
            print(f"   [Attention] Erreur lors de la lecture des métadonnées: {e}")

    print("\n4. Analyse des notes utilisateur (Letterboxd)...")
    user_df = pd.read_csv(USER_CSV_PATH)
    user_df['title_clean'] = user_df['Name'].apply(clean_title)
    
    watched_inner_ids = set()
    watched_movie_ids = []
    user_ratings = []
    user_ratings_dict = {}

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
                r_val = float(row['Rating'])
                user_ratings.append(r_val)
                user_ratings_dict[inner_id] = r_val

    print(f"-> {len(watched_inner_ids)} films de votre profil Letterboxd cartographiés.")

    print("\n5. Projection Ridge du profil utilisateur...")
    X = [algo.qi[i_id] for i_id in watched_inner_ids]
    y = [user_ratings_dict[i_id] - mu - algo.bi[i_id] for i_id in watched_inner_ids]
    clf = Ridge(alpha=1.5)
    clf.fit(np.array(X), np.array(y))
    p_u = clf.coef_
    b_u = clf.intercept_

    print("\n6. Réduction dimensionnelle 2D (PCA 25D -> UMAP 2D)...")
    t0 = time.time()
    pca = PCA(n_components=25, random_state=42)
    qi_pca = pca.fit_transform(qi)
    
    reducer = umap.UMAP(n_neighbors=25, min_dist=0.15, n_components=2, n_jobs=-1, random_state=42)
    coords_2d = reducer.fit_transform(qi_pca)
    print(f"-> Projection UMAP 2D réalisée en {time.time() - t0:.2f} s.")

    # Normalisation des coordonnées entre -100 et 100 pour affichage fluide
    x_min, x_max = coords_2d[:, 0].min(), coords_2d[:, 0].max()
    y_min, y_max = coords_2d[:, 1].min(), coords_2d[:, 1].max()
    coords_norm_x = ((coords_2d[:, 0] - x_min) / (x_max - x_min) * 200 - 100).round(2)
    coords_norm_y = ((coords_2d[:, 1] - y_min) / (y_max - y_min) * 200 - 100).round(2)

    print("\n7. Clustering K-Means (8 clusters sémantiques)...")
    n_clusters = 8
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    cluster_labels = kmeans.fit_predict(qi)

    # Couleurs néon distinctes adaptées au thème sombre
    CLUSTER_COLORS = [
        "#f59e0b", # 0: Amber / Orange
        "#38bdf8", # 1: Sky Blue
        "#ec4899", # 2: Pink / Rose
        "#10b981", # 3: Emerald
        "#a855f7", # 4: Purple
        "#ef4444", # 5: Red
        "#06b6d4", # 6: Cyan
        "#eab308", # 7: Yellow
    ]

    print("\n8. Analyse des clusters et détection automatique du cluster Jeunesse / Animation...")
    cluster_movies = {c: [] for c in range(n_clusters)}
    all_movies_data = []
    predictions_all = []

    for inner_id in range(n_items):
        m_id = trainset.to_raw_iid(inner_id)
        slug_title = id_to_title.get(m_id, str(m_id))
        slug_clean = clean_title(slug_title)
        
        # Metadata lookup
        meta = meta_dict.get(slug_clean, {})
        display_name = meta.get("name") or slug_title.replace("-", " ").title()
        year = meta.get("year")
        genres = meta.get("genres", "")
        avg_rating = meta.get("rating")

        # Calcul prédiction
        b_i = algo.bi[inner_id]
        q_i = algo.qi[inner_id]
        score_predit = mu + b_u + b_i + float(np.dot(p_u, q_i))
        score_predit = round(max(0.5, min(5.0, score_predit)), 2)

        is_watched = inner_id in watched_inner_ids
        user_score = user_ratings_dict.get(inner_id)

        c_id = int(cluster_labels[inner_id])
        m_info = {
            "id": inner_id,
            "raw_id": str(m_id),
            "title": display_name,
            "slug": slug_title,
            "year": year,
            "genres": genres,
            "x": float(coords_norm_x[inner_id]),
            "y": float(coords_norm_y[inner_id]),
            "cluster": c_id,
            "pred": score_predit,
            "watched": is_watched,
            "user_rating": user_score,
            "avg_rating": avg_rating
        }
        all_movies_data.append(m_info)
        cluster_movies[c_id].append(m_info)
        
        if not is_watched:
            predictions_all.append((m_info, score_predit))

    # Classement Top 100 global
    predictions_all.sort(key=lambda x: x[1], reverse=True)
    top_100_ids = set([x[0]["id"] for x in predictions_all[:100]])
    for m in all_movies_data:
        m["is_top100"] = m["id"] in top_100_ids

    # Caractérisation de chaque cluster
    cluster_profiles = []
    kids_cluster_id = None
    max_kids_ratio = -1.0

    KIDS_KEYWORDS = ["animation", "family", "children", "disney", "pixar", "dreamworks"]
    
    for c_id in range(n_clusters):
        items = cluster_movies[c_id]
        total_in_cluster = len(items)
        
        # Détection mots-clés jeunesse
        kids_count = 0
        for m in items:
            text = (m["title"] + " " + m["slug"] + " " + m["genres"]).lower()
            if any(k in text for k in KIDS_KEYWORDS):
                kids_count += 1
                
        kids_ratio = kids_count / max(total_in_cluster, 1)
        if kids_ratio > max_kids_ratio:
            max_kids_ratio = kids_ratio
            kids_cluster_id = c_id

        # Exemples de films emblématiques dans le cluster
        sample_titles = [m["title"] for m in items[:4]]
        
        cluster_profiles.append({
            "id": c_id,
            "count": total_in_cluster,
            "kids_ratio": round(kids_ratio, 3),
            "sample": sample_titles,
            "color": CLUSTER_COLORS[c_id]
        })

    # Attribuer des labels explicites aux clusters
    cluster_names = {}
    for prof in cluster_profiles:
        cid = prof["id"]
        if cid == kids_cluster_id:
            name = "Animation & Films Jeunesse"
        else:
            # Donner un nom indicatif basé sur les genres/titres les plus fréquents
            genres_counts = {}
            for m in cluster_movies[cid]:
                for g in m["genres"].split(","):
                    g_clean = g.strip()
                    if g_clean:
                        genres_counts[g_clean] = genres_counts.get(g_clean, 0) + 1
            top_g = sorted(genres_counts.items(), key=lambda x: x[1], reverse=True)
            if top_g:
                name = " & ".join([g[0] for g in top_g[:2]])
            else:
                name = f"Groupe Ciné {cid+1}"
        cluster_names[cid] = name
        prof["name"] = name

    print(f"\n=> CLUSTER JEUNESSE IDENTIFIÉ : Cluster #{kids_cluster_id} ({cluster_names[kids_cluster_id]}) avec {max_kids_ratio*100:.1f}% de films jeunesse/animation.")
    
    for prof in cluster_profiles:
        print(f"   Cluster {prof['id']} : {prof['name']} ({prof['count']} films) - Ex: {', '.join(prof['sample'])}")

    # Calcul Top 100 filtré (sans le cluster jeunesse)
    predictions_filtered = [p for p in predictions_all if p[0]["cluster"] != kids_cluster_id]
    top_100_filtered = [p[0] for p in predictions_filtered[:100]]
    
    print("\n9. Comparaison du Top 10 avant / après bannissement du cluster Jeunesse :")
    print("   --- AVANT (Actuel) ---")
    for i, (m, score) in enumerate(predictions_all[:10], 1):
        c_flag = " [JEUNESSE]" if m["cluster"] == kids_cluster_id else ""
        print(f"   {i:02d}. {m['title']} ({score}/5){c_flag}")
        
    print("\n   --- APRÈS (Cluster Jeunesse banni) ---")
    for i, m in enumerate(top_100_filtered[:10], 1):
        print(f"   {i:02d}. {m['title']} ({m['pred']}/5) [Cluster: {cluster_names[m['cluster']]}]")

    print(f"\n10. Sauvegarde de la cartographie dans {OUTPUT_JSON_PATH}...")
    export_payload = {
        "metadata": {
            "total_movies": n_items,
            "user_watched_count": len(watched_inner_ids),
            "kids_cluster_id": kids_cluster_id,
            "clusters": cluster_profiles,
        },
        "movies": all_movies_data
    }
    
    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(export_payload, f, ensure_ascii=False)
    print("✓ Fichier JSON cartographique généré avec succès !")
    return export_payload

if __name__ == "__main__":
    build_cartographie()
