"""
pre_seed.py — Warm the Layer 1 recipe cache before going live.

Uses local Ollama (qwen3.5) to generate recipes — no internet, no proxy issues.
Production continues to use DeepSeek; this is a one-time seeding step.

Usage:
    # Make sure Ollama is running: ollama serve
    cd tinytastes-backend
    source .venv/bin/activate
    python pre_seed.py
"""

import sqlite3
import json
import os
import time
import urllib.request
import urllib.error

DB_PATH      = os.getenv("DB_PATH", "tinytastes_core.db")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:latest")
OLLAMA_URL   = os.getenv("OLLAMA_URL", "http://localhost:11434")

SYSTEM_PROMPT = """You are a Pediatric Nutritionist AI for TinyTastes.
Generate safe, age-appropriate Indian baby food recipes. Respond with valid JSON only — no prose, no markdown fences, no thinking tags.

MEDICAL RULES:
- Never suggest honey or cow's milk for infants under 12 months.
- Populate allergen_flags for: peanuts, eggs, fish, dairy, gluten, soy, tree nuts.
- Scale preparation steps to match the texture_milestone.
- ingredients_required must list every ingredient the recipe needs.

OUTPUT FORMAT (JSON only, no other text):
{
  "recipe_name": "string",
  "suitability_score": 8,
  "allergen_flags": ["string"],
  "preparation_steps": ["string (4-6 steps)"],
  "texture_modification_notes": "string",
  "regional_substitute_suggestions": ["string"],
  "ingredients_required": ["string"]
}"""

# (ingredients_list, texture, region, age_months)
COMBOS = [
    # ── Purees (4-7 months) ───────────────────────────────────────
    (["rice", "moong dal"],                   "puree",       "North Indian", 6),
    (["ragi", "banana"],                      "puree",       "South Indian", 6),
    (["sweet potato", "ghee"],                "puree",       "North Indian", 6),
    (["carrot", "ghee"],                      "puree",       "North Indian", 6),
    (["apple", "carrot"],                     "puree",       "North Indian", 6),
    (["mango", "rice"],                       "puree",       "South Indian", 6),
    (["pumpkin", "ghee"],                     "puree",       "North Indian", 6),
    (["pear", "oats"],                        "puree",       "North Indian", 6),
    (["ragi", "ghee"],                        "puree",       "Karnataka",    6),
    (["moong dal", "rice", "ghee"],           "puree",       "North Indian", 6),

    # ── Chunky (8-11 months) ──────────────────────────────────────
    (["rice", "moong dal", "carrot", "ghee"], "chunky",      "North Indian", 9),
    (["oats", "banana", "curd"],              "chunky",      "North Indian", 9),
    (["ragi", "banana", "ghee"],              "chunky",      "South Indian", 9),
    (["rice", "toor dal", "tomato", "ghee"],  "chunky",      "South Indian", 9),
    (["sweet potato", "paneer"],              "chunky",      "North Indian", 9),
    (["semolina", "carrot", "pea"],           "chunky",      "North Indian", 9),
    (["rice", "spinach", "moong dal"],        "chunky",      "West Bengal",  9),
    (["banana", "oats", "curd"],              "chunky",      "North Indian", 9),
    (["potato", "pea", "ghee"],               "chunky",      "North Indian", 9),
    (["carrot", "potato", "moong dal"],       "chunky",      "North Indian", 9),

    # ── Finger foods (12+ months) ────────────────────────────────
    (["oats", "banana", "egg"],               "finger_food", "North Indian", 13),
    (["sweet potato", "paneer"],              "finger_food", "North Indian", 13),
    (["carrot", "egg"],                       "finger_food", "North Indian", 13),
    (["ragi", "banana", "ghee"],              "finger_food", "South Indian", 13),
    (["paneer", "spinach"],                   "finger_food", "North Indian", 13),
    (["potato", "pea"],                       "finger_food", "North Indian", 13),
    (["apple", "cinnamon", "oats"],           "finger_food", "North Indian", 13),
    (["chickpea", "carrot"],                  "finger_food", "North Indian", 13),
    (["rice", "egg", "carrot"],               "finger_food", "North Indian", 13),
    (["banana", "oats", "ghee"],              "finger_food", "North Indian", 13),
]


def already_seeded(conn: sqlite3.Connection, ingredients: list, texture: str) -> bool:
    key = ",".join(sorted(i.lower().strip() for i in ingredients))
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM recipes WHERE ingredient_key = ? AND target_texture = ?",
        (key, texture),
    )
    return cursor.fetchone() is not None


def extract_json(text: str) -> dict | None:
    """Robustly pull the first {...} block out of a response."""
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    start = text.find("{")
    end   = text.rfind("}")
    if start == -1 or end == -1:
        return None
    return json.loads(text[start:end + 1])


def get_recipe(ingredients: list, texture: str, region: str, age: int) -> dict | None:
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
        "think": False,          # Ollama native param — disables Qwen3 thinking
        "format": "json",        # forces JSON output
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
            data = json.loads(resp.read())
            content = data["message"]["content"]
            result = extract_json(content)
            if result is None:
                print(f"\n  ✗ Could not parse JSON. Raw:\n{content[:300]}")
            return result
    except Exception as e:
        print(f"  ✗ {e}")
        return None


def main():
    # Check Ollama is reachable
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=5) as r:
            tags = json.loads(r.read())
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
        # Ensure table exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recipes (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                ingredient_key    TEXT    NOT NULL,
                target_texture    TEXT    NOT NULL,
                recipe_name       TEXT    NOT NULL,
                preparation_steps TEXT    NOT NULL,
                full_ingredients  TEXT    NOT NULL,
                allergen_flags    TEXT    NOT NULL DEFAULT '[]',
                timestamp         DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

        total   = len(COMBOS)
        added   = 0
        skipped = 0

        for i, (ingredients, texture, region, age) in enumerate(COMBOS, 1):
            label = f"{'+'.join(ingredients)} [{texture}]"
            print(f"[{i}/{total}] {label} ...", end=" ", flush=True)

            if already_seeded(conn, ingredients, texture):
                print("(already exists, skipped)")
                skipped += 1
                continue

            recipe = get_recipe(ingredients, texture, region, age)
            if not recipe:
                skipped += 1
                continue

            key = ",".join(sorted(i.lower().strip() for i in ingredients))
            conn.execute(
                "INSERT INTO recipes (ingredient_key, target_texture, recipe_name, "
                "preparation_steps, full_ingredients, allergen_flags) VALUES (?,?,?,?,?,?)",
                (
                    key,
                    texture,
                    recipe["recipe_name"],
                    json.dumps(recipe["preparation_steps"]),
                    json.dumps(recipe.get("ingredients_required", ingredients)),
                    json.dumps(recipe.get("allergen_flags", [])),
                ),
            )
            conn.commit()
            print(f"✓ {recipe['recipe_name']}")
            added += 1

            time.sleep(0.2)

    total_db = sqlite3.connect(DB_PATH).execute("SELECT COUNT(*) FROM recipes").fetchone()[0]
    print(f"\nDone. Added {added} recipes, skipped {skipped}.")
    print(f"Total in Layer 1 cache: {total_db} recipes.")


if __name__ == "__main__":
    main()
