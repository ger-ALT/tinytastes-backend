import sqlite3
import json
import os
import tempfile
import urllib.parse
import urllib.request
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator
from openai import OpenAI

# Error monitoring — only activates when SENTRY_DSN env var is set
import sentry_sdk
_SENTRY_DSN = os.getenv("SENTRY_DSN", "")
if _SENTRY_DSN:
    sentry_sdk.init(
        dsn=_SENTRY_DSN,
        traces_sample_rate=0.1,
        environment=os.getenv("RAILWAY_ENVIRONMENT", "production"),
    )

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DEEPSEEK_API_KEY    = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL      = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DB_PATH             = os.getenv("DB_PATH", "tinytastes_core.db")
AI_PROVIDER         = os.getenv("AI_PROVIDER", "deepseek")   # "deepseek" | "ollama"
OLLAMA_MODEL        = os.getenv("OLLAMA_MODEL", "qwen3.5:latest")
OLLAMA_URL          = os.getenv("OLLAMA_URL", "http://localhost:11434")
AMAZON_AFFILIATE_TAG = os.getenv("AMAZON_AFFILIATE_TAG", "tinytastes-21")  # set in Railway

# Web Push (VAPID) — generate keys once: python -c "from py_vapid import Vapid; v=Vapid(); v.generate_keys(); print(v.private_key_pem, v.public_key_str)"
VAPID_PRIVATE_KEY   = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC_KEY    = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_CLAIMS        = {"sub": "mailto:hello@tinytastes.in"}

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
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                ingredient_key       TEXT    NOT NULL,
                target_texture       TEXT    NOT NULL,
                recipe_name          TEXT    NOT NULL,
                preparation_steps    TEXT    NOT NULL,
                full_ingredients     TEXT    NOT NULL,
                allergen_flags       TEXT    NOT NULL DEFAULT '[]',
                serving_size         TEXT    NOT NULL DEFAULT '',
                storage_instructions TEXT    NOT NULL DEFAULT '',
                timestamp            DATETIME DEFAULT CURRENT_TIMESTAMP
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
        # Schema migration: add new columns to existing deployments
        for col, default in [("serving_size", "''"), ("storage_instructions", "''")] :
            try:
                cursor.execute(f"ALTER TABLE recipes ADD COLUMN {col} TEXT NOT NULL DEFAULT {default}")
            except Exception:
                pass  # column already exists — skip
        conn.commit()
        _seed_recipes(cursor, conn)


# Storage / serving constants reused in seed data
_STORE_PUREE   = "Refrigerate up to 2 days. Freeze in ice cube trays up to 1 month."
_STORE_CHUNKY  = "Refrigerate up to 2 days. Freeze in portions up to 1 month."
_STORE_FINGER  = "Best served fresh. Refrigerate up to 1 day."
_SERVE_PUREE   = "1-2 tablespoons per meal (increase gradually)"
_SERVE_CHUNKY  = "3-4 tablespoons per meal"
_SERVE_FINGER  = "3-4 pieces per meal, let baby self-feed"


