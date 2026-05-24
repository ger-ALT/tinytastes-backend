import sqlite3
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import ollama

app = FastAPI(title="TinyTastes AI Hybrid Backend")

# --- Pydantic Data Validation Tiers ---
class RecipeRequest(BaseModel):
    user_region: str
    available_ingredients: List[str]
    baby_age_months: int
    texture_milestone: str
    custom_constraints: Optional[str] = None

class RecipeResponseSchema(BaseModel):
    recipe_name: str
    suitability_score: int
    allergen_flags: List[str]
    preparation_steps: List[str]
    texture_modification_notes: str
    regional_substitute_suggestions: List[str]

# --- Layer 1: Deterministic Datastore Controller ---
def check_local_database(ingredients: List[str], texture: str) -> Optional[dict]:
    # Standardized key normalization matching DB records
    sorted_key = ",".join(sorted([i.lower().strip() for i in ingredients]))
    
    conn = sqlite3.connect("tinytastes_core.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT recipe_name, preparation_steps FROM recipes WHERE ingredient_key = ? AND target_texture = ?", 
        (sorted_key, texture.lower())
    )
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "recipe_name": row[0],
            "suitability_score": 10,
            "allergen_flags": [],
            "preparation_steps": json.loads(row[1]),
            "texture_modification_notes": "Verified standard pediatric recipe profile.",
            "regional_substitute_suggestions": []
        }
    return None

# --- Layer 2: Affiliate Link Generation ---
def generate_affiliate_links(selected_ingredients: List[str], expected_recipe_ingredients: List[str], region: str):
    """
    Compares user ingredients against target optimal ingredient configurations.
    Returns targeted affiliate cart links mapping directly to regional APIs (e.g., Instacart).
    """
    missing_items = list(set(expected_recipe_ingredients) - set(selected_ingredients))
    affiliate_payload = []
    for item in missing_items:
        affiliate_payload.append({
            "item": item,
            "action_url": f"https://partner-grocery-api.com/v1/checkout?item={item}&region={region}&affiliate_id=tinytastes"
        })
    return affiliate_payload

# --- Layer 2 Fallback: Invoke Local Ollama Structured JSON Infrastructure ---
@app.post("/api/v1/get-recipe", response_model=RecipeResponseSchema)
async def process_recipe_engine(request: RecipeRequest):
    # Try deterministic mapping first (Zero API/Inference Costs)
    cached_match = check_local_database(request.available_ingredients, request.texture_milestone)
    if cached_match and not request.custom_constraints:
        return cached_match

    # Layer 2 Fallback: Invoke Local Ollama Structured JSON Infrastructure
    try:
        prompt_input = {
            "ingredients": request.available_ingredients,
            "age": request.baby_age_months,
            "milestone": request.texture_milestone,
            "special_notes": request.custom_constraints
        }

        # Utilizing Ollama's native structured JSON schema compliance capability
        response = ollama.chat(
            model="tinytastes",
            messages=[{"role": "user", "content": json.dumps(prompt_input)}],
            format=RecipeResponseSchema.model_json_schema()
        )
        
        structured_data = json.loads(response['message']['content'])
        return structured_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Engine Extraction Failure: {str(e)}")

# --- PDF Cookbook Export Endpoint (Microtransaction Hook) ---
@app.post("/api/v1/export-pdf")
async def export_pdf(request: RecipeRequest):
    """
    Bundles successful recipe records into a sequential dataset for document processing.
    """
    document_data = {
        "document_header": "My Baby's First Foods Daily Journal",
        "meta": { 
            "compiled_for_months": request.baby_age_months, 
            "regional_profile": request.user_region 
        },
        "rendered_content_blocks": [
            {
                "type": "recipe_card",
                "title": "Generated Custom AI Recipe",
                "body": "Detailed compilation of safe textures, preparation intervals, and nutrition insights."
            }
        ]
    }
    return document_data

# --- Health Check Endpoint ---
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "TinyTastes AI"}

# --- Database Initialization ---
def init_db():
    with sqlite3.connect("tinytastes_core.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ingredient_key TEXT,
                target_texture TEXT,
                recipe_name TEXT,
                preparation_steps TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

# Initialize database on startup
init_db()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
