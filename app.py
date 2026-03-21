import os, json, re, io
from datetime import datetime
import anthropic
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS

app = Flask(__name__, static_folder="static")
CORS(app)

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
client  = anthropic.Anthropic(api_key=API_KEY) if API_KEY else None

# ── SUPPORTED LANGUAGES ───────────────────────────────────────
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

def require_client():
    if not client:
        raise RuntimeError("ANTHROPIC_API_KEY not configured on server")

def ask(prompt, max_tokens=6000, lang="en"):
    require_client()
    system = f"You respond ONLY with valid JSON. No text before or after. No backticks. No explanations. All text values in the JSON must be written in {LANGUAGES.get(lang, 'English')}."
    msg = client.messages.create(
        model="claude-sonnet-4-6", max_tokens=max_tokens,
        system=system,
        messages=[{"role":"user","content":prompt}]
    )
    return parse_json(msg.content[0].text)

@app.route("/")
def index(): return send_from_directory("static", "index.html")

@app.route("/api/health")
def health(): return jsonify({"ok":True,"api_configured":bool(API_KEY),"languages":len(LANGUAGES)})

@app.route("/api/languages")
def get_languages():
    return jsonify({"ok":True,"languages":LANGUAGES})

# ── DETECT LANGUAGE ───────────────────────────────────────────
@app.route("/api/detect-lang", methods=["POST"])
def detect_lang():
    try:
        require_client()
        d = request.json or {}
        text = d.get("text","").strip()
        if not text or len(text) < 3:
            return jsonify({"ok":True,"lang":"en","name":"English"})

        msg = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=20,
            system="You detect the language of text. Reply ONLY with the 2-letter ISO 639-1 language code (e.g. 'fr', 'en', 'es'). Nothing else. No punctuation.",
            messages=[{"role":"user","content":f"Detect language: \"{text[:200]}\""}]
        )
        detected = msg.content[0].text.strip().lower().replace('"','').replace("'","")[:2]
        # Validate
        if detected not in LANGUAGES:
            detected = "en"
        return jsonify({"ok":True,"lang":detected,"name":LANGUAGES[detected]})
    except Exception as e:
        return jsonify({"ok":True,"lang":"en","name":"English"})

# ── TRANSLATE UI ──────────────────────────────────────────────
@app.route("/api/translate-ui", methods=["POST"])
def translate_ui():
    """Translate all UI strings to the requested language."""
    try:
        require_client()
        d = request.json or {}
        lang = d.get("lang","en")
        lang_name = LANGUAGES.get(lang,"English")

        if lang == "en":
            return jsonify({"ok":True,"lang":"en","strings":get_english_strings()})

        prompt = f"""Translate these UI strings to {lang_name}. Keep them concise and natural for a professional cooking app.
Return ONLY a JSON object with the same keys, translated values.

{json.dumps(get_english_strings(), ensure_ascii=False)}"""

        msg = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=6000,
            system="Translate UI strings. Return ONLY valid JSON with translated values. Keep ALL keys identical. Never omit any key.",
            messages=[{"role":"user","content":prompt}]
        )
        translated = parse_json(msg.content[0].text)
        # Ensure all keys present — fill missing with English fallback
        english = get_english_strings()
        for k, v in english.items():
            if k not in translated:
                translated[k] = v
        return jsonify({"ok":True,"lang":lang,"strings":translated})
    except Exception as e:
        return jsonify({"ok":True,"lang":"en","strings":get_english_strings()})

