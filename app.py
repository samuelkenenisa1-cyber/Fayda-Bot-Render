"""
Fayda Ethiopian Digital ID Card Generator
Python 3.13 compatible – Render Free Plan Safe
"""

import os
import io
import json
import time
import logging
import traceback
from datetime import datetime

from flask import Flask, request
from telebot import TeleBot, types

from PIL import Image, ImageDraw, ImageFont
import numpy as np
import cv2
from pypdf import PdfReader

# ===================== BASIC SETUP =====================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fayda-bot")

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN environment variable not set")

bot = TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__)

BASE_DIR = os.getcwd()
OUTPUT_DIR = os.path.join(BASE_DIR, "data")
TEMPLATE_PATH = os.path.join(BASE_DIR, "assets", "template.png")
FONT_PATH = os.path.join(BASE_DIR, "assets", "fonts", "arial.ttf")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ===================== SAFE UTILITIES =====================

def safe_qr_decode(pil_image):
    """Lazy QR decode (prevents Render boot crash)"""
    from pyzbar.pyzbar import decode
    cv_img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    results = decode(cv_img)
    if not results:
        return None
    return results[0].data.decode("utf-8", errors="ignore")

def extract_pdf_page_image(pdf_bytes):
    """Render-safe PDF handling (no pdf2image)"""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    if not reader.pages:
        raise ValueError("Empty PDF")

    # placeholder canvas
    img = Image.new("RGB", (1200, 1600), "white")
    draw = ImageDraw.Draw(img)

    text = reader.pages[0].extract_text() or ""
    draw.text((40, 40), "PDF loaded successfully", fill="black")
    draw.text((40, 80), text[:500], fill="black")

    return img

def load_font(size=24):
    try:
        if os.path.exists(FONT_PATH):
            return ImageFont.truetype(FONT_PATH, size)
    except Exception:
        pass
    return ImageFont.load_default()

# ===================== TEMPLATE =====================

def create_template():
    if os.path.exists(TEMPLATE_PATH):
        return

    os.makedirs(os.path.dirname(TEMPLATE_PATH), exist_ok=True)

    img = Image.new("RGB", (1500, 1000), "white")
    d = ImageDraw.Draw(img)

    d.rectangle((0, 0, 1500, 120), fill=(0, 122, 51))
    d.text((750, 60), "ETHIOPIAN DIGITAL ID", anchor="mm",
           fill="white", font=load_font(36))

    d.rectangle((80, 180, 380, 480), outline="black", width=3)
    d.text((230, 500), "PHOTO", anchor="mm")

    labels = [
        "Name", "DOB", "Gender", "Phone",
        "Address", "Nationality", "ID Number", "Expiry"
    ]

    y = 200
    for lbl in labels:
        d.text((420, y), f"{lbl}:", fill="black", font=load_font(22))
        y += 50

    d.rectangle((1100, 650, 1400, 950), outline="black", width=3)
    d.text((1250, 970), "QR CODE", anchor="mm")

    img.save(TEMPLATE_PATH)
    logger.info("✅ Template created")

# ===================== MAIN PROCESS =====================

def generate_id(pdf_bytes, user_id):
    create_template()

    template = Image.open(TEMPLATE_PATH).convert("RGB")
    draw = ImageDraw.Draw(template)
    font = load_font(22)

    pdf_img = extract_pdf_page_image(pdf_bytes)

    qr_raw = safe_qr_decode(pdf_img)
    if not qr_raw:
        return None, "QR code not found"

    try:
        qr_raw = qr_raw.replace("'", '"')
        data = json.loads(qr_raw)
    except Exception:
        return None, "Invalid QR JSON"

    info = {
        "name": data.get("fullName", "N/A"),
        "dob": data.get("dateOfBirth", "N/A"),
        "gender": data.get("sex", "N/A"),
        "phone": data.get("phone", "N/A"),
        "address": data.get("address", "N/A"),
        "nationality": data.get("nationality", "Ethiopian"),
        "id": data.get("nationalId", "N/A"),
        "expiry": data.get("expiryDate", "N/A"),
    }

    values = [
        info["name"],
        info["dob"],
        info["gender"],
        info["phone"],
        info["address"][:30],
        info["nationality"],
        info["id"],
        info["expiry"],
    ]

    y = 200
    for val in values:
        draw.text((580, y), str(val), fill="black", font=font)
        y += 50

    output_path = os.path.join(
        OUTPUT_DIR,
        f"fayda_{user_id}_{int(time.time())}.png"
    )
    template.save(output_path)
    return output_path, info

# ===================== TELEGRAM =====================

@bot.message_handler(commands=["start", "help"])
def start(msg):
    bot.send_message(
        msg.chat.id,
        "🪪 *FAYDA Digital ID Generator*\n\nSend a FAYDA PDF to begin.",
        parse_mode="Markdown"
    )

@bot.message_handler(content_types=["document"])
def handle_pdf(msg):
    try:
        if not msg.document.file_name.lower().endswith(".pdf"):
            bot.reply_to(msg, "❌ Please send a PDF file")
            return

        status = bot.reply_to(msg, "⏳ Processing PDF...")
        file_info = bot.get_file(msg.document.file_id)
        pdf_bytes = bot.download_file(file_info.file_path)

        result, info = generate_id(pdf_bytes, msg.chat.id)

        if not result:
            bot.edit_message_text(f"❌ {info}", msg.chat.id, status.message_id)
            return

        with open(result, "rb") as f:
            bot.send_photo(
                msg.chat.id,
                f,
                caption=f"✅ *ID Generated*\n\n👤 {info['name']}\n🆔 {info['id']}",
                parse_mode="Markdown"
            )

        os.remove(result)
        bot.delete_message(msg.chat.id, status.message_id)

    except Exception as e:
        logger.error(traceback.format_exc())
        bot.reply_to(msg, f"❌ Error: {e}")

# ===================== FLASK =====================

@app.route("/")
def index():
    return "✅ Fayda ID Bot is running"

@app.route("/webhook", methods=["POST"])
def webhook():
    update = types.Update.de_json(request.get_json(force=True))
    bot.process_new_updates([update])
    return "", 200

# ===================== START =====================

if __name__ == "__main__":
    create_template()

    if os.environ.get("RENDER"):
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(os.environ["RENDER_EXTERNAL_URL"] + "/webhook")
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
    else:
        bot.polling(none_stop=True)