def _seed_recipes(cursor: sqlite3.Cursor, conn: sqlite3.Connection) -> None:
    cursor.execute("SELECT COUNT(*) FROM recipes")
    if cursor.fetchone()[0] > 0:
        return

    # Tuple: (ingredient_key, texture, name, steps_json, ingredients_json, allergens_json, serving_size, storage_instructions)
    seed = [
        # ── Purees (4-7m) ────────────────────────────────────────────────────
        ("apple,sweet potato", "puree", "Apple Sweet Potato Puree",
         '["Peel and dice 1 apple and 1 sweet potato.", "Steam for 10–12 minutes until very soft.", "Blend with 2–3 tbsp water until completely smooth.", "Cool to room temperature before serving."]',
         '["apple", "sweet potato"]', '[]', _SERVE_PUREE, _STORE_PUREE),

        ("banana,avocado", "puree", "Banana Avocado Mash",
         '["Mash half a ripe banana with a fork.", "Mash a quarter of a ripe avocado.", "Combine and mix until smooth.", "Serve immediately."]',
         '["banana", "avocado"]', '[]', _SERVE_PUREE, "Best served fresh — do not store."),

        ("carrot,pea", "puree", "Carrot Pea Puree",
         '["Steam 2 medium carrots and ¼ cup peas for 8 minutes.", "Blend together with a splash of water.", "Pass through a fine sieve for extra smoothness.", "Cool before serving."]',
         '["carrot", "pea"]', '[]', _SERVE_PUREE, _STORE_PUREE),

        ("broccoli,potato", "puree", "Broccoli Potato Puree",
         '["Dice 1 medium potato and steam with broccoli florets for 10 minutes.", "Blend with 3 tbsp water until smooth.", "Check temperature before serving."]',
         '["broccoli", "potato"]', '[]', _SERVE_PUREE, _STORE_PUREE),

        ("mango,banana", "puree", "Mango Banana Puree",
         '["Peel and chop a ripe mango.", "Blend with half a banana until completely smooth.", "No cooking required for ripe fruit.", "Refrigerate up to 24 hours."]',
         '["mango", "banana"]', '[]', _SERVE_PUREE, "Refrigerate up to 24 hours."),

        ("pear,spinach", "puree", "Pear Spinach Puree",
         '["Core and cube 1 ripe pear.", "Steam with a handful of spinach for 5 minutes.", "Blend until very smooth.", "Strain through a sieve if needed."]',
         '["pear", "spinach"]', '[]', _SERVE_PUREE, _STORE_PUREE),

        ("carrot,sweet potato", "puree", "Carrot Sweet Potato Puree",
         '["Peel and dice 1 medium carrot and 1 small sweet potato.", "Steam together for 12 minutes until very soft.", "Blend with 3-4 tbsp water to a smooth puree.", "Cool before serving."]',
         '["carrot", "sweet potato"]', '[]', _SERVE_PUREE, _STORE_PUREE),

        ("potato,carrot", "puree", "Potato Carrot Mash",
         '["Peel and dice 1 potato and 1 carrot.", "Boil in water for 12 minutes until very tender.", "Drain and mash until completely smooth.", "Thin with a little boiled water if needed."]',
         '["potato", "carrot"]', '[]', _SERVE_PUREE, _STORE_PUREE),

        ("moong dal,rice", "puree", "Moong Dal Rice Puree",
         '["Rinse 2 tbsp moong dal and 2 tbsp rice together.", "Cook in 1 cup water on low heat for 15 minutes until very soft.", "Blend to a smooth puree with extra water if needed.", "Add a tiny drop of ghee before serving."]',
         '["moong dal", "rice", "ghee"]', '[]', _SERVE_PUREE, _STORE_PUREE),

        ("banana,ragi", "puree", "Ragi Banana Porridge",
         '["Mix 2 tbsp ragi flour with ½ cup water to form a lump-free slurry.", "Cook on low heat stirring constantly for 4-5 minutes until thick.", "Mash in half a ripe banana and stir well.", "Cool to warm temperature before serving."]',
         '["ragi", "banana"]', '[]', _SERVE_PUREE, "Refrigerate up to 1 day. Best served fresh."),

        ("apple,carrot", "puree", "Apple Carrot Puree",
         '["Peel and dice 1 apple and 1 carrot.", "Steam together for 10 minutes until soft.", "Blend with 2 tbsp water until silky smooth.", "Strain for younger babies under 6 months."]',
         '["apple", "carrot"]', '[]', _SERVE_PUREE, _STORE_PUREE),

        ("papaya", "puree", "Papaya Puree",
         '["Peel ripe papaya and remove seeds.", "Cut into small cubes.", "Blend until completely smooth — no cooking needed.", "Strain through a sieve for younger babies."]',
         '["papaya"]', '[]', _SERVE_PUREE, "Refrigerate up to 1 day."),

        ("sweet potato", "puree", "Sweet Potato Puree",
         '["Peel and dice 1 medium sweet potato.", "Steam for 12-15 minutes until very soft.", "Blend with 3-4 tbsp water until silky smooth.", "Cool before serving."]',
         '["sweet potato"]', '[]', _SERVE_PUREE, _STORE_PUREE),

        ("pumpkin,carrot", "puree", "Pumpkin Carrot Puree",
         '["Peel and dice equal parts pumpkin and carrot.", "Steam for 10 minutes until very soft.", "Blend with a splash of water until smooth.", "Cool and serve."]',
         '["pumpkin", "carrot"]', '[]', _SERVE_PUREE, _STORE_PUREE),

        # ── Chunky (8-10m) ───────────────────────────────────────────────────
        ("carrot,chicken,potato", "chunky", "Chicken Vegetable Stew",
         '["Dice chicken breast into very small pieces.", "Chop carrot and potato into pea-sized cubes.", "Simmer all in 1 cup water for 20 minutes until very soft.", "Mash lightly — leave soft lumps for texture.", "Cool before serving."]',
         '["chicken", "carrot", "potato"]', '[]', _SERVE_CHUNKY, _STORE_CHUNKY),

        ("carrot,lentil,tomato", "chunky", "Red Lentil Vegetable Dal",
         '["Rinse ¼ cup red lentils.", "Simmer with diced carrot and tomato in 1 cup water for 15 minutes.", "Mash to chunky consistency.", "A pinch of mild cumin is fine for babies over 8 months."]',
         '["masoor dal", "tomato", "carrot"]', '[]', _SERVE_CHUNKY, _STORE_CHUNKY),

        ("avocado,egg", "chunky", "Avocado Egg Scramble",
         '["Whisk one large egg.", "Scramble over low heat until just set — small soft curds.", "Mash in a quarter of a ripe avocado.", "Break into small pieces, cool slightly, and serve warm."]',
         '["avocado", "egg"]', '["egg"]', _SERVE_CHUNKY, "Best served fresh."),

        ("banana,oat", "chunky", "Banana Oat Porridge",
         '["Cook ¼ cup oats in ½ cup water for 3–4 minutes.", "Mash in half a ripe banana.", "Leave slightly lumpy to encourage chewing practice.", "Cool to warm temperature."]',
         '["oats", "banana"]', '["gluten"]', _SERVE_CHUNKY, "Refrigerate up to 1 day. Best served fresh."),

        ("black bean,sweet potato", "chunky", "Sweet Potato Black Bean Mash",
         '["Bake or microwave sweet potato until very tender.", "Mash with a fork, leaving some texture.", "Stir in 2 tbsp rinsed and mashed black beans.", "Serve warm."]',
         '["sweet potato", "black bean"]', '[]', _SERVE_CHUNKY, _STORE_CHUNKY),

        ("ghee,moong dal,rice", "chunky", "Classic Khichdi",
         '["Rinse 3 tbsp rice and 2 tbsp moong dal together.", "Cook in 1.5 cups water with a pinch of turmeric for 20 minutes until very soft.", "Mash to a soft, slightly chunky texture.", "Stir in half a teaspoon of ghee before serving."]',
         '["rice", "moong dal", "ghee"]', '[]', _SERVE_CHUNKY, _STORE_CHUNKY),

        ("carrot,dalia (broken wheat)", "chunky", "Dalia Vegetable Khichdi",
         '["Dry roast 3 tbsp dalia (broken wheat) for 2 minutes until fragrant.", "Add diced carrot and 1 cup water, cook covered for 15 minutes.", "Mash lightly with a spoon.", "Add a few drops of ghee and serve warm."]',
         '["dalia (broken wheat)", "carrot", "ghee"]', '["gluten"]', _SERVE_CHUNKY, _STORE_CHUNKY),

        ("carrot,pea,semolina (suji)", "chunky", "Soft Vegetable Upma",
         '["Dry roast 3 tbsp semolina for 2 minutes.", "Add diced carrot and peas with 1 cup water.", "Cook on low heat stirring for 5 minutes until soft.", "Leave slightly grainy — good texture practice."]',
         '["semolina (suji)", "carrot", "pea"]', '["gluten"]', _SERVE_CHUNKY, "Refrigerate up to 1 day."),

        ("banana,curd / yoghurt", "chunky", "Banana Curd Bowl",
         '["Mash half a ripe banana with a fork.", "Mix with 2 tbsp plain full-fat curd.", "Leave slightly lumpy — no cooking required.", "Serve immediately at room temperature."]',
         '["banana", "curd"]', '["dairy"]', _SERVE_CHUNKY, "Serve immediately."),

        ("potato,spinach", "chunky", "Palak Aloo Mash",
         '["Boil 1 potato until very soft, peel and mash.", "Blanch a handful of spinach in hot water for 2 minutes, then puree.", "Mix mashed potato with spinach puree.", "Leave slightly chunky, add a drop of ghee."]',
         '["potato", "spinach", "ghee"]', '[]', _SERVE_CHUNKY, _STORE_CHUNKY),

        ("apple,oat", "chunky", "Apple Oat Porridge",
         '["Peel and grate 1 small apple.", "Cook ¼ cup oats in ½ cup water for 3 minutes.", "Stir in grated apple and cook 1 more minute.", "Leave slightly lumpy — cool before serving."]',
         '["oats", "apple"]', '["gluten"]', _SERVE_CHUNKY, "Refrigerate up to 1 day."),

        # ── Finger Foods (10m+) ──────────────────────────────────────────────
        ("banana", "finger_food", "Banana Fingers",
         '["Peel a firm-ripe banana.", "Cut into 3-inch finger-length strips.", "The natural stickiness helps baby grip safely.", "Serve as-is — no preparation needed."]',
         '["banana"]', '[]', _SERVE_FINGER, "Serve immediately."),

        ("blueberry,ricotta", "finger_food", "Blueberry Ricotta Bites",
         '["Halve fresh blueberries lengthwise to remove choking risk.", "Mix with 2 tbsp ricotta.", "Form into small bite-sized mounds.", "Chill briefly to firm up, then serve."]',
         '["blueberry", "ricotta"]', '["dairy"]', _SERVE_FINGER, _STORE_FINGER),

        ("egg,spinach", "finger_food", "Spinach Egg Mini Frittata",
         '["Whisk 2 eggs with a handful of finely chopped spinach.", "Pour into a greased mini muffin tin.", "Bake at 180°C for 12 minutes until set.", "Cool, then cut into finger-sized strips."]',
         '["egg", "spinach"]', '["egg"]', _SERVE_FINGER, "Refrigerate up to 2 days."),

        ("chickpea,sweet potato", "finger_food", "Sweet Potato Chickpea Patties",
         '["Mash ½ cup cooked sweet potato with ¼ cup chickpeas.", "Form into small flat patties.", "Pan-fry in a drop of oil for 3 minutes each side until golden.", "Cool — patties should squish easily between fingers."]',
         '["sweet potato", "chickpea"]', '[]', _SERVE_FINGER, "Refrigerate up to 2 days."),

        ("apple,cinnamon", "finger_food", "Soft Cinnamon Apple Wedges",
         '["Peel and slice apple into thin wedges.", "Steam for 5–6 minutes until very soft but holding shape.", "Dust lightly with a pinch of cinnamon.", "Cool to room temperature before serving."]',
         '["apple", "cinnamon"]', '[]', _SERVE_FINGER, _STORE_FINGER),

        ("cheese,zucchini", "finger_food", "Cheesy Zucchini Sticks",
         '["Cut zucchini into 2-inch sticks.", "Roast at 200°C for 15 minutes until soft and slightly golden.", "Sprinkle with grated mild cheese in the last 2 minutes.", "Cool and serve as soft finger food."]',
         '["zucchini", "cheese"]', '["dairy"]', _SERVE_FINGER, _STORE_FINGER),

        ("banana,blueberry,oat", "finger_food", "Baby Oat Pancakes",
         '["Mash 1 ripe banana, mix with ¼ cup oats and 1 egg.", "Fold in a few halved blueberries.", "Drop small spoonfuls onto a non-stick pan over low heat.", "Cook 2 minutes each side.", "Slice into finger strips when cool."]',
         '["oats", "banana", "blueberry", "egg"]', '["egg", "gluten"]', _SERVE_FINGER, "Refrigerate up to 1 day."),

        ("paneer", "finger_food", "Soft Paneer Cubes",
         '["Cut fresh paneer into small 1cm cubes.", "Lightly pan-fry in ½ tsp ghee for 1 minute each side until just golden.", "Cool completely before serving.", "Ensure cubes are soft enough to squish between fingers."]',
         '["paneer", "ghee"]', '["dairy"]', _SERVE_FINGER, "Refrigerate up to 1 day."),

        ("sweet potato", "finger_food", "Baked Sweet Potato Fingers",
         '["Peel sweet potato and cut into thick finger-shaped sticks.", "Toss lightly in ½ tsp ghee.", "Bake at 200°C for 20 minutes until soft inside and slightly crisp outside.", "Cool completely — they should squish easily between fingers."]',
         '["sweet potato", "ghee"]', '[]', _SERVE_FINGER, "Refrigerate up to 2 days."),

        ("banana,ragi", "finger_food", "Ragi Banana Mini Pancakes",
         '["Mix 3 tbsp ragi flour with 1 mashed banana and 2 tbsp water to form a thick batter.", "Drop small rounds onto a non-stick pan over low heat.", "Cook 2-3 minutes each side until cooked through.", "Cool and serve as soft finger food."]',
         '["ragi", "banana"]', '[]', _SERVE_FINGER, "Refrigerate up to 1 day."),

        ("egg,banana", "finger_food", "Banana Egg Bites",
         '["Mash 1 ripe banana with 2 eggs until smooth.", "Pour into a greased mini muffin tin.", "Bake at 180°C for 10-12 minutes until set.", "Cool completely before serving."]',
         '["banana", "egg"]', '["egg"]', _SERVE_FINGER, "Refrigerate up to 2 days."),
    ]

    cursor.executemany(
        "INSERT INTO recipes (ingredient_key, target_texture, recipe_name, preparation_steps, full_ingredients, allergen_flags, serving_size, storage_instructions) VALUES (?,?,?,?,?,?,?,?)",
        seed,
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Affiliate links — Amazon Associates India
# ---------------------------------------------------------------------------
# Items always at home — never link
PANTRY_STAPLES = {
    "water", "salt", "black salt", "rock salt", "pink salt",
    "oil", "cooking oil", "vegetable oil", "sunflower oil",
    "butter",
    "sugar", "jaggery",
    "black pepper", "pepper",
}

# Specialty / expensive items — always link even if user has them
# (worth buying premium / organic versions)
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
}

