"""
pre_seed.py — Warm the Layer 1 recipe cache with AI-generated Indian recipes.

Provider auto-detection:
  - DEEPSEEK_API_KEY set → uses DeepSeek (production / Railway)
  - Not set             → uses local Ollama (local dev, no proxy issues)

Usage:
    # Local (Ollama must be running: ollama serve)
    python pre_seed.py

    # Railway — runs against production DB with DeepSeek
    railway run python pre_seed.py
    # OR from Railway dashboard → service → Shell tab:
    python pre_seed.py
"""

import sqlite3
import json
import os
import time
import urllib.request
import urllib.error

# ── Config ──────────────────────────────────────────────────────────────────
DB_PATH          = os.getenv("DB_PATH", "tinytastes_core.db")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL   = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
OLLAMA_MODEL     = os.getenv("OLLAMA_MODEL", "qwen3.5:latest")
OLLAMA_URL       = os.getenv("OLLAMA_URL", "http://localhost:11434")

USE_DEEPSEEK = bool(DEEPSEEK_API_KEY)

SYSTEM_PROMPT = """You are a Pediatric Nutritionist AI for TinyTastes.
Generate safe, age-appropriate Indian baby food recipes. Respond with valid JSON only — no prose, no markdown fences, no thinking tags.

MEDICAL RULES:
- Never suggest honey or cow's milk for infants under 12 months.
- Populate allergen_flags for: peanuts, eggs, fish, dairy, gluten, soy, tree nuts.
- Scale preparation steps to match the texture_milestone (puree=smooth, chunky=soft lumps, finger_food=graspable pieces).
- ingredients_required must list every ingredient the recipe needs.
- Always include serving_size: 4-6m → "1-2 tablespoons", 7-9m → "3-4 tablespoons", 10-12m → "4-6 tablespoons", 12m+ → "small bowl"
- Always include storage_instructions (e.g. "Refrigerate up to 2 days. Freeze up to 1 month.")

SIMPLICITY RULES:
- Baby food must be simple — 4-6 preparation steps maximum.
- Use mild spices only (cumin, turmeric, cardamom — never chilli).
- Prioritise digestibility and safety.

OUTPUT FORMAT (JSON only):
{
  "recipe_name": "string",
  "suitability_score": 8,
  "allergen_flags": ["string"],
  "preparation_steps": ["string"],
  "texture_modification_notes": "string",
  "regional_substitute_suggestions": ["string"],
  "ingredients_required": ["string"],
  "serving_size": "string",
  "storage_instructions": "string"
}"""

