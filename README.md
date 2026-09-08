# AI Calorie & Macro Tracker

A private, autonomous calorie and macronutrient tracking bot powered by Python, `aiogram` v3, SQLite, and the Google Gemini API (`gemini-2.5-flash`).

---

## Overview

The **AI Calorie & Macro Tracker** is a self-hosted personal AI wrapper designed to eliminate the friction of manual calorie counting. Instead of manually searching through bloated food databases or navigating multi-screen mobile apps, you log meals by sending a text message or snapping a photo inside Telegram.

By pairing Telegram's native cross-platform interface with Gemini's multimodal inference, the system accurately estimates portion sizes, calculates calorie and macro breakdowns (protein, carbohydrates, fat), and persists relational data locally on your own hardware. The system prioritizes speed, absolute data ownership, and zero recurring subscription fees.

---

## Core Features

* **Multimodal Vision & Prompt Precedence**: Send meal photos directly from your phone. The vision parser enforces strict prompt precedence: user-provided text captions serve as absolute ground truth for ingredients and preparation methods (e.g., distinguishing turkey bacon from pork bacon or oat milk from dairy), while image pixels are used to evaluate portion sizing and plate volume.
* **Natural Language Text Ingestion**: Send freeform text logs (e.g., *"3 scrambled eggs with 1 tbsp butter and a slice of sourdough toast"*) to receive instant itemized breakdowns.
* **Deterministic Structured Outputs**: Uses Gemini's native structured outputs (`response_schema`) mapped to Pydantic models, guaranteeing valid JSON formatting and eliminating markdown hallucination artifacts.
* **Relational Local Persistence**: Stores structured data inside a local SQLite database (`calories.db`) across two relational tables (`meals` and `food_items`), allowing granular aggregation and historical reporting.
* **Interactive Editing & Audit Trail**: Correct misidentified foods or portion miscalculations using `/edit <id> <notes>`. The bot injects existing database items and your correction into the model context to recalculate and overwrite the meal cleanly.
* **Access Control & Whitelisting**: An application-level `aiogram` middleware intercepts all incoming updates and rejects any requests originating from numeric Telegram User IDs not explicitly defined in your environment configuration.

---

## Architecture & Data Flow

```text
  [ Telegram Mobile / Desktop Client ]
                   │
                   ▼ (HTTPS / Long Polling)
         [ aiogram v3 Bot ]
                   │
                   ▼
       ┌───────────────────────┐
       │  Whitelist Middleware │ ──► Unauthorized ID? ──► [ Access Denied (403) ]
       └───────────────────────┘
                   │ Authorized User
                   ▼
         [ Command / Event Router ]
        /            │            \
       /             │             \
 [ Slash Commands ]  [ Text Message ] [ Photo Upload ]
   (/summary, etc.)         │                  │
       │                    ▼                  ▼
       │             [ Parser Engine (parser.py) ]
       │                    │
       │                    ├─► Offload to Worker Thread (asyncio.to_thread)
       │                    └─► Gemini 2.5 Flash API (Structured Pydantic JSON)
       │                                       │
       │                                       ▼
       └───────────────► [ Persistence Layer (database.py) ] ◄──┘
                                       │
                                       ▼
                                [ calories.db ]
                          (meals & food_items tables)

```

---

## Prerequisites & Installation

### 1. System Requirements

* Python 3.11 or newer
* A Telegram Bot Token (obtained from [@BotFather](https://t.me/BotFather))
* A Google Gemini API Key (obtained from [Google AI Studio](https://aistudio.google.com/))
* Your numeric Telegram User ID (obtained from [@userinfobot](https://t.me/userinfobot))

### 2. Clone the Repository

```bash
git clone https://github.com/AaronRamawad/calorie-tracker.git
cd calorie-tracker

```

### 3. Set Up Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate

```

### 4. Install Dependencies

```bash
pip install -r requirements.txt

```

### 5. Configure Environment Variables

Create a `.env` file in the root directory:

```bash
cp .env.example .env

```

Populate the file with your credentials:

```env
TELEGRAM_BOT_TOKEN="1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ"
GEMINI_API_KEY="AIzaSyYourGeminiApiKeyHere"
ALLOWED_USERS="123456789"

```

> **Note**: For multiple authorized users, supply comma-separated numeric IDs: `ALLOWED_USERS="123456789,987654321"`

---

## Command Reference

| Command | Arguments | Description |
| --- | --- | --- |
| `/start` | None | Initializes chat, prints bot capabilities and usage instructions. |
| `/summary` | None | Displays today's aggregated metrics: total meals, calories, protein, carbs, and fat. |
| `/recent` | None | Lists the 5 most recent meal logs alongside their database IDs, descriptions, and calories. |
| `/edit` | `<id> <notes>` | Re-evaluates meal `<id>` with Gemini based on user instructions and overwrites SQLite records. |
| `/delete` | `<id>` | Deletes the meal record with ID `<id>` and cascades deletion to child `food_items`. |
| `/cleartoday` | None | Removes all meals and food items logged during the current UTC day. |
| `/reset` | `confirm` | Wipes all records from `meals` and `food_items`, resetting autoincrement counters. |

---

## Local Deployment (systemd)

To run the bot 24/7 on local Linux hardware (such as an Arch Linux or Debian/Ubuntu home server) without keeping an open terminal, configure it as a `systemd` background service.

### 1. Create Service Unit File

```bash
sudo nano /etc/systemd/system/calorie-bot.service

```

Paste the following unit definition (adjust paths and user accordingly):

```ini
[Unit]
Description=Telegram AI Calorie & Macro Tracker
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/home/your_username/calorie-tracker
ExecStart=/home/your_username/calorie-tracker/venv/bin/python bot.py
Restart=always
RestartSec=5
EnvironmentFile=/home/your_username/calorie-tracker/.env

[Install]
WantedBy=multi-user.target

```

### 2. Enable and Start the Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable calorie-bot.service
sudo systemctl start calorie-bot.service

```

### 3. Verify Operational Status & Logs

```bash
# Check service status
sudo systemctl status calorie-bot.service

# Follow live application logs
journalctl -u calorie-bot.service -f

```

---

## Security Considerations

* **Authorization at the Edge**: The application implements an `aiogram` `BaseMiddleware` that filters all incoming events by `from_user.id` against `ALLOWED_USERS`. Unlisted IDs are denied execution, safeguarding your private database and preventing Gemini API quota exhaustion.
* **Local-First Data Ownership**: All nutritional logs, timestamps, and food items reside strictly inside the local `calories.db` SQLite file. No external database or analytics tracking is utilized.
* **Secrets Isolation**: The `.env` file is excluded via `.gitignore` to avoid leaking credentials to version control. Pass API tokens strictly using environment variables or systemd unit definitions.