# Curated Amazon search queries — more specific = better product results
AMAZON_SEARCH_OVERRIDES: dict = {
    # ── Grains ──────────────────────────────────────────────────────────
    "ragi":                    "ragi flour organic baby cereal",
    "ragi flour":              "ragi flour organic baby food",
    "oats":                    "rolled oats baby porridge",
    "jowar":                   "jowar flour sorghum organic",
    "bajra":                   "bajra flour pearl millet organic",
    "sattu":                   "sattu powder roasted chana",
    "semolina (suji)":         "fine semolina suji rava baby",
    "semolina":                "fine semolina suji rava",
    "suji":                    "fine semolina suji baby",
    "dalia (broken wheat)":    "dalia broken wheat organic porridge",
    "dalia":                   "dalia broken wheat organic",
    "wheat":                   "whole wheat flour atta organic",
    "amaranth (rajgira)":      "rajgira amaranth flour organic",
    "amaranth":                "rajgira amaranth flour",
    "sabudana (tapioca)":      "sabudana tapioca pearls medium",
    "sabudana":                "sabudana tapioca pearls",
    "buckwheat (kuttu)":       "kuttu buckwheat flour organic",
    "buckwheat":               "buckwheat flour kuttu",
    # ── Dairy & Fats ────────────────────────────────────────────────────
    "ghee":                    "desi ghee pure cow organic",
    "a2 ghee":                 "a2 cow ghee organic",
    "desi ghee":               "desi ghee pure cow organic",
    "paneer":                  "fresh paneer cottage cheese",
    "ricotta":                 "ricotta cheese",
    "cream cheese":            "cream cheese plain",
    "coconut milk":            "coconut milk organic unsweetened",
    # ── Fruits ──────────────────────────────────────────────────────────
    "avocado":                 "fresh avocado ripe",
    "blueberry":               "fresh blueberries",
    "blueberries":             "fresh blueberries",
    "dates":                   "soft dates seedless medjool",
    "guava":                   "guava fresh",
    "peach":                   "peach fresh",
    "chikoo (sapota)":         "chikoo sapota fresh",
    "custard apple (sitaphal)":"sitaphal custard apple fresh",
    "nendran banana":          "nendran banana kerala raw",
    # ── Protein ─────────────────────────────────────────────────────────
    "tofu":                    "firm tofu organic",
    "chickpea":                "chickpea kabuli chana organic",
    "rajma (kidney beans)":    "rajma red kidney beans organic",
    "rajma":                   "rajma red kidney beans",
    "chana dal":               "chana dal split bengal gram organic",
    "urad dal":                "urad dal white split organic",
    "masoor dal":              "masoor dal red lentils organic",
    "toor dal":                "toor dal arhar dal organic",
    "moong dal":               "moong dal yellow split organic",
    "fish":                    "rohu fish fresh frozen baby",
    # ── Nuts & Seeds ────────────────────────────────────────────────────
    "peanut butter":           "peanut butter unsalted natural no sugar baby",
    "almond butter":           "almond butter unsalted natural",
    "cashew":                  "cashew nuts whole raw organic",
    "sesame (til)":            "white sesame seeds til organic",
    "flaxseed (alsi)":         "flaxseed alsi powder organic",
    "flax seeds":              "organic flax seeds alsi",
    "pumpkin seeds":           "pumpkin seeds roasted unsalted",
    # ── Spices ──────────────────────────────────────────────────────────
    "fennel (saunf)":          "saunf fennel seeds organic baby",
    "coriander (dhania)":      "coriander powder dhania organic",
    "cloves (laung)":          "laung cloves whole organic",
    # ── Legacy / misc ───────────────────────────────────────────────────
    "saffron":                 "pure saffron kesar",
    "quinoa":                  "organic quinoa seeds",
    "chia seeds":              "organic chia seeds",
    "almond flour":            "almond flour blanched",
    "coconut flour":           "coconut flour organic",
}

