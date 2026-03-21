# ChefMind v3 — Intelligence Gastronomique

## Stack
- **Backend**: Python Flask + Anthropic claude-sonnet-4-5
- **Frontend**: HTML/CSS/JS vanilla — zéro dépendance
- **PDF**: ReportLab (côté serveur, vrai PDF pro)
- **Déploiement**: Render.com (gratuit)

## Fonctionnalités

### ✦ Recette complète
- Génération IA niveau chef étoilé
- Ingrédients avec grammages et coûts
- Étapes structurées avec durées et astuces
- Dressage, note du chef, variante créative
- Accords vins avec cépage et région
- Valeurs nutritionnelles complètes
- Analyse financière : coût matière, prix de vente, marge brute

### ⚖️ Scaling en temps réel
- Recalcul instantané des quantités pour n'importe quel nombre de couverts

### ✨ Variantes créatives
- 3 variantes générées à partir de chaque recette (facile / intermédiaire / expert)

### 🍽 Menu complet
- Entrée + plat + dessert cohérents
- Timing de service
- Accord vin global
- Analyse financière du menu

### 📄 Export PDF professionnel
- Fiche technique complète
- Mise en page gastronomique
- Prête pour HACCP et formation

### 🔐 Auth + Paywall
- Compte gratuit : 3 recettes/mois
- Compte Pro : illimité + menu + variantes

## Déploiement Render (5 min)

1. Crée un repo GitHub → upload les fichiers
2. render.com → New Web Service → connecte le repo
3. Environment → ajoute `ANTHROPIC_API_KEY`
4. Deploy → URL disponible en 2 min

## Structure
```
chefmind/
├── app.py              ← Backend Flask (6 endpoints)
├── requirements.txt    ← anthropic + flask + reportlab
├── render.yaml         ← Config auto Render
└── static/
    └── index.html      ← Frontend complet (3 vues)
```

## Endpoints API
- POST /api/generate    → Recette complète
- POST /api/menu        → Menu complet (E+P+D)
- POST /api/variantes   → 3 variantes créatives
- POST /api/scale       → Scaling des quantités
- POST /api/pdf         → Export PDF (ReportLab)
- GET  /api/health      → Statut serveur
