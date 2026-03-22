import os, json, re, io, time
from datetime import datetime
import requests
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS

app = Flask(__name__, static_folder="static")
CORS(app)

# ── GROQ CONFIG ───────────────────────────────────────────────
GROQ_KEY  = os.environ.get("GROQ_API_KEY", "")
GROQ_URL  = "https://api.groq.com/openai/v1/chat/completions"
# Modèles par ordre de préférence (fallback automatique)
MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-70b-versatile",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
]

LANGUAGES = {
    "fr": "français", "en": "English", "es": "español", "pt": "português",
    "de": "Deutsch", "it": "italiano", "nl": "Nederlands", "pl": "polski",
    "ru": "русский", "zh": "中文", "ja": "日本語", "ko": "한국어",
    "ar": "العربية", "hi": "हिन्दी", "tr": "Türkçe", "sv": "svenska",
    "da": "dansk", "fi": "suomi", "nb": "norsk", "ro": "română",
    "cs": "čeština", "hu": "magyar", "el": "ελληνικά", "he": "עברית",
    "th": "ภาษาไทย", "vi": "tiếng Việt", "id": "bahasa Indonesia",
    "ms": "bahasa Melayu", "tl": "Filipino", "uk": "українська",
    "ca": "català", "hr": "hrvatski", "sk": "slovenčina", "bg": "български",
    "lt": "lietuvių", "lv": "latviešu", "et": "eesti", "sl": "slovenščina",
    "fa": "فارسی", "bn": "বাংলা", "ta": "தமிழ்", "sw": "Kiswahili",
}

def parse_json(raw):
    raw = raw.strip()
    for attempt in [raw, raw.replace("```json","").replace("```","").strip()]:
        try: return json.loads(attempt)
        except: pass
    a, b = raw.find("{"), raw.rfind("}")
    if a != -1 and b > a:
        try: return json.loads(raw[a:b+1])
        except: pass
    raise ValueError(f"JSON invalide: {raw[:200]}")

def ask(prompt, lang="en"):
    """Appel Groq avec fallback automatique sur plusieurs modèles."""
    if not GROQ_KEY:
        raise RuntimeError("GROQ_API_KEY non configurée sur le serveur")
    lang_name = LANGUAGES.get(lang, "English")
    system = f"You respond ONLY with valid JSON. No text before or after. No backticks. No explanations. All string values in the JSON must be written in {lang_name}."
    last_error = None
    for model in MODELS:
        try:
            resp = requests.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user",   "content": prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 4096,
                },
                timeout=45
            )
            if resp.status_code == 429:  # Rate limit — essayer le modèle suivant
                time.sleep(1)
                last_error = f"Rate limit sur {model}"
                continue
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"]
            return parse_json(raw)
        except Exception as e:
            last_error = str(e)
            continue
    raise RuntimeError(f"Tous les modèles ont échoué. Dernière erreur: {last_error}")

def ask_simple(prompt, max_tokens=20):
    """Appel simple pour detect-lang — sans JSON."""
    if not GROQ_KEY: return ""
    try:
        resp = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
            json={"model": "llama-3.1-8b-instant",
                  "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": max_tokens, "temperature": 0},
            timeout=10
        )
        return resp.json()["choices"][0]["message"]["content"].strip()
    except: return ""

@app.route("/")
def index(): return send_from_directory("static", "index.html")

@app.route("/api/health")
def health(): return jsonify({"ok": True, "api_configured": bool(GROQ_KEY), "provider": "groq", "models": MODELS[0]})

@app.route("/api/languages")
def get_languages(): return jsonify({"ok": True, "languages": LANGUAGES})

# ── DETECT LANGUAGE ───────────────────────────────────────────
@app.route("/api/detect-lang", methods=["POST"])
def detect_lang():
    try:
        d = request.json or {}
        text = d.get("text", "").strip()
        if not text or len(text) < 3:
            return jsonify({"ok": True, "lang": "en", "name": "English"})
        result = ask_simple(f"Reply ONLY with the 2-letter ISO 639-1 language code for: \"{text[:80]}\"")
        detected = result.lower().replace('"','').replace("'","").strip()[:2]
        if detected not in LANGUAGES: detected = "en"
        return jsonify({"ok": True, "lang": detected, "name": LANGUAGES[detected]})
    except:
        return jsonify({"ok": True, "lang": "en", "name": "English"})

