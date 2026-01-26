"""
Fayda Ethiopian Digital ID Card Generator
Deploy on Render.com - Free Tier
"""

import os
import json
import fitz  # PyMuPDF
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pyzbar.pyzbar import decode
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

# Get bot token from environment (set in Render Dashboard)
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN not found in environment variables!")
    logger.info("💡 Please set BOT_TOKEN in Render Dashboard → Environment Variables")
    BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # For local testing only

# Initialize Telegram bot
bot = telebot.TeleBot(BOT_TOKEN)

# Configuration
DPI = 200  # Lower for Render free tier memory limits
TEMPLATE_PATH = "assets/fayda_template.png"
OUTPUT_DIR = "data/processed"
FONT_PATH = "assets/fonts/arial.ttf"

# Ensure directories exist
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.dirname(TEMPLATE_PATH), exist_ok=True)

# ==================== TEMPLATE FUNCTIONS ====================

def create_default_template():
    """
    Create a default template if none exists.
    YOU SHOULD REPLACE THIS WITH YOUR REAL TEMPLATE!
    """
    try:
        # Create a simple Ethiopian ID template (1500x1000 pixels)
        template = Image.new('RGB', (1500, 1000), color=(255, 255, 255))
        draw = ImageDraw.Draw(template)
        
        # Try to load font
        try:
            font = ImageFont.truetype("arial.ttf", 24) if os.path.exists(FONT_PATH) else ImageFont.load_default()
        except:
            font = ImageFont.load_default()
        
        # Header - Ethiopian colors
        draw.rectangle([(0, 0), (1500, 100)], fill=(0, 122, 51), outline=None)  # Green
        draw.rectangle([(0, 100), (1500, 120)], fill=(241, 196, 15), outline=None)  # Yellow
        draw.rectangle([(0, 120), (1500, 140)], fill=(203, 45, 62), outline=None)  # Red
        
        # Title
        draw.text((750, 50), "ETHIOPIAN DIGITAL ID CARD", 
                 font=font, fill='white', anchor="mm")
        
        # Photo area placeholder
        draw.rectangle([(80, 180), (380, 480)], 
                      fill=(240, 240, 240), outline='black', width=3)
        draw.text((230, 500), "PHOTO", fill='black', font=font, anchor="mm")
        
        # QR code area placeholder
        draw.rectangle([(1100, 700), (1400, 1000)], 
                      fill=(240, 240, 240), outline='black', width=3)
        draw.text((1250, 1020), "QR CODE", fill='black', font=font, anchor="mm")
        
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
            draw.text((x, y), label, fill='black', font=font)
        
        # Footer
        draw.rectangle([(0, 900), (1500, 1000)], fill=(0, 122, 51), outline=None)
        draw.text((750, 950), "Government of Ethiopia - FAYDA National ID System", 
                 font=font, fill='white', anchor="mm")
        
        # Save template
        template.save(TEMPLATE_PATH)
        logger.info(f"✅ Created default template at {TEMPLATE_PATH}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to create template: {e}")
        return False

# ==================== PDF PROCESSING FUNCTIONS ====================

