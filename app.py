"""
Fayda Ethiopian Digital ID Card Generator
Using pdf2image for compatibility with Render free tier
"""

import os
import json
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pyzbar.pyzbar import decode
from pdf2image import convert_from_bytes  # CHANGED: Using pdf2image
from datetime import datetime
import telebot
from flask import Flask, request
import logging
import traceback
import time

# ==================== CONFIGURATION ====================

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Get bot token from environment
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN not found!")
    BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

bot = telebot.TeleBot(BOT_TOKEN)

# Configuration
DPI = 150  # Lower DPI for Render free tier memory
TEMPLATE_PATH = "assets/fayda_template.png"
OUTPUT_DIR = "data/processed"
FONT_PATH = "assets/fonts/arial.ttf"

# Ensure directories exist
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==================== PDF PROCESSING ====================

def generate_fayda_id(pdf_bytes, user_id):
    """Generate ID card from PDF using pdf2image"""
    try:
        # Check/create template
        if not os.path.exists(TEMPLATE_PATH):
            create_default_template()
        
        # Load template
        template = Image.open(TEMPLATE_PATH).convert("RGB")
        draw = ImageDraw.Draw(template)
        
        # ===== CONVERT PDF TO IMAGE (pdf2image) =====
        try:
            images = convert_from_bytes(pdf_bytes, dpi=DPI, fmt='png')
            pdf_img = images[0]  # Get first page
            logger.info(f"📄 PDF converted: {pdf_img.size}")
        except Exception as e:
            logger.error(f"❌ PDF conversion failed: {e}")
            return None, f"PDF conversion failed: {str(e)}"
        
        # ===== EXTRACT PHOTO =====
        try:
            photo_crop = pdf_img.crop((100, 250, 550, 850))
            photo = photo_crop.resize((300, 300))
            template.paste(photo, (80, 180))
            logger.info("✅ Photo extracted")
        except Exception as e:
            logger.warning(f"⚠️ Photo extraction failed: {e}")
        
        # ===== FIND QR CODE =====
        qr_found = False
        qr_data = None
        qr_image = None
        
        search_areas = [
            (1200, 700, 1650, 1150),
            (1100, 650, 1550, 1100),
            (1000, 600, 1450, 1050),
        ]
        
        for area in search_areas:
            try:
                qr_crop = pdf_img.crop(area)
                qr_cv = cv2.cvtColor(np.array(qr_crop), cv2.COLOR_RGB2BGR)
                decoded = decode(qr_cv)
                
                if decoded:
                    qr_data = decoded[0].data.decode("utf-8", errors='ignore')
                    qr_image = qr_crop
                    qr_found = True
                    logger.info(f"✅ QR found")
                    break
            except:
                continue
        
        if not qr_found:
            return None, "QR code not found"
        
        # ===== PARSE QR DATA =====
        try:
            qr_data = qr_data.replace("'", '"').replace("None", "null")
            data = json.loads(qr_data)
        except:
            return None, "Invalid QR code data"
        
        # Extract information
        info = {
            'name': data.get("fullName", "N/A"),
            'dob': data.get("dateOfBirth", "N/A"),
            'gender': data.get("sex", "N/A"),
            'id': data.get("nationalId", "N/A"),
            'address': data.get("address", "N/A"),
            'phone': data.get("phone", "N/A"),
            'nationality': data.get("nationality", "Ethiopian"),
            'expiry': data.get("expiryDate", "N/A")
        }
        
        # ===== ADD TEXT TO TEMPLATE =====
        try:
            font = ImageFont.load_default()
            
            # Text positions
            text_x = 400
            text_y = 200
            line_height = 50
            
            draw.text((text_x, text_y), str(info['name']), font=font, fill='black')
            draw.text((text_x, text_y + line_height), f"DOB: {info['dob']}", font=font, fill='black')
            draw.text((text_x, text_y + line_height*2), f"Gender: {info['gender']}", font=font, fill='black')
            draw.text((text_x, text_y + line_height*3), f"Expiry: {info['expiry']}", font=font, fill='black')
            draw.text((text_x, text_y + line_height*4), f"Phone: {info['phone']}", font=font, fill='black')
            draw.text((text_x, text_y + line_height*5), f"Nationality: {info['nationality']}", font=font, fill='black')
            draw.text((text_x, text_y + line_height*6), f"Address: {info['address'][:30]}...", font=font, fill='black')
            draw.text((text_x, text_y + line_height*7), f"ID: {info['id']}", font=font, fill='black')
            
        except Exception as e:
            logger.error(f"⚠️ Text error: {e}")
        
        # ===== PASTE QR CODE =====
        if qr_image:
            template.paste(qr_image.resize((300, 300)), (1100, 700))
        
        # ===== SAVE OUTPUT =====
        output_path = os.path.join(OUTPUT_DIR, f"{user_id}_{int(time.time())}.png")
        template.save(output_path)
        
        return output_path, info
        
    except Exception as e:
        logger.error(f"❌ Processing error: {str(e)}")
        return None, f"Error: {str(e)}"

