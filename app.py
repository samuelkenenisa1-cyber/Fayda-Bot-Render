import os
import cv2
import numpy as np
import telebot
from telebot.types import Message
from pdf2image import convert_from_bytes

# ================== CONFIG ==================

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ BOT_TOKEN environment variable not set")
    exit(1)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ================== HELPERS ==================

def extract_qr_from_pdf(pdf_bytes: bytes):
    """
    Converts first page of PDF to image and extracts QR using OpenCV
    """
    try:
        images = convert_from_bytes(
            pdf_bytes,
            dpi=200,
            first_page=1,
            last_page=1,
            poppler_path="/usr/bin"
        )
    except Exception as e:
        return None, f"❌ PDF conversion failed: {e}"

    if not images:
        return None, "❌ No image generated from PDF"

    # Convert PIL image → OpenCV format
    pil_img = images[0].convert("RGB")
    img_np = np.array(pil_img)
    img_cv = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

    detector = cv2.QRCodeDetector()
    data, _, _ = detector.detectAndDecode(img_cv)

    if not data:
        return None, "❌ QR code not found in PDF"

    return data, None

# ================== BOT HANDLERS ==================

@bot.message_handler(commands=["start"])
def start(message: Message):
    bot.reply_to(
        message,
        "👋 <b>Fayda ID Bot</b>\n\n"
        "📄 Send your Fayda PDF and I will extract the QR code."
    )

@bot.message_handler(content_types=["document"])
def handle_pdf(message: Message):
    if not message.document.file_name.lower().endswith(".pdf"):
        bot.reply_to(message, "❌ Please send a PDF file.")
        return

    status = bot.reply_to(message, "⏳ Processing your PDF...")

    try:
        file_info = bot.get_file(message.document.file_id)
        pdf_bytes = bot.download_file(file_info.file_path)

        qr_data, error = extract_qr_from_pdf(pdf_bytes)

        if error:
            bot.edit_message_text(
                error,
                chat_id=message.chat.id,
                message_id=status.message_id
            )
            return

        bot.edit_message_text(
            "✅ <b>QR Code Found</b>\n\n<code>{}</code>".format(qr_data),
            chat_id=message.chat.id,
            message_id=status.message_id
        )

    except Exception as e:
        bot.edit_message_text(
            f"❌ Unexpected error: {e}",
            chat_id=message.chat.id,
            message_id=status.message_id
        )

# ================== RUN ==================

print("🤖 Fayda Bot is running...")
bot.infinity_polling(timeout=30, long_polling_timeout=30)
