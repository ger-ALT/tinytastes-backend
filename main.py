import sqlite3
import json
import os
import tempfile
import urllib.request
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator
from openai import OpenAI

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL   = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DB_PATH          = os.getenv("DB_PATH", "tinytastes_core.db")
AI_PROVIDER      = os.getenv("AI_PROVIDER", "deepseek")   # "deepseek" | "ollama"
OLLAMA_MODEL     = os.getenv("OLLAMA_MODEL", "qwen3.5:latest")
OLLAMA_URL       = os.getenv("OLLAMA_URL", "http://localhost:11434")

SYSTEM_PROMPT = """You are a Pediatric Nutritionist AI for TinyTastes.
Generate safe, age-appropriate baby food recipes. Respond with valid JSON only — no prose, no markdown fences.

MEDICAL RULES:
- Never suggest honey or cow's milk for infants under 12 months.
- Populate allergen_flags for: peanuts, eggs, fish, dairy, gluten, soy, tree nuts.
- Scale preparation steps to match the texture_milestone (puree=fully smooth, chunky=soft lumps, finger_food=graspable soft pieces).
- ingredients_required must list every ingredient the recipe needs, not just what the user provided.
- Always include serving_size appropriate for the baby's age_months. Newborns (4-6m): 1-2 tbsp. Mid (7-9m): 3-4 tbsp. Older (10-12m): 4-6 tbsp. Toddlers (12m+): small bowl.

SIMPLICITY RULES:
- Baby food must always be simple. Never create complex or multi-layered recipes.
- If more than 4 ingredients are provided, pick the 3-4 most nutritionally complementary ones and ignore the rest.
- Preparation steps must be 4-6 steps maximum — simple enough for a parent to follow quickly.
- Flavour should be mild. No strong spices, no heavy seasoning.
- Always prioritise digestibility and safety over variety.

OUTPUT FORMAT (JSON, no other text):
{
  "recipe_name": "string",
  "suitability_score": 1-10 integer,
  "allergen_flags": ["string"],
  "preparation_steps": ["string"],
  "texture_modification_notes": "string",
  "regional_substitute_suggestions": ["string"],
  "ingredients_required": ["string"],
  "serving_size": "string (e.g. '2-3 tablespoons per meal')",
  "storage_instructions": "string (e.g. 'Refrigerate up to 2 days, freeze up to 1 month')"
}"""


# ---------------------------------------------------------------------------
# DeepSeek client (lazy singleton)
# ---------------------------------------------------------------------------
_client: Optional[OpenAI] = None

def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not DEEPSEEK_API_KEY:
            raise RuntimeError("DEEPSEEK_API_KEY environment variable is not set")
        _client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    return _client


# ---------------------------------------------------------------------------
# Ollama call (native API — handles Qwen3 thinking mode correctly)
# ---------------------------------------------------------------------------
def _call_ollama(prompt_input: dict) -> "AIRecipeOutput":
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": json.dumps(prompt_input)},
        ],
        "think":  False,
        "format": "json",
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data    = json.loads(resp.read())
        content = data["message"]["content"]
        # Trim to outermost { }
        start, end = content.find("{"), content.rfind("}")
        if start == -1 or end == -1:
            raise ValueError(f"No JSON object in Ollama response: {content[:200]}")
        return AIRecipeOutput.model_validate_json(content[start:end + 1])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------
class RecipeRequest(BaseModel):
    user_region: str
    available_ingredients: List[str]
    baby_age_months: int
    texture_milestone: str
    custom_constraints: Optional[str] = None
    known_allergens: List[str] = []

    @field_validator("available_ingredients")
    @classmethod
    def limit_ingredients(cls, v: List[str]) -> List[str]:
        return v[:6]  # cap at 6 — LLM prompt further reduces to 3-4 best

    @field_validator("texture_milestone")
    @classmethod
    def validate_texture(cls, v: str) -> str:
        allowed = {"puree", "chunky", "finger_food"}
        if v.lower() not in allowed:
            raise ValueError(f"texture_milestone must be one of {sorted(allowed)}")
        return v.lower()

    @field_validator("baby_age_months")
    @classmethod
    def validate_age(cls, v: int) -> int:
        if not (4 <= v <= 36):
            raise ValueError("baby_age_months must be between 4 and 36")
        return v