# ── TRANSLATE UI ──────────────────────────────────────────────
@app.route("/api/translate-ui", methods=["POST"])
def translate_ui():
    try:
        d = request.json or {}
        lang = d.get("lang", "en")
        if lang == "en":
            return jsonify({"ok": True, "lang": "en", "strings": get_english_strings()})
        lang_name = LANGUAGES.get(lang, "English")
        english = get_english_strings()
        prompt = f"Translate these UI strings to {lang_name}. Concise and natural for a cooking app. Return ONLY a JSON object with the same keys and translated values.\n{json.dumps(english, ensure_ascii=False)}"
        translated = ask(prompt, lang=lang)
        for k, v in english.items():
            if k not in translated: translated[k] = v
        return jsonify({"ok": True, "lang": lang, "strings": translated})
    except:
        return jsonify({"ok": True, "lang": "en", "strings": get_english_strings()})

def get_english_strings():
    return {
        "nav_create":"Create","nav_menu":"Full Menu","nav_history":"My Recipes",
        "hero_eyebrow":"Gastronomic Intelligence",
        "hero_headline1":"Your kitchen brigade","hero_headline2":"augmented.",
        "hero_desc":"Enter your ingredients. ChefMind creates an exceptional gourmet recipe — Michelin technique, financial analysis, wine pairings — in seconds.",
        "stat1_num":"20+","stat1_lbl":"years of expertise",
        "stat2_num":"∞","stat2_lbl":"possible recipes",
        "stat3_num":"3s","stat3_lbl":"AI generation",
        "form_title":"New Creation",
        "label_ingredients":"Available ingredients","hint_ingredients":"comma-separated",
        "label_couverts":"Servings","label_budget":"Budget / serving",
        "label_style":"Cuisine style","label_allergenes":"Allergens to exclude",
        "label_type":"Dish type","label_niveau":"Skill level",
        "placeholder_ingredients":"e.g. tuna fillet, coconut milk, lime, ginger…",
        "placeholder_budget":"e.g. $8",
        "btn_generate":"✦  Create the recipe",
        "btn_login_required":"✦  Login to generate",
        "btn_limit":"✦  Limit reached",
        "type_all":"Any type","type_cold_starter":"Cold starter",
        "type_warm_starter":"Warm starter","type_main":"Main course",
        "type_dessert":"Dessert","type_amuse":"Amuse-bouche","type_sauce":"Sauce / Condiment",
        "level_all":"Any level","level_easy":"Easy","level_medium":"Intermediate",
        "level_advanced":"Advanced","level_expert":"Expert",
        "style_polynesian":"Polynesian","style_french":"French classic",
        "style_asian":"Asian fusion","style_mediterranean":"Mediterranean",
        "style_gastro":"Gastronomic","style_street":"Street food","style_japanese":"Japanese",
        "aller_gluten":"Gluten","aller_lactose":"Lactose","aller_eggs":"Eggs",
        "aller_nuts":"Tree nuts","aller_shellfish":"Shellfish","aller_fish":"Fish","aller_soy":"Soy",
        "paywall_msg":"Your 3 free recipes are used up this month.",
        "btn_go_pro":"✦ Go Pro — $9/month",
        "section_prep":"Mise en place","section_technique":"Technique",
        "section_dressage":"Plating & presentation","section_note":"Chef's Note",
        "meta_prep":"Prep","meta_cook":"Cook","meta_total":"Total",
        "meta_servings":"Servings","meta_level":"Level",
        "action_pdf":"PDF Sheet","action_scale":"Adjust servings","action_variantes":"Creative variants",
        "side_finance":"Financial Analysis","side_nutrition":"Nutritional Values",
        "side_wine":"Wine Pairings","side_allergens":"Allergens",
        "cost_per_serving":"Cost / serving","suggested_price":"Suggested price","gross_margin":"Gross margin",
        "scale_label":"Recalculate for","scale_unit":"servings","btn_recalculate":"Recalculate",
        "menu_title":"Full Menu","menu_desc_txt":"Generate a cohesive menu with timing and wine pairing.",
        "label_theme":"Theme / Style","label_saison":"Season",
        "btn_generate_menu":"✦  Generate the menu",
        "menu_evening":"Evening menu","menu_cost":"Total cost / serving",
        "menu_price":"Suggested price","menu_margin":"Gross margin",
        "menu_timing":"Service timing","menu_wine":"Wine pairing",
        "cat_starter":"Starter","cat_main":"Main course","cat_dessert":"Dessert",
        "cost_serving":"Cost / serving",
        "hist_title":"My Recipes","hist_empty":"No recipes generated yet.","btn_clear_all":"Clear all",
        "auth_login":"Login","auth_register":"Create account",
        "auth_email":"Email","auth_password":"Password","auth_name":"Full name",
        "auth_placeholder_email":"chef@restaurant.com",
        "auth_placeholder_pass":"••••••••",
        "auth_placeholder_name":"Benjamin Martin",
        "auth_placeholder_pass_min":"6 characters minimum",
        "btn_login":"Log in","btn_register":"Create my account",
        "auth_free_note":"3 free recipes · No credit card required",
        "auth_err_fields":"Please fill in all fields.",
        "auth_err_pass":"Password: 6 characters minimum.",
        "auth_err_email":"Invalid email.",
        "auth_err_exists":"Account already exists.",
        "auth_err_wrong":"Incorrect email or password.",
        "pricing_title":"Go Pro","pricing_sub":"Unlimited generation + all premium features",
        "pricing_stripe":"🔒 Secure Stripe payment · Cancel anytime",
        "plan_free":"Free","plan_pro":"Pro",
        "feat_3recipes":"3 recipes / month","feat_pdf":"Technical PDF sheet",
        "feat_finance":"Financial analysis","feat_hist30":"30 recipe history",
        "feat_unlimited":"Unlimited recipes","feat_menu":"Unlimited full menus",
        "feat_variantes":"Creative variants","feat_wine":"Premium wine pairings",
        "feat_nutri":"Nutritional values","feat_export":"Professional PDF export",
        "feat_hist_unlimited":"Unlimited history",
        "btn_continue_free":"Continue free","btn_subscribe":"Subscribe — $9/month",
        "toast_welcome":"Welcome","toast_created":"Account created! 3 free recipes available.",
        "toast_logout":"See you soon!","toast_pro":"🌟 ChefMind Pro activated!",
        "toast_scaled":"Recalculated for","toast_servings":"servings",
        "toast_pdf_gen":"📄 Generating PDF…","toast_pdf_done":"✅ PDF downloaded!",
        "lang_label":"Language","lang_auto":"Auto-detect",
    }

