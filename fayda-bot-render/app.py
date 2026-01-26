import os
import json
import tempfile
import fitz
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pyzbar.pyzbar import decode
from datetime import datetime
import telebot
from flask import Flask, request
import io
import logging
import traceback
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Get bot token from environment
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN not found!")
    BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Replace for local testing

bot = telebot.TeleBot(BOT_TOKEN)

# Configuration
DPI = 200  # Lower DPI for faster processing on free tier
TEMPLATE_PATH = "assets/fayda_template.png"
OUTPUT_DIR = "data/processed"
FONT_PATH = "assets/fonts/arial.ttf"

# Ensure directories exist
os.makedirs(OUTPUT_DIR, exist_ok=True)

def create_default_template():
    """Create a simple template if none exists"""
    try:
        # Simple template with labels
        template = Image.new('RGB', (1500, 1000), color='white')
        draw = ImageDraw.Draw(template)
        
        # Add borders and labels
        draw.rectangle([(80, 180), (380, 480)], outline='black', width=2)
        draw.text((230, 500), "PHOTO", fill='black')
        
        draw.rectangle([(1000, 650), (1240, 890)], outline='black', width=2)
        draw.text((1120, 910), "QR CODE", fill='black')
        
        # Labels
        labels = ["Full Name:", "DOB:", "Gender:", "ID Number:", "Address:"]
        y_start = 200
        for i, label in enumerate(labels):
            draw.text((400, y_start + i*70), label, fill='black')
        
        template.save(TEMPLATE_PATH)
        logger.info(f"✅ Created default template")
        
    except Exception as e:
        logger.error(f"❌ Failed to create template: {e}")

def generate_fayda_id(pdf_bytes, user_id):
    """Generate ID card from PDF - SIMPLIFIED for free tier"""
    try:
        # Create template if doesn't exist
        if not os.path.exists(TEMPLATE_PATH):
            create_default_template()
        
        # Load template
        template = Image.open(TEMPLATE_PATH).convert("RGB")
        draw = ImageDraw.Draw(template)
        
        # Load PDF (memory efficient)
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc.load_page(0)
        
        # Lower DPI for free tier memory limits
        pix = page.get_pixmap(dpi=DPI)
        pdf_img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        
        # ----- EXTRACT PHOTO (adjust these numbers for your PDF) -----
        # Try default coordinates
        try:
            photo_crop = pdf_img.crop((100, 250, 550, 850))  # Left, Top, Right, Bottom
            photo = photo_crop.resize((300, 380))
            template.paste(photo, (80, 180))
        except:
            logger.warning("⚠️ Could not extract photo")
        
        # ----- FIND QR CODE -----
        qr_found = False
        qr_data = None
        
        # Try multiple areas for QR code
        search_areas = [
            (1100, 600, 1550, 1050),  # Area 1
            (1000, 550, 1450, 1000),  # Area 2
            (1200, 650, 1650, 1100),  # Area 3
        ]
        
        for area in search_areas:
            try:
                qr_crop = pdf_img.crop(area)
                qr_cv = cv2.cvtColor(np.array(qr_crop), cv2.COLOR_RGB2BGR)
                decoded = decode(qr_cv)
                
                if decoded:
                    qr_data = decoded[0].data.decode("utf-8")
                    # Paste QR to template
                    template.paste(qr_crop.resize((240, 240)), (1000, 650))
                    qr_found = True
                    logger.info(f"✅ QR found in area {area}")
                    break
            except:
                continue
        
        if not qr_found:
            return None, "QR code not found in PDF"
        
        # ----- PARSE QR DATA -----
        try:
            # Clean data
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
            'address': data.get("address", "N/A")
        }
        
        # ----- ADD TEXT TO TEMPLATE -----
        try:
            # Try to load font, use default if fails
            try:
                font = ImageFont.truetype(FONT_PATH, 28) if os.path.exists(FONT_PATH) else ImageFont.load_default()
            except:
                font = ImageFont.load_default()
            
            # Position text
            y_pos = 200
            line_height = 70
            
            draw.text((500, y_pos), str(info['name']), font=font, fill='black')
            draw.text((500, y_pos + line_height), str(info['dob']), font=font, fill='black')
            draw.text((500, y_pos + line_height*2), str(info['gender']), font=font, fill='black')
            draw.text((500, y_pos + line_height*3), str(info['id']), font=font, fill='black')
            
            # Address might be long - truncate
            address = str(info['address'])
            if len(address) > 40:
                address = address[:40] + "..."
            draw.text((500, y_pos + line_height*4), address, font=font, fill='black')
            
        except Exception as e:
            logger.error(f"⚠️ Text rendering error: {e}")
        
        # ----- SAVE OUTPUT -----
        output_path = os.path.join(OUTPUT_DIR, f"{user_id}_{int(time.time())}.png")
        template.save(output_path)
        
        doc.close()
        
        return output_path, info
        
    except Exception as e:
        logger.error(f"❌ Processing error: {str(e)}")
        return None, f"Error: {str(e)}"

