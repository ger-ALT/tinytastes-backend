"""
seed_via_api.py — Seed local DB by calling the live Railway backend.

Uses the production /api/v1/get-recipe endpoint (which can reach DeepSeek)
and saves results into the local tinytastes_core.db so it can be committed.

Usage:
    python3 seed_via_api.py
"""
from __future__ import annotations

import json
import sqlite3
import ssl
import time
import urllib.request
import urllib.error
import os

# macOS Python 3.9 has outdated system certs — skip verification for this local tool
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

DB_PATH  = os.getenv("DB_PATH", "tinytastes_core.db")
API_BASE = "https://tinytastes-backend-production.up.railway.app"

# Same combos as pre_seed.py — (ingredients, texture, region, age_months)
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

TEXTURE_AGE = {"puree": 6, "chunky": 9, "finger_food": 13}


def already_seeded(conn: sqlite3.Connection, ingredients: list, texture: str) -> bool:
    key = ",".join(sorted(i.lower().strip() for i in ingredients))
    return conn.execute(
        "SELECT id FROM recipes WHERE ingredient_key=? AND target_texture=?",
        (key, texture),
    ).fetchone() is not None


def fetch_recipe(ingredients: list, texture: str, region: str, age: int) -> dict | None:
    """Call the live Railway backend to generate a recipe."""
    payload = json.dumps({
        "user_region": "IN-DL",
        "available_ingredients": ingredients,
        "baby_age_months": age,
        "texture_milestone": texture,
        "custom_constraints": None,
        "known_allergens": [],
    }).encode()

    req = urllib.request.Request(
        f"{API_BASE}/api/v1/get-recipe",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90, context=_SSL_CTX) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read()[:200] if e.fp else b""
        print(f"  ✗ API error {e.code}: {body.decode(errors='ignore')}")
        return None
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return None


def main():
    print(f"TinyTastes seeder — via production API ({API_BASE})")
    print(f"Database: {DB_PATH}\n")

    with sqlite3.connect(DB_PATH) as conn:
        total = len(COMBOS)
        added, skipped, failed = 0, 0, 0

        for i, (ingredients, texture, region, age) in enumerate(COMBOS, 1):
            label = "+".join(ingredients)
            print(f"[{i:2}/{total}] {label} [{texture}] ...", end=" ", flush=True)

            if already_seeded(conn, ingredients, texture):
                print("already exists — skipped")
                skipped += 1
                continue

            recipe = fetch_recipe(ingredients, texture, region, age)
            if not recipe:
                failed += 1
                continue

            key = ",".join(sorted(i.lower().strip() for i in ingredients))
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO recipes "
                    "(ingredient_key, target_texture, recipe_name, preparation_steps, "
                    "full_ingredients, allergen_flags, serving_size, storage_instructions) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (
                        key, texture,
                        recipe["recipe_name"],
                        json.dumps(recipe["preparation_steps"]),
                        json.dumps([l["item"] for l in recipe.get("affiliate_links", [])]
                                   or ingredients),
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

            time.sleep(0.3)  # be polite to our own server

    total_db = sqlite3.connect(DB_PATH).execute("SELECT COUNT(*) FROM recipes").fetchone()[0]
    print(f"\n{'─'*55}")
    print(f"Done. Added: {added}  |  Skipped: {skipped}  |  Failed: {failed}")
    print(f"Total in Layer 1 cache: {total_db} recipes")


if __name__ == "__main__":
    main()
