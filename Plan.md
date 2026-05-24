[SPEC] TECHNICAL ARCHITECTURE PROPOSAL & SPECIFICATION
Project Code Name: TinyTastes AI

Target Architecture: LLM-Optional / Hybrid Deterministic-Generative Implementation

Backend Framework Strategy: Python / FastAPI / SQLite / Ollama SDK

1. CORE ARCHITECTURE CONSTRAINTS
1.1 The "LLM-Optional" Operational Flow
To minimize compute costs and maintain sub-100ms response times for standard use cases, execution follows a strict hierarchical check:

[ User Selects Ingredients & Target Age Group ]
                       │
                       ▼
         〔 Layer 1: Deterministic Check 〕
            Does sorted array match an entry 
            in the Local SQLite Database?
                       │
             ┌─────────┴─────────┐
             ▼ YES               ▼ NO
   [ Return Free Recipe ]   〔 Layer 2: Premium AI Trigger 〕
   (Cost: $0 / Time: <5ms)   Isolate edge-case combinations.
                             Execute Structured JSON via Ollama.
1.2 Data Schemas (JSON/Pydantic Format)
1.2.1 Ingestion Payload
JSON
{
  "user_region": "string (e.g., US-NE, IN-HR)",
  "available_ingredients": ["string"],
  "baby_age_months": "integer",
  "texture_milestone": "string [puree, chunky, finger_food]",
  "custom_constraints": "string or null"
}
1.2.2 Mandated LLM Output Schema (Structured Output)
The LLM must reject standard conversational text and enforce a strict structural payload matching this exact format:

JSON
{
  "recipe_name": "string",
  "suitability_score": "integer [1-10]",
  "allergen_flags": ["string"],
  "preparation_steps": ["string"],
  "texture_modification_notes": "string",
  "regional_substitute_suggestions": ["string"]
}
2. PRODUCTION OLLAMA MODELFILE DEFINITION
Save this configuration precisely to a file named TinyTastesModelfile and compile using ollama create tinytastes -f ./TinyTastesModelfile.

Dockerfile
# TinyTastes Custom Pediatric Nutritionist Engine
FROM llama3.2

# Lock parameters for highly deterministic, safe culinary behavior
PARAMETER temperature 0.0
PARAMETER top_p 0.1
PARAMETER num_ctx 4096

# Define strict operational boundaries
SYSTEM """
You are the isolated core AI engine for TinyTastes AI, working as a Pediatric Nutritionist API.

[CRITICAL INSTRUCTIONS]
1. Your output must be purely valid JSON matching the mandated output schema. Do not prefix or suffix your response with conversational filler.
2. MEDICAL PROTECTION RULE: If an infant is under 12 months, NEVER suggest honey or cow's milk as a primary ingredient due to infant botulism and digestive safety risks.
3. If an input contains high-allergen foods (e.g., peanuts, eggs, fish), you must populating the "allergen_flags" array with distinct warning strings.
4. Scale preparation steps to match the structural safety dictated by the "texture_milestone" parameter.
"""
3. CORE PYTHON IMPLEMENTATION BLUEPRINT (FASTAPI + OLLAMA)
Python
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

# --- Main Business Logic Route Implementation ---
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
4. MONETIZATION HOOK ARCHITECTURE
To ensure high-margin operations, intercept the payload at the application routing level to embed contextual user upsells:

4.1 Missing Ingredient Affiliate Hook (E-Commerce Injection)
Python
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
4.2 On-Demand PDF Cookbook Microtransaction ($2.99 Export)
When processing successful premium requests, bundle records into a sequential dataset matching this profile to feed directly into your document processing script (e.g., ReportLab or FPDF frameworks):

JSON
{
  "document_header": "My Baby's First Foods Daily Journal",
  "meta": { "compiled_for_months": 8, "regional_profile": "US-NE" },
  "rendered_content_blocks": [
    {
      "type": "recipe_card",
      "title": "Generated Custom AI Recipe",
      "body": "Detailed compilation of safe textures, preparation intervals, and nutrition insights."
    }
  ]
}