# ── GENERATE RECIPE ───────────────────────────────────────────
@app.route("/api/generate", methods=["POST"])
def generate():
    try:
        d = request.json or {}
        ingredients = d.get("ingredients", "").strip()
        if not ingredients:
            return jsonify({"ok": False, "error": "Missing ingredients"}), 400
        lang      = d.get("lang", "en")
        lang_name = LANGUAGES.get(lang, "English")
        couverts  = d.get("couverts", "4")
        budget    = d.get("budget", "not specified")
        type_plat = d.get("typePlat", "any")
        styles    = d.get("styles", [])
        allergenes= d.get("allergenes", [])
        niveau    = d.get("niveau", "")

        prompt = f"""You are Chef de Cuisine with 3 Michelin stars and 25 years of haute cuisine experience. You trained under Robuchon and Ducasse. Create a technically precise, restaurant-grade recipe for professional kitchen use.

PARAMETERS:
- Main ingredients: {ingredients}
- Servings: {couverts} covers
- Dish type: {type_plat or "chef's choice"}
- Culinary style: {", ".join(styles) or "contemporary French gastronomy"}
- Excluded allergens: {", ".join(allergenes) or "none"}
- Food cost target per cover: {budget}
- Technical level: {niveau or "professional brigade"}
- Language for ALL text values: {lang_name}

REQUIREMENTS FOR PROFESSIONAL QUALITY:
- Use precise culinary terminology (brunoise, chiffonade, nappe, monter au beurre, etc.)
- Include exact temperatures in °C (e.g., "Sear at 220°C", "Bake at 165°C fan", "Core temperature 58°C")
- Include precise timings (e.g., "reduce by 2/3 over 8 minutes", "rest 4 minutes tented")
- Include exact weights in grams for all ingredients
- Use professional techniques: sous-vide, beurre noisette, emulsion, liaison, etc.
- The "astuce" field must contain a real chef's secret or professional trick, not obvious advice
- "histoire" must reference the terroir, producer, or culinary tradition with depth
- "dressage" must describe the exact plating geometry, sauce application technique, and garnish placement
- "note_chef" must contain a precise technical tip only an experienced chef would know
- Each step must be written as a professional would brief their brigade — precise, direct, technical

Return ONLY this complete JSON (no extra text, no backticks):
{{"nom":"Poetic evocative name (3-5 words max)","sous_titre":"Precise technical subtitle describing the key technique or terroir","histoire":"2 sentences — origin, terroir, artisan producer or culinary tradition that inspired this dish",
"temps_prep":"XX min","temps_cuisson":"XX min","temps_total":"XX min",
"difficulte":"Avancé","temperature_service":"XX°C","saison":"Automne",
"ingredients":[
  {{"nom":"Ingredient with precision (e.g. 'Beurre de Normandie AOP, clarified')", "quantite":"XXXg","cout_estime":X.XX,"preparation":"Exact prep technique (e.g. 'brunoise 3mm, dégorged 20min in coarse salt')"}}
],
"etapes":[
  {{"numero":1,"titre":"Station and technique name","description":"Precise brigade-level instruction with temperatures, timings and visual cues (e.g. 'In a rondeau over high heat, bring clarified butter to 165°C until hazelnut aroma. Sear the fish skin-side down pressing gently for 90 seconds until golden and crisp. Flip, baste continuously for 45 seconds. Remove to rack.')" ,"duree":"X min","astuce":"Real professional secret — e.g. specific temperature, unexpected technique, textural trick"}}
],
"dressage":"Precise plating instruction: exact position on plate, sauce quenelle or dots, microherb placement, sauce mirror technique, height and geometry of the composition",
"accords_vins":[
  {{"type":"Blanc de blancs sec","region":"Bourgogne — Puligny-Montrachet","cepage":"Chardonnay","pourquoi":"Precise technical pairing reason — acidity balance, fat cut, aromatic echo"}}
],
"valeurs_nutritionnelles":{{"calories":XXX,"proteines":"XXg","glucides":"XXg","lipides":"XXg","fibres":"XXg"}},
"cout_matiere_total":XX.XX,"cout_par_couvert":X.XX,"prix_vente_suggere":XX.00,"marge_brute_pct":XX,
"allergenes_presents":[],"allergenes_absents":["Gluten","Lactose","Oeufs","Fruits à coque","Crustacés","Poisson","Soja"],
"tags":["technique-clé","terroir","saison"],"note_chef":"One precise technical tip only an experienced chef would know — a real brigade secret","variante":"A creative, technically grounded variation that changes the profile of the dish"}}"""

        recipe = ask(prompt, lang=lang)
        return jsonify({"ok": True, "recipe": recipe})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ── MENU ─────────────────────────────────────────────────────
