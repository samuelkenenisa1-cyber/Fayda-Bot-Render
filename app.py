import os
import io
import telebot
from telebot.types import Message
from pdf2image import convert_from_bytes
from PIL import Image
from pyzbar.pyzbar import decode

# ================== CONFIG ==================

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ BOT_TOKEN environment variable not set")
    exit(1)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ================== HELPERS ==================

def extract_qr_from_pdf(pdf_bytes: bytes):
    """
    Converts first page of PDF to image and scans for QR
    Returns: (qr_data or None, error_message or None)
    """
    try:
        images = convert_from_bytes(
            pdf_bytes,
            dpi=150,                 # low DPI = faster on Render Free
            first_page=1,
            last_page=1,
            poppler_path="/usr/bin"  # REQUIRED on Render
        )
    except Exception as e:
        return None, f"❌ PDF conversion failed: {e}"

    if not images:
        return None, "❌ PDF conversion failed (no image generated)"

    img = images[0]
    qr_codes = decode(img)

    if not qr_codes:
        return None, "❌ QR code not found in PDF"

    return qr_codes[0].data.decode("utf-8"), None

# ================== BOT HANDLERS ==================

@bot.message_handler(commands=["start"])
def start(message: Message):
    bot.reply_to(
        message,
        "👋 <b>Welcome to Fayda ID Bot</b>\n\n"
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