def generate_fayda_id(pdf_bytes, user_id):
    """
    Generate Ethiopian Digital ID card from PDF
    Returns: (output_path, info_dict) or (None, error_message)
    """
    try:
        # Check if template exists, create default if not
        if not os.path.exists(TEMPLATE_PATH):
            logger.warning("⚠️ Template not found, creating default...")
            if not create_default_template():
                return None, "Failed to create template"
        
        # Load your Ethiopian ID template
        template = Image.open(TEMPLATE_PATH).convert("RGB")
        draw = ImageDraw.Draw(template)
        
        # Load PDF document
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc.load_page(0)  # First page
        
        # Render PDF page to image (lower DPI for memory efficiency)
        pix = page.get_pixmap(dpi=DPI)
        pdf_img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        
        logger.info(f"📄 PDF rendered: {pix.width}x{pix.height} pixels")
        
        # ===== EXTRACT PHOTO FROM PDF =====
        # ADJUST THESE COORDINATES based on your PDF layout!
        photo_success = False
        try:
            # Coordinates to crop photo from PDF: (left, top, right, bottom)
            photo_crop_coords = (100, 250, 550, 850)
            photo_crop = pdf_img.crop(photo_crop_coords)
            
            # Resize to fit template (300x300 pixels)
            photo = photo_crop.resize((300, 300))
            
            # Position on template: (x, y) coordinates
            photo_position = (80, 180)
            template.paste(photo, photo_position)
            photo_success = True
            
            logger.info(f"✅ Photo extracted: {photo_crop_coords} → {photo_position}")
            
        except Exception as e:
            logger.warning(f"⚠️ Could not extract photo: {e}")
        
        # ===== FIND AND EXTRACT QR CODE =====
        qr_found = False
        qr_data = None
        qr_image = None
        
        # Try multiple areas for QR code (adjust these based on your PDF)
        search_areas = [
            (1200, 700, 1650, 1150),  # Bottom right (most common)
            (1100, 650, 1550, 1100),  # Slightly left/up
            (1000, 600, 1450, 1050),  # More left/up
            (800, 500, 1250, 950),    # Left side
        ]
        
        for area_idx, area in enumerate(search_areas, 1):
            try:
                qr_crop = pdf_img.crop(area)
                qr_cv = cv2.cvtColor(np.array(qr_crop), cv2.COLOR_RGB2BGR)
                decoded = decode(qr_cv)
                
                if decoded:
                    qr_data = decoded[0].data.decode("utf-8", errors='ignore')
                    qr_image = qr_crop
                    qr_found = True
                    logger.info(f"✅ QR found in area {area_idx}: {area}")
                    break
                    
            except Exception as e:
                logger.debug(f"Area {area_idx} failed: {e}")
                continue
        
        if not qr_found:
            return None, "QR code not found in PDF. Please ensure PDF contains a QR code."
        
        # ===== PARSE QR CODE DATA =====
        try:
            # Clean the data (sometimes has single quotes or formatting issues)
            qr_data = qr_data.strip()
            qr_data = qr_data.replace("'", '"').replace("None", "null").replace("True", "true").replace("False", "false")
            
            # Parse JSON data
            data = json.loads(qr_data)
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ QR data is not valid JSON: {qr_data[:100]}...")
            return None, f"Invalid QR code data format: {str(e)}"
        
        # ===== EXTRACT INFORMATION FOR ETHIOPIAN ID =====
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
        
        # Clean up values
        for key in info:
            if info[key] is None:
                info[key] = "N/A"
            else:
                info[key] = str(info[key]).strip()
        
        logger.info(f"📋 Extracted data: {info['name'][:20]}... | ID: {info['id_number']}")
        
        # ===== ADD TEXT TO TEMPLATE =====
        try:
            # Load font (arial.ttf or default)
            try:
                if os.path.exists(FONT_PATH):
                    font = ImageFont.truetype(FONT_PATH, 24)
                else:
                    font = ImageFont.truetype("arial.ttf", 24) if os.path.exists("arial.ttf") else ImageFont.load_default()
            except:
                font = ImageFont.load_default()
            
            # ===== ADJUST THESE COORDINATES FOR YOUR TEMPLATE! =====
            # Current coordinates for default template
            text_start_x = 400      # X position for all text
            text_start_y = 200      # Starting Y position
            line_height = 50        # Space between lines
            
            # Draw each field on the template
            draw.text((text_start_x, text_start_y), 
                     f"{info['name']}", font=font, fill='black')
            
            draw.text((text_start_x, text_start_y + line_height), 
                     f"DOB: {info['dob']}", font=font, fill='black')
            
            draw.text((text_start_x, text_start_y + line_height * 2), 
                     f"Gender: {info['gender']}", font=font, fill='black')
            
            draw.text((text_start_x, text_start_y + line_height * 3), 
                     f"Expiry: {info['expiry']}", font=font, fill='black')
            
            draw.text((text_start_x, text_start_y + line_height * 4), 
                     f"Phone: {info['phone']}", font=font, fill='black')
            
            draw.text((text_start_x, text_start_y + line_height * 5), 
                     f"Nationality: {info['nationality']}", font=font, fill='black')
            
            # Address might be long - truncate if necessary
            address = info['address']
            if len(address) > 40:
                address = address[:40] + "..."
            draw.text((text_start_x, text_start_y + line_height * 6), 
                     f"Address: {address}", font=font, fill='black')
            
            draw.text((text_start_x, text_start_y + line_height * 7), 
                     f"ID: {info['id_number']}", font=font, fill='black')
            
        except Exception as e:
            logger.error(f"⚠️ Text rendering error: {e}")
        
        # ===== PASTE QR CODE ON TEMPLATE =====
        if qr_image:
            qr_position = (1100, 700)  # ADJUST THIS FOR YOUR TEMPLATE!
            template.paste(qr_image.resize((300, 300)), qr_position)
            logger.info(f"✅ QR code pasted at position {qr_position}")
        
        # ===== SAVE THE GENERATED ID CARD =====
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"fayda_id_{user_id}_{timestamp}.png"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        
        # Save with good quality
        template.save(output_path, "PNG", optimize=True)
        logger.info(f"💾 Saved ID card: {output_path}")
        
        # Clean up
        doc.close()
        
        return output_path, info
        
    except Exception as e:
        logger.error(f"❌ Error in generate_fayda_id: {str(e)}")
        logger.error(traceback.format_exc())
        return None, f"Processing error: {str(e)}"

