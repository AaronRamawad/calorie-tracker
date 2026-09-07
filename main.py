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

from parser import parse_meal_text
from database import init_db, save_meal, get_daily_summary

def main():
    #Setup tables if they do not exist
    init_db()
    
    meal_text = "Chicken breast with a cup of white rice and steamed broccoli"
    print(f"Parsing meal: '{meal_text}'...")
    
    # Step 1: Parse with Gemini
    analysis = parse_meal_text(meal_text)
    
    # Step 2: Save to SQLite
    meal_id = save_meal(meal_text, analysis)
    print(f"Saved meal successfully with ID: {meal_id}")
    
    # Step 3: Check today's totals
    summary = get_daily_summary()
    print("\n--- Today's Nutrition Summary ---")
    print(f"Meals Logged: {summary['meals_logged']}")
    print(f"Calories: {summary['total_calories']} kcal")
    print(f"Protein: {summary['protein_g']}g | Carbs: {summary['carbs_g']}g | Fat: {summary['fat_g']}g")

if __name__ == "__main__":
    main()