class AffiliateLink(BaseModel):
    item: str
    action_url: str


class RecipeResponseSchema(BaseModel):
    recipe_name: str
    suitability_score: int
    allergen_flags: List[str]
    preparation_steps: List[str]
    texture_modification_notes: str
    regional_substitute_suggestions: List[str]
    affiliate_links: List[AffiliateLink] = []
    serving_size: str = ""
    storage_instructions: str = ""
    allergen_warning: List[str] = []


class AIRecipeOutput(BaseModel):
    recipe_name: str
    suitability_score: int
    allergen_flags: List[str]

    @field_validator("suitability_score")
    @classmethod
    def clamp_score(cls, v: int) -> int:
        return max(1, min(10, v))

    preparation_steps: List[str]
    texture_modification_notes: str
    regional_substitute_suggestions: List[str]
    ingredients_required: List[str]
    serving_size: str = ""
    storage_instructions: str = ""


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recipes (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                ingredient_key   TEXT    NOT NULL,
                target_texture   TEXT    NOT NULL,
                recipe_name      TEXT    NOT NULL,
                preparation_steps TEXT   NOT NULL,
                full_ingredients  TEXT   NOT NULL,
                allergen_flags    TEXT   NOT NULL DEFAULT '[]',
                timestamp        DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historical_recipes (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                age_months        INTEGER,
                ingredients_input TEXT,
                recipe_output     TEXT,
                timestamp         DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        _seed_recipes(cursor, conn)


def _seed_recipes(cursor: sqlite3.Cursor, conn: sqlite3.Connection) -> None:
    cursor.execute("SELECT COUNT(*) FROM recipes")
    if cursor.fetchone()[0] > 0:
        return

    seed = [
        # ── Purees ──────────────────────────────────────────────────────────
        ("apple,sweet potato", "puree", "Apple Sweet Potato Puree",
         '["Peel and dice 1 apple and 1 sweet potato.", "Steam for 10–12 minutes until very soft.", "Blend with 2–3 tbsp water until completely smooth.", "Cool to room temperature before serving."]',
         '["apple", "sweet potato"]', '[]'),

        ("banana,avocado", "puree", "Banana Avocado Mash",
         '["Mash half a ripe banana with a fork.", "Mash a quarter of a ripe avocado.", "Combine and mix until smooth.", "Serve immediately — do not store."]',
         '["banana", "avocado"]', '[]'),

        ("carrot,pea", "puree", "Carrot Pea Puree",
         '["Steam 2 medium carrots and ¼ cup peas for 8 minutes.", "Blend together with a splash of water.", "Pass through a fine sieve for extra smoothness.", "Cool before serving."]',
         '["carrot", "pea"]', '[]'),

        ("butternut squash", "puree", "Butternut Squash Puree",
         '["Halve squash and remove seeds.", "Roast cut-side down at 375°F for 45 minutes.", "Scoop flesh and blend until silky.", "Thin with breast milk or formula if needed."]',
         '["butternut squash"]', '[]'),

        ("broccoli,potato", "puree", "Broccoli Potato Puree",
         '["Dice 1 medium potato and steam with broccoli florets for 10 minutes.", "Blend with 3 tbsp water until smooth.", "Check temperature before serving."]',
         '["broccoli", "potato"]', '[]'),

        ("mango,banana", "puree", "Mango Banana Puree",
         '["Peel and chop a ripe mango.", "Blend with half a banana until completely smooth.", "No cooking required for ripe fruit.", "Refrigerate up to 24 hours."]',
         '["mango", "banana"]', '[]'),

        ("pear,spinach", "puree", "Pear Spinach Puree",
         '["Core and cube 1 ripe pear.", "Steam with a handful of spinach for 5 minutes.", "Blend until very smooth.", "Strain through a sieve if needed."]',
         '["pear", "spinach"]', '[]'),

        # ── Chunky ──────────────────────────────────────────────────────────
        ("carrot,chicken,potato", "chunky", "Chicken & Vegetable Stew",
         '["Dice chicken breast into small pieces.", "Chop carrot and potato into pea-sized cubes.", "Simmer all ingredients in low-sodium broth for 20 minutes.", "Mash lightly — leave soft lumps.", "Cool and serve."]',
         '["chicken", "carrot", "potato"]', '[]'),

        ("carrot,lentil,tomato", "chunky", "Red Lentil & Vegetable Dhal",
         '["Rinse ¼ cup red lentils.", "Simmer with diced carrot and tomato in 1 cup water for 15 minutes.", "Mash to chunky consistency.", "A pinch of mild cumin is fine for babies over 8 months.", "Cool before serving."]',
         '["lentil", "tomato", "carrot"]', '[]'),

        ("avocado,egg", "chunky", "Avocado Egg Scramble",
         '["Whisk one large egg.", "Scramble over low heat until just set — small soft curds.", "Mash in a quarter of a ripe avocado.", "Break into small pieces and cool slightly.", "Serve warm."]',
         '["avocado", "egg"]', '["egg"]'),

        ("banana,oat", "chunky", "Banana Oat Porridge",
         '["Cook ¼ cup oats in ½ cup water for 3–4 minutes.", "Mash in half a ripe banana.", "Leave slightly lumpy to encourage chewing practice.", "Cool to a warm serving temperature."]',
         '["banana", "oat"]', '["gluten"]'),

        ("black bean,sweet potato", "chunky", "Sweet Potato Black Bean Mash",
         '["Bake or microwave sweet potato until very tender.", "Mash with a fork, leaving some texture.", "Stir in 2 tbsp rinsed black beans.", "Serve warm."]',
         '["sweet potato", "black bean"]', '[]'),

        ("pasta,pea", "chunky", "Pea & Pasta Mini",
         '["Cook star-shaped pasta or orzo until very soft.", "Stir in cooked peas.", "Lightly mash with a fork to break some peas.", "Serve at room temperature."]',
         '["pea", "pasta"]', '["gluten"]'),

        # ── Finger Foods ─────────────────────────────────────────────────────
        ("banana", "finger_food", "Banana Fingers",
         '["Peel a firm-ripe banana.", "Cut into 3-inch finger-length strips.", "The natural stickiness helps baby grip safely.", "Serve as-is — no preparation needed."]',
         '["banana"]', '[]'),

        ("blueberry,ricotta", "finger_food", "Blueberry Ricotta Bites",
         '["Halve fresh blueberries lengthwise to remove choking risk.", "Mix with 2 tbsp ricotta.", "Form into small bite-sized mounds.", "Chill briefly to firm up, then serve."]',
         '["blueberry", "ricotta"]', '["dairy"]'),

        ("egg,spinach", "finger_food", "Spinach Egg Mini Frittata",
         '["Whisk 2 eggs with a handful of finely chopped spinach.", "Pour into a greased mini muffin tin.", "Bake at 350°F for 12 minutes until set.", "Cool, then cut into finger-sized strips.", "Refrigerate leftovers up to 2 days."]',
         '["egg", "spinach"]', '["egg"]'),

        ("chickpea,sweet potato", "finger_food", "Sweet Potato Chickpea Patties",
         '["Mash ½ cup cooked sweet potato with ¼ cup chickpeas.", "Form into small flat patties.", "Pan-fry in a drop of olive oil for 3 minutes each side.", "Cool — patties should squish easily between fingers."]',
         '["sweet potato", "chickpea"]', '[]'),

        ("apple,cinnamon", "finger_food", "Soft Cinnamon Apple Wedges",
         '["Peel and slice apple into thin wedges.", "Steam for 5–6 minutes until very soft but holding shape.", "Dust lightly with a pinch of cinnamon.", "Cool to room temperature before serving."]',
         '["apple", "cinnamon"]', '[]'),

        ("cheese,zucchini", "finger_food", "Cheesy Zucchini Sticks",
         '["Cut zucchini into 2-inch sticks.", "Roast at 400°F for 15 minutes until soft and slightly golden.", "Sprinkle with grated mild cheese in the last 2 minutes.", "Cool and serve as soft finger food."]',
         '["zucchini", "cheese"]', '["dairy"]'),

        ("banana,blueberry,oat", "finger_food", "Baby Oat Pancakes",
         '["Mash 1 ripe banana, mix with ¼ cup oats and 1 egg.", "Fold in a few halved blueberries.", "Drop small spoonfuls onto a non-stick pan over low heat.", "Cook 2 minutes each side.", "Slice into finger strips when cool."]',
         '["oat", "banana", "blueberry", "egg"]', '["egg", "gluten"]'),
    ]

    cursor.executemany(
        "INSERT INTO recipes (ingredient_key, target_texture, recipe_name, preparation_steps, full_ingredients, allergen_flags) VALUES (?,?,?,?,?,?)",
        seed,
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Affiliate links
# ---------------------------------------------------------------------------
# Items always assumed to be at home — never generate affiliate links for these
PANTRY_STAPLES = {
    "water", "salt", "black salt", "rock salt", "pink salt",
    "oil", "cooking oil", "vegetable oil", "sunflower oil",
    "butter",
    "sugar", "jaggery",
    "black pepper", "pepper",
}

# Specialty / expensive items — always show a link even if user said they have it
SPECIALTY_ITEMS = {
    "ragi", "ragi flour", "jowar", "bajra", "sattu",
    "paneer", "tofu",
    "avocado",
    "blueberry", "blueberries",
    "ricotta", "cream cheese",
    "saffron",
    "ghee", "a2 ghee", "desi ghee",
    "quinoa",
    "chia seeds", "flax seeds",
    "almond flour", "coconut flour",
    "formula", "breast milk",
}

def generate_affiliate_links(available: List[str], required: List[str], region: str) -> List[AffiliateLink]:
    available_set = {i.lower().strip() for i in available}
    links = []
    seen  = set()
    for item in required:
        key = item.lower().strip()
        if key in seen or key in PANTRY_STAPLES:
            continue
        # Show link if: user doesn't have it OR it's a specialty item worth buying premium
        if key not in available_set or key in SPECIALTY_ITEMS:
            links.append(AffiliateLink(
                item=item,
                action_url=f"https://partner-grocery-api.com/v1/checkout?item={item}&region={region}&affiliate_id=tinytastes",
            ))
            seen.add(key)
    return links


# ---------------------------------------------------------------------------
# Allergen normalisation + cross-check
# ---------------------------------------------------------------------------
ALLERGEN_NORMALIZER: dict = {
    "milk / dairy": {"dairy", "milk", "lactose", "cheese", "paneer", "curd", "yogurt", "yoghurt", "ricotta"},
    "eggs": {"egg", "eggs"},
    "peanuts": {"peanut", "peanuts"},
    "tree nuts": {"tree nuts", "nuts", "almond", "cashew", "walnut", "pistachio"},
    "wheat / gluten": {"gluten", "wheat"},
    "fish": {"fish"},
    "soy": {"soy", "soya", "tofu"},
}

def check_allergen_overlap(known_allergens: List[str], recipe_flags: List[str]) -> List[str]:
    recipe_set = {f.lower().strip() for f in recipe_flags}
    warnings = []
    for known in known_allergens:
        triggers = ALLERGEN_NORMALIZER.get(known.lower().strip(), {known.lower().strip()})
        if triggers & recipe_set:
            warnings.append(known)
    return warnings


# ---------------------------------------------------------------------------
# Layer 1: deterministic DB lookup
# ---------------------------------------------------------------------------
def check_local_database(ingredients: List[str], texture: str) -> Optional[dict]:
    sorted_key = ",".join(sorted(i.lower().strip() for i in ingredients))
    user_set = set(sorted_key.split(","))

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        # Exact match first
        cursor.execute(
            "SELECT recipe_name, preparation_steps, full_ingredients, allergen_flags "
            "FROM recipes WHERE ingredient_key = ? AND target_texture = ?",
            (sorted_key, texture.lower()),
        )
        row = cursor.fetchone()
        if row:
            return _build_cache_result(row)

        # Subset match: find best cached recipe whose ingredients the user has
        cursor.execute(
            "SELECT recipe_name, preparation_steps, full_ingredients, allergen_flags, ingredient_key "
            "FROM recipes WHERE target_texture = ?",
            (texture.lower(),),
        )
        best_row, best_overlap = None, 0
        for r in cursor.fetchall():
            cached_set = set(r[4].split(","))
            if cached_set.issubset(user_set) and len(cached_set) > best_overlap:
                best_row, best_overlap = r, len(cached_set)
        if best_row:
            return _build_cache_result(best_row[:4])

    return None

def _build_cache_result(row) -> dict:
    return {
        "recipe_name": row[0],
        "suitability_score": 10,
        "allergen_flags": json.loads(row[3]),
        "preparation_steps": json.loads(row[1]),
        "texture_modification_notes": "Verified standard pediatric recipe profile.",
        "regional_substitute_suggestions": [],
        "serving_size": "",
        "storage_instructions": "",
        "_full_ingredients": json.loads(row[2]),
    }


# ---------------------------------------------------------------------------
# Core recipe logic
# ---------------------------------------------------------------------------
async def _get_recipe(request: RecipeRequest) -> RecipeResponseSchema:
    cached = check_local_database(request.available_ingredients, request.texture_milestone)
    if cached and not request.custom_constraints:
        full_ingredients: List[str] = cached.pop("_full_ingredients")
        return RecipeResponseSchema(
            **cached,
            affiliate_links=generate_affiliate_links(
                request.available_ingredients, full_ingredients, request.user_region
            ),
            allergen_warning=check_allergen_overlap(request.known_allergens, cached["allergen_flags"]),
        )

    # Layer 2: AI fallback (DeepSeek or Ollama)
    try:
        prompt_input = {
            "ingredients": request.available_ingredients,
            "age_months": request.baby_age_months,
            "texture_milestone": request.texture_milestone,
            "region": request.user_region,
            "special_notes": request.custom_constraints,
        }
        if AI_PROVIDER == "ollama":
            ai = _call_ollama(prompt_input)
        else:
            response = _get_client().chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(prompt_input)},
                ],
                response_format={"type": "json_object"},
                max_tokens=1024,
            )
            content = response.choices[0].message.content
            ai = AIRecipeOutput.model_validate_json(content)

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO historical_recipes (age_months, ingredients_input, recipe_output) VALUES (?,?,?)",
                (request.baby_age_months, json.dumps(request.available_ingredients), ai.model_dump_json()),
            )

        # Auto-cache to Layer 1 for future instant lookups
        sorted_key = ",".join(sorted(i.lower().strip() for i in request.available_ingredients))
        try:
            with sqlite3.connect(DB_PATH) as conn:
                existing = conn.execute(
                    "SELECT id FROM recipes WHERE ingredient_key = ? AND target_texture = ?",
                    (sorted_key, request.texture_milestone)
                ).fetchone()
                if not existing:
                    conn.execute(
                        "INSERT INTO recipes (ingredient_key, target_texture, recipe_name, preparation_steps, full_ingredients, allergen_flags) VALUES (?,?,?,?,?,?)",
                        (sorted_key, request.texture_milestone, ai.recipe_name,
                         json.dumps(ai.preparation_steps), json.dumps(ai.ingredients_required),
                         json.dumps(ai.allergen_flags))
                    )
        except Exception:
            pass  # auto-cache is non-critical

        return RecipeResponseSchema(
            recipe_name=ai.recipe_name,
            suitability_score=ai.suitability_score,
            allergen_flags=ai.allergen_flags,
            preparation_steps=ai.preparation_steps,
            texture_modification_notes=ai.texture_modification_notes,
            regional_substitute_suggestions=ai.regional_substitute_suggestions,
            affiliate_links=generate_affiliate_links(
                request.available_ingredients, ai.ingredients_required, request.user_region
            ),
            serving_size=ai.serving_size,
            storage_instructions=ai.storage_instructions,
            allergen_warning=check_allergen_overlap(request.known_allergens, ai.allergen_flags),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Engine Failure: {e}")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="TinyTastes AI",
    description="LLM-optional pediatric recipe engine — deterministic fast-path with DeepSeek AI fallback.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.post("/api/v1/get-recipe", response_model=RecipeResponseSchema)
async def process_recipe_engine(request: RecipeRequest):
    return await _get_recipe(request)


@app.post("/api/v1/export-pdf")
async def export_pdf(request: RecipeRequest):
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer
    except ImportError:
        raise HTTPException(status_code=500, detail="reportlab not installed — run: pip install reportlab")

    recipe = await _get_recipe(request)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    doc = SimpleDocTemplate(tmp.name, pagesize=letter, leftMargin=1 * inch, rightMargin=1 * inch)
    styles = getSampleStyleSheet()

    ORANGE = colors.HexColor("#FF6B35")
    title_style = ParagraphStyle("TTTitle", parent=styles["Heading1"], alignment=TA_CENTER, textColor=ORANGE, fontSize=22, spaceAfter=4)
    sub_style = ParagraphStyle("TTSub", parent=styles["Normal"], alignment=TA_CENTER, textColor=colors.HexColor("#666666"), fontSize=10)
    section_style = ParagraphStyle("TTSection", parent=styles["Heading2"], textColor=ORANGE, fontSize=13, spaceBefore=10, spaceAfter=4)
    warn_style = ParagraphStyle("TTWarn", parent=styles["Normal"], textColor=colors.red, fontSize=10)
    body = styles["Normal"]

    story = [
        Paragraph("TinyTastes AI", title_style),
        Paragraph("My Baby's First Foods Journal", sub_style),
        Spacer(1, 0.1 * inch),
        Paragraph(
            f"Age: <b>{request.baby_age_months} months</b> &nbsp;|&nbsp; "
            f"Region: <b>{request.user_region}</b> &nbsp;|&nbsp; "
            f"Texture: <b>{request.texture_milestone}</b>",
            sub_style,
        ),
        Spacer(1, 0.3 * inch),
        Paragraph(recipe.recipe_name, section_style),
        Paragraph(f"Suitability Score: <b>{recipe.suitability_score}/10</b>", body),
        Spacer(1, 0.1 * inch),
    ]

    if recipe.allergen_flags:
        story.append(Paragraph(f"Allergen Warning: {', '.join(recipe.allergen_flags)}", warn_style))
        story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph("Preparation Steps", section_style))
    story.append(
        ListFlowable(
            [ListItem(Paragraph(step, body), leftIndent=20) for step in recipe.preparation_steps],
            bulletType="1",
        )
    )
    story.append(Spacer(1, 0.15 * inch))

    story.append(Paragraph("Texture Notes", section_style))
    story.append(Paragraph(recipe.texture_modification_notes, body))

    if recipe.regional_substitute_suggestions:
        story.append(Spacer(1, 0.1 * inch))
        story.append(Paragraph("Regional Substitutes", section_style))
        story.append(
            ListFlowable(
                [ListItem(Paragraph(s, body), leftIndent=20) for s in recipe.regional_substitute_suggestions],
                bulletType="bullet",
            )
        )

    if recipe.affiliate_links:
        story.append(Spacer(1, 0.1 * inch))
        story.append(Paragraph("Get Missing Ingredients", section_style))
        for link in recipe.affiliate_links:
            story.append(Paragraph(f'<link href="{link.action_url}" color="#FF6B35">{link.item}</link>', body))

    doc.build(story)
    safe_name = recipe.recipe_name.lower().replace(" ", "_")[:40]
    return FileResponse(tmp.name, media_type="application/pdf", filename=f"tinytastes_{safe_name}.pdf")


@app.get("/health")
async def health_check():
    db_ok = False
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("SELECT 1")
        db_ok = True
    except Exception:
        pass

    return {
        "status": "healthy",
        "service": "TinyTastes AI",
        "db": "ok" if db_ok else "error",
        "ai_provider": "DeepSeek",
        "model": DEEPSEEK_MODEL,
        "api_key_set": bool(DEEPSEEK_API_KEY),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