# ==================== TELEGRAM BOT HANDLERS ====================

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """Welcome message with instructions"""
    welcome_text = """
    🪪 *Ethiopian Digital ID Card Generator*
    
    *Official FAYDA National ID System*
    
    📋 *How to use:*
    1️⃣ Send me your FAYDA PDF document
    2️⃣ Wait 10-20 seconds for processing
    3️⃣ Receive your formatted ID card
    
    ⚠️ *Requirements:*
    • PDF must contain a QR code with data
    • PDF should be clear and readable
    • File size under 20MB
    
    🔧 *Commands:*
    /start - Show this message
    /ping - Check if bot is alive
    /help - Get help
    
    📞 *Support:* Contact if you have issues
    
    Made with ❤️ for Ethiopia
    """
    bot.send_message(message.chat.id, welcome_text, parse_mode='Markdown')

@bot.message_handler(commands=['ping'])
def send_status(message):
    """Check bot status"""
    bot.reply_to(message, "✅ Bot is running on Render.com!")

@bot.message_handler(commands=['template'])
def send_template_info(message):
    """Information about template"""
    template_info = """
    🖼️ *Template Information:*
    
    Your ID card will be formatted using the Ethiopian Digital ID template.
    
    *Current coordinates:*
    • Photo position: (80, 180)
    • QR position: (1100, 700)
    • Text start: (400, 200)
    
    *Need to adjust?* Contact support with your template image.
    """
    bot.send_message(message.chat.id, template_info, parse_mode='Markdown')

@bot.message_handler(content_types=['document'])
def handle_document(message):
    """Handle PDF document uploads"""
    try:
        chat_id = message.chat.id
        user_name = message.from_user.first_name or "User"
        
        # Check if it's a PDF
        if not message.document.file_name.lower().endswith('.pdf'):
            bot.reply_to(message, "❌ Please send a PDF file (.pdf extension)")
            return
        
        # File size check (Render free tier limit)
        if message.document.file_size > 20 * 1024 * 1024:  # 20MB
            bot.reply_to(message, "❌ File too large! Please send PDF under 20MB")
            return
        
        # Send initial response
        status_msg = bot.reply_to(message, f"👋 Hello {user_name}!\n📥 Downloading your PDF...")
        
        # Download the PDF file
        file_info = bot.get_file(message.document.file_id)
        file_bytes = bot.download_file(file_info.file_path)
        
        bot.edit_message_text("🔄 Processing PDF...\n⏳ This may take 15-20 seconds", 
                             chat_id, status_msg.message_id)
        
        # Generate the ID card
        output_path, info = generate_fayda_id(file_bytes, chat_id)
        
        if output_path and os.path.exists(output_path):
            # Send success message with ID card
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

