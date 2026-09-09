import asyncio
import io
import logging
import os
import sys
from dotenv import load_dotenv
from typing import Callable, Dict, Any, Awaitable
import time
import hashlib

from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, TelegramObject

from database import (
    init_db, 
    save_meal, 
    get_daily_summary, 
    delete_meal, 
    get_recent_meals, 
    clear_today_meals, 
    reset_all_data, 
    get_meal_by_id, 
    update_meal,
    set_user_goals,
    get_user_goals,
    get_today_meals_breakdown
)
from parser import (
    parse_meal_text,
    parse_meal_image, 
    MealAnalysis, 
    recalculate_meal_correction,
    generate_coaching_report,
    CoachingReport
)

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

# -------------- Coach Feature ----------------------------

COACH_CACHE = {}
CACHE_TTL_SECONDS = 900 # 15 minutes

def compute_meals_fingerprint(meal: list[dict], summary: dict) -> str:
    # Generate an MD5 signature of today's intake to invalidate cache when data changes.
    raw = "f{summary['total_calories']}:{summary['protein_g']}:{len(meals)}"
    return hashlib.md5(raw.encode()).hexdigest()

def render_coach_html(report: CoachingReport, goals: dict, rem_cals: int, rem_p: float) -> str:
    # Formats structed pydantic report into telegram HTML
    suggestions = ""
    for s in report.closing_strategy:
        suggestions += (
            f"• <b>{s.name}</b> ({s.portion})\n"
            f"  └ <i>{s.calories} kcal | {s.protein_g}g P | {s.carbs_g}g C | {s.fat_g}g F</i>\n"
        )
        
    critique = "\n".join([f"• {c}" for c in report.dietary_critique])
    
    return (
        f"🧠 <b>AI Nutrition Coach</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>Daily Target:</b> <code>{goals['target_calories']} kcal</code> | <code>{goals['target_protein']}g P</code>\n"
        f"⏳ <b>Remaining:</b> <code>{rem_cals} kcal</code> | <code>{rem_p}g P</code>\n\n"
        f"📊 <b>Pacing:</b>\n{report.pacing_status}\n\n"
        f"🔍 <b>Meal Critique:</b>\n{critique}\n\n"
        f"💡 <b>Suggested Next Options:</b>\n{suggestions if suggestions else '• No additional foods needed today.'}\n"
        f"📌 <b>Next Action:</b>\n{report.action_item}"
    )

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
        "• <b>/edit &lt;meal_id&gt; &lt;your correction&gt;</b>: Edit a exisiting meal\n" 
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
    
@dp.message(Command("setgoals"))
async def handle_setgoals(message: Message):
    #Usage /setgoals <calories> <protein> <carbs> <fat>
    args = message.text.split[1:]
    if len (args) != 4:
        await message.answer(
            "⚠️ <b>Format:</b> <code>/setgoals &lt;cals&gt; &lt;protein&gt; &lt;carbs&gt; &lt;fat&gt;</code>\n"
            "<b>Example:</b> <code>/setgoals 2200 160 220 70</code>"
        )
        return
    
    try:
        cals = int(args[0])
        p, c, f = float(args[1]), float(args[2]), float(args[3])
        set_user_goals(message.from_user.id, cals, p, c, f)
        
        # Invalidate Cache
        COACH_CACHE.pop(message.from_user.id, None)
        
        await message.answer(
            f"🎯 <b>Goals Updated:</b>\n"
            f"• Calories: <code>{cals} kcal</code>\n"
            f"• Protein: <code>{p}g</code>\n"
            f"• Carbs: <code>{c}g</code>\n"
            f"• Fat: <code>{f}g</code>"
        )
    except ValueError:
        await message.answer("❌ Invalid values. Enter whole numbers for calories and numbers for macros.")
        
@dp.message(Command("coach"))
async def handle_coach(message: Message):
    user_id = message.from_user.id
    goals = get_user_goals(user_id)
    
    if not goals:
        await message.answer(
            "⚠️ You have not configured your nutritional goals yet.\n"
            "Use <code>/setgoals &lt;calories&gt; &lt;protein&gt; &lt;carbs&gt; &lt;fat&gt;</code> first."
        )
        return
    
    summary = get_daily_summary()
    today_meals = get_today_meals_breakdown()
    current_hash = compute_meals_fingerprint(today_meals, summary)
    now = time.time()
    
    # Check cache validity
    cached = COACH_CACHE.get(user_id)
    if cached and cached["hash"] == current_hash and (now - cached["timestamp"] < CACHE_TTL_SECONDS) :
        await message.answer(cached["text"] + "\n\n<i>(Cached review)</i>")
        return
    
    status_msg = await message.answer("🧠 <i>Analyzing your meals and calculating remaining targets...</i>")
    
    rem_cals = goals["target_calories"] - summary["total_calories"]
    rem_p = round(goals["target_protein"] - summary["protein_g"], 1)
    
    try:
        report = await asyncio.to_thread(generate_coaching_report, goals, summary, today_meals)
        response_text = render_coach_html(report, goals, rem_cals, rem_p)
        
        # Store in cache
        COACH_CACHE[user_id] = {
            "hash": current_hash,
            "text": response_text,
            "timestamp": now
        }
        
        await status_msg.edit(response_text)
    except Exception as err:
        logging.error(f"Error generating coaching advice: {err}")
        # Deterministic offline fallback
        fallback = (
            f"🎯 <b>Daily Target Status (Offline Fallback)</b>\n"
            f"• Consumed: {summary['total_calories']} / {goals['target_calories']} kcal\n"
            f"• Remaining: <b>{rem_cals} kcal</b> | <b>{rem_p}g Protein</b>\n\n"
            f"⚠️ <i>AI Coach is temporarily unavailable. Focus on meeting your remaining protein target.</i>"
        )
        await status_msg.edit_text(fallback)
        

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