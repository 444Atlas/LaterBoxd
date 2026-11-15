import json
import os

MAP_JSON_PATH = "data/movies_map.json"
OUTPUT_WORKSPACE_HTML = "cartographie_interactive.html"
ARTIFACT_DIR = "/home/paullv/.gemini/antigravity/brain/58aed7d7-7305-4dd7-9da6-919f76d83f90"
OUTPUT_ARTIFACT_HTML = os.path.join(ARTIFACT_DIR, "cartographie_interactive.html")

def generate_html():
    print("Chargement des données cartographiques...")
    with open(MAP_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    meta = data["metadata"]
    movies = data["movies"]
    kids_cluster_id = meta["kids_cluster_id"]
    
    # Préparer les données compactes pour injecter dans le template HTML
    compact_movies = []
    for m in movies:
        compact_movies.append([
            m["id"],
            m["title"],
            m["year"] or 0,
            m["genres"] or "",
            round(m["x"], 2),
            round(m["y"], 2),
            m["cluster"],
            m["pred"],
            1 if m["watched"] else 0,
            m["user_rating"] or 0,
            round(m["avg_rating"], 2) if m["avg_rating"] else 0
        ])

    payload = {
        "clusters": meta["clusters"],
        "kids_cluster_id": kids_cluster_id,
        "movies": compact_movies
    }
    json_str = json.dumps(payload, separators=(',', ':'), ensure_ascii=False)

    html_content = f"""<!DOCTYPE html>
<html lang="fr" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>LaterBoxd // Cartographie SVD & Clusters</title>
  <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
  <style>
    body {{
      background-color: #06080d;
      color: #e2e8f0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      overflow-x: hidden;
    }}
    .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }}
    ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
    ::-webkit-scrollbar-track {{ background: #0b0f19; }}
    ::-webkit-scrollbar-thumb {{ background: #1e293b; border-radius: 3px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: #334155; }}
    .glow-cyan {{ box-shadow: 0 0 15px rgba(6, 182, 212, 0.35); }}
    .glow-emerald {{ box-shadow: 0 0 15px rgba(16, 185, 129, 0.4); }}
    .glow-rose {{ box-shadow: 0 0 15px rgba(236, 72, 153, 0.35); }}
    .glass-panel {{
      background: rgba(11, 15, 25, 0.85);
      backdrop-filter: blur(12px);
      border: 1px solid rgba(255, 255, 255, 0.08);
    }}
  </style>
</head>
<body class="p-3 md:p-6 min-h-screen flex flex-col gap-5 text-sm">

  <!-- TOP BAR / HEADER (Style MPPREDICTOR) -->
  <header class="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-white/10">
    <div>
      <div class="flex items-center gap-3">
        <span class="mono text-xs text-blue-400 font-semibold tracking-wider">LATERBOXD // 01 CARTOGRAPHIE & DÉTECTION SVD</span>
        <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-950/80 text-emerald-400 border border-emerald-500/30">
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
          Modèle actif
        </span>
      </div>
      <h1 class="text-2xl md:text-3xl font-extrabold tracking-tight text-white mt-1">
        Cartographie 2D de l'Espace Latent & Filtrage des Clusters
      </h1>
      <p class="text-xs text-slate-400 mt-1">
        Projection UMAP de 4 658 films issus du modèle SVD • Visualisation des affinités, des 211 films notés et du Top 100 de recommandations
      </p>
    </div>

    <!-- STATS RAPIDES -->
    <div class="flex items-center gap-4 bg-slate-900/80 p-3 rounded-xl border border-white/10 mono text-xs">
      <div>
        <div class="text-slate-400 text-[10px] uppercase">Films Base</div>
        <div class="text-white font-bold text-base">4 658</div>
      </div>
      <div class="w-px h-8 bg-white/10"></div>
      <div>
        <div class="text-slate-400 text-[10px] uppercase">Letterboxd</div>
        <div class="text-amber-400 font-bold text-base">211 vus</div>
      </div>
      <div class="w-px h-8 bg-white/10"></div>
      <div>
        <div class="text-slate-400 text-[10px] uppercase">Top 100</div>
        <div id="statTop100Count" class="text-blue-400 font-bold text-base">100 dispo</div>
      </div>
    </div>
  </header>

  <!-- CONTROLS & ACTION BAR -->
  <div class="flex flex-wrap items-center justify-between gap-3 p-3 rounded-xl glass-panel">
    <!-- Barre de recherche -->
    <div class="relative flex-1 min-w-[260px] max-w-md">
      <input 
        id="searchInput" 
        type="text" 
        placeholder="Rechercher un film (ex: Ratatouille, Dark Knight...)" 
        class="w-full bg-slate-950/80 border border-white/10 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
      />
      <div id="searchResults" class="absolute left-0 right-0 top-full mt-1 bg-slate-950 border border-white/10 rounded-lg shadow-2xl z-50 max-h-56 overflow-y-auto hidden"></div>
    </div>

    <!-- Bouton maître : Bannir le cluster Jeunesse -->
    <button 
      id="toggleKidsBtn" 
      class="flex items-center gap-2 px-4 py-2 rounded-lg font-semibold text-xs transition-all border shadow-lg bg-emerald-600/20 text-emerald-300 border-emerald-500/40 hover:bg-emerald-600/30 glow-emerald"
    >
      <span id="kidsBtnIcon">🚫</span>
      <span id="kidsBtnText">Bannir Cluster Jeunesse / Animation</span>
    </button>

    <!-- Filtres d'affichage rapides -->
    <div class="flex items-center gap-1.5 mono text-xs bg-slate-950/70 p-1 rounded-lg border border-white/10">
      <button id="viewAllBtn" class="px-3 py-1.5 rounded-md bg-blue-600 text-white font-medium">Tous (4658)</button>
      <button id="viewWatchedBtn" class="px-3 py-1.5 rounded-md text-slate-400 hover:text-white">Mes vus (211)</button>
      <button id="viewTopBtn" class="px-3 py-1.5 rounded-md text-slate-400 hover:text-white">Top 100</button>
    </div>
  </div>

  <!-- MAIN GRID : CARTE + PANNEAU LATÉRAL -->
  <div class="grid grid-cols-1 lg:grid-cols-12 gap-5 flex-1 min-h-[640px]">

    <!-- CARTE INTERACTIVE CANVAS (8 colonnes) -->
    <div class="lg:col-span-8 flex flex-col rounded-xl glass-panel overflow-hidden relative">
      <div class="flex items-center justify-between px-4 py-2.5 border-b border-white/10 bg-slate-950/50">
        <span class="mono text-xs text-slate-400 flex items-center gap-2">
          <span>CANVAS 2D</span> • 
          <span class="text-slate-500">Glisser pour déplacer | Molette pour zoomer</span>
        </span>
        <div class="flex items-center gap-2">
          <button id="zoomInBtn" class="w-7 h-7 rounded bg-slate-900 border border-white/10 text-white hover:bg-slate-800 flex items-center justify-center font-bold">+</button>
          <button id="zoomOutBtn" class="w-7 h-7 rounded bg-slate-900 border border-white/10 text-white hover:bg-slate-800 flex items-center justify-center font-bold">-</button>
          <button id="zoomResetBtn" class="px-2.5 h-7 rounded bg-slate-900 border border-white/10 text-xs text-slate-300 hover:bg-slate-800">Recentrer</button>
        </div>
      </div>

      <!-- Canvas container -->
      <div class="relative flex-1 w-full h-[520px] bg-[#05070c]" id="canvasContainer">
        <canvas id="mapCanvas" class="w-full h-full cursor-grab active:cursor-grabbing block"></canvas>
        
        <!-- Tooltip flottant -->
        <div id="movieTooltip" class="absolute pointer-events-none hidden z-40 bg-slate-950/95 border border-white/20 p-3 rounded-xl shadow-2xl max-w-xs text-xs backdrop-blur-md">
          <div class="flex items-center justify-between gap-2 pb-1.5 border-b border-white/10">
            <span id="ttTitle" class="font-bold text-white text-sm truncate">Titre</span>
            <span id="ttYear" class="mono text-slate-400 text-[11px]">2020</span>
          </div>
          <div class="mt-2 space-y-1 text-slate-300">
            <div class="flex items-center gap-1.5">
              <span id="ttClusterBadge" class="px-1.5 py-0.5 rounded text-[10px] font-bold text-black bg-white">Cluster</span>
              <span id="ttGenres" class="text-slate-400 truncate text-[11px]">Genres</span>
            </div>
            <div class="flex items-center justify-between pt-1 text-[11px]">
              <span class="text-slate-400">Note estimée :</span>
              <span id="ttPred" class="font-bold text-blue-400 mono text-xs">4.5/5</span>
            </div>
            <div id="ttUserRatingRow" class="flex items-center justify-between text-[11px] text-amber-400">
              <span>Votre note Letterboxd :</span>
              <span id="ttUserRating" class="font-bold mono text-xs">5/5 ★</span>
            </div>
          </div>
        </div>

        <!-- Légende des formes (bas gauche) -->
        <div class="absolute bottom-3 left-3 bg-slate-950/85 border border-white/10 rounded-lg p-2.5 text-[11px] mono flex flex-col gap-1.5 backdrop-blur">
          <div class="flex items-center gap-2">
            <span class="w-2.5 h-2.5 rounded-full bg-slate-400 inline-block"></span>
            <span class="text-slate-300">Film de la base</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="w-3 h-3 rotate-45 bg-amber-400 inline-block border border-amber-200"></span>
            <span class="text-amber-300 font-bold">Film vu (Letterboxd)</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="w-3 h-3 rounded-full bg-blue-500 border border-white inline-block"></span>
            <span class="text-blue-300 font-bold">Top 100 Recommandé</span>
          </div>
        </div>
      </div>

      <!-- Sélecteur de clusters en bas de carte -->
      <div class="p-3 border-t border-white/10 bg-slate-950/90 flex flex-wrap gap-2 items-center text-xs">
        <span class="mono text-slate-400 text-[11px] mr-1 uppercase">Clusters :</span>
        <div id="clusterPillsContainer" class="flex flex-wrap gap-1.5 flex-1"></div>
      </div>
    </div>

    <!-- PANNEAU LATÉRAL (4 colonnes) : TOP 100 DYNAMIQUE AVEC FILTRE -->
    <div class="lg:col-span-4 flex flex-col rounded-xl glass-panel overflow-hidden">
      <div class="p-4 border-b border-white/10 bg-slate-950/60 flex items-center justify-between">
        <div>
          <div class="mono text-xs text-blue-400 font-semibold uppercase">Classement Personnalisé</div>
          <h2 class="text-base font-bold text-white flex items-center gap-2">
            <span>Top Recommandations</span>
            <span id="topFilterBadge" class="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-white/10">Filtre actif</span>
          </h2>
        </div>
        <button id="copyTopBtn" class="px-2.5 py-1.5 rounded-lg bg-slate-900 border border-white/10 text-xs text-slate-300 hover:bg-slate-800 hover:text-white transition-all mono">
          📋 Copier
        </button>
      </div>

      <!-- Alerte comparative bannissement -->
      <div id="bannedAlertBox" class="p-3 bg-emerald-950/40 border-b border-emerald-500/20 text-xs text-emerald-300 flex items-center justify-between">
        <span>✓ <strong>Cluster Jeunesse banni</strong> : les films pour enfants sont exclus.</span>
      </div>

      <!-- Liste des films du top -->
      <div id="topListContainer" class="flex-1 overflow-y-auto divide-y divide-white/5 max-h-[500px]">
        <!-- Rempli par JavaScript -->
      </div>
    </div>

  </div>

  <!-- SCRIPT APPLICATION -->
  <script>
    const DATA = {json_str};
    const CLUSTERS = DATA.clusters;
    const KIDS_CLUSTER_ID = DATA.kids_cluster_id;
    const RAW_MOVIES = DATA.movies;

    // Structure des films pour accès rapide
    // [id, title, year, genres, x, y, c, pred, w, ur, ar]
    const movies = RAW_MOVIES.map(row => ({{
      id: row[0],
      title: row[1],
      year: row[2],
      genres: row[3],
      x: row[4],
      y: row[5],
      cluster: row[6],
      pred: row[7],
      watched: row[8] === 1,
      user_rating: row[9],
      avg_rating: row[10]
    }}));

    // États
    let activeClusters = new Set(CLUSTERS.map(c => c.id));
    let isKidsBanned = false;
    let currentViewMode = "all"; // "all" | "watched" | "top"
    let highlightedMovie = null;

    // Canvas & Viewport
    const canvas = document.getElementById("mapCanvas");
    const ctx = canvas.getContext("2d");
    let scale = 1.0;
    let offsetX = 0;
    let offsetY = 0;
    let isDragging = false;
    let startX, startY;

    function resizeCanvas() {{
      const rect = canvas.parentElement.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      ctx.scale(dpr, dpr);
      draw();
    }}
    window.addEventListener("resize", resizeCanvas);

    // Initialisation des Pills de clusters
    function initClusterPills() {{
      const container = document.getElementById("clusterPillsContainer");
      container.innerHTML = "";
      CLUSTERS.forEach(c => {{
        const isKids = c.id === KIDS_CLUSTER_ID;
        const btn = document.createElement("button");
        btn.id = `pill-cluster-${{c.id}}`;
        btn.className = `px-2 py-1 rounded text-[11px] font-medium flex items-center gap-1.5 transition-all border ${{
          activeClusters.has(c.id) ? 'bg-slate-900 border-white/20 text-white' : 'bg-slate-950/60 border-white/5 text-slate-500 opacity-50'
        }}`;
        btn.innerHTML = `
          <span class="w-2 h-2 rounded-full" style="background-color: ${{c.color}}"></span>
          <span>${{c.name}} (${{c.count}})</span>
          ${{isKids ? '<span class="text-[9px] px-1 bg-amber-500/20 text-amber-300 rounded font-bold">CIBLE</span>' : ''}}
        `;
        btn.addEventListener("click", () => {{
          if (activeClusters.has(c.id)) {{
            activeClusters.delete(c.id);
          }} else {{
            activeClusters.add(c.id);
          }}
          updateKidsButtonState();
          updateClusterPills();
          draw();
          updateTopList();
        }});
        container.appendChild(btn);
      }});
    }}

    function updateClusterPills() {{
      CLUSTERS.forEach(c => {{
        const btn = document.getElementById(`pill-cluster-${{c.id}}`);
        if (!btn) return;
        if (activeClusters.has(c.id)) {{
          btn.className = `px-2 py-1 rounded text-[11px] font-medium flex items-center gap-1.5 transition-all border bg-slate-900 border-white/20 text-white`;
        }} else {{
          btn.className = `px-2 py-1 rounded text-[11px] font-medium flex items-center gap-1.5 transition-all border bg-slate-950/60 border-white/5 text-slate-500 opacity-50`;
        }}
      }});
    }}

    // Bouton de bannissement du cluster Jeunesse
    const toggleKidsBtn = document.getElementById("toggleKidsBtn");
    const kidsBtnText = document.getElementById("kidsBtnText");
    const kidsBtnIcon = document.getElementById("kidsBtnIcon");
    const bannedAlertBox = document.getElementById("bannedAlertBox");

    function updateKidsButtonState() {{
      isKidsBanned = !activeClusters.has(KIDS_CLUSTER_ID);
      if (isKidsBanned) {{
        toggleKidsBtn.className = "flex items-center gap-2 px-4 py-2 rounded-lg font-semibold text-xs transition-all border shadow-lg bg-rose-600/20 text-rose-300 border-rose-500/40 hover:bg-rose-600/30 glow-rose";
        kidsBtnIcon.textContent = "✓";
        kidsBtnText.textContent = "Cluster Jeunesse Banni (Réactiver)";
        bannedAlertBox.classList.remove("hidden");
      }} else {{
        toggleKidsBtn.className = "flex items-center gap-2 px-4 py-2 rounded-lg font-semibold text-xs transition-all border shadow-lg bg-emerald-600/20 text-emerald-300 border-emerald-500/40 hover:bg-emerald-600/30 glow-emerald";
        kidsBtnIcon.textContent = "🚫";
        kidsBtnText.textContent = "Bannir Cluster Jeunesse / Animation";
        bannedAlertBox.classList.add("hidden");
      }}
    }}

    toggleKidsBtn.addEventListener("click", () => {{
      if (activeClusters.has(KIDS_CLUSTER_ID)) {{
        activeClusters.delete(KIDS_CLUSTER_ID);
      }} else {{
        activeClusters.add(KIDS_CLUSTER_ID);
      }}
      updateKidsButtonState();
      updateClusterPills();
      draw();
      updateTopList();
    }});

    // Filtres d'affichage rapides
    document.getElementById("viewAllBtn").addEventListener("click", (e) => setViewMode("all", e.target));
    document.getElementById("viewWatchedBtn").addEventListener("click", (e) => setViewMode("watched", e.target));
    document.getElementById("viewTopBtn").addEventListener("click", (e) => setViewMode("top", e.target));

    function setViewMode(mode, targetBtn) {{
      currentViewMode = mode;
      ["viewAllBtn", "viewWatchedBtn", "viewTopBtn"].forEach(id => {{
        document.getElementById(id).className = "px-3 py-1.5 rounded-md text-slate-400 hover:text-white";
      }});
      targetBtn.className = "px-3 py-1.5 rounded-md bg-blue-600 text-white font-medium";
      draw();
    }}

    // Mise à jour de la liste Top 100 dynamique
    let currentTopMovies = [];
    function updateTopList() {{
      const availableMovies = movies.filter(m => !m.watched && activeClusters.has(m.cluster));
      availableMovies.sort((a, b) => b.pred - a.pred);
      currentTopMovies = availableMovies.slice(0, 100);

      document.getElementById("statTop100Count").textContent = `${{currentTopMovies.length}} prêts`;
      document.getElementById("topFilterBadge").textContent = isKidsBanned ? "Sans films enfants" : "Complet (8 clusters)";

      const container = document.getElementById("topListContainer");
      container.innerHTML = "";

      currentTopMovies.forEach((m, idx) => {{
        const cInfo = CLUSTERS[m.cluster] || {{ name: "Autre", color: "#64748b" }};
        const item = document.createElement("div");
        item.className = "p-3 hover:bg-white/5 cursor-pointer flex items-center justify-between gap-3 transition-colors";
        item.innerHTML = `
          <div class="flex items-center gap-3 min-w-0">
            <span class="mono text-xs font-bold text-slate-500 w-6 text-right">${{(idx + 1).toString().padStart(2, '0')}}</span>
            <div class="min-w-0">
              <div class="font-semibold text-white truncate text-xs">${{m.title}}</div>
              <div class="flex items-center gap-1.5 text-[11px] text-slate-400 mt-0.5">
                <span class="w-1.5 h-1.5 rounded-full" style="background-color: ${{cInfo.color}}"></span>
                <span class="truncate">${{cInfo.name}}</span>
                ${{m.year ? `• <span>${{m.year}}</span>` : ''}}
              </div>
            </div>
          </div>
          <div class="text-right shrink-0">
            <div class="mono font-bold text-blue-400 text-xs">${{m.pred.toFixed(2)}}/5</div>
            <div class="text-[10px] text-slate-500">estimé</div>
          </div>
        `;
        item.addEventListener("click", () => {{
          highlightMovie(m);
        }});
        container.appendChild(item);
      }});
    }}

    // Canvas Rendering
    function getScreenCoords(normX, normY) {{
      const rect = canvas.getBoundingClientRect();
      const cx = rect.width / 2 + offsetX;
      const cy = rect.height / 2 + offsetY;
      // Les coordonnées normX/normY sont entre -100 et 100
      const sx = cx + (normX / 100) * (rect.width * 0.42) * scale;
      const sy = cy + (normY / 100) * (rect.height * 0.42) * scale;
      return {{ x: sx, y: sy }};
    }}

    function getNormCoords(screenX, screenY) {{
      const rect = canvas.getBoundingClientRect();
      const cx = rect.width / 2 + offsetX;
      const cy = rect.height / 2 + offsetY;
      const nx = ((screenX - cx) / (rect.width * 0.42 * scale)) * 100;
      const ny = ((screenY - cy) / (rect.height * 0.42 * scale)) * 100;
      return {{ x: nx, y: ny }};
    }}

    function draw() {{
      const rect = canvas.getBoundingClientRect();
      ctx.clearRect(0, 0, rect.width, rect.height);

      // Grille subtile en fond
      ctx.strokeStyle = "rgba(255, 255, 255, 0.03)";
      ctx.lineWidth = 1;
      const gridSize = 40 * scale;
      const startGridX = (rect.width / 2 + offsetX) % gridSize;
      const startGridY = (rect.height / 2 + offsetY) % gridSize;

      for (let x = startGridX; x < rect.width; x += gridSize) {{
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, rect.height);
        ctx.stroke();
      }}
      for (let y = startGridY; y < rect.height; y += gridSize) {{
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(rect.width, y);
        ctx.stroke();
      }}

      // Ensemble des IDs du top 100 actif pour rendu prioritaire
      const topIdsSet = new Set(currentTopMovies.map(m => m.id));

      // 1. DESSIN DES POINTS STANDARD
      movies.forEach(m => {{
        if (!activeClusters.has(m.cluster)) return;
        if (currentViewMode === "watched" && !m.watched) return;
        if (currentViewMode === "top" && !topIdsSet.has(m.id)) return;

        const pos = getScreenCoords(m.x, m.y);
        if (pos.x < -20 || pos.x > rect.width + 20 || pos.y < -20 || pos.y > rect.height + 20) return;

        const cInfo = CLUSTERS[m.cluster] || {{ color: "#64748b" }};

        if (m.watched) {{
          // Film noté par l'utilisateur (Losange doré)
          ctx.save();
          ctx.translate(pos.x, pos.y);
          ctx.rotate(Math.PI / 4);
          ctx.fillStyle = "#facc15";
          ctx.shadowColor = "rgba(250, 204, 21, 0.6)";
          ctx.shadowBlur = 6;
          const s = Math.max(4, 5.5 * scale * 0.8);
          ctx.fillRect(-s/2, -s/2, s, s);
          ctx.restore();
        }} else if (topIdsSet.has(m.id)) {{
          // Film du Top 100 recommandé (Cercle bleu électrique brillant)
          ctx.save();
          ctx.fillStyle = "#38bdf8";
          ctx.shadowColor = "rgba(56, 189, 248, 0.8)";
          ctx.shadowBlur = 8;
          ctx.beginPath();
          ctx.arc(pos.x, pos.y, Math.max(3.5, 4.5 * scale * 0.8), 0, Math.PI * 2);
          ctx.fill();
          ctx.restore();
        }} else {{
          // Film standard
          ctx.fillStyle = cInfo.color;
          ctx.beginPath();
          ctx.arc(pos.x, pos.y, Math.max(1.8, 2.5 * scale * 0.7), 0, Math.PI * 2);
          ctx.fill();
        }}
      }});

      // 2. HIGHLIGHT FILM RECHERCHÉ / SÉLECTIONNÉ
      if (highlightedMovie) {{
        const pos = getScreenCoords(highlightedMovie.x, highlightedMovie.y);
        ctx.save();
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 2;
        ctx.shadowColor = "#38bdf8";
        ctx.shadowBlur = 15;
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, 14, 0, Math.PI * 2);
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, 20, 0, Math.PI * 2);
        ctx.strokeStyle = "rgba(56, 189, 248, 0.5)";
        ctx.stroke();
        ctx.restore();
      }}
    }}

    // Navigation & Interaction Canvas
    canvas.addEventListener("mousedown", (e) => {{
      isDragging = true;
      startX = e.clientX - offsetX;
      startY = e.clientY - offsetY;
    }});

    window.addEventListener("mouseup", () => {{
      isDragging = false;
    }});

    canvas.addEventListener("mousemove", (e) => {{
      if (isDragging) {{
        offsetX = e.clientX - startX;
        offsetY = e.clientY - startY;
        draw();
        return;
      }}
      handleHover(e);
    }});

    canvas.addEventListener("wheel", (e) => {{
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 1.15 : 0.87;
      scale = Math.max(0.4, Math.min(6.0, scale * zoomFactor));
      draw();
    }}, {{ passive: false }});

    // Zoom buttons
    document.getElementById("zoomInBtn").addEventListener("click", () => {{
      scale = Math.min(6.0, scale * 1.25);
      draw();
    }});
    document.getElementById("zoomOutBtn").addEventListener("click", () => {{
      scale = Math.max(0.4, scale * 0.8);
      draw();
    }});
    document.getElementById("zoomResetBtn").addEventListener("click", () => {{
      scale = 1.0;
      offsetX = 0;
      offsetY = 0;
      highlightedMovie = null;
      draw();
    }});

    // Tooltip Hover
    const tooltip = document.getElementById("movieTooltip");
    function handleHover(e) {{
      const rect = canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      let closestMovie = null;
      let minDistance = 14; // pixels

      for (let i = 0; i < movies.length; i++) {{
        const m = movies[i];
        if (!activeClusters.has(m.cluster)) continue;
        if (currentViewMode === "watched" && !m.watched) continue;

        const pos = getScreenCoords(m.x, m.y);
        const dist = Math.hypot(pos.x - mouseX, pos.y - mouseY);
        if (dist < minDistance) {{
          minDistance = dist;
          closestMovie = m;
        }}
      }}

      if (closestMovie) {{
        const cInfo = CLUSTERS[closestMovie.cluster] || {{ name: "Cluster", color: "#64748b" }};
        document.getElementById("ttTitle").textContent = closestMovie.title;
        document.getElementById("ttYear").textContent = closestMovie.year ? closestMovie.year : "";
        
        const badge = document.getElementById("ttClusterBadge");
        badge.textContent = cInfo.name;
        badge.style.backgroundColor = cInfo.color;
        badge.style.color = "#000000";

        document.getElementById("ttGenres").textContent = closestMovie.genres || "Genres non renseignés";
        document.getElementById("ttPred").textContent = `${{closestMovie.pred.toFixed(2)}} / 5`;

        const userRow = document.getElementById("ttUserRatingRow");
        if (closestMovie.watched) {{
          userRow.classList.remove("hidden");
          document.getElementById("ttUserRating").textContent = `${{closestMovie.user_rating}} / 5 ★`;
        }} else {{
          userRow.classList.add("hidden");
        }}

        tooltip.style.left = `${{Math.min(rect.width - 240, mouseX + 15)}}px`;
        tooltip.style.top = `${{Math.min(rect.height - 130, mouseY + 15)}}px`;
        tooltip.classList.remove("hidden");
      }} else {{
        tooltip.classList.add("hidden");
      }}
    }}

    function highlightMovie(m) {{
      highlightedMovie = m;
      // Centrer la vue sur le film
      const rect = canvas.getBoundingClientRect();
      offsetX = -(m.x / 100) * (rect.width * 0.42) * scale;
      offsetY = -(m.y / 100) * (rect.height * 0.42) * scale;
      scale = 1.8;
      draw();
    }}

    // Recherche de films
    const searchInput = document.getElementById("searchInput");
    const searchResults = document.getElementById("searchResults");

    searchInput.addEventListener("input", (e) => {{
      const q = e.target.value.toLowerCase().trim();
      if (q.length < 2) {{
        searchResults.classList.add("hidden");
        return;
      }}
      const matches = movies.filter(m => m.title.toLowerCase().includes(q)).slice(0, 8);
      if (matches.length === 0) {{
        searchResults.innerHTML = `<div class="p-2.5 text-xs text-slate-500">Aucun résultat</div>`;
        searchResults.classList.remove("hidden");
        return;
      }}
      searchResults.innerHTML = "";
      matches.forEach(m => {{
        const cInfo = CLUSTERS[m.cluster] || {{ name: "Autre", color: "#64748b" }};
        const item = document.createElement("div");
        item.className = "p-2.5 hover:bg-slate-800/80 cursor-pointer flex items-center justify-between text-xs border-b border-white/5";
        item.innerHTML = `
          <div class="truncate mr-2">
            <span class="font-semibold text-white">${{m.title}}</span>
            <span class="text-slate-400 text-[11px] ml-1">(${{m.year || 'N/A'}})</span>
          </div>
          <span class="text-[10px] px-1.5 py-0.5 rounded font-mono shrink-0" style="background-color: ${{cInfo.color}}20; color: ${{cInfo.color}}">${{cInfo.name}}</span>
        `;
        item.addEventListener("click", () => {{
          highlightMovie(m);
          searchInput.value = m.title;
          searchResults.classList.add("hidden");
        }});
        searchResults.appendChild(item);
      }});
      searchResults.classList.remove("hidden");
    }});

    document.addEventListener("click", (e) => {{
      if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {{
        searchResults.classList.add("hidden");
      }}
    }});

    // Bouton Copier le Top 100
    document.getElementById("copyTopBtn").addEventListener("click", () => {{
      let text = "=== TOP RECOMMANDATIONS LATERBOXD ===\\n";
      text += isKidsBanned ? "(Filtre actif : Cluster Jeunesse banni)\\n\\n" : "(Tous clusters actifs)\\n\\n";
      currentTopMovies.forEach((m, idx) => {{
        text += `${{(idx + 1).toString().padStart(3, '0')}}. ${{m.title}} (${{m.year || ''}}) | Note estimée : ${{m.pred.toFixed(2)}}/5\\n`;
      }});
      navigator.clipboard.writeText(text).then(() => {{
        const btn = document.getElementById("copyTopBtn");
        btn.textContent = "✓ Copié !";
        btn.classList.add("text-emerald-400", "border-emerald-500");
        setTimeout(() => {{
          btn.textContent = "📋 Copier";
          btn.classList.remove("text-emerald-400", "border-emerald-500");
        }}, 2000);
      }});
    }});

    // Démarrage
    initClusterPills();
    updateKidsButtonState();
    updateTopList();
    setTimeout(resizeCanvas, 50);
  </script>
</body>
</html>
"""

    print(f"Écriture dans {OUTPUT_WORKSPACE_HTML}...")
    with open(OUTPUT_WORKSPACE_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Écriture dans {OUTPUT_ARTIFACT_HTML}...")
    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    with open(OUTPUT_ARTIFACT_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)

    print("✓ Cartographie interactive HTML générée avec succès !")

if __name__ == "__main__":
    generate_html()
