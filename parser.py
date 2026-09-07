import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

class FoodItem(BaseModel):
    name: str = Field(description="Ingredient or item name")
    grams: float = Field(description="Estimated Portion in Grams")
    calories: int
    protein: float
    carbs: float
    fat: float
    
class MealAnalysis(BaseModel):
    items: list[FoodItem]
    total_calories: int
    
def parse_meal_text(description: str) -> MealAnalysis:
    prompt = (
        "You are a nutritional calculator. Break down the meal into individual "
        f"ingredients, estimate weights in grams, and calculate macros and calories. \n\nMeal: {description}"
    )
    
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=MealAnalysis,
            temperature=0.2,
        ),
    )
    
    #Gemini automaticaly parses the JSON directly into the Pydantic Object
    return response.parsed

if __name__ == "__main__":
    test_input = "Chicken breast with a cup of white rice and steamed broccoli"
    result = parse_meal_text(test_input)

    print(f"\n--- Meal Summary ---")
    print(f"Total Calories: {result.total_calories} kcal")
    for item in result.items:
        print(f"- {item.name} ({item.grams}g): {item.calories} kcal | P: {item.protein}g C: {item.carbs}g F: {item.fat}g")