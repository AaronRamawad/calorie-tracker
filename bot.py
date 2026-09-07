import asyncio
import io
import logging
import os
import sys
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from database import init_db, save_meal, get_daily_summary, delete_meal, get_recent_meals
from parser import parse_meal_text, parse_meal_image, MealAnalysis

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is missing from .env")

dp = Dispatcher()

# --------- Response Formatting Helpers -----------------

def format_meal_reply(meal_desc: str, meal_id: int, analysis: MealAnalysis) -> str:
    lines = [
        f"✅ <b>Meal Logged (ID: {meal_id})</b>",
        f"<i>{meal_desc}</i>",
        f"\n<b>Total:</b> {analysis.total_calories} kcal\n",
    ]
    for item in analysis.items:
        lines.append(
            f"• {item.name} ({item.grams}g): {item.calories} kcal "
            f"[P: {item.protein}g | C: {item.carbs}g | F: {item.fat}g]"
        )
    return "\n".join(lines)

def format_daily_summary_reply() -> str:
    summary = get_daily_summary()
    return (
        f"\n📊 <b>Today's Running Total</b>\n"
        f"• Meals Logged: {summary['meals_logged']}\n"
        f"• Calories: <b>{summary['total_calories']} kcal</b>\n"
        f"• Protein: {summary['protein_g']}g\n"
        f"• Carbs: {summary['carbs_g']}g\n"
        f"• Fat: {summary['fat_g']}g"
    )
    
# ------ Bot Command Handlers --------

@dp.message(CommandStart())
async def handle_start(message: Message):
    await message.answer(
        "👋 <b>Welcome to your AI Calorie Tracker!</b>\n\n"
        "How to use:\n"
        "• <b>Text:</b> Send what you ate (e.g. <i>'2 eggs, toast with butter'</i>)\n"
        "• <b>Photo:</b> Snap/upload a meal photo (add a caption for cooking oils, etc.)\n"
        "• <b>/summary:</b> View your macro totals for today\n"
        "• <b>/recent:</b> View last 5 meals and their IDs\n"
        "• <b>/delete &lt;id&gt;:</b> Delete a specific meal entry\n"
    )
    
@dp.message(Command("summary"))
async def handle_summary(message: Message):
    await message.answer(format_daily_summary_reply())
    
@dp.message(Command("recent"))
async def handle_recent(message: Message):
    meals = get_recent_meals(limit=5)
    if not meals:
        await message.answer("No meals recorded yet.")
        return
    
    lines = ["🕒 <b>Recent Meals:</b>\n"]
    for m in meals:
        lines.append(f"• <b>[ID: {m['id']}]</b> {m['desc']} — {m['calories']} kcal")
    lines.append("\nTo remove an entry, type <code>/delete &lt;id&gt;</code>")
    await message.answer("\n".join(lines))
    
@dp.message(Command("delete"))
async def handle_delete(message: Message):
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("⚠️ Usage: <code>/delete &lt;meal_id&gt;</code>\nUse /recent to see IDs.")
        return
    
    meal_id = int(args[1])
    success = delete_meal(meal_id)
    
    if success:
        reply = f"🗑️ Deleted meal ID {meal_id}.\n" + format_daily_summary_reply()
        await message.answer(reply)
    else:
        await message.answer(f"❌ Could not find meal with ID {meal_id}.")
        
# ---- Message Ingestion Handlers ----

@dp.message(F.photo)
async def handle_photo(message: Message, bot: Bot):
    status_msg = await message.answer("🔍 Analyzing image...")
    
    try:
        # Telegram sends multiple photo sizes so we set it to the highest resolution
        photo = message.photo[-1]
        
        # Download photo directly to the memomry buffer
        photo_bytes = io.BytesIO()
        await bot.download(photo, destination=photo_bytes)
        photo_bytes.seek(0)
        
        user_caption = message.caption or ""
        
        # Run the Gemini analysis in a thread to keep the asyncio event loop unblocked
        analysis = await asyncio.to_thread(parse_meal_image, photo_bytes, user_caption)
        
        desc = f"Photo" + (f" ({user_caption})" if user_caption else "")
        meal_id = save_meal(desc, analysis)
        
        reply = format_meal_reply(desc, meal_id, analysis) + "\n\n" + format_daily_summary_reply()
        await status_msg.edit_text(reply)
        
    except Exception as e:
        logging.error(f"Error parsing image: {e}")
        await status_msg.edit_text("❌ Failed to parse image. Please try again.")
        
@dp.message(F.text)
async def handle_text(message: Message):
    # Ignore any unregistered slash comands
    if message.text.startswith("/"):
        return
    
    status_msg = await message.answer("🔍 Estimating macros...")
    
    try:
        meal_text = message.text.strip()
        analysis = await asyncio.to_thread(parse_meal_text, meal_text)
        
        meal_id = save_meal(meal_text, analysis)
        
        reply = format_meal_reply(meal_text, meal_id, analysis) + "\n\n" + format_daily_summary_reply()
        await status_msg.edit_text(reply)
        
    except Exception as e:
        logging.error(f"Error parsing text meal: {e}")
        await status_msg.edit_text("❌ Failed to calculate nutrition. Please try again.")


# --- Execution Entrypoint ---

async def main():
    init_db()
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    print("Bot is running. Open Telegram on your phone and send a message or photo.")
    await dp.start_polling(bot)
    
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())