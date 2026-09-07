'''
Name: Aaron Ramawad
Project: Calorie Tracker

Notes:
Order of Development
1. Core Parser
2. Local Database
3. API / Bot Controller
4. Frontend UI
'''

from pathlib import Path
from parser import parse_meal_text, parse_meal_image, MealAnalysis
from database import init_db, save_meal, get_daily_summary, get_recent_meals, delete_meal

def format_meal_report(meal_desc: str, analysis: MealAnalysis):
    #prints a clean breakdown of the analyzed meal
    print(f"\n===============================")
    print(f"     Meal Loggged: {meal_desc}")
    print(f"Calories: {analysis.total_calories} kcal")
    print("--------------------------------")
    for item in analysis.items:
        print(f"- {item.name} ({item.grams}g): {item.calories} kcal | "
              f"P: {item.protein}g | C: {item.carbs}g | F: {item.fat}g")

def print_daily_summary():
    #Fetches and displays today's aggregated macro totals.
    summary = get_daily_summary()
    print("\n📊 TODAY'S RUNNING TOTAL")
    print(f"Meals Logged Today: {summary['meals_logged']}")
    print(f"Calories: {summary['total_calories']} kcal")
    print(f"Protein : {summary['protein_g']} g")
    print(f"Carbs   : {summary['carbs_g']} g")
    print(f"Fat     : {summary['fat_g']} g")
    print(f"==============================\n")
    
def process_and_log_meal(meal_input: str, is_image: bool = False, notes: str = ""):
    #Core pipeline: parse the input, save to SQLite, and prints report
    if is_image:
        print(f"\nAnalyzing image: {meal_input}...")
        analysis = parse_meal_image(meal_input, user_notes=notes)
        log_desc = meal_input
    else: 
        print(f"\nAnalyzing text: '{meal_input}'...")
        analysis = parse_meal_text(meal_input)
        log_desc = meal_input
        
    # Save meal to database
    meal_id = save_meal(log_desc, analysis)
    print(f"Saved to database (ID: {meal_id})")
    
    # Print individual meal breakdown
    format_meal_report(log_desc, analysis)
    
    # Print the updated daily total
    print_daily_summary()
    
if __name__ == "__main__":
    init_db()
    
    # --- TEST 1: Text Input ---
    #process_and_log_meal("Greek yogurt with blueberries and honey")

    # --- TEST 2: Photo Input ---
    """
    test_image = "temp_images/food.jpeg"
    if Path(test_image).exists():
        process_and_log_meal(test_image, is_image=True, notes="Cooked in 1 tbsp olive oil")
    else:
        print(f"To test image logging, drop a picture named '{test_image}' into your folder and re-run.")
    """ 
    
    # --- TEST 3: Get Recent meals ---
    for meal in get_recent_meals():
        print(f"[{meal['id']}] {meal['desc']} - {meal['calories']} kcal")
        
    # --- TEST 4: Delete Meals ---
    delete_meal(meal_id=1)
        