def get_english_strings():
    return {
        # Nav
        "nav_create": "Create", "nav_menu": "Full Menu", "nav_history": "My Recipes",
        # Hero
        "hero_eyebrow": "Gastronomic Intelligence",
        "hero_headline1": "Your kitchen brigade",
        "hero_headline2": "augmented.",
        "hero_desc": "Enter your ingredients. ChefMind creates an exceptional gourmet recipe — Michelin technique, financial analysis, wine pairings — in seconds.",
        "stat1_num": "20+", "stat1_lbl": "years of expertise",
        "stat2_num": "∞",  "stat2_lbl": "possible recipes",
        "stat3_num": "3s", "stat3_lbl": "AI generation",
        # Form
        "form_title": "New Creation",
        "label_ingredients": "Available ingredients",
        "hint_ingredients": "comma-separated",
        "label_couverts": "Servings",
        "label_budget": "Budget / serving",
        "label_style": "Cuisine style",
        "label_allergenes": "Allergens to exclude",
        "label_type": "Dish type",
        "label_niveau": "Skill level",
        "placeholder_ingredients": "e.g. tuna fillet, coconut milk, lime, ginger, black sesame…",
        "placeholder_budget": "e.g. $8",
        "btn_generate": "✦  Create the recipe",
        "btn_login_required": "✦  Login to generate",
        "btn_limit": "✦  Limit reached",
        "type_all": "Any type",
        "type_cold_starter": "Cold starter",
        "type_warm_starter": "Warm starter",
        "type_main": "Main course",
        "type_dessert": "Dessert",
        "type_amuse": "Amuse-bouche",
        "type_sauce": "Sauce / Condiment",
        "level_all": "Any level",
        "level_easy": "Easy", "level_medium": "Intermediate",
        "level_advanced": "Advanced", "level_expert": "Expert",
        # Styles / allergens
        "style_polynesian": "Polynesian", "style_french": "French classic",
        "style_asian": "Asian fusion", "style_mediterranean": "Mediterranean",
        "style_gastro": "Gastronomic", "style_street": "Street food", "style_japanese": "Japanese",
        "aller_gluten": "Gluten", "aller_lactose": "Lactose", "aller_eggs": "Eggs",
        "aller_nuts": "Tree nuts", "aller_shellfish": "Shellfish",
        "aller_fish": "Fish", "aller_soy": "Soy",
        # Paywall
        "paywall_msg": "Your 3 free recipes are used up this month.",
        "btn_go_pro": "✦ Go Pro — $49/month",
        # Result sections
        "section_prep": "Mise en place", "section_technique": "Technique",
        "section_dressage": "Plating & presentation", "section_note": "Chef's Note",
        "meta_prep": "Prep", "meta_cook": "Cook", "meta_total": "Total",
        "meta_servings": "Servings", "meta_level": "Level",
        # Actions
        "action_pdf": "PDF Sheet", "action_scale": "Adjust servings",
        "action_variantes": "Creative variants",
        # Side panel
        "side_finance": "Financial Analysis", "side_nutrition": "Nutritional Values",
        "side_wine": "Wine Pairings", "side_allergens": "Allergens",
        "cost_per_serving": "Cost / serving", "suggested_price": "Suggested price",
        "gross_margin": "Gross margin",
        # Scale
        "scale_label": "Recalculate for", "scale_unit": "servings",
        "btn_recalculate": "Recalculate",
        # Menu
        "menu_title": "Full Menu", "menu_desc_txt": "Generate a cohesive menu — starter, main, dessert — with service timing and wine pairing.",
        "label_theme": "Theme / Style", "label_saison": "Season",
        "btn_generate_menu": "✦  Generate the menu",
        "menu_evening": "Evening menu", "menu_cost": "Total cost / serving",
        "menu_price": "Suggested price", "menu_margin": "Gross margin",
        "menu_timing": "Service timing", "menu_wine": "Wine pairing",
        "cat_starter": "Starter", "cat_main": "Main course", "cat_dessert": "Dessert",
        "cost_serving": "Cost / serving",
        # History
        "hist_title": "My Recipes", "hist_empty": "No recipes generated yet.",
        "btn_clear_all": "Clear all",
        # Auth
        "auth_login": "Login", "auth_register": "Create account",
        "auth_email": "Email", "auth_password": "Password", "auth_name": "Full name",
        "auth_placeholder_email": "chef@restaurant.com",
        "auth_placeholder_pass": "••••••••",
        "auth_placeholder_name": "Benjamin Martin",
        "auth_placeholder_pass_min": "6 characters minimum",
        "btn_login": "Log in", "btn_register": "Create my account",
        "auth_free_note": "3 free recipes · No credit card required",
        "auth_err_fields": "Please fill in all fields.",
        "auth_err_pass": "Password: 6 characters minimum.",
        "auth_err_email": "Invalid email.",
        "auth_err_exists": "Account already exists.",
        "auth_err_wrong": "Incorrect email or password.",
        # Pricing
        "pricing_title": "Go Pro",
        "pricing_sub": "Unlimited generation + all premium features",
        "pricing_stripe": "🔒 Secure Stripe payment · Cancel anytime · No commitment",
        "plan_free": "Free", "plan_pro": "Pro",
        "feat_3recipes": "3 recipes / month",
        "feat_pdf": "Technical PDF sheet",
        "feat_finance": "Financial analysis",
        "feat_hist30": "30 recipe history",
        "feat_unlimited": "Unlimited recipes",
        "feat_menu": "Unlimited full menus",
        "feat_variantes": "Creative variants",
        "feat_wine": "Premium wine pairings",
        "feat_nutri": "Nutritional values",
        "feat_export": "Professional PDF export",
        "feat_hist_unlimited": "Unlimited history",
        "btn_continue_free": "Continue free",
        "btn_subscribe": "Subscribe — $49/month",
        # Toasts
        "toast_welcome": "Welcome", "toast_created": "Account created! 3 free recipes available.",
        "toast_logout": "See you soon!", "toast_pro": "🌟 ChefMind Pro activated! Unlimited generation.",
        "toast_scaled": "Recalculated for", "toast_servings": "servings",
        "toast_pdf_gen": "📄 Generating PDF…", "toast_pdf_done": "✅ PDF downloaded!",
        # Language
        "lang_label": "Language",
        "lang_auto": "Auto-detect",
    }