@app.route("/api/menu", methods=["POST"])
def generate_menu():
    try:
        d = request.json or {}
        lang = d.get("lang", "en")
        prompt = f"""You are a 3-Michelin-star Chef de Cuisine. Create a complete, technically precise tasting menu for a professional restaurant brigade. ALL text in {LANGUAGES.get(lang,"English")}.

Menu concept: {d.get("theme","Contemporary gastronomic")}
Covers: {d.get("couverts","4")} | Food cost target/cover: {d.get("budget","40")} | Season: {d.get("saison","All seasons")}
Allergens excluded: {", ".join(d.get("allergenes",[])) or "none"}

Requirements:
- Each course must have a clear narrative arc (amuse → build → climax → resolution)
- Technical coherence: same terroir thread, complementary textures, no repeated ingredients
- Each step must be brigade-level precise with temperatures and timings
- The timing_service must include exact brigade coordination (e.g. "Entrée: sauce reduced 20min before service. Plat: filet rested 4min, sauce mounted à la minute. Dessert: soufflé started at dessert order, 12min oven")

JSON: {{"nom_menu":"Evocative menu name","description":"1 precise sentence — concept, terroir or narrative",
"entree":{{"nom":"...","sous_titre":"...","temps_total":"XX min",
  "ingredients":[{{"nom":"Precise ingredient","quantite":"XXg"}}],
  "etapes":["Step with temperature and timing","Step 2"],
  "cout_par_couvert":X.XX,
  "note_chef":"Real technical tip for brigade"
}},
"plat":{{"nom":"...","sous_titre":"...","temps_total":"XX min",
  "ingredients":[{{"nom":"Precise ingredient","quantite":"XXg"}}],
  "etapes":["Step with temperature and timing","Step 2"],
  "cout_par_couvert":X.XX,
  "note_chef":"Real technical tip for brigade"
}},
"dessert":{{"nom":"...","sous_titre":"...","temps_total":"XX min",
  "ingredients":[{{"nom":"Precise ingredient","quantite":"XXg"}}],
  "etapes":["Step with temperature and timing","Step 2"],
  "cout_par_couvert":X.XX,
  "note_chef":"Real technical tip for brigade"
}},
"accord_vin_menu":{{"vin":"Specific producer and cuvée","region":"Appellation précise","pourquoi":"Technical pairing rationale"}},
"cout_total_par_couvert":X.XX,"prix_menu_suggere":XX.00,"marge_pct":XX,
"timing_service":"Precise brigade coordination with exact timings for each course"}}"""
        menu = ask(prompt, lang=lang)
        return jsonify({"ok": True, "menu": menu})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ── VARIANTES ────────────────────────────────────────────────
