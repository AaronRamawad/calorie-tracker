import os
import io
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image
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
    
BASE_SYSTEM_PROMPT = (
    "You are a nutritional calculator. Break down the meal into individual "
    "ingredients, estimate weight in grams, and calculate macros and calories."
)    
    
def parse_meal_text(description: str) -> MealAnalysis:
    prompt = f"{BASE_SYSTEM_PROMPT}\n\nMeal: {description}" 
    
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

def parse_meal_image(image_path: str, user_notes: str = "") -> MealAnalysis:
    #Accepts either a string path, Path Object, or io.BytesIO buffer
    if isinstance(image_path, (str, Path)):
        img = Image.open(image_path)
    elif isinstance(image_path, io.BytesIO):
        img = Image.open(image_path)
    elif isinstance(image_path, Image.Image):
        img = image_path
    else:
        raise ValueError("Unsupported image source type")
    
    prompt = prompt = f"""
    You are a precise nutritional calculator. Analyze the meal using both the image and the user's caption.

    CRITICAL INSTRUCTIONS ON PRECEDENCE:
    1. GROUND TRUTH: The user's caption is ABSOLUTE GROUND TRUTH for ingredients, preparations, brand names, and hidden contents (e.g., specific sauces, oils, milk alternatives, or meats).
    2. NEVER CONTRADICT THE USER: If the user states an item is turkey bacon, tofu, oat milk, or a specific protein, DO NOT label it as pork bacon, chicken, dairy, or guess otherwise based on appearance.
    3. DIVISION OF LABOR:
    - Use the USER CAPTION to identify WHAT the food is.
    - Use the IMAGE primarily to estimate the PORTION SIZE, WEIGHT (grams), and visual scale.
    4. UNMENTIONED ITEMS: If items are visible in the photo but omitted from the caption (e.g., a side salad, garnish, bread), identify and estimate them normally.

    User Caption: "{user_notes if user_notes.strip() else 'None provided'}"
    """

    if user_notes:
        prompt += "f\nAdditonal context from the user : {user_notes}"
        
    # Pass the PIL Image object directly into contents alongside the prompt
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=[img, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=MealAnalysis,
            temperature=0.2,
        ),
    )
    return response.parsed
    

if __name__ == "__main__":
    # Example usage with a local photo:
    # Drop any sample food image (e.g., meal.jpg) into your project folder
    test_image = "temp_images/food.jpeg"
    
    if Path(test_image).exists():
        print(f"Analyzing {test_image}...")
        result = parse_meal_image(test_image)
        
        print("\n--- Meal Summary from Image ---")
        print(f"Total Calories: {result.total_calories} kcal")
        for item in result.items:
            print(f"- {item.name} ({item.grams}g): {item.calories} kcal | P: {item.protein}g C: {item.carbs}g F: {item.fat}g")
    else:
        print(f"Place a sample image named '{test_image}' in your directory to test image parsing.")