def _amazon_url(item: str) -> str:
    """Generate an Amazon.in affiliate search URL for a grocery item."""
    query = AMAZON_SEARCH_OVERRIDES.get(item.lower().strip(), f"{item} for babies")
    encoded = urllib.parse.quote_plus(query)
    return f"https://www.amazon.in/s?k={encoded}&tag={AMAZON_AFFILIATE_TAG}"

def generate_affiliate_links(available: List[str], required: List[str], region: str) -> List[AffiliateLink]:
    available_set = {i.lower().strip() for i in available}
    links = []
    seen  = set()
    for item in required:
        key = item.lower().strip()
        if key in seen or key in PANTRY_STAPLES:
            continue
        # Link if: user doesn't have it OR it's a specialty item worth buying premium quality
        if key not in available_set or key in SPECIALTY_ITEMS:
            links.append(AffiliateLink(item=item, action_url=_amazon_url(item)))
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
            "SELECT recipe_name, preparation_steps, full_ingredients, allergen_flags, serving_size, storage_instructions "
            "FROM recipes WHERE ingredient_key = ? AND target_texture = ?",
            (sorted_key, texture.lower()),
        )
        row = cursor.fetchone()
        if row:
            return _build_cache_result(row)

        # Subset match: find best cached recipe whose ingredients the user has
        cursor.execute(
            "SELECT recipe_name, preparation_steps, full_ingredients, allergen_flags, ingredient_key, serving_size, storage_instructions "
            "FROM recipes WHERE target_texture = ?",
            (texture.lower(),),
        )
        best_row, best_overlap = None, 0
        for r in cursor.fetchall():
            cached_set = set(r[4].split(","))
            if cached_set.issubset(user_set) and len(cached_set) > best_overlap:
                best_row, best_overlap = r, len(cached_set)
        if best_row:
            # Re-order: name, steps, ingredients, allergens, serving_size, storage_instructions
            return _build_cache_result((best_row[0], best_row[1], best_row[2], best_row[3], best_row[5], best_row[6]))

    return None