# ==================== TEMPLATE FUNCTION ====================

def create_default_template():
    """Create default template if none exists"""
    try:
        template = Image.new('RGB', (1500, 1000), color='white')
        draw = ImageDraw.Draw(template)
        
        # Header
        draw.rectangle([(0, 0), (1500, 100)], fill=(0, 122, 51))
        
        # Photo area
        draw.rectangle([(80, 180), (380, 480)], outline='black', width=3)
        
        # QR area
        draw.rectangle([(1100, 700), (1400, 1000)], outline='black', width=3)
        
        # Save
        template.save(TEMPLATE_PATH)
        logger.info(f"✅ Created default template")
        
    except Exception as e:
        logger.error(f"❌ Template creation failed: {e}")

# ==================== TELEGRAM BOT ====================

@bot.message_handler(commands=['start'])
def start_handler(message):
    welcome = """
    🪪 *Ethiopian Digital ID Card Generator*
    
    Send me a FAYDA PDF to create an ID card!
    
    Made with ❤️ on Render.com
    """
    bot.send_message(message.chat.id, welcome, parse_mode='Markdown')

@bot.message_handler(content_types=['document'])
def handle_pdf(message):
    try:
        chat_id = message.chat.id
        
        if not message.document.file_name.lower().endswith('.pdf'):
            bot.reply_to(message, "❌ Please send a PDF file!")
            return
        
        processing_msg = bot.reply_to(message, "📥 Downloading PDF...")
        
        # Download file
        file_info = bot.get_file(message.document.file_id)
        file_bytes = bot.download_file(file_info.file_path)
        
        bot.edit_message_text("🔄 Processing PDF...", chat_id, processing_msg.message_id)
        
        # Generate ID card
        output_path, info = generate_fayda_id(file_bytes, chat_id)
        
        if output_path and os.path.exists(output_path):
            with open(output_path, 'rb') as photo:
                caption = f"""
✅ *ID Card Generated*
                
👤 *Name:* {info['name']}
🆔 *ID:* {info['id']}
📅 *DOB:* {info['dob']}
⚧️ *Gender:* {info['gender']}
                """
                bot.send_photo(chat_id, photo, caption=caption, parse_mode='Markdown')
            
            os.remove(output_path)
            bot.delete_message(chat_id, processing_msg.message_id)
        else:
            error_msg = f"❌ Failed: {info}"
            bot.edit_message_text(error_msg, chat_id, processing_msg.message_id)
            
    except Exception as e:
        error_text = f"❌ Error: {str(e)}"
        bot.reply_to(message, error_text)

# ==================== FLASK ROUTES ====================

@app.route('/')
def home():
    return "🤖 Ethiopian Digital ID Bot is running on Render!"

@app.route('/health')
def health():
    return {"status": "healthy"}, 200

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    return 'Error', 403

# ==================== MAIN ====================

if __name__ == '__main__':
    if not os.path.exists(TEMPLATE_PATH):
        create_default_template()
    
    if os.environ.get('RENDER'):
        render_url = os.environ.get('RENDER_EXTERNAL_URL')
        if render_url:
            bot.remove_webhook()
            time.sleep(1)
            bot.set_webhook(url=f"{render_url}/webhook")
        
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        bot.remove_webhook()
        bot.polling(none_stop=True)