# ── GENERATE RECIPE ───────────────────────────────────────────
@app.route("/api/generate", methods=["POST"])
def generate():
    try:
        require_client()
        d = request.json or {}
        ingredients = d.get("ingredients","").strip()
        if not ingredients:
            return jsonify({"ok":False,"error":"Missing ingredients"}), 400

        couverts   = d.get("couverts","4")
        budget     = d.get("budget","not specified")
        type_plat  = d.get("typePlat","any")
        styles     = d.get("styles",[])
        allergenes = d.get("allergenes",[])
        niveau     = d.get("niveau","")
        lang       = d.get("lang","en")
        lang_name  = LANGUAGES.get(lang,"English")

        prompt = f"""You are a 3-Michelin-star chef. Create an exceptional gourmet recipe.
ALL text values in the JSON response must be written in {lang_name}.

PARAMETERS:
Ingredients: {ingredients} | Servings: {couverts} | Type: {type_plat or "any"}
Style: {", ".join(styles) or "Free"} | Excluded allergens: {", ".join(allergenes) or "none"}
Budget/serving: {budget} | Level: {niveau or "any"}

Return ONLY this complete JSON (decimal numbers for costs, no units in numeric fields):
{{
  "nom": "Poetic short name",
  "sous_titre": "Evocative description",
  "histoire": "2 inspiring sentences about origin and terroir",
  "temps_prep": "25 min", "temps_cuisson": "15 min", "temps_total": "40 min",
  "difficulte": "Intermediate", "temperature_service": "Hot", "saison": "All seasons",
  "ingredients": [{{"nom":"Ingredient","quantite":"200g","cout_estime":2.50,"preparation":"finely sliced"}}],
  "etapes": [{{"numero":1,"titre":"Short title","description":"Precise technical description","duree":"5 min","astuce":"Pro tip"}}],
  "dressage": "Precise plating instructions",
  "accords_vins": [{{"type":"Dry white","region":"Burgundy","cepage":"Chardonnay","pourquoi":"Perfect balance because..."}}],
  "valeurs_nutritionnelles": {{"calories":320,"proteines":"28g","glucides":"12g","lipides":"18g","fibres":"3g"}},
  "cout_matiere_total": 18.50, "cout_par_couvert": 4.62,
  "prix_vente_suggere": 24.00, "marge_brute_pct": 81,
  "allergenes_presents": [], "allergenes_absents": ["Gluten","Lactose","Eggs","Tree nuts","Shellfish","Fish","Soy"],
  "tags": ["umami","fusion","quick"],
  "note_chef": "Signature technical tip",
  "variante": "Creative variation of the dish"
}}"""

        recipe = ask(prompt, max_tokens=6000, lang=lang)
        return jsonify({"ok":True,"recipe":recipe})
    except Exception as e:
        return jsonify({"ok":False,"error":str(e)}), 500