def _build_cache_result(row) -> dict:
    return {
        "recipe_name": row[0],
        "suitability_score": 10,
        "allergen_flags": json.loads(row[3]),
        "preparation_steps": json.loads(row[1]),
        "texture_modification_notes": "Verified standard pediatric recipe.",
        "regional_substitute_suggestions": [],
        "serving_size": row[4] if len(row) > 4 else "",
        "storage_instructions": row[5] if len(row) > 5 else "",
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
                        "INSERT INTO recipes (ingredient_key, target_texture, recipe_name, preparation_steps, full_ingredients, allergen_flags, serving_size, storage_instructions) VALUES (?,?,?,?,?,?,?,?)",
                        (sorted_key, request.texture_milestone, ai.recipe_name,
                         json.dumps(ai.preparation_steps), json.dumps(ai.ingredients_required),
                         json.dumps(ai.allergen_flags), ai.serving_size, ai.storage_instructions)
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


# ---------------------------------------------------------------------------
# Push notification routes
# ---------------------------------------------------------------------------
class PushSubscriptionKeys(BaseModel):
    p256dh: str
    auth: str

class PushSubscription(BaseModel):
    endpoint: str
    keys: PushSubscriptionKeys

class SendPushRequest(BaseModel):
    subscription: PushSubscription
    title: str = "TinyTastes 🍱"
    body: str = "Today's recipe is ready — tap to see what's perfect for your baby!"
    url: str = "/recipe"


@app.get("/api/v1/push/vapid-key")
async def get_vapid_key():
    """Return the VAPID public key so the frontend can subscribe."""
    if not VAPID_PUBLIC_KEY:
        raise HTTPException(status_code=503, detail="Push notifications not configured — set VAPID_PUBLIC_KEY env var")
    return {"public_key": VAPID_PUBLIC_KEY}


@app.post("/api/v1/push/send")
async def send_push_notification(req: SendPushRequest):
    """Send a Web Push notification to a specific subscription endpoint."""
    if not VAPID_PRIVATE_KEY or not VAPID_PUBLIC_KEY:
        raise HTTPException(status_code=503, detail="Push not configured — VAPID keys missing")
    try:
        from pywebpush import webpush, WebPushException
        payload = json.dumps({"title": req.title, "body": req.body, "url": req.url})
        webpush(
            subscription_info={
                "endpoint": req.subscription.endpoint,
                "keys": {"p256dh": req.subscription.keys.p256dh, "auth": req.subscription.keys.auth},
            },
            data=payload,
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims=VAPID_CLAIMS,
            ttl=86400,  # 24 hours
        )
        return {"sent": True}
    except Exception as e:
        err_str = str(e)
        # Subscription expired / unregistered — client should re-subscribe
        if "410" in err_str or "404" in err_str:
            raise HTTPException(status_code=410, detail="Subscription expired — client must re-subscribe")
        raise HTTPException(status_code=500, detail=f"Push send failed: {err_str}")


@app.get("/health")
async def health_check():
    db_ok = False
    recipe_count = 0
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("SELECT 1")
            db_ok = True
            recipe_count = conn.execute("SELECT COUNT(*) FROM recipes").fetchone()[0]
    except Exception:
        pass

    return {
        "status": "healthy",
        "service": "TinyTastes AI",
        "db": "ok" if db_ok else "error",
        "cached_recipes": recipe_count,
        "ai_provider": "DeepSeek",
        "model": DEEPSEEK_MODEL,
        "api_key_set": bool(DEEPSEEK_API_KEY),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
