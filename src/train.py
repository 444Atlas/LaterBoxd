import os
import time
from surprise import SVD, accuracy, dump
from surprise.model_selection import train_test_split
from nettoyage import main as load_data

def train_model():
    print("--- DÉMARRAGE DE L'ENTRAÎNEMENT ---")
    data = load_data()

    print("\n4. Division des données...")
    trainset, testset = train_test_split(data, test_size=0.2, random_state=42)

    print("5. Initialisation de l'algorithme SVD...")
    algo = SVD(n_factors=100, random_state=42)

    print("6. Entraînement du modèle...")
    start_time = time.time()
    algo.fit(trainset)
    print(f"-> Entraînement terminé en {time.time() - start_time:.2f} secondes.")

    print("7. Évaluation du modèle...")
    predictions = algo.test(testset)
    rmse = accuracy.rmse(predictions, verbose=False)
    print(f"RÉSULTAT : RMSE = {rmse:.4f}")
    
    return algo

if __name__ == "__main__":
    algo_entraine = train_model()
    os.makedirs("models", exist_ok=True)
    chemin_modele = "models/svd_model.pkl"
    print(f"\nSauvegarde du modèle dans {chemin_modele}...")
    dump.dump(chemin_modele, predictions=None, algo=algo_entraine)
    print("Modèle sauvegardé avec succès !")