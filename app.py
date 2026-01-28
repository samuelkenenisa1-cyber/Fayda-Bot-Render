import os
import io
import time
import logging

from flask import Flask, request
import telebot

from PIL import Image
import cv2
import numpy as np
import requests
from pypdf import PdfReader

# =========================
# CONFIG
# =========================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable not set")

RENDER = os.environ.get("RENDER", False)
PORT = int(os.environ.get("PORT", 10000))

bot = telebot.TeleBot(BOT_TOKEN, threaded=True)
app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =========================
# QR DETECTION (OpenCV ONLY)
# =========================

def find_qr_code_in_image(img: Image.Image):
    """
    Detect QR code using OpenCV QRCodeDetector (Render-safe)
    """
    try:
        cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        detector = cv2.QRCodeDetector()
        data, points, _ = detector.detectAndDecode(cv_img)

        if data:
            logger.info("✅ QR detected")
            return data

    except Exception as e:
        logger.error(f"QR detection error: {e}")

    logger.warning("❌ QR not found")
    return None


# =========================
# PDF HANDLING
# =========================

def extract_images_from_pdf(pdf_bytes):
    """
    Extract images from PDF pages (simple approach)
    """
    images = []

    reader = PdfReader(io.BytesIO(pdf_bytes))
    for page in reader.pages:
        if "/XObject" in page["/Resources"]:
            xobjects = page["/Resources"]["/XObject"].get_object()
            for obj in xobjects:
                xobj = xobjects[obj]
                if xobj["/Subtype"] == "/Image":
                    data = xobj.get_data()
                    try:
                        img = Image.open(io.BytesIO(data)).convert("RGB")
                        images.append(img)
                    except Exception:
                        continue
    return images


# =========================
# TELEGRAM HANDLERS
# =========================

@bot.message_handler(commands=["start", "help"])
def start_handler(message):
    bot.reply_to(
        message,
        "👋 Send me a Fayda ID image or PDF.\n"
        "I’ll extract the QR code for you."
    )


@bot.message_handler(content_types=["photo"])
def photo_handler(message):
    try:
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        file_data = bot.download_file(file_info.file_path)

        img = Image.open(io.BytesIO(file_data)).convert("RGB")
        qr_data = find_qr_code_in_image(img)

        if qr_data:
            bot.reply_to(message, f"✅ QR Code Found:\n\n{qr_data}")
        else:
            bot.reply_to(message, "❌ No QR code found in the image.")

    except Exception as e:
        logger.exception(e)
        bot.reply_to(message, "⚠️ Failed to process image.")


@bot.message_handler(content_types=["document"])
def document_handler(message):
    try:
        file_name = message.document.file_name.lower()
        file_info = bot.get_file(message.document.file_id)
        file_data = bot.download_file(file_info.file_path)

        # ================= PDF =================
        if file_name.endswith(".pdf"):
            images = extract_images_from_pdf(file_data)

            for img in images:
                qr_data = find_qr_code_in_image(img)
                if qr_data:
                    bot.reply_to(message, f"✅ QR Code Found:\n\n{qr_data}")
                    return

            bot.reply_to(message, "❌ No QR code found in the PDF.")
            return

        # ================= IMAGE =================
        img = Image.open(io.BytesIO(file_data)).convert("RGB")
        qr_data = find_qr_code_in_image(img)

        if qr_data:
            bot.reply_to(message, f"✅ QR Code Found:\n\n{qr_data}")
        else:
            bot.reply_to(message, "❌ No QR code found in the file.")

    except Exception as e:
        logger.exception(e)
        bot.reply_to(message, "⚠️ Failed to process document.")


# =========================
# FLASK WEBHOOK
# =========================

@app.route("/webhook", methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200


@app.route("/")
def index():
    return "Fayda ID Bot is running ✅", 200


# =========================
# STARTUP LOGIC
# =========================

if __name__ == "__main__":
    if RENDER:
        render_url = os.environ.get("RENDER_EXTERNAL_URL")
        if not render_url:
            raise RuntimeError("RENDER_EXTERNAL_URL not set")

        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=f"{render_url}/webhook")

        logger.info("🚀 Bot running on Render with webhook")
        app.run(host="0.0.0.0", port=PORT)

    else:
        logger.info("🤖 Bot running locally with polling")
        bot.infinity_polling(timeout=30, long_polling_timeout=30)
