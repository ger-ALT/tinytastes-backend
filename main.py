import json
import sqlite3
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import ollama

app = FastAPI(title="TinyTastes Local Data Engine", version="1.0.0")
DB_NAME = "tinytastes_core.db"

# --- PYDANTIC SCHEMAS ---
class IngestionPayload(BaseModel):
    baby_age_months: int = Field(..., ge=4, le=36, description="Age of the infant in months")
    ingredients: List[str] = Field(..., min_length=1, description="List of raw text ingredients available")

class RecipeResponseSchema(BaseModel):
    recipe_name: str
    preparation_time_mins: int
    texture_profile: str  # e.g., "Smooth Puree", "Soft Mash", "Finger Food Finger-Length Strips"
    choking_hazard_warning: Optional[str] = None
    step_by_step_instructions: List[str]
    nutritional_benefit_focus: str

# --- DATABASE SETUP ---
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historical_recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                age_months INTEGER,
                ingredients_input TEXT,
                recipe_output TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

init_db()

# --- UTILITY FUNCTIONS ---
def validate_recipe_data(data):
    try:
        RecipeResponseSchema(**data)
    except Exception as e:
        raise ValueError(f"Invalid recipe data: {str(e)}")

def check_choking_hazards(ingredients, baby_age_months):
    choking_hazards = {
        "4-6 months": ["grapes", "hot dogs", "raw carrots"],
        "7-9 months": ["peanuts", "honey", "hard candies"],
        "10-12 months": ["cherry tomatoes", "raisins", "whole grapes"],
        "13-18 months": ["nuts", "seeds", "hard candies"],
        "19-24 months": ["grapes", "hot dogs", "raw carrots"],
        "25-36 months": ["peanuts", "honey", "hard candies"]
    }
    
    warning = None
    for ingredient in ingredients:
        if baby_age_months <= 6 and ingredient in choking_hazards["4-6 months"]:
            warning = f"Warning: {ingredient} is a choking hazard for babies under 7 months."
        elif 7 <= baby_age_months <= 9 and ingredient in choking_hazards["7-9 months"]:
            warning = f"Warning: {ingredient} is a choking hazard for babies under 10 months."
        elif 10 <= baby_age_months <= 12 and ingredient in choking_hazards["10-12 months"]:
            warning = f"Warning: {ingredient} is a choking hazard for babies under 13 months."
        elif 13 <= baby_age_months <= 18 and ingredient in choking_hazards["13-18 months"]:
            warning = f"Warning: {ingredient} is a choking hazard for babies under 19 months."
        elif 19 <= baby_age_months <= 24 and ingredient in choking_hazards["19-24 months"]:
            warning = f"Warning: {ingredient} is a choking hazard for babies under 25 months."
        elif 25 <= baby_age_months <= 36 and ingredient in choking_hazards["25-36 months"]:
            warning = f"Warning: {ingredient} is a choking hazard for babies under 37 months."
    
    return warning

# --- ROUTES ---
@app.post("/api/v1/recipes/generate", response_model=RecipeResponseSchema)
async def generate_baby_recipe(payload: IngestionPayload):
    # Construct an explicit prompt passing the data payload and a reminder of the strict format
    user_prompt = f"""
    Generate a baby-safe recipe for a child of {payload.baby_age_months} months old.
    Available raw ingredients: {', '.join(payload.ingredients)}.
    
    Output must match this JSON structure:
    {{
        "recipe_name": "string",
        "preparation_time_mins": integer,
        "texture_profile": "string",
        "choking_hazard_warning": "string or null",
        "step_by_step_instructions": ["string"],
        "nutritional_benefit_focus": "string"
    }}
    """
    
    try:
        # Request inference from our custom compiled local model
        response = ollama.generate(
            model='tinytastes',
            prompt=user_prompt,
            options={"temperature": 0.0} # Locking down randomness for stable structure
        )
        
        # Log the raw response for debugging
        print(f"Raw Response: {response}")
        
        # Parse the raw response string to ensure it's clean JSON
        raw_output = response['response'].strip()
        recipe_data = json.loads(raw_output)
        
        # Validate the response against the Pydantic schema
        validate_recipe_data(recipe_data)
        
        # Check for choking hazards
        choking_hazard_warning = check_choking_hazards(payload.ingredients, payload.baby_age_months)
        if choking_hazard_warning:
            recipe_data['choking_hazard_warning'] = choking_hazard_warning
        
        # Log the successful transaction safely to our local SQLite data store
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO historical_recipes (age_months, ingredients_input, recipe_output) VALUES (?, ?, ?)",
                (payload.baby_age_months, json.dumps(payload.ingredients), raw_output)
            )
            conn.commit()
            
        return RecipeResponseSchema(**recipe_data)

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"JSON Decode Error: {str(e)}")
    except ValueError as ve:
        raise HTTPException(status_code=500, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference Engine Error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