# ── Combos to seed ───────────────────────────────────────────────────────────
# (ingredients, texture, region, age_months)
COMBOS = [
    # ── Purees (4-7m) ─────────────────────────────────────────────────────
    (["rice", "moong dal"],                        "puree",       "North Indian",  6),
    (["ragi", "banana"],                           "puree",       "South Indian",  6),
    (["sweet potato", "ghee"],                     "puree",       "North Indian",  6),
    (["carrot", "ghee"],                           "puree",       "North Indian",  6),
    (["apple", "carrot"],                          "puree",       "North Indian",  6),
    (["mango", "rice"],                            "puree",       "South Indian",  6),
    (["pumpkin", "ghee"],                          "puree",       "North Indian",  6),
    (["pear", "oats"],                             "puree",       "North Indian",  6),
    (["ragi", "ghee"],                             "puree",       "Karnataka",     6),
    (["moong dal", "rice", "ghee"],                "puree",       "North Indian",  6),
    (["banana", "ghee"],                           "puree",       "Kerala",        6),
    (["papaya", "banana"],                         "puree",       "South Indian",  6),
    (["chikoo (sapota)", "banana"],                "puree",       "Maharashtra",   6),
    (["bottle gourd", "moong dal"],                "puree",       "North Indian",  6),
    (["beetroot", "potato"],                       "puree",       "North Indian",  6),
    # new purees ──────────────────────────────────────────────────────────
    (["cauliflower", "potato", "ghee"],            "puree",       "North Indian",  6),
    (["raw banana", "ghee"],                       "puree",       "Kerala",        6),
    (["pumpkin", "moong dal"],                     "puree",       "North Indian",  6),
    (["spinach", "rice", "ghee"],                  "puree",       "North Indian",  6),
    (["dates", "banana", "ghee"],                  "puree",       "North Indian",  6),
    (["peach", "rice"],                            "puree",       "North Indian",  6),
    (["guava", "banana"],                          "puree",       "South Indian",  6),
    (["sabudana (tapioca)", "sweet potato"],        "puree",       "Maharashtra",   6),
    (["amaranth (rajgira)", "banana"],              "puree",       "Gujarat",       6),
    (["colocasia (arbi)", "ghee"],                 "puree",       "North Indian",  6),
    (["apple", "sweet potato", "cinnamon"],        "puree",       "North Indian",  6),
    (["pear", "banana"],                           "puree",       "North Indian",  6),
    (["broccoli", "potato"],                       "puree",       "North Indian",  6),
    (["tomato", "rice", "ghee"],                   "puree",       "South Indian",  6),
    (["oats", "apple", "ghee"],                    "puree",       "North Indian",  6),

    # ── Chunky (8-11m) ────────────────────────────────────────────────────
    (["rice", "moong dal", "carrot", "ghee"],      "chunky",      "North Indian",  9),
    (["oats", "banana", "curd / yoghurt"],         "chunky",      "North Indian",  9),
    (["ragi", "banana", "ghee"],                   "chunky",      "South Indian",  9),
    (["rice", "toor dal", "tomato", "ghee"],       "chunky",      "South Indian",  9),
    (["sweet potato", "paneer"],                   "chunky",      "North Indian",  9),
    (["semolina (suji)", "carrot", "pea"],         "chunky",      "North Indian",  9),
    (["rice", "spinach", "moong dal"],             "chunky",      "West Bengal",   9),
    (["banana", "oats", "curd / yoghurt"],         "chunky",      "North Indian",  9),
    (["potato", "pea", "ghee"],                    "chunky",      "North Indian",  9),
    (["carrot", "potato", "moong dal"],            "chunky",      "North Indian",  9),
    (["dalia (broken wheat)", "spinach"],          "chunky",      "North Indian",  9),
    (["rice", "masoor dal", "ghee"],               "chunky",      "West Bengal",   9),
    (["semolina (suji)", "banana"],                "chunky",      "South Indian",  9),
    (["rice", "egg", "carrot"],                    "chunky",      "North Indian",  9),
    (["jowar", "banana", "ghee"],                  "chunky",      "Maharashtra",   9),
    # new chunky ──────────────────────────────────────────────────────────
    (["rice", "chana dal", "ghee"],                "chunky",      "North Indian",  9),
    (["dalia (broken wheat)", "carrot", "pea"],    "chunky",      "North Indian",  9),
    (["semolina (suji)", "spinach", "tomato"],     "chunky",      "South Indian",  9),
    (["oats", "apple", "cinnamon"],                "chunky",      "North Indian",  9),
    (["rice", "toor dal", "drumstick leaves"],     "chunky",      "Tamil Nadu",    9),
    (["bajra", "carrot", "ghee"],                  "chunky",      "Rajasthan",     9),
    (["jowar", "carrot", "ghee"],                  "chunky",      "Maharashtra",   9),
    (["potato", "chicken", "carrot"],              "chunky",      "North Indian",  9),
    (["paneer", "pea", "ghee"],                    "chunky",      "North Indian",  9),
    (["cauliflower", "potato", "ghee"],            "chunky",      "North Indian",  9),
    (["rice", "fish", "ghee"],                     "chunky",      "West Bengal",   9),
    (["urad dal", "rice", "ghee"],                 "chunky",      "South Indian",  9),
    (["tofu", "carrot", "ghee"],                   "chunky",      "North Indian",  9),
    (["french beans", "potato", "ghee"],           "chunky",      "North Indian",  9),
    (["rice", "egg", "spinach"],                   "chunky",      "North Indian",  9),

    # ── Finger Foods (12m+) ───────────────────────────────────────────────
    (["oats", "banana", "egg"],                    "finger_food", "North Indian",  13),
    (["sweet potato", "paneer"],                   "finger_food", "North Indian",  13),
    (["carrot", "egg"],                            "finger_food", "North Indian",  13),
    (["ragi", "banana", "ghee"],                   "finger_food", "South Indian",  13),
    (["paneer", "spinach"],                        "finger_food", "North Indian",  13),
    (["potato", "pea"],                            "finger_food", "North Indian",  13),
    (["apple", "cinnamon", "oats"],                "finger_food", "North Indian",  13),
    (["chickpea", "carrot"],                       "finger_food", "North Indian",  13),
    (["banana", "oats", "ghee"],                   "finger_food", "North Indian",  13),
    (["paneer", "carrot"],                         "finger_food", "North Indian",  13),
    (["sweet potato", "chickpea"],                 "finger_food", "South Indian",  13),
    (["egg", "potato"],                            "finger_food", "North Indian",  13),
    (["banana", "ragi", "egg"],                    "finger_food", "South Indian",  13),
    (["avocado", "banana"],                        "finger_food", "North Indian",  13),
    (["oats", "carrot", "ghee"],                   "finger_food", "North Indian",  13),
    # new finger foods ────────────────────────────────────────────────────
    (["paneer", "beetroot"],                       "finger_food", "North Indian",  13),
    (["oats", "blueberry", "banana"],              "finger_food", "North Indian",  13),
    (["rajma (kidney beans)", "carrot"],           "finger_food", "North Indian",  13),
    (["chicken", "sweet potato"],                  "finger_food", "North Indian",  13),
    (["egg", "spinach", "potato"],                 "finger_food", "North Indian",  13),
    (["ragi", "dates", "ghee"],                    "finger_food", "Karnataka",     13),
    (["semolina (suji)", "pea", "carrot"],         "finger_food", "North Indian",  13),
    (["fish", "potato", "ghee"],                   "finger_food", "West Bengal",   13),
    (["sattu", "banana"],                          "finger_food", "Bihar",         13),
    (["dalia (broken wheat)", "carrot", "paneer"], "finger_food", "North Indian",  13),
    (["cauliflower", "paneer"],                    "finger_food", "North Indian",  13),
    (["urad dal", "rice"],                         "finger_food", "South Indian",  13),
    (["tofu", "sweet potato", "carrot"],           "finger_food", "North Indian",  13),
    (["coconut milk", "ragi", "banana"],           "finger_food", "Kerala",        13),
    (["oats", "carrot", "cheese"],                 "finger_food", "North Indian",  13),
]


