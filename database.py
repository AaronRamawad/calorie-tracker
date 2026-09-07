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
                (meal_id, item.name, item.grams, item.calories, item.protein, item.carbs, item.fat),
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
        
def delete_meal(meal_id: int) -> bool:
    # Deletes a meal and its associated ingredients by ID
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        
        # Deletes a related ingredients first (foreign key dependency)
        cursor.execute("DELETE FROM food_items WHERE meal_id = ?", (meal_id,))
        cursor.execute("DELETE FROM meals WHERE id = ?", (meal_id,))
        conn.commit()
        return cursor.rowcount > 0
    
def get_recent_meals(limit: int = 5) -> list[dict]:
    # Fetches recent meals so you know which ID to delete
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, timestamp, meal_description, total_calories
            FROM meals
            ORDER BY id DESC LIMIT ?
            """,
            (limit,),               
        )
        rows = cursor.fetchall()
        return [
            {"id": r[0], "time": r[1], "desc": r[2], "calories": r[3]} for r in rows
        ]
        
def clear_today_meals(target_date: str = None) -> int:
    # Deletes all meals logged for today and returns the count removed
    if target_date is None:
        target_date = datetime.utcnow().strftime("%Y-%m-%d")
        
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        
        # Delete associated food items for meals matching today's date
        cursor.execute(
            """
            DELETE FROM food_items
            WHERE meal_id IN (
                SELECT id FROM meals WHERE DATE(timestamp) = DATE(?)
            )
            """,
            (target_date,),
        )
        
        # Delete the meals themselves
        cursor.execute(
            "DELETE FROM meals WHERE DATE(timestamp) = DATE(?)",
            (target_date,),
        )
        deleted_count = cursor.rowcount
        conn.commit()
        return deleted_count
    
def reset_all_data() -> None:
    # Permantly drops all records from both tables
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM food_items")
        cursor.execute("DELETE FROM meals")
            
        # Reset the autoincrement ID counters badck to 1
        cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('meals', 'food_items')")
        conn.commit()
        
def get_meal_by_id(meal_id: int) -> dict | None:
    # Fetches a meal and its food items by meal_id
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, meal_description, total_calories FROM meals WHERE id = ?", (meal_id,),)
        meal_row = cursor.fetchone()
        if not meal_row:
            return None
        
        cursor.execute("SELECT name, grams, calories, protein, carbs, fat FROM food_items WHERE meal_id = ?", (meal_id,))
        items = cursor.fetchall()
        
        return {
            "id": meal_row[0],
            "description": meal_row[1],
            "total_calories": meal_row[2],
            "items": [
                {"name": r[0], "grams": r[1], "calories": r[2], "protein": r[3], "carbs": r[4], "fat": r[5]}
                for r in items
            ],
        }
        
def update_meal(meal_id: int, new_description: str, analysis: MealAnalysis) -> bool:
    # Replaces food items and updates total calories for an existing meal
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        
        # Verify that meal exist
        cursor.execute("SELECT id FROM meals WHERE id = ?", (meal_id,))
        if not cursor.fetchone():
            return False
        
        # Update parent meal
        cursor.execute(
            "UPDATE meals SET meal_description = ?, total_calories = ? WHERE id = ?",
            (new_description, analysis.total_calories, meal_id)
        )
        
        # Clear old line items and update the revised ones
        cursor.execute("DELETE FROM food_items WHERE meal_id = ?", (meal_id,))
        for item in analysis.items:
            cursor.execute(
                """
                INSERT INTO food_items (meal_id, name, grams, calories, protein, carbs, fat)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (meal_id, item.name, item.grams, item.calories, item.protein, item.carbs, item.fat),
            )
        conn.commit()
        return True