@app.route("/api/variantes", methods=["POST"])
def get_variantes():
    try:
        d = request.json or {}
        recipe = d.get("recipe", {})
        lang   = d.get("lang", "en")
        prompt = f"""You are a 3-Michelin-star Chef de Cuisine. Propose 3 technically precise creative variants of this dish: "{recipe.get("nom","")}"
Original key ingredients: {", ".join([i["nom"] for i in recipe.get("ingredients",[])[:6]])}
ALL text in {LANGUAGES.get(lang,"English")}.

Each variant must:
- Change a fundamental technique OR a key ingredient OR the flavour profile entirely
- Be technically coherent and restaurant-executable
- Have a clear creative rationale — not just a minor substitution

JSON: {{"variantes":[
  {{"nom":"Technically precise variant name","sous_titre":"Key technique or ingredient change","changements":"Precise description of what changes technically and why — mention specific technique, temperature or ingredient swap","difficulte":"Confirmé","impact_cout":"±X.XX€/couvert"}},
  {{"nom":"...","sous_titre":"...","changements":"...","difficulte":"Expert","impact_cout":"±X.XX€/couvert"}},
  {{"nom":"...","sous_titre":"...","changements":"...","difficulte":"Chef","impact_cout":"±X.XX€/couvert"}}
]}}"""
        result = ask(prompt, lang=lang)
        return jsonify({"ok": True, "variantes": result.get("variantes", [])})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ── SCALE ─────────────────────────────────────────────────────