# ── Helpers ──────────────────────────────────────────────────────────────────
def already_seeded(conn: sqlite3.Connection, ingredients: list, texture: str) -> bool:
    key = ",".join(sorted(i.lower().strip() for i in ingredients))
    return conn.execute(
        "SELECT id FROM recipes WHERE ingredient_key = ? AND target_texture = ?",
        (key, texture),
    ).fetchone() is not None


def extract_json(text: str) -> dict | None:
    """Pull the first complete {...} JSON object out of a response."""
    text = text.strip()
    # Strip markdown fences and think tags
    for tag in ["```json", "```", "<think>", "</think>"]:
        text = text.replace(tag, "")
    start = text.find("{")
    end   = text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


def get_recipe_deepseek(ingredients: list, texture: str, region: str, age: int) -> dict | None:
    """Call DeepSeek via OpenAI-compatible API."""
    import urllib.parse
    payload = json.dumps({
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": json.dumps({
                "ingredients": ingredients,
                "texture_milestone": texture,
                "region": region,
                "age_months": age,
            })},
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 1024,
    }).encode()

    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data    = json.loads(resp.read())
            content = data["choices"][0]["message"]["content"]
            result  = extract_json(content)
            if result is None:
                print(f"\n  ✗ Could not parse JSON. Raw:\n{content[:300]}")
            return result
    except Exception as e:
        print(f"  ✗ DeepSeek error: {e}")
        return None