# ── MENU COMPLET ──────────────────────────────────────────────
@app.route("/api/menu", methods=["POST"])
def generate_menu():
    try:
        require_client()
        d = request.json or {}
        lang = d.get("lang","en")
        lang_name = LANGUAGES.get(lang,"English")

        prompt = f"""You are a Michelin-starred chef. Create a complete, coherent menu (starter + main + dessert).
ALL text values must be in {lang_name}.

Theme: {d.get("theme","Gastronomic")} | Servings: {d.get("couverts","4")}
Total budget/serving: {d.get("budget","40")} | Season: {d.get("saison","All seasons")}
Excluded allergens: {", ".join(d.get("allergenes",[])) or "none"}

JSON:
{{"nom_menu":"Menu name","description":"Concept in 1 sentence",
"entree":{{"nom":"...","sous_titre":"...","temps_total":"X min","ingredients":[{{"nom":"...","quantite":"..."}}],"etapes":["..."],"cout_par_couvert":0.00,"note_chef":"..."}},"plat":{{"nom":"...","sous_titre":"...","temps_total":"X min","ingredients":[{{"nom":"...","quantite":"..."}}],"etapes":["..."],"cout_par_couvert":0.00,"note_chef":"..."}},"dessert":{{"nom":"...","sous_titre":"...","temps_total":"X min","ingredients":[{{"nom":"...","quantite":"..."}}],"etapes":["..."],"cout_par_couvert":0.00,"note_chef":"..."}},"accord_vin_menu":{{"vin":"...","region":"...","pourquoi":"..."}},"cout_total_par_couvert":0.00,"prix_menu_suggere":0.00,"marge_pct":0,"timing_service":"Service timing description"}}"""

        menu = ask(prompt, max_tokens=8000, lang=lang)
        return jsonify({"ok":True,"menu":menu})
    except Exception as e:
        return jsonify({"ok":False,"error":str(e)}), 500

# ── VARIANTES ─────────────────────────────────────────────────
@app.route("/api/variantes", methods=["POST"])
def get_variantes():
    try:
        require_client()
        d = request.json or {}
        recipe = d.get("recipe",{})
        lang = d.get("lang","en")
        lang_name = LANGUAGES.get(lang,"English")

        prompt = f"""Michelin chef. Suggest 3 creative variants of this recipe: {recipe.get("nom","")}.
Original ingredients: {", ".join([i["nom"] for i in recipe.get("ingredients",[])])}
ALL text in {lang_name}.

JSON:
{{"variantes":[
  {{"nom":"Variant 1","sous_titre":"...","changements":"What changes","difficulte":"Easy","impact_cout":"±X per serving"}},
  {{"nom":"Variant 2","sous_titre":"...","changements":"What changes","difficulte":"Intermediate","impact_cout":"±X per serving"}},
  {{"nom":"Variant 3","sous_titre":"...","changements":"What changes","difficulte":"Advanced","impact_cout":"±X per serving"}}
]}}"""

        result = ask(prompt, max_tokens=2000, lang=lang)
        return jsonify({"ok":True,"variantes":result.get("variantes",[])})
    except Exception as e:
        return jsonify({"ok":False,"error":str(e)}), 500

# ── SCALE ─────────────────────────────────────────────────────
@app.route("/api/scale", methods=["POST"])
def scale_recipe():
    try:
        d = request.json or {}
        recipe  = d.get("recipe",{})
        old_cov = float(d.get("old_couverts",4))
        new_cov = float(d.get("new_couverts",4))
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
        for ing in recipe.get("ingredients",[]):
            si = dict(ing)
            si["quantite"] = scale_qty(ing.get("quantite",""))
            si["cout_estime"] = round(float(ing.get("cout_estime",0)) * ratio, 2)
            scaled_ings.append(si)

        scaled = dict(recipe)
        scaled["ingredients"]        = scaled_ings
        scaled["cout_matiere_total"] = round(float(recipe.get("cout_matiere_total",0)) * ratio, 2)
        scaled["cout_par_couvert"]   = round(float(recipe.get("cout_par_couvert",0)), 2)
        scaled["prix_vente_suggere"] = round(float(recipe.get("prix_vente_suggere",0)), 2)
        return jsonify({"ok":True,"recipe":scaled,"new_couverts":int(new_cov)})
    except Exception as e:
        return jsonify({"ok":False,"error":str(e)}), 500

