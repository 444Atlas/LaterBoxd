import json
import os

TEMPLATE_PATH = "templates/index.html"
DATA_PATH = "data/movies_map.json"
WORKSPACE_OUTPUT = "cartographie_interactive.html"
BRAIN_OUTPUT = "/home/paullv/.gemini/antigravity/brain/58aed7d7-7305-4dd7-9da6-919f76d83f90/cartographie_interactive.html"

def main():
    print("Lecture de templates/index.html...")
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    print("Lecture de data/movies_map.json...")
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data_json = f.read().strip()

    target = "    // Initialisation\n    async function init() {"
    if target not in template:
        raise ValueError(f"Impossible de trouver le point d'ancrage: {target}")

    embedded_block = f"""    // Initialisation avec données intégrées
    const EMBEDDED_DATA = {data_json};

    async function init() {{
      let loaded = false;
      try {{
        const res = await fetch("/api/data");
        if (res.ok) {{ appData = await res.json(); loaded = true; }}
      }} catch (e) {{}}
      if (!loaded && typeof EMBEDDED_DATA !== "undefined") {{ appData = EMBEDDED_DATA; }}
      if (appData) {{
        if (window.location.port) {{
          document.getElementById('portDisplay').textContent = 'FastAPI : Port ' + window.location.port;
        }}
        clusters = appData.metadata.clusters;
        kidsClusterId = appData.metadata.kids_cluster_id;
        allMovies = appData.movies;
        renderClustersList();
        renderGenrePills();
        resizeCanvas();
        applyFiltersAndUpdate();
        return;
      }}
"""

    result = template.replace(target, embedded_block, 1)

    print(f"Écriture de {WORKSPACE_OUTPUT} ({len(result):,} octets)...")
    with open(WORKSPACE_OUTPUT, "w", encoding="utf-8") as f:
        f.write(result)

    if os.path.exists(os.path.dirname(BRAIN_OUTPUT)):
        print(f"Écriture de {BRAIN_OUTPUT}...")
        with open(BRAIN_OUTPUT, "w", encoding="utf-8") as f:
            f.write(result)

    print("Synchronisation terminée avec succès !")

if __name__ == "__main__":
    main()
