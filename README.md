Here is an updated `README.md` formatted to match the original layout, structure, and style while integrating all additions—including the AI Fitness Coach, macro-goal management, in-memory coaching cache, and timezone-aligned relational meal breakdowns:

---

```markdown
# 🥗 AI Calorie & Macro Tracker Bot

A private, local-first Telegram bot that tracks daily calories and macronutrients using multimodal computer vision and natural language processing powered by **Google Gemini 2.5 Flash**. The bot logs meals to an SQLite database, supports retroactive editing and deletion, tracks custom daily macronutrient targets, and features an integrated **AI Performance Nutrition Coach** that offers real-time pacing advice and macro-friendly food recommendations.

Designed to run continuously as a lightweight background `systemd` service on Linux (Arch Linux).

---

## ✨ Features

- **Multimodal Logging:** Send a food picture with an optional text caption, or log directly via plain text (e.g., *"3 scrambled eggs with sourdough toast"*).
- **Structured Macro Extraction:** Leverages Gemini 2.5 Flash and Pydantic schemas to deterministically extract itemized ingredients, gram weights, calories, protein, carbs, and fat.
- **Target & Goal Management (`/setgoals`):** Configure custom daily targets for calories, protein, carbs, and fat with persistence in SQLite.
- **AI Performance Nutrition Coach (`/coach`):** Evaluates daily intake against remaining budgets, provides meal quality critiques, and suggests concrete food options to hit target numbers without exceeding calories.
- **In-Memory Performance Caching:** Features a 15-minute MD5 state-based cache for `/coach` to eliminate redundant API calls, reduce latency, and control token usage.
- **Local Timezone Consistency:** Aligns meal timestamps and daily summary resets with the host machine's local time zone instead of UTC.
- **Full Meal Lifecycle Control:**
  - `/summary` for daily aggregate metrics and remaining budget.
  - `/recent` to view the last 5 logged meals with unique IDs.
  - `/edit <id> <notes>` to recalculate and update past meals with extra context.
  - `/delete <id>` to remove individual meal entries.
  - `/cleartoday` to wipe current day logs without resetting historical data.
- **Security & Access Control:** Restricts bot operations exclusively to authorized Telegram User IDs.

---

## 🛠 Tech Stack

- **Language:** Python 3.11+
- **Telegram Framework:** [aiogram 3.x](https://github.com/aiogram/aiogram) (AsyncIO)
- **AI Engine:** [Google GenAI SDK](https://github.com/google-gemini/generative-ai-python) (`gemini-2.5-flash`)
- **Data Validation:** [Pydantic v2](https://github.com/pydantic/pydantic)
- **Database:** SQLite3 (Local storage, relational `meals`, `food_items`, and `user_goals` schema)
- **Host OS:** Arch Linux (managed via `systemd`)

---

## 📁 Project Structure

```text
calorie-tracker/
├── bot.py               # aiogram entrypoint, handlers (/coach, /setgoals), and caching
├── parser.py            # Gemini 2.5 Flash integration, prompts, and Pydantic models
├── database.py          # SQLite persistence, relational joins, and aggregations
├── requirements.txt     # Python project dependencies
├── .env                 # Environment variables (API keys, Telegram IDs)
└── calories.db          # Local SQLite database (created automatically)

```

---

## 🚀 Setup & Installation

### 1. Clone the Repository

```bash
git clone [https://github.com/AaronRamawad/calorie-tracker.git](https://github.com/AaronRamawad/calorie-tracker.git)
cd calorie-tracker

```

### 2. Create and Activate a Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate

```

### 3. Install Dependencies

```bash
pip install -r requirements.txt

```

### 4. Configure Environment Variables

Create a `.env` file in the root directory:

```env
TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
GEMINI_API_KEY="your_google_gemini_api_key"
ALLOWED_TELEGRAM_USER_IDS="your_telegram_numeric_id"

```

> **Note:** Find your Telegram numeric user ID using `@userinfobot` on Telegram.

---

## 🤖 Telegram Bot Commands

| Command | Description | Example |
| --- | --- | --- |
| `/start` | View introduction, instructions, and list of commands | `/start` |
| `/setgoals` | Set daily caloric and macro targets (`<cals> <p> <c> <f>`) | `/setgoals 2200 160 220 70` |
| `/coach` | Get an AI critique, pacing evaluation, and food suggestions | `/coach` |
| `/summary` | View total calories and macros consumed today | `/summary` |
| `/recent` | View the last 5 logged meals with their IDs | `/recent` |
| `/edit` | Re-estimate a meal by ID with corrective notes | `/edit 4 use 2 slices of bread` |
| `/delete` | Delete a specific meal and its food items by ID | `/delete 4` |
| `/cleartoday` | Remove all meals logged today | `/cleartoday` |
| `/reset confirm` | Permanently delete all meals and food history | `/reset confirm` |

---

## ⚙️ Running as a Systemd Service (Linux)

To ensure the bot runs continuously in the background and restarts automatically on system reboots:

1. Create a service file:
```bash
sudo nano /etc/systemd/system/calorie-bot.service

```


2. Add the following unit configuration (update paths and user to match your system):
```ini
[Unit]
Description=Telegram AI Calorie & Nutrition Tracker Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/home/your_username/calorie-tracker
ExecStart=/home/your_username/calorie-tracker/venv/bin/python bot.py
Restart=always
RestartSec=10
EnvironmentFile=/home/your_username/calorie-tracker/.env

[Install]
WantedBy=multi-user.target

```


3. Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable calorie-bot.service
sudo systemctl start calorie-bot.service

```


4. View live logs:
```bash
journalctl -u calorie-bot.service -e -f

```



---

## 🔒 Privacy & Data Storage

* All nutritional records, targets, and logs reside inside the local `calories.db` SQLite database on your host machine.
* Image bytes and meal descriptions are passed directly to Google's Gemini API over TLS exclusively for inference and are not permanently retained in external databases.

```

```