*Note:* This is an official Ethiopian Digital ID card
                """
                bot.send_photo(chat_id, photo, caption=caption, parse_mode='Markdown')
            
            # Clean up temporary file
            try:
                os.remove(output_path)
            except:
                pass
            
            # Update status message
            bot.delete_message(chat_id, status_msg.message_id)
            bot.send_message(chat_id, "🎉 Done! Your ID card has been generated.")
            
        else:
            # Error occurred
            error_msg = f"""
❌ *Processing Failed*

*Reason:* {info}

*Possible issues:*
• QR code not detected
• PDF format not supported
• Template alignment issue

*Please try:*
1. Ensure PDF has clear QR code
2. Try a different PDF
3. Contact support if issue persists
            """
            bot.edit_message_text(error_msg, chat_id, status_msg.message_id, parse_mode='Markdown')
            
    except Exception as e:
        error_text = f"❌ Unexpected error: {str(e)}"
        bot.reply_to(message, error_text)
        logger.error(f"Telegram bot error: {traceback.format_exc()}")

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    """Handle all other text messages"""
    text = message.text.lower()
    
    if text in ['hi', 'hello', 'hey', 'hola']:
        bot.reply_to(message, "👋 Hello! Send me a FAYDA PDF to generate an ID card.")
    elif 'id' in text or 'fayda' in text:
        bot.reply_to(message, "Send me your FAYDA PDF file to get started!")
    elif 'thank' in text or 'thanks' in text:
        bot.reply_to(message, "You're welcome! 🇪🇹")
    else:
        bot.reply_to(message, "I can generate Ethiopian Digital ID cards from FAYDA PDFs. Send me a PDF to get started!")

# ==================== FLASK ROUTES FOR RENDER ====================

@app.route('/')
def home():
    """Render homepage"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Ethiopian Digital ID Bot</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }
            
            body {
                background: linear-gradient(135deg, #0e7a3d 0%, #0c6935 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 20px;
            }
            
            .container {
                background: white;
                border-radius: 20px;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
                max-width: 800px;
                width: 100%;
                overflow: hidden;
            }
            
            .header {
                background: linear-gradient(135deg, #0e7a3d 0%, #0c6935 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }
            
            .header h1 {
                font-size: 2.5rem;
                margin-bottom: 10px;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 15px;
            }
            
            .header p {
                font-size: 1.1rem;
                opacity: 0.9;
            }
            
            .content {
                padding: 40px;
            }
            
            .status-card {
                background: #f0f9f4;
                border-left: 5px solid #0e7a3d;
                padding: 20px;
                margin-bottom: 30px;
                border-radius: 10px;
            }
            
            .status-card h3 {
                color: #0e7a3d;
                margin-bottom: 10px;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            
            .status-card p {
                color: #333;
                line-height: 1.6;
            }
            
            .features {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin: 30px 0;
            }
            
            .feature {
                background: #f8f9fa;
                padding: 20px;
                border-radius: 10px;
                text-align: center;
                transition: transform 0.3s;
            }
            
            .feature:hover {
                transform: translateY(-5px);
            }
            
            .feature-icon {
                font-size: 2.5rem;
                margin-bottom: 15px;
            }
            
            .feature h4 {
                color: #0e7a3d;
                margin-bottom: 10px;
            }
            
            .instructions {
                background: #fff9e6;
                border: 2px dashed #f1c40f;
                padding: 25px;
                border-radius: 10px;
                margin-top: 30px;
            }
            
            .instructions h3 {
                color: #d35400;
                margin-bottom: 15px;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            
            ol {
                padding-left: 20px;
            }
            
            li {
                margin-bottom: 10px;
                line-height: 1.6;
            }
            
            .telegram-btn {
                display: inline-block;
                background: #0088cc;
                color: white;
                text-decoration: none;
                padding: 15px 30px;
                border-radius: 50px;
                font-weight: bold;
                margin-top: 20px;
                transition: background 0.3s;
            }
            
            .telegram-btn:hover {
                background: #006699;
            }
            
            .footer {
                text-align: center;
                padding: 20px;
                background: #f8f9fa;
                color: #666;
                border-top: 1px solid #eee;
            }
            
            @media (max-width: 600px) {
                .header h1 {
                    font-size: 2rem;
                    flex-direction: column;
                }
                
                .content {
                    padding: 20px;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>
                    <span>🤖</span>
                    Ethiopian Digital ID Bot
                </h1>
                <p>FAYDA National ID Card Generator</p>
            </div>
            
            <div class="content">
                <div class="status-card">
                    <h3>✅ <span>Status: Running</span></h3>
                    <p>Bot is successfully deployed on Render.com and ready to process your FAYDA PDF documents.</p>
                </div>
                
                <div class="features">
                    <div class="feature">
                        <div class="feature-icon">🪪</div>
                        <h4>ID Generation</h4>
                        <p>Convert FAYDA PDFs to formatted ID cards with photo and QR code</p>
                    </div>
                    
                    <div class="feature">
                        <div class="feature-icon">🔒</div>
                        <h4>Secure Processing</h4>
                        <p>Your documents are processed securely and not stored permanently</p>
                    </div>
                    
                    <div class="feature">
                        <div class="feature-icon">⚡</div>
                        <h4>Fast Processing</h4>
                        <p>Generate ID cards in under 20 seconds</p>
                    </div>
                </div>
                
                <div class="instructions">
                    <h3>📋 How to Use</h3>
                    <ol>
                        <li>Open Telegram and find @YourBotName</li>
                        <li>Send the command <code>/start</code> to begin</li>
                        <li>Upload your FAYDA PDF document</li>
                        <li>Wait 15-20 seconds for processing</li>
                        <li>Receive your formatted Ethiopian Digital ID card</li>
                    </ol>
                    
                    <a href="https://t.me/YourBotName" class="telegram-btn" target="_blank">
                        Open in Telegram →
                    </a>
                </div>
            </div>
            
            <div class="footer">
                <p>Made with ❤️ for Ethiopia | Powered by Render.com</p>
                <p>© 2024 Ethiopian Digital ID System</p>
            </div>
        </div>
        
        <script>
            // Auto-update status
            setInterval(() => {
                fetch('/health')
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'healthy') {
                            document.querySelector('.status-card h3 span').innerHTML = '✅ Status: Running';
                        }
                    })
                    .catch(() => {
                        document.querySelector('.status-card h3 span').innerHTML = '⚠️ Status: Checking...';
                    });
            }, 30000);
        </script>
    </body>
    </html>
    """

@app.route('/health')
def health_check():
    """Health check endpoint for Render"""
    return {
        "status": "healthy",
        "service": "ethiopian-id-bot",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }, 200

@app.route('/webhook', methods=['POST'])
def webhook():
    """Telegram webhook endpoint"""
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    return 'Invalid content type', 403

# ==================== MAIN EXECUTION ====================

if __name__ == '__main__':
    # Create default template if doesn't exist
    if not os.path.exists(TEMPLATE_PATH):
        logger.info("Creating default template...")
        create_default_template()
    
    # Check if running on Render
    if os.environ.get('RENDER'):
        logger.info("🚀 Running on Render.com")
        
        try:
            # Get Render URL
            render_url = os.environ.get('RENDER_EXTERNAL_URL')
            if render_url:
                # Remove any existing webhook
                bot.remove_webhook()
                time.sleep(1)
                
                # Set new webhook
                webhook_url = f"{render_url}/webhook"
                success = bot.set_webhook(url=webhook_url)
                
                if success:
                    logger.info(f"✅ Webhook set to: {webhook_url}")
                else:
                    logger.error("❌ Failed to set webhook")
            
            # Start Flask app
            port = int(os.environ.get('PORT', 5000))
            logger.info(f"Starting Flask on port {port}")
            app.run(host='0.0.0.0', port=port, debug=False)
            
        except Exception as e:
            logger.error(f"❌ Render startup failed: {e}")
            logger.error(traceback.format_exc())
    
    else:
        # Local development - use polling
        logger.info("💻 Running locally in polling mode")
        bot.remove_webhook()
        bot.polling(none_stop=True, interval=1, timeout=30)