# ── PDF EXPORT ────────────────────────────────────────────────
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
        r = d.get("recipe",{})
        couverts   = d.get("couverts","4")
        restaurant = d.get("restaurant","ChefMind")

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
            leftMargin=2*cm, rightMargin=2*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)

        GOLD = colors.HexColor("#c9973a")
        DARK = colors.HexColor("#1a1820")
        MUTED= colors.HexColor("#7a7488")

        def sty(name, **kw):
            base={"fontName":"Times-Roman","fontSize":10,"textColor":DARK,"spaceAfter":6,"leading":16}
            base.update(kw); return ParagraphStyle(name,**base)

        styles = {
            "title":   sty("t", fontName="Times-Bold",   fontSize=22, textColor=DARK, spaceAfter=4, leading=26),
            "subtitle":sty("s", fontName="Times-Italic", fontSize=12, textColor=MUTED,spaceAfter=10),
            "section": sty("sc",fontName="Courier-Bold", fontSize=8,  textColor=GOLD, spaceAfter=8, spaceBefore=12),
            "body":    sty("b", spaceAfter=8, leading=16),
            "bold":    sty("bo",fontName="Times-Bold",   spaceAfter=4),
            "small":   sty("sm",fontName="Courier",      fontSize=8,  textColor=MUTED,spaceAfter=4),
            "note":    sty("n", fontName="Times-Italic", fontSize=9.5,textColor=DARK, leftIndent=12, spaceAfter=8, leading=15),
            "center":  sty("c", fontSize=9, textColor=MUTED, alignment=TA_CENTER, spaceAfter=4),
        }

        story = []
        story.append(Paragraph(f"✦ {restaurant.upper()} · PROFESSIONAL RECIPE SHEET", styles["small"]))
        story.append(HRFlowable(width="100%", thickness=0.8, color=GOLD, spaceAfter=14))
        story.append(Paragraph(r.get("nom",""), styles["title"]))
        story.append(Paragraph(r.get("sous_titre",""), styles["subtitle"]))
        if r.get("histoire"):
            story.append(Paragraph(r["histoire"], styles["note"]))
        story.append(Spacer(1, 0.3*cm))

        meta_data = [
            ["PREP","COOK","TOTAL","SERVINGS","LEVEL","SEASON"],
            [r.get("temps_prep","—"),r.get("temps_cuisson","—"),r.get("temps_total","—"),
             str(couverts),r.get("difficulte","—"),r.get("saison","—")]
        ]
        mt = Table(meta_data, colWidths=[2.7*cm]*6)
        mt.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),DARK),("TEXTCOLOR",(0,0),(-1,0),GOLD),
            ("FONTNAME",(0,0),(-1,0),"Courier-Bold"),("FONTSIZE",(0,0),(-1,0),6.5),
            ("FONTNAME",(0,1),(-1,1),"Times-Bold"),("FONTSIZE",(0,1),(-1,1),10),
            ("TEXTCOLOR",(0,1),(-1,1),DARK),("ALIGN",(0,0),(-1,-1),"CENTER"),
            ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#e0dcd4")),
            ("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8),
        ]))
        story.append(mt)
        story.append(Spacer(1, 0.5*cm))

        story.append(HRFlowable(width="100%", thickness=0.3, color=colors.HexColor("#e0dcd4")))
        story.append(Paragraph("INGREDIENTS — MISE EN PLACE", styles["section"]))
        ing_data = [["INGREDIENT","QUANTITY","PREPARATION","COST"]]
        for ing in r.get("ingredients",[]):
            ing_data.append([ing.get("nom",""),ing.get("quantite",""),ing.get("preparation","—"),
                f"{float(ing.get('cout_estime',0)):.2f}"])
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
        story.append(it)
        story.append(Spacer(1,0.5*cm))

        story.append(HRFlowable(width="100%",thickness=0.3,color=colors.HexColor("#e0dcd4")))
        story.append(Paragraph("TECHNIQUE", styles["section"]))
        for i, etape in enumerate(r.get("etapes",[])):
            if isinstance(etape,dict):
                num=etape.get("numero",i+1); titre=etape.get("titre","")
                desc=etape.get("description",""); duree=etape.get("duree",""); tip=etape.get("astuce","")
                hdr=f"<b>{str(num).zfill(2)}. {titre}</b>"
                if duree: hdr+=f"  <font color='#7a7488'>— {duree}</font>"
                story.append(Paragraph(hdr,styles["bold"]))
                story.append(Paragraph(desc,styles["body"]))
                if tip: story.append(Paragraph(f"✦ {tip}",styles["note"]))
            else:
                story.append(Paragraph(f"• {etape}",styles["body"]))

        if r.get("dressage"):
            story.append(HRFlowable(width="100%",thickness=0.3,color=colors.HexColor("#e0dcd4")))
            story.append(Paragraph("PLATING & PRESENTATION",styles["section"]))
            story.append(Paragraph(r["dressage"],styles["note"]))

        if r.get("note_chef"):
            story.append(HRFlowable(width="100%",thickness=0.5,color=GOLD))
            story.append(Paragraph("CHEF'S NOTE",styles["section"]))
            story.append(Paragraph(f"« {r['note_chef']} »",styles["note"]))

        story.append(HRFlowable(width="100%",thickness=0.3,color=colors.HexColor("#e0dcd4")))
        story.append(Paragraph("FINANCIAL ANALYSIS",styles["section"]))
        fin_data=[
            ["Total food cost",f"{float(r.get('cout_matiere_total',0)):.2f}"],
            ["Cost per serving",f"{float(r.get('cout_par_couvert',0)):.2f}"],
            ["Suggested price",f"{float(r.get('prix_vente_suggere',0)):.2f}"],
            ["Gross margin",f"{r.get('marge_brute_pct',0)}%"],
        ]
        ft=Table(fin_data,colWidths=[10*cm,6*cm])
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

        pres=r.get("allergenes_presents",[]); abs_=r.get("allergenes_absents",[])
        if pres or abs_:
            story.append(Spacer(1,0.4*cm))
            story.append(Paragraph("ALLERGENS",styles["section"]))
            if pres: story.append(Paragraph("<font color='#e87a92'>"+" | ".join([f"⚠ {a}" for a in pres])+"</font>",styles["small"]))
            if abs_: story.append(Paragraph("<font color='#7ab890'>"+" | ".join([f"✓ {a}" for a in abs_])+"</font>",styles["small"]))

        vins=r.get("accords_vins",[])
        if vins:
            story.append(Spacer(1,0.3*cm))
            story.append(Paragraph("WINE PAIRINGS",styles["section"]))
            for v in vins:
                story.append(Paragraph(f"<b>{v.get('type','')} — {v.get('cepage','')} — {v.get('region','')}</b>",styles["bold"]))
                story.append(Paragraph(v.get("pourquoi",""),styles["body"]))

        story.append(Spacer(1,0.6*cm))
        story.append(HRFlowable(width="100%",thickness=0.8,color=GOLD))
        story.append(Spacer(1,0.2*cm))
        story.append(Paragraph(
            f"Generated by ChefMind — Gastronomic Intelligence  ·  {datetime.now().strftime('%d %B %Y')}  ·  {couverts} servings",
            styles["center"]))

        doc.build(story)
        buf.seek(0)
        safe = re.sub(r'[^a-zA-Z0-9]','_', r.get('nom','recipe'))
        return send_file(buf, mimetype="application/pdf",
            as_attachment=True, download_name=f"recipe_{safe}.pdf")

    except ImportError:
        return jsonify({"ok":False,"error":"ReportLab not installed"}), 500
    except Exception as e:
        return jsonify({"ok":False,"error":str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0", port=port, debug=False)