@app.route("/api/scale", methods=["POST"])
def scale_recipe():
    try:
        d = request.json or {}
        recipe  = d.get("recipe", {})
        old_cov = float(d.get("old_couverts", 4))
        new_cov = float(d.get("new_couverts", 4))
        if old_cov <= 0: raise ValueError("Invalid servings")
        ratio = new_cov / old_cov

        def scale_qty(qty_str):
            nums = re.findall(r'[\d]+\.?\d*', str(qty_str))
            result = qty_str
            for n in nums:
                scaled = round(float(n) * ratio, 1)
                scaled = int(scaled) if scaled == int(scaled) else scaled
                result = result.replace(n, str(scaled), 1)
            return result

        scaled_ings = []
        for ing in recipe.get("ingredients", []):
            si = dict(ing)
            si["quantite"]    = scale_qty(ing.get("quantite", ""))
            si["cout_estime"] = round(float(ing.get("cout_estime", 0)) * ratio, 2)
            scaled_ings.append(si)

        scaled = dict(recipe)
        scaled["ingredients"]        = scaled_ings
        scaled["cout_matiere_total"] = round(float(recipe.get("cout_matiere_total", 0)) * ratio, 2)
        scaled["cout_par_couvert"]   = round(float(recipe.get("cout_par_couvert", 0)), 2)
        scaled["prix_vente_suggere"] = round(float(recipe.get("prix_vente_suggere", 0)), 2)
        return jsonify({"ok": True, "recipe": scaled, "new_couverts": int(new_cov)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ── PHOTO DU PLAT ─────────────────────────────────────────────
# Banque d'images TheMealDB par catégorie — URLs CDN stables, pas d'appel API
PHOTO_BANK = {
    "fish":     ["https://www.themealdb.com/images/media/meals/xxyupu1468262513.jpg",
                 "https://www.themealdb.com/images/media/meals/y115bt1683711927.jpg",
                 "https://www.themealdb.com/images/media/meals/vvtvtr1491930647.jpg"],
    "seafood":  ["https://www.themealdb.com/images/media/meals/wuvryu1468237429.jpg",
                 "https://www.themealdb.com/images/media/meals/xxyupu1468262513.jpg"],
    "chicken":  ["https://www.themealdb.com/images/media/meals/tuqmql1511180740.jpg",
                 "https://www.themealdb.com/images/media/meals/roysjt1511644919.jpg",
                 "https://www.themealdb.com/images/media/meals/xxrxux1503070723.jpg"],
    "beef":     ["https://www.themealdb.com/images/media/meals/sytuqu1511553755.jpg",
                 "https://www.themealdb.com/images/media/meals/c18lr11546891536.jpg",
                 "https://www.themealdb.com/images/media/meals/wrssvt1511556563.jpg"],
    "lamb":     ["https://www.themealdb.com/images/media/meals/1523771856.jpg",
                 "https://www.themealdb.com/images/media/meals/1529442785.jpg"],
    "pasta":    ["https://www.themealdb.com/images/media/meals/sutysw1468247559.jpg",
                 "https://www.themealdb.com/images/media/meals/wvqpwt1468339226.jpg"],
    "vegetarian":["https://www.themealdb.com/images/media/meals/wuxrtu1483564410.jpg",
                  "https://www.themealdb.com/images/media/meals/1548772327.jpg"],
    "dessert":  ["https://www.themealdb.com/images/media/meals/adxcbq1511999601.jpg",
                 "https://www.themealdb.com/images/media/meals/rqvwxt1511384809.jpg",
                 "https://www.themealdb.com/images/media/meals/1550441882.jpg"],
    "soup":     ["https://www.themealdb.com/images/media/meals/vvpprx1487325699.jpg",
                 "https://www.themealdb.com/images/media/meals/uuuspp1511297945.jpg"],
    "rice":     ["https://www.themealdb.com/images/media/meals/1520081754.jpg",
                 "https://www.themealdb.com/images/media/meals/uvuyxu1503067369.jpg"],
    "salad":    ["https://www.themealdb.com/images/media/meals/g373701551450225.jpg",
                 "https://www.themealdb.com/images/media/meals/1520082096.jpg"],
    "pork":     ["https://www.themealdb.com/images/media/meals/sytuqu1511553755.jpg",
                 "https://www.themealdb.com/images/media/meals/xwrpuu1511564228.jpg"],
    "breakfast":["https://www.themealdb.com/images/media/meals/1550441882.jpg",
                 "https://www.themealdb.com/images/media/meals/utxryw1511721587.jpg"],
    "default":  ["https://www.themealdb.com/images/media/meals/tuqmql1511180740.jpg",
                 "https://www.themealdb.com/images/media/meals/sytuqu1511553755.jpg",
                 "https://www.themealdb.com/images/media/meals/sutysw1468247559.jpg",
                 "https://www.themealdb.com/images/media/meals/wuvryu1468237429.jpg",
                 "https://www.themealdb.com/images/media/meals/xxyupu1468262513.jpg"],
}

# Mots-clés → catégorie
CATEGORY_MAP = {
    "fish":"fish","thon":"fish","saumon":"fish","cabillaud":"fish","bar":"fish",
    "sole":"fish","turbot":"fish","daurade":"fish","truite":"fish","tuna":"fish",
    "salmon":"fish","cod":"fish","sea bass":"fish",
    "crevette":"seafood","homard":"seafood","langouste":"seafood","coquille":"seafood",
    "shrimp":"seafood","lobster":"seafood","scallop":"seafood","prawn":"seafood",
    "poulet":"chicken","volaille":"chicken","canard":"chicken",
    "chicken":"chicken","duck":"chicken","poultry":"chicken",
    "boeuf":"beef","veau":"beef","entrecôte":"beef","filet":"beef",
    "beef":"beef","veal":"beef","steak":"beef",
    "agneau":"lamb","lamb":"lamb","rack":"lamb",
    "porc":"pork","cochon":"pork","pork":"pork","lard":"pork",
    "pâtes":"pasta","pasta":"pasta","risotto":"pasta","gnocchi":"pasta",
    "légume":"vegetarian","tomate":"vegetarian","végétal":"vegetarian",
    "vegetable":"vegetarian","tomato":"vegetarian",
    "dessert":"dessert","chocolat":"dessert","sucre":"dessert","gâteau":"dessert",
    "chocolate":"dessert","cake":"dessert","tart":"dessert",
    "soupe":"soup","bouillon":"soup","velouté":"soup","soup":"soup","broth":"soup",
    "riz":"rice","rice":"rice",
    "salade":"salad","salad":"salad",
}

@app.route("/api/photo", methods=["POST"])
def get_photo():
    """Retourne une photo depuis la banque intégrée — 0 dépendance externe."""
    import hashlib
    try:
        d = request.json or {}
        nom         = (d.get("nom") or "").lower()
        tags        = [t.lower() for t in (d.get("tags") or [])]
        ingredients = d.get("ingredients") or []

        # Déterminer la catégorie
        category = "default"
        search_text = nom + " " + " ".join(tags) + " " + " ".join(
            i.get("nom","").lower() for i in ingredients[:4]
        )

        for keyword, cat in CATEGORY_MAP.items():
            if keyword in search_text:
                category = cat
                break

        # Choisir une image de façon déterministe (même recette = même photo)
        pool = PHOTO_BANK.get(category, PHOTO_BANK["default"])
        seed = int(hashlib.md5((nom or "recipe").encode()).hexdigest(), 16)
        url = pool[seed % len(pool)]

        return jsonify({"ok": True, "url": url, "source": "ChefMind", "category": category})

    except Exception as e:
        # Fallback absolu — image garantie
        return jsonify({
            "ok": True,
            "url": PHOTO_BANK["default"][0],
            "source": "ChefMind"
        })

# ── PDF ───────────────────────────────────────────────────────
@app.route("/api/pdf", methods=["POST"])
def export_pdf():
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.enums import TA_CENTER

        d = request.json or {}
        r          = d.get("recipe", {})
        couverts   = d.get("couverts", "4")
        restaurant = d.get("restaurant", "ChefMind")

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
            leftMargin=2*cm, rightMargin=2*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)

        GOLD = colors.HexColor("#c9973a")
        DARK = colors.HexColor("#1a1820")
        MUTED= colors.HexColor("#7a7488")

        def sty(name, **kw):
            base = {"fontName":"Times-Roman","fontSize":10,"textColor":DARK,"spaceAfter":6,"leading":16}
            base.update(kw); return ParagraphStyle(name, **base)

        styles = {
            "title":   sty("t",  fontName="Times-Bold",   fontSize=22, spaceAfter=4, leading=26),
            "subtitle":sty("s",  fontName="Times-Italic", fontSize=12, textColor=MUTED, spaceAfter=10),
            "section": sty("sc", fontName="Courier-Bold", fontSize=8,  textColor=GOLD, spaceAfter=8, spaceBefore=12),
            "body":    sty("b",  spaceAfter=8, leading=16),
            "bold":    sty("bo", fontName="Times-Bold",   spaceAfter=4),
            "note":    sty("n",  fontName="Times-Italic", fontSize=9.5, leftIndent=12, spaceAfter=8, leading=15),
            "small":   sty("sm", fontName="Courier",      fontSize=8,  textColor=MUTED, spaceAfter=4),
            "center":  sty("c",  fontSize=9, textColor=MUTED, alignment=TA_CENTER, spaceAfter=4),
        }

        story = []
        story.append(Paragraph(f"✦ {restaurant.upper()} · PROFESSIONAL RECIPE SHEET", styles["small"]))
        story.append(HRFlowable(width="100%", thickness=0.8, color=GOLD, spaceAfter=14))
        story.append(Paragraph(r.get("nom", ""), styles["title"]))
        story.append(Paragraph(r.get("sous_titre", ""), styles["subtitle"]))
        if r.get("histoire"): story.append(Paragraph(r["histoire"], styles["note"]))
        story.append(Spacer(1, 0.3*cm))

        meta = [["PREP","COOK","TOTAL","SERVINGS","LEVEL","SEASON"],
                [r.get("temps_prep","—"),r.get("temps_cuisson","—"),r.get("temps_total","—"),
                 str(couverts),r.get("difficulte","—"),r.get("saison","—")]]
        mt = Table(meta, colWidths=[2.7*cm]*6)
        mt.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),DARK),("TEXTCOLOR",(0,0),(-1,0),GOLD),
            ("FONTNAME",(0,0),(-1,0),"Courier-Bold"),("FONTSIZE",(0,0),(-1,0),6.5),
            ("FONTNAME",(0,1),(-1,1),"Times-Bold"),("FONTSIZE",(0,1),(-1,1),10),
            ("TEXTCOLOR",(0,1),(-1,1),DARK),("ALIGN",(0,0),(-1,-1),"CENTER"),
            ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#e0dcd4")),
            ("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8),
        ]))
        story.append(mt); story.append(Spacer(1, 0.5*cm))

        story.append(HRFlowable(width="100%",thickness=0.3,color=colors.HexColor("#e0dcd4")))
        story.append(Paragraph("INGREDIENTS", styles["section"]))
        ing_data = [["INGREDIENT","QUANTITY","PREPARATION","COST"]]
        for ing in r.get("ingredients",[]):
            ing_data.append([ing.get("nom",""),ing.get("quantite",""),
                             ing.get("preparation","—"),f"{float(ing.get('cout_estime',0)):.2f}"])
        it = Table(ing_data, colWidths=[5.5*cm,3*cm,5*cm,2.5*cm])
        it.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),DARK),("TEXTCOLOR",(0,0),(-1,0),GOLD),
            ("FONTNAME",(0,0),(-1,0),"Courier-Bold"),("FONTSIZE",(0,0),(-1,0),7),
            ("FONTNAME",(0,1),(-1,-1),"Times-Roman"),("FONTSIZE",(0,1),(-1,-1),9),
            ("TEXTCOLOR",(0,1),(-1,-1),DARK),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#faf8f4")]),
            ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#e0dcd4")),
            ("ALIGN",(3,0),(3,-1),"RIGHT"),
            ("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7),("LEFTPADDING",(0,0),(-1,-1),10),
        ]))
        story.append(it); story.append(Spacer(1, 0.5*cm))

        story.append(HRFlowable(width="100%",thickness=0.3,color=colors.HexColor("#e0dcd4")))
        story.append(Paragraph("TECHNIQUE", styles["section"]))
        for i, etape in enumerate(r.get("etapes",[])):
            if isinstance(etape, dict):
                num=etape.get("numero",i+1); titre=etape.get("titre","")
                desc=etape.get("description",""); duree=etape.get("duree",""); tip=etape.get("astuce","")
                hdr = f"<b>{str(num).zfill(2)}. {titre}</b>"
                if duree: hdr += f"  <font color='#7a7488'>— {duree}</font>"
                story.append(Paragraph(hdr, styles["bold"]))
                story.append(Paragraph(desc, styles["body"]))
                if tip: story.append(Paragraph(f"✦ {tip}", styles["note"]))
            else:
                story.append(Paragraph(f"• {etape}", styles["body"]))

        if r.get("dressage"):
            story.append(Paragraph("PLATING", styles["section"]))
            story.append(Paragraph(r["dressage"], styles["note"]))
        if r.get("note_chef"):
            story.append(HRFlowable(width="100%",thickness=0.5,color=GOLD))
            story.append(Paragraph("CHEF'S NOTE", styles["section"]))
            story.append(Paragraph(f"« {r['note_chef']} »", styles["note"]))

        story.append(Paragraph("FINANCIAL ANALYSIS", styles["section"]))
        fin = [["Total food cost",   f"{float(r.get('cout_matiere_total',0)):.2f}"],
               ["Cost per serving",  f"{float(r.get('cout_par_couvert',0)):.2f}"],
               ["Suggested price",   f"{float(r.get('prix_vente_suggere',0)):.2f}"],
               ["Gross margin",      f"{r.get('marge_brute_pct',0)}%"]]
        ft = Table(fin, colWidths=[10*cm,6*cm])
        ft.setStyle(TableStyle([
            ("FONTNAME",(0,0),(0,-1),"Times-Roman"),("FONTNAME",(1,0),(1,-1),"Times-Bold"),
            ("FONTSIZE",(0,0),(-1,-1),10),("TEXTCOLOR",(0,0),(0,-1),MUTED),
            ("TEXTCOLOR",(1,0),(1,-2),DARK),("TEXTCOLOR",(1,3),(1,3),colors.HexColor("#5a8a6a")),
            ("ALIGN",(1,0),(1,-1),"RIGHT"),
            ("ROWBACKGROUNDS",(0,0),(-1,-1),[colors.white,colors.HexColor("#faf8f4")]),
            ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#e0dcd4")),
            ("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8),("LEFTPADDING",(0,0),(-1,-1),12),
        ]))
        story.append(ft)
        story.append(Spacer(1, 0.6*cm))
        story.append(HRFlowable(width="100%",thickness=0.8,color=GOLD))
        story.append(Paragraph(
            f"Generated by ChefMind  ·  {datetime.now().strftime('%d %B %Y')}  ·  {couverts} servings",
            styles["center"]))

        doc.build(story)
        buf.seek(0)
        safe = re.sub(r'[^a-zA-Z0-9]','_', r.get('nom','recipe'))
        return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name=f"recipe_{safe}.pdf")

    except ImportError:
        return jsonify({"ok": False, "error": "ReportLab not installed"}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
