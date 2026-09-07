import sqlite3
from datetime import datetime
from parser import MealAnalysis

DB_NAME = "calories.db"

def init_db():
    #Initializes the meals and food items tables.
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        
        # Table to track each meal entry
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS meals (
                id INTEGER  PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                meal_description TEXT,
                total_calories INTEGER
            )
        """)
        
        # Table to track individual items within a meal
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS food_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meal_id INTEGER,
                name TEXT,
                grams REAL,
                calories INTEGER,
                protein REAL,
                carbs REAL,
                fat REAL,
                FOREIGN KEY (meal_id) REFERENCES meals (id)
            )
        """)
        conn.commit()
        
def save_meal(description: str, analysis: MealAnalysis) -> int:
    #Saves a meal and its breakdown to SQLite
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO meals (meal_description, total_calories) VALUES (?, ?)",
            (description, analysis.total_calories),
        )
        meal_id = cursor.lastrowid
        
        for item in analysis.items:
            cursor.execute("""
                INSERT INTO food_items (meal_id, name, grams, calories, protein, carbs, fat)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (meal_id, item.name, item.grams, item.calories, item.protein, item.calories, item.fat),
            )
        conn.commit()
        return meal_id
    
def get_daily_summary(target_date: str = None) -> dict:
    """
    Returns aggregated calories and macros for a given date (YYYY-MM-DD)
    Defaults to today (UTC).
    """
    if target_date is None:
        target_date = datetime.utcnow().strftime("%Y-%m-%d")
        
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                COALESCE(SUM(fi.calories), 0),
                COALESCE(SUM(fi.protein), 0),
                COALESCE(SUM(fi.carbs), 0),
                COALESCE(SUM(fi.fat), 0),
                COUNT(DISTINCT m.id)
            FROM meals m
            JOIN food_items fi ON m.id = fi.meal_id
            WHERE DATE(m.timestamp) = DATE(?)
            """,
            (target_date,),
        )
        cals, protein, carbs, fat, meal_count = cursor.fetchone()
        
        return {
            "date": target_date,
            "meals_logged": meal_count,
            "total_calories": round(cals),
            "protein_g": round(protein, 1),
            "carbs_g": round(carbs, 1),
            "fat_g": round(fat, 1),
        }