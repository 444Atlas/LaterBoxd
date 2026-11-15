import os
import polars as pl
from surprise import Dataset, Reader


MIN_RATINGS_PER_MOVIE = 500   # Un film doit avoir au moins 50 notes
MIN_RATINGS_PER_USER = 20    # Un utilisateur doit avoir noté au moins 20 films


DATA_PATH = "data/train.parquet"

def main():
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"Le fichier {DATA_PATH} est introuvable. Place-le dans le bon dossier.")

    print("1. Chargement des données avec Polars...")
    lf = pl.scan_parquet(DATA_PATH)
    
    print(f"Colonnes détectées : {lf.collect_schema().names()}")


    lf = lf.drop_nulls().unique(subset=["user", "movie_id"])

    print("2. Filtrage des films et utilisateurs peu actifs...")
    # Étape A : Filtrer les films populaires
    movies_to_keep = (
        lf.group_by("movie_id")
        .agg(pl.len().alias("movie_rating_count"))
        .filter(pl.col("movie_rating_count") >= MIN_RATINGS_PER_MOVIE)
        .select("movie_id")
    )

    users_to_keep = (
        lf.group_by("user")
        .agg(pl.len().alias("user_rating_count"))
        .filter(pl.col("user_rating_count") >= MIN_RATINGS_PER_USER)
        .select("user")
    )

    lf_filtered = (
        lf.join(movies_to_keep, on="movie_id", how="inner")
        .join(users_to_keep, on="user", how="inner")
    )


    df_filtered = lf_filtered.collect()
    
    print(f"-> Données après filtrage : {df_filtered.shape[0]:,} lignes.")
    print(f"-> Nombre d'utilisateurs uniques : {df_filtered['user'].n_unique():,}")
    print(f"-> Nombre de films uniques : {df_filtered['movie_id'].n_unique():,}")

    print("3. Conversion pour la bibliothèque Surprise...")
    df_pandas = df_filtered.select(["user", "movie_id", "rating"]).to_pandas()

    reader = Reader(rating_scale=(0.5, 5.0))
    
    data = Dataset.load_from_df(df_pandas[["user", "movie_id", "rating"]], reader)
    
    print("✓ Dataset Surprise prêt pour l'entraînement !")
    return data

if __name__ == "__main__":
    data_surprise = main()