# ============= TELEGRAM BOT HANDLERS =============

@bot.message_handler(commands=['start'])
def start_handler(message):
    """Handle /start command"""
    welcome = """
    🪪 *Fayda ID Card Generator*
    
    Send me a Fayda PDF and I'll create an ID card for you!
    
    *How to use:*
    1. Upload your Fayda PDF
    2. Wait 10-20 seconds
    3. Receive your ID card
    
    *Note:* PDF must contain a QR code with data.
    
    Made with ❤️ on Render.com
    """
    bot.send_message(message.chat.id, welcome, parse_mode='Markdown')

@bot.message_handler(commands=['ping'])
def ping_handler(message):
    """Check if bot is alive"""
    bot.reply_to(message, "✅ Bot is running on Render!")

@bot.message_handler(content_types=['document'])
def handle_pdf(message):
    """Handle PDF uploads"""
    try:
        chat_id = message.chat.id
        
        # Check if PDF
        if not message.document.file_name.lower().endswith('.pdf'):
            bot.reply_to(message, "❌ Please send a PDF file!")
            return
        
        # Inform user
        processing_msg = bot.reply_to(message, "📥 Downloading PDF...")
        
        # Download file
        file_info = bot.get_file(message.document.file_id)
        file_bytes = bot.download_file(file_info.file_path)
        
        bot.edit_message_text("🔄 Processing PDF...", chat_id, processing_msg.message_id)
        
        # Generate ID card
        output_path, info = generate_fayda_id(file_bytes, chat_id)
        
        if output_path and os.path.exists(output_path):
            # Send the result
            with open(output_path, 'rb') as photo:
                caption = f"""
✅ *ID Card Generated*
                
👤 *Name:* {info['name']}
🆔 *ID:* {info['id']}
📅 *DOB:* {info['dob']}
⚧️ *Gender:* {info['gender']}
📍 *Address:* {info['address'][:30]}...
                """
                bot.send_photo(chat_id, photo, caption=caption, parse_mode='Markdown')
            
            # Clean up
            os.remove(output_path)
            bot.delete_message(chat_id, processing_msg.message_id)
        else:
            error_msg = f"❌ Failed: {info}"
            bot.edit_message_text(error_msg, chat_id, processing_msg.message_id)
            
    except Exception as e:
        error_text = f"❌ Error: {str(e)}"
        bot.reply_to(message, error_text)
        logger.error(f"Bot error: {traceback.format_exc()}")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    """Handle all other messages"""
    if message.text.lower() in ['hi', 'hello', 'hey']:
        bot.reply_to(message, "👋 Hello! Send me a Fayda PDF.")
    else:
        bot.reply_to(message, "Send me a Fayda PDF file to get started! Use /start for help.")

# ============= FLASK ROUTES =============

@app.route('/')
def home():
    """Render homepage"""
    return """
    <html>
    <head>
        <title>Fayda ID Bot</title>
        <style>
            body { font-family: Arial; max-width: 600px; margin: 50px auto; padding: 20px; }
            .container { background: #f0f8ff; padding: 30px; border-radius: 15px; text-align: center; }
            h1 { color: #2c3e50; }
            .status { color: green; font-weight: bold; font-size: 18px; }
            .info { background: white; padding: 15px; border-radius: 10px; margin: 20px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 Fayda ID Card Generator</h1>
            <p class="status">✅ Bot is running on Render.com</p>
            <div class="info">
                <p><strong>Free Tier Status:</strong> Active</p>
                <p><strong>Service:</strong> May sleep after 15min inactivity</p>
                <p><strong>Usage:</strong> Send PDF to bot on Telegram</p>
            </div>
            <p>Made with ❤️ for Ethiopia</p>
        </div>
    </body>
    </html>
    """

@app.route('/health')
def health():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}, 200

@app.route('/webhook', methods=['POST'])
def webhook():
    """Telegram webhook endpoint"""
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    return 'Error', 403

# ============= MAIN =============

if __name__ == '__main__':
    # Create default template
    if not os.path.exists(TEMPLATE_PATH):
        create_default_template()
    
    # On Render, use webhook
    if os.environ.get('RENDER'):
        # Get Render URL
        render_url = os.environ.get('RENDER_EXTERNAL_URL')
        if render_url:
            bot.remove_webhook()
            time.sleep(1)
            bot.set_webhook(url=f"{render_url}/webhook")
            logger.info(f"✅ Webhook set to: {render_url}/webhook")
        
        # Start Flask
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        # Local development - use polling
        logger.info("💻 Running locally in polling mode")
        bot.remove_webhook()
        bot.polling(none_stop=True)