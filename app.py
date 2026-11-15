import io
import os
import re
import time
import json
import unicodedata
from typing import Optional

import numpy as np
import pandas as pd
import polars as pl
from fastapi import FastAPI, File, UploadFile, Query
from fastapi.responses import HTMLResponse, FileResponse, PlainTextResponse
from surprise import dump
from sklearn.linear_model import Ridge

app = FastAPI(title="LaterBoxd API", description="Moteur de recommandation SVD et cartographie d'espace latent")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "models/svd_model.pkl")
DATA_PARQUET_PATH = os.path.join(BASE_DIR, "data/train.parquet")
MAP_JSON_PATH = os.path.join(BASE_DIR, "data/movies_map.json")
TEMPLATE_PATH = os.path.join(BASE_DIR, "templates/index.html")

# Variables globales préchargées
MODEL_ALGO = None
TRAINSET = None
GLOBAL_MEAN = 0.0
TITLE_TO_ID = {}
MOVIES_MAP_DATA = None

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

@app.on_event("startup")
def startup_load_data():
    global MODEL_ALGO, TRAINSET, GLOBAL_MEAN, TITLE_TO_ID, MOVIES_MAP_DATA
    print("-> Chargement du modèle SVD...")
    if os.path.exists(MODEL_PATH):
        _, MODEL_ALGO = dump.load(MODEL_PATH)
        TRAINSET = MODEL_ALGO.trainset
        GLOBAL_MEAN = TRAINSET.global_mean
        print(f"   Modèle SVD chargé : {TRAINSET.n_items} films répertoriés.")

    print("-> Chargement de la table des correspondances de titres...")
    if os.path.exists(DATA_PARQUET_PATH):
        m_df = pl.scan_parquet(DATA_PARQUET_PATH).select(["movie_id", "title"]).unique().collect().to_pandas()
        m_df['title_clean'] = m_df['title'].apply(clean_title)
        TITLE_TO_ID = dict(zip(m_df['title_clean'], m_df['movie_id']))
        print(f"   {len(TITLE_TO_ID):,} titres cartographiés.")

    print("-> Chargement du fichier cartographique JSON...")
    if os.path.exists(MAP_JSON_PATH):
        with open(MAP_JSON_PATH, "r", encoding="utf-8") as f:
            MOVIES_MAP_DATA = json.load(f)
        print(f"   Cartographie chargée : {len(MOVIES_MAP_DATA['movies']):,} coordonnées prêtes.")

@app.get("/", response_class=HTMLResponse)
def get_home():
    if os.path.exists(TEMPLATE_PATH):
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Fichier template introuvable</h1>", status_code=404)

@app.get("/api/data")
def get_map_data():
    if MOVIES_MAP_DATA is None:
        return {"error": "Données non initialisées."}
    return MOVIES_MAP_DATA