def get_recipe_ollama(ingredients: list, texture: str, region: str, age: int) -> dict | None:
    """Call local Ollama."""
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": json.dumps({
                "ingredients": ingredients,
                "texture_milestone": texture,
                "region": region,
                "age_months": age,
            })},
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
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data    = json.loads(resp.read())
            content = data["message"]["content"]
            result  = extract_json(content)
            if result is None:
                print(f"\n  ✗ Could not parse JSON. Raw:\n{content[:300]}")
            return result
    except Exception as e:
        print(f"  ✗ Ollama error: {e}")
        return None


def get_recipe(ingredients: list, texture: str, region: str, age: int) -> dict | None:
    if USE_DEEPSEEK:
        return get_recipe_deepseek(ingredients, texture, region, age)
    return get_recipe_ollama(ingredients, texture, region, age)


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
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
    # Migrate existing deployments
    for col, default in [("serving_size", "''"), ("storage_instructions", "''")] :
        try:
            conn.execute(f"ALTER TABLE recipes ADD COLUMN {col} TEXT NOT NULL DEFAULT {default}")
        except Exception:
            pass
    conn.commit()


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    provider = "DeepSeek" if USE_DEEPSEEK else f"Ollama ({OLLAMA_MODEL})"
    print(f"TinyTastes pre-seeder — provider: {provider}")
    print(f"Database: {DB_PATH}\n")

    # Check connectivity
    if USE_DEEPSEEK:
        print("✓ DeepSeek API key found — using DeepSeek\n")
    else:
        try:
            with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=5) as r:
                tags      = json.loads(r.read())
                available = [m["name"] for m in tags.get("models", [])]
                if OLLAMA_MODEL not in available:
                    print(f"✗ Model '{OLLAMA_MODEL}' not found. Available: {available}")
                    return
                print(f"✓ Ollama ready — using {OLLAMA_MODEL}\n")
        except Exception as e:
            print(f"✗ Cannot reach Ollama at {OLLAMA_URL}: {e}")
            print("  Start it with: ollama serve")
            return

    with sqlite3.connect(DB_PATH) as conn:
        ensure_schema(conn)

        total   = len(COMBOS)
        added   = 0
        skipped = 0
        failed  = 0

        for i, (ingredients, texture, region, age) in enumerate(COMBOS, 1):
            label = f"{'+'.join(ingredients)} [{texture}]"
            print(f"[{i:2}/{total}] {label} ...", end=" ", flush=True)

            if already_seeded(conn, ingredients, texture):
                print("already exists — skipped")
                skipped += 1
                continue

            recipe = get_recipe(ingredients, texture, region, age)
            if not recipe:
                failed += 1
                continue

            key = ",".join(sorted(i.lower().strip() for i in ingredients))
            try:
                conn.execute(
                    "INSERT INTO recipes (ingredient_key, target_texture, recipe_name, "
                    "preparation_steps, full_ingredients, allergen_flags, "
                    "serving_size, storage_instructions) VALUES (?,?,?,?,?,?,?,?)",
                    (
                        key,
                        texture,
                        recipe["recipe_name"],
                        json.dumps(recipe["preparation_steps"]),
                        json.dumps(recipe.get("ingredients_required", ingredients)),
                        json.dumps(recipe.get("allergen_flags", [])),
                        recipe.get("serving_size", ""),
                        recipe.get("storage_instructions", ""),
                    ),
                )
                conn.commit()
                print(f"✓ {recipe['recipe_name']}")
                added += 1
            except Exception as e:
                print(f"  ✗ DB error: {e}")
                failed += 1

            # Polite rate limiting
            time.sleep(0.5 if USE_DEEPSEEK else 0.2)

    total_db = sqlite3.connect(DB_PATH).execute("SELECT COUNT(*) FROM recipes").fetchone()[0]
    print(f"\n{'─'*50}")
    print(f"Done. Added: {added}  |  Skipped: {skipped}  |  Failed: {failed}")
    print(f"Total in Layer 1 cache: {total_db} recipes")


if __name__ == "__main__":
    main()
