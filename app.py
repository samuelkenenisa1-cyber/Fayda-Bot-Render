"""
Fayda Ethiopian Digital ID Bot
Render.com SAFE version (Python 3.13)
- No crash at import time
- Lazy BOT_TOKEN loading
- Webhook-based
"""

import os
import io
import json
import time
import logging
import traceback
from datetime import datetime

from flask import Flask, request
import telebot
from telebot import types

from PIL import Image, ImageDraw
import numpy as np
import cv2
from pypdf import PdfReader

# ===================== BASIC SETUP =====================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fayda-bot")

app = Flask(__name__)

bot = None  # lazy init (VERY IMPORTANT)

OUTPUT_DIR = "data"
TEMPLATE_PATH = "template.png"
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ===================== ENV SAFE =====================

def get_bot_token():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        logger.warning("⚠️ BOT_TOKEN not found yet")
    return token


def init_bot():
    global bot
    token = get_bot_token()
    if not token:
        raise RuntimeError("❌ BOT_TOKEN missing at runtime")
    bot = telebot.TeleBot(token, parse_mode="Markdown")
    logger.info("✅ Telegram bot initialized")


# ===================== TEMPLATE =====================

def create_template():
    if os.path.exists(TEMPLATE_PATH):
        return

    img = Image.new("RGB", (1200, 800), "white")
    d = ImageDraw.Draw(img)

    d.rectangle((0, 0, 1200, 100), fill=(0, 122, 51))
    d.text((600, 50), "ETHIOPIAN DIGITAL ID", fill="white", anchor="mm")

    d.rectangle((50, 150, 350, 450), outline="black", width=3)
    d.text((200, 470), "PHOTO", anchor="mm")

    d.rectangle((850, 450, 1150, 750), outline="black", width=3)
    d.text((1000, 760), "QR", anchor="mm")

    img.save(TEMPLATE_PATH)
    logger.info("✅ Template created")


# ===================== QR HANDLING =====================

def find_qr(img: Image.Image):
    cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    detector = cv2.QRCodeDetector()

    data, points, _ = detector.detectAndDecode(cv_img)
    if data:
        return data

    return None


# ===================== PDF PROCESS =====================

def process_pdf(pdf_bytes, user_id):
    reader = PdfReader(io.BytesIO(pdf_bytes))

    page = reader.pages[0]
    text = page.extract_text() or ""

    img = Image.new("RGB", (1000, 1400), "white")
    draw = ImageDraw.Draw(img)
    draw.text((50, 50), "PDF Loaded", fill="black")

    qr_data = find_qr(img)
    if not qr_data:
        return None, "❌ QR code not found"

    try:
        data = json.loads(qr_data)
    except Exception:
        return None, "❌ QR data is not valid JSON"

    create_template()
    template = Image.open(TEMPLATE_PATH).copy()
    d = ImageDraw.Draw(template)

    d.text((400, 200), f"Name: {data.get('fullName','N/A')}")
    d.text((400, 250), f"ID: {data.get('nationalId','N/A')}")

    out = f"{OUTPUT_DIR}/id_{user_id}_{int(time.time())}.png"
    template.save(out)

    return out, data


# ===================== BOT HANDLERS =====================

def register_handlers():

    @bot.message_handler(commands=["start", "help"])
    def start(msg):
        bot.reply_to(
            msg,
            "🪪 *FAYDA ID Bot*\n\nSend your FAYDA PDF and I’ll generate your ID card 🇪🇹",
        )

    @bot.message_handler(content_types=["document"])
    def handle_pdf(msg):
        if not msg.document.file_name.lower().endswith(".pdf"):
            bot.reply_to(msg, "❌ Please send a PDF file")
            return

        file_info = bot.get_file(msg.document.file_id)
        pdf_bytes = bot.download_file(file_info.file_path)

        status = bot.reply_to(msg, "⏳ Processing your PDF...")

        result, info = process_pdf(pdf_bytes, msg.chat.id)

        if not result:
            bot.edit_message_text(info, msg.chat.id, status.message_id)
            return

        with open(result, "rb") as f:
            bot.send_photo(msg.chat.id, f, caption="✅ ID Generated")

        os.remove(result)
        bot.delete_message(msg.chat.id, status.message_id)


# ===================== FLASK ROUTES =====================

@app.route("/")
def home():
    return "✅ Fayda ID Bot is running"


@app.route("/health")
def health():
    return {"status": "ok", "time": datetime.now().isoformat()}


@app.route("/webhook", methods=["POST"])
def webhook():
    if request.headers.get("content-type") == "application/json":
        update = telebot.types.Update.de_json(
            request.get_data().decode("utf-8")
        )
        bot.process_new_updates([update])
        return "", 200
    return "invalid", 403


# ===================== MAIN =====================

if __name__ == "__main__":
    print("🔎 ENV KEYS:", list(os.environ.keys()))

    init_bot()
    register_handlers()

    if os.environ.get("RENDER"):
        bot.remove_webhook()
        time.sleep(1)

        url = os.environ.get("RENDER_EXTERNAL_URL")
        if url:
            bot.set_webhook(f"{url}/webhook")
            logger.info(f"🔗 Webhook set: {url}/webhook")

        port = int(os.environ.get("PORT", 5000))
        app.run(host="0.0.0.0", port=port)

    else:
        bot.remove_webhook()
        bot.infinity_polling()