@app.post("/api/upload-csv")
async def upload_letterboxd_csv(file: UploadFile = File(...)):
    global MODEL_ALGO, TRAINSET, TITLE_TO_ID, MOVIES_MAP_DATA
    t0 = time.time()
    
    try:
        contents = await file.read()
        user_df = pd.read_csv(io.BytesIO(contents))
        
        # Vérification des colonnes minimales
        name_col = next((c for c in user_df.columns if c.lower() in ["name", "title", "film", "nom"]), None)
        rating_col = next((c for c in user_df.columns if c.lower() in ["rating", "note", "ratings"]), None)
        year_col = next((c for c in user_df.columns if c.lower() in ["year", "annee", "année"]), None)
        
        if not name_col or not rating_col:
            return {
                "success": False,
                "error": "Le CSV doit comporter au moins les colonnes 'Name' et 'Rating' (format export Letterboxd standard)."
            }

        user_df['title_clean'] = user_df[name_col].apply(clean_title)
        
        watched_inner_ids = set()
        watched_movie_ids = []
        user_ratings_dict = {}

        for _, row in user_df.iterrows():
            title_clean = row['title_clean']
            year = str(row[year_col]) if year_col and pd.notna(row[year_col]) else ""
            titres_a_chercher = [f"{title_clean}-{year}", title_clean] if year else [title_clean]
            
            if title_clean in ALIAS_TITRES:
                for alias in ALIAS_TITRES[title_clean]:
                    if year:
                        titres_a_chercher.extend([f"{alias}-{year}", alias])
                    else:
                        titres_a_chercher.append(alias)

            m_id = None
            for t_cherche in titres_a_chercher:
                if t_cherche in TITLE_TO_ID:
                    m_id = TITLE_TO_ID[t_cherche]
                    break
                    
            if m_id is not None:
                inner_id = None
                try:
                    inner_id = TRAINSET.to_inner_iid(m_id)
                except ValueError:
                    try:
                        inner_id = TRAINSET.to_inner_iid(int(m_id))
                    except (ValueError, TypeError):
                        try:
                            inner_id = TRAINSET.to_inner_iid(str(m_id))
                        except ValueError:
                            pass
                
                if inner_id is not None and pd.notna(row[rating_col]):
                    watched_inner_ids.add(inner_id)
                    watched_movie_ids.append(m_id)
                    user_ratings_dict[inner_id] = float(row[rating_col])

        if len(watched_inner_ids) < 3:
            return {
                "success": False,
                "error": f"Seulement {len(watched_inner_ids)} films reconnus. Au moins 3 films correspondants sont requis."
            }

        # Régression Ridge rapide
        X = [MODEL_ALGO.qi[i_id] for i_id in watched_inner_ids]
        y = [user_ratings_dict[i_id] - GLOBAL_MEAN - MODEL_ALGO.bi[i_id] for i_id in watched_inner_ids]
        clf = Ridge(alpha=1.5)
        clf.fit(np.array(X), np.array(y))
        
        p_u = clf.coef_
        b_u = clf.intercept_

        # Calcul matriciel vectorisé des prédictions pour les 4658 films
        # score = mu + b_u + b_i + (qi @ p_u)
        all_bi = MODEL_ALGO.bi
        all_scores = GLOBAL_MEAN + b_u + all_bi + (MODEL_ALGO.qi @ p_u)
        all_scores = np.clip(all_scores, 0.5, 5.0)

        # Mise à jour des films
        updated_movies = []
        for m in MOVIES_MAP_DATA["movies"]:
            m_copy = dict(m)
            inner_id = m_copy["id"]
            m_copy["pred"] = round(float(all_scores[inner_id]), 2)
            m_copy["watched"] = inner_id in watched_inner_ids
            m_copy["user_rating"] = user_ratings_dict.get(inner_id)
            updated_movies.append(m_copy)

        calc_ms = round((time.time() - t0) * 1000, 1)
        return {
            "success": True,
            "matched_count": len(watched_inner_ids),
            "calc_time_ms": calc_ms,
            "movies": updated_movies
        }

    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/export", response_class=PlainTextResponse)
def export_top100(excluded: Optional[str] = Query(None)):
    global MOVIES_MAP_DATA
    if not MOVIES_MAP_DATA:
        return PlainTextResponse("Données non chargées.", status_code=500)

    excluded_set = set()
    if excluded:
        for val in excluded.split(","):
            val = val.strip()
            if val.isdigit():
                excluded_set.add(int(val))

    eligible = [m for m in MOVIES_MAP_DATA["movies"] if not m["watched"] and m["cluster"] not in excluded_set]
    eligible.sort(key=lambda x: x["pred"], reverse=True)
    top_100 = eligible[:100]

    cluster_names = {c["id"]: c["name"] for c in MOVIES_MAP_DATA["metadata"]["clusters"]}

    lines = [
        "=" * 75,
        "LATERBOXD — TOP 100 DES RECOMMANDATIONS FILMS (PROJECTION RIDGE SVD)",
        "=" * 75,
        f"Généré le : {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Filtre clusters exclus : {', '.join([cluster_names.get(cid, str(cid)) for cid in excluded_set]) if excluded_set else 'Aucun'}",
        "-" * 75,
        f"{'RANG':<6} {'TITRE':<42} {'ANNÉE':<8} {'CLUSTER':<24} {'NOTE ESTIMÉE'}",
        "-" * 75
    ]

    for idx, m in enumerate(top_100, 1):
        c_name = cluster_names.get(m['cluster'], 'Autre')
        yr = str(m['year']) if m.get('year') else 'N/A'
        title = m['title'][:40]
        lines.append(f"{idx:03d}.   {title:<42} {yr:<8} {c_name:<24} {m['pred']:.2f} / 5")

    lines.append("=" * 75)
    return PlainTextResponse("\n".join(lines), media_type="text/plain", headers={"Content-Disposition": "attachment; filename=recommandations_laterboxd.txt"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
