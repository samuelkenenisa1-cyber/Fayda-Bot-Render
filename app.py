"""
Fayda Ethiopian Digital ID Card Generator
Render.com compatible - No pdf2image, No poppler needed
"""

import os
import json
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pyzbar.pyzbar import decode
import io
from pypdf import PdfReader  # Changed from PyPDF2
from datetime import datetime
from telebot import TeleBot  # If using pytelegrambotapi
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
DPI = 150  # Lower DPI for memory efficiency
TEMPLATE_PATH = "assets/fayda_template.png"
OUTPUT_DIR = "data/processed"
FONT_PATH = "assets/fonts/arial.ttf"

# Ensure directories exist
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==================== TEMPLATE FUNCTIONS ====================

def create_default_template():
    """Create a default template if none exists"""
    try:
        # Create 1500x1000 template
        template = Image.new('RGB', (1500, 1000), color=(255, 255, 255))
        draw = ImageDraw.Draw(template)
        
        # Header with Ethiopian colors
        draw.rectangle([(0, 0), (1500, 100)], fill=(0, 122, 51))  # Green
        draw.rectangle([(0, 100), (1500, 120)], fill=(241, 196, 15))  # Yellow
        draw.rectangle([(0, 120), (1500, 140)], fill=(203, 45, 62))  # Red
        
        # Title
        draw.text((750, 50), "ETHIOPIAN DIGITAL ID CARD", 
                 font=ImageFont.load_default(), fill='white', anchor="mm")
        
        # Photo area
        draw.rectangle([(80, 180), (380, 480)], 
                      fill=(240, 240, 240), outline='black', width=3)
        draw.text((230, 500), "PHOTO", fill='black', anchor="mm")
        
        # QR code area
        draw.rectangle([(1100, 700), (1400, 1000)], 
                      fill=(240, 240, 240), outline='black', width=3)
        draw.text((1250, 1020), "QR CODE", fill='black', anchor="mm")
        
        # Information labels
        labels = [
            ("FULL NAME:", 400, 200),
            ("DATE OF BIRTH:", 400, 250),
            ("GENDER:", 400, 300),
            ("EXPIRY DATE:", 400, 350),
            ("PHONE NUMBER:", 400, 400),
            ("NATIONALITY:", 400, 450),
            ("ADDRESS:", 400, 500),
            ("ID NUMBER:", 400, 550)
        ]
        
        for label, x, y in labels:
            draw.text((x, y), label, fill='black')
        
        # Footer
        draw.rectangle([(0, 900), (1500, 1000)], fill=(0, 122, 51))
        draw.text((750, 950), "Government of Ethiopia - FAYDA National ID System", 
                 fill='white', anchor="mm")
        
        # Save template
        template.save(TEMPLATE_PATH)
        logger.info(f"✅ Created default template at {TEMPLATE_PATH}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to create template: {e}")
        return False

# ==================== PDF PROCESSING WITHOUT PDF2IMAGE ====================

def extract_image_from_pdf(pdf_bytes):
    """
    Extract image from PDF using pypdf (Python 3.13 compatible)
    """
    try:
        pdf_file = io.BytesIO(pdf_bytes)
        reader = PdfReader(pdf_file)
        
        if len(reader.pages) > 0:
            # Extract text for logging
            text = reader.pages[0].extract_text()
            logger.info(f"📄 PDF text found: {text[:100]}...")
        
        # Create placeholder (same as before)
        placeholder = Image.new('RGB', (1200, 1600), color='white')
        draw = ImageDraw.Draw(placeholder)
        draw.text((100, 100), "PDF Loaded Successfully", fill='black')
        
        return placeholder
        
    except Exception as e:
        logger.warning(f"⚠️ PDF processing failed: {e}")
        return Image.new('RGB', (1200, 1600), color='white')

