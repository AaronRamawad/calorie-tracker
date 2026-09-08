import asyncio
import io
import logging
import os
import sys
from dotenv import load_dotenv
from typing import Callable, Dict, Any, Awaitable

from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, TelegramObject

from database import init_db, save_meal, get_daily_summary, delete_meal, get_recent_meals, clear_today_meals, reset_all_data, get_meal_by_id, update_meal
from parser import parse_meal_text, parse_meal_image, MealAnalysis, recalculate_meal_correction

load_dotenv()

# Parse allowed IDs into a set of integers
ALLOWED_USERS = {
    int(uid.strip())
    for uid in os.getenv("ALLOWED_USERS", "").split(",")
    if uid.strip().isdigit()
}

class WhitelistMiddleware(BaseMiddleware):
    
    #Blocks any incoming mesages from users not defined in ALLOWED_USERS
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        #check if the incoming event is a standard message
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
            
            if user_id not in ALLOWED_USERS:
                logging.warning(f"Unauthorized access attempt by user ID: {user_id} (@{event.from_user.username})")
                await event.answer("⛔ <b>Access Denied:</b> You are not authorized to use this bot.")
                return
            
        return await handler(event, data)


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
        "• <b>Photo:</b> Upload a meal picture with optional caption\n"
        "• <b>/summary:</b> View today's calories and macros\n"
        "• <b>/recent:</b> View last 5 meals and their IDs\n"
        "• <b>/delete &lt;id&gt;:</b> Delete a specific meal\n"
        "• <b>/cleartoday:</b> Clear only today's logged meals\n"
        "• <b>/reset confirm:</b> Wipe all history from the database\n"
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
    
@dp.message(Command("cleartoday"))
async def handle_clear_today(message: Message):
    #Wipes only today's logs (useful for testing and restarting the day)
    count = clear_today_meals()
    if count > 0:
        await message.answer(f"🧹 Cleared <b>{count}</b> meal(s) from today.\n" + format_daily_summary_reply())
    else:
        await message.answer("ℹ️ No meals were recorded for today.")
        
@dp.message(Command("reset"))
async def handle_reset(message: Message):
    # Require user to type '/reset confirm' to prevent accidental database wipes
    args = message.text.split()
    
    # Safety Guard: Check if user typed 'confirm'
    if len(args) < 2 or args[1].lower() != "confirm":
        await message.answer(
            "⚠️ <b>Warning:</b> This will permanently delete <b>all</b> logged meals and history.\n\n"
            "To confirm, send:\n"
            "<code>/reset confirm</code>"
        )
        return

    # User confirmed
    reset_all_data()
    await message.answer("💥 <b>Database reset.</b> All meals and items have been deleted.")

@dp.message(Command("edit"))
async def handle_edit(message: Message):
    '''
    Usage: /edit <id> <what to change>
    Example /edit 3 that was tofu not chicken, and no rice
    '''
    
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3 or not parts[1].isdigit():
        await message.answer(
            "⚠️ <b>Usage:</b>\n"
            "<code>/edit &lt;meal_id&gt; &lt;your correction&gt;</code>\n\n"
            "<b>Example:</b>\n"
            "<code>/edit 2 that was turkey bacon, not pork, and only 1 egg</code>"
        )
        return
    
    meal_id = int(parts[1])
    correction_text = parts[2]
    
    # Fetch current meal from database
    existing_meal = get_meal_by_id(meal_id)
    if not existing_meal:
        await message.answer(f"❌ Could not find meal with ID {meal_id}. Use /recent to check IDs.")
        return
    
    status_msg = await message.answer(f"✏️ Updating Meal #{meal_id}...")
    
    try:
        # Re-parse with Gemini
        revised_analysis = await asyncio.to_thread(
            recalculate_meal_correction, existing_meal["items"], correction_text
        )
        
        #Update SQLite DB
        new_desc = f"{existing_meal['description']} (Edited: {correction_text}"
        update_meal(meal_id, new_desc, revised_analysis)
        
        # Return updated meal & running day totals
        reply = (
            f"🔄 <b>Meal #{meal_id} Updated!</b>\n\n"
            + format_meal_reply(new_desc, meal_id, revised_analysis)
            + "\n\n"
            + format_daily_summary_reply()
        )
        await status_msg.edit_text(reply)
        
    except Exception as e:
        logging.error(f"Error editing meal: {e}")
        await status_msg.edit_text("❌ Failed to update the meal. Please try again.")
    

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
    
    # Register the whitelist middleware on all message events
    
    dp.message.middleware(WhitelistMiddleware())
    
    print("Bot is running. Open Telegram on your phone and send a message or photo.")
    await dp.start_polling(bot)
    
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())