def find_qr_code_in_image(img):
    """
    Find QR code in an image using multiple methods
    """
    # Convert PIL to OpenCV
    cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    
    # Try multiple detection methods
    methods = [
        # Full image
        (0, 0, img.width, img.height),
        # Bottom right quadrant (most common for QR)
        (img.width//2, img.height//2, img.width, img.height),
        # Top right quadrant
        (img.width//2, 0, img.width, img.height//2),
        # Center area
        (img.width//4, img.height//4, img.width*3//4, img.height*3//4),
    ]
    
    for x1, y1, x2, y2 in methods:
        try:
            # Crop area
            cropped = img.crop((x1, y1, x2, y2))
            cv_crop = cv2.cvtColor(np.array(cropped), cv2.COLOR_RGB2BGR)
            
            # Decode QR
            decoded = decode(cv_crop)
            if decoded:
                qr_data = decoded[0].data.decode("utf-8", errors='ignore')
                qr_image = cropped
                logger.info(f"✅ QR found at ({x1},{y1})-({x2},{y2})")
                return qr_data, qr_image, (x1, y1, x2, y2)
                
        except Exception as e:
            continue
    
    return None, None, None

def generate_fayda_id(pdf_bytes, user_id):
    """Generate ID card from PDF without pdf2image"""
    try:
        # Check/create template
        if not os.path.exists(TEMPLATE_PATH):
            create_default_template()
        
        # Load template
        template = Image.open(TEMPLATE_PATH).convert("RGB")
        draw = ImageDraw.Draw(template)
        
        # ===== EXTRACT IMAGE FROM PDF =====
        pdf_img = extract_image_from_pdf(pdf_bytes)
        logger.info(f"📄 PDF processed: {pdf_img.size}")
        
        # ===== EXTRACT PHOTO =====
        # Try to find photo area (adjust coordinates based on your PDF)
        photo_extracted = False
        try:
            # Common photo positions in ID cards
            photo_areas = [
                (100, 200, 400, 600),   # Top-left area
                (150, 250, 450, 650),   # Slightly adjusted
                (200, 300, 500, 700),   # More adjusted
            ]
            
            for area in photo_areas:
                try:
                    if (area[2] <= pdf_img.width and area[3] <= pdf_img.height):
                        photo_crop = pdf_img.crop(area)
                        # Check if area has content (not just white)
                        np_photo = np.array(photo_crop)
                        if np.mean(np_photo) < 250:  # Not mostly white
                            photo = photo_crop.resize((300, 300))
                            template.paste(photo, (80, 180))
                            photo_extracted = True
                            logger.info(f"✅ Photo extracted from area {area}")
                            break
                except:
                    continue
                    
            if not photo_extracted:
                logger.warning("⚠️ Could not extract photo, using placeholder")
                
        except Exception as e:
            logger.warning(f"⚠️ Photo extraction failed: {e}")
        
        # ===== FIND QR CODE =====
        qr_data, qr_image, qr_position = find_qr_code_in_image(pdf_img)
        
        if not qr_data:
            return None, "QR code not found in PDF"
        
        # ===== PARSE QR DATA =====
        try:
            # Clean the data
            qr_data = qr_data.strip()
            qr_data = qr_data.replace("'", '"').replace("None", "null")
            qr_data = qr_data.replace("True", "true").replace("False", "false")
            
            # Parse JSON
            data = json.loads(qr_data)
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ QR data is not valid JSON: {qr_data[:100]}...")
            return None, f"Invalid QR code data: {str(e)}"
        
        # ===== EXTRACT INFORMATION =====
        info = {
            'name': data.get("fullName") or data.get("full_name") or data.get("name") or "N/A",
            'dob': data.get("dateOfBirth") or data.get("dob") or data.get("birthDate") or "N/A",
            'gender': data.get("sex") or data.get("gender") or data.get("Sex") or "N/A",
            'id_number': data.get("nationalId") or data.get("idNumber") or data.get("FIN") or data.get("id") or "N/A",
            'address': data.get("address") or data.get("residentialAddress") or data.get("Address") or "N/A",
            'phone': data.get("phone") or data.get("phoneNumber") or data.get("mobile") or "N/A",
            'nationality': data.get("nationality") or "Ethiopian",
            'expiry': data.get("expiryDate") or data.get("dateOfExpiry") or data.get("validUntil") or "N/A"
        }
        
        # Clean values
        for key in info:
            if info[key] is None:
                info[key] = "N/A"
            else:
                info[key] = str(info[key]).strip()
        
        logger.info(f"📋 Extracted: {info['name'][:20]}... | ID: {info['id_number']}")
        
        # ===== ADD TEXT TO TEMPLATE =====
        try:
            # Try to load font
            try:
                if os.path.exists(FONT_PATH):
                    font = ImageFont.truetype(FONT_PATH, 24)
                else:
                    font = ImageFont.load_default()
            except:
                font = ImageFont.load_default()
            
            # Text positions (adjust for your template)
            text_start_x = 400
            text_start_y = 200
            line_height = 50
            
            # Draw fields
            fields = [
                info['name'],
                f"DOB: {info['dob']}",
                f"Gender: {info['gender']}",
                f"Expiry: {info['expiry']}",
                f"Phone: {info['phone']}",
                f"Nationality: {info['nationality']}",
                f"Address: {info['address'][:30]}{'...' if len(info['address']) > 30 else ''}",
                f"ID: {info['id_number']}"
            ]
            
            for i, field in enumerate(fields):
                y_pos = text_start_y + (i * line_height)
                draw.text((text_start_x, y_pos), field, font=font, fill='black')
                
        except Exception as e:
            logger.error(f"⚠️ Text rendering error: {e}")
        
        # ===== PASTE QR CODE =====
        if qr_image:
            template.paste(qr_image.resize((300, 300)), (1100, 700))
            logger.info("✅ QR code pasted")
        
        # ===== SAVE OUTPUT =====
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"fayda_id_{user_id}_{timestamp}.png"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        
        template.save(output_path, "PNG", optimize=True)
        logger.info(f"💾 Saved ID card: {output_path}")
        
        return output_path, info
        
    except Exception as e:
        logger.error(f"❌ Error in generate_fayda_id: {str(e)}")
        logger.error(traceback.format_exc())
        return None, f"Processing error: {str(e)}"

# ==================== TELEGRAM BOT HANDLERS ====================

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """Welcome message"""
    welcome_text = """
    🪪 *Ethiopian Digital ID Card Generator*
    
    *Official FAYDA National ID System*
    
    📋 *How to use:*
    1️⃣ Send me your FAYDA PDF document
    2️⃣ Wait 10-15 seconds for processing
    3️⃣ Receive your formatted ID card
    
    ⚠️ *Requirements:*
    • PDF must contain a QR code with data
    • File size under 20MB
    
    Made with ❤️ for Ethiopia
    """
    bot.send_message(message.chat.id, welcome_text, parse_mode='Markdown')

@bot.message_handler(commands=['ping'])
def send_status(message):
    """Check bot status"""
    bot.reply_to(message, "✅ Bot is running on Render.com!")

@bot.message_handler(content_types=['document'])
def handle_document(message):
    """Handle PDF uploads"""
    try:
        chat_id = message.chat.id
        user_name = message.from_user.first_name or "User"
        
        # Check if PDF
        if not message.document.file_name.lower().endswith('.pdf'):
            bot.reply_to(message, "❌ Please send a PDF file (.pdf)")
            return
        
        # File size check
        if message.document.file_size > 20 * 1024 * 1024:
            bot.reply_to(message, "❌ File too large! Please send PDF under 20MB")
            return
        
        # Send initial response
        status_msg = bot.reply_to(message, f"👋 Hello {user_name}!\n📥 Downloading your PDF...")
        
        # Download PDF
        file_info = bot.get_file(message.document.file_id)
        file_bytes = bot.download_file(file_info.file_path)
        
        bot.edit_message_text("🔄 Processing PDF...\n⏳ This may take 10-15 seconds", 
                             chat_id, status_msg.message_id)
        
        # Generate ID card
        output_path, info = generate_fayda_id(file_bytes, chat_id)
        
        if output_path and os.path.exists(output_path):
            # Send success with ID card
            with open(output_path, 'rb') as photo:
                caption = f"""
✅ *ID Card Generated Successfully!*

*Extracted Information:*
👤 *Name:* {info['name']}
🆔 *ID Number:* {info['id_number']}
📅 *Date of Birth:* {info['dob']}
⚧️ *Gender:* {info['gender']}
📱 *Phone:* {info['phone']}
📍 *Address:* {info['address'][:30]}...

*Note:* Ethiopian Digital ID Card
                """
                bot.send_photo(chat_id, photo, caption=caption, parse_mode='Markdown')
            
            # Clean up
            try:
                os.remove(output_path)
            except:
                pass
            
            # Update status
            bot.delete_message(chat_id, status_msg.message_id)
            
        else:
            # Error occurred
            error_msg = f"""
❌ *Processing Failed*

*Reason:* {info}

*Please ensure:*
• PDF has a clear QR code
• QR code contains valid JSON data
• PDF is not corrupted
            """
            bot.edit_message_text(error_msg, chat_id, status_msg.message_id, parse_mode='Markdown')
            
    except Exception as e:
        error_text = f"❌ Unexpected error: {str(e)}"
        bot.reply_to(message, error_text)
        logger.error(f"Telegram bot error: {traceback.format_exc()}")

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    """Handle other messages"""
    text = message.text.lower()
    
    if text in ['hi', 'hello', 'hey']:
        bot.reply_to(message, "👋 Hello! Send me a FAYDA PDF to generate an ID card.")
    elif 'thank' in text:
        bot.reply_to(message, "You're welcome! 🇪🇹")
    else:
        bot.reply_to(message, "I can generate Ethiopian Digital ID cards. Send me a FAYDA PDF to get started!")

# ==================== FLASK ROUTES ====================

@app.route('/')
def home():
    """Homepage"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Ethiopian Digital ID Bot</title>
        <style>
            body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
            .container { max-width: 800px; margin: 0 auto; }
            h1 { color: #0e7a3d; }
            .status { color: green; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 Ethiopian Digital ID Bot</h1>
            <p class="status">✅ Bot is running on Render.com</p>
            <p>FAYDA National ID Card Generator</p>
            <p>Send a PDF to the bot on Telegram to get started.</p>
            <p>Made with ❤️ for Ethiopia</p>
        </div>
    </body>
    </html>
    """

@app.route('/health')
def health_check():
    """Health endpoint"""
    return {
        "status": "healthy",
        "service": "ethiopian-id-bot",
        "timestamp": datetime.now().isoformat()
    }, 200

@app.route('/webhook', methods=['POST'])
def webhook():
    """Telegram webhook"""
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    return 'Invalid content type', 403

# ==================== MAIN EXECUTION ====================

if __name__ == '__main__':
    # Create default template if needed
    if not os.path.exists(TEMPLATE_PATH):
        logger.info("Creating default template...")
        create_default_template()
    
    # Check if running on Render
    if os.environ.get('RENDER'):
        logger.info("🚀 Running on Render.com")
        
        try:
            # Get Render URL and set webhook
            render_url = os.environ.get('RENDER_EXTERNAL_URL')
            if render_url:
                bot.remove_webhook()
                time.sleep(1)
                webhook_url = f"{render_url}/webhook"
                bot.set_webhook(url=webhook_url)
                logger.info(f"✅ Webhook set to: {webhook_url}")
            
            # Start Flask
            port = int(os.environ.get('PORT', 5000))
            app.run(host='0.0.0.0', port=port, debug=False)
            
        except Exception as e:
            logger.error(f"❌ Render startup failed: {e}")
    
    else:
        # Local development
        logger.info("💻 Running locally in polling mode")
        bot.remove_webhook()
        bot.polling(none_stop=True)

