"""
Test Script to Visualize Template Coordinates
Run this to see where elements will be placed on your template
"""

from PIL import Image, ImageDraw, ImageFont
import os

# Configuration
TEMPLATE_PATH = "assets/fayda_template.png"
OUTPUT_GUIDE_PATH = "template_with_guides.png"

def create_coordinate_guide():
    """Create a visual guide showing where elements will be placed"""
    
    # Check if template exists
    if not os.path.exists(TEMPLATE_PATH):
        print(f"❌ Template not found: {TEMPLATE_PATH}")
        print("💡 Please add your template image to the assets folder")
        return False
    
    try:
        # Load your template
        template = Image.open(TEMPLATE_PATH).convert("RGB")
        draw = ImageDraw.Draw(template)
        
        print(f"📐 Template size: {template.size} (width x height)")
        
        # Try to load a font
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except:
            font = ImageFont.load_default()
        
        # ===== DRAW PHOTO AREA =====
        photo_x, photo_y = 50, 150
        photo_width, photo_height = 300, 300
        draw.rectangle([
            (photo_x, photo_y), 
            (photo_x + photo_width, photo_y + photo_height)
        ], outline='red', width=3)
        draw.text((photo_x + 10, photo_y + photo_height + 10), 
                 f"PHOTO: ({photo_x}, {photo_y})", fill='red', font=font)
        
        # ===== DRAW QR CODE AREA =====
        qr_x, qr_y = 1100, 700
        qr_size = 300
        draw.rectangle([
            (qr_x, qr_y), 
            (qr_x + qr_size, qr_y + qr_size)
        ], outline='blue', width=3)
        draw.text((qr_x + 10, qr_y + qr_size + 10), 
                 f"QR CODE: ({qr_x}, {qr_y})", fill='blue', font=font)
        
        # ===== DRAW TEXT POSITIONS =====
        text_x = 400
        text_y_start = 200
        line_height = 50
        
        text_fields = [
            "1. Full Name",
            "2. Date of Birth",
            "3. Gender",
            "4. Expiry Date",
            "5. Phone Number",
            "6. Nationality",
            "7. Address",
            "8. FIN/ID Number"
        ]
        
        for i, field in enumerate(text_fields):
            y_pos = text_y_start + (i * line_height)
            
            # Draw green dot at text start
            draw.ellipse([
                (text_x - 5, y_pos - 5),
                (text_x + 5, y_pos + 5)
            ], fill='green')
            
            # Draw text label
            draw.text((text_x + 15, y_pos - 10), 
                     f"{field}: ({text_x}, {y_pos})", 
                     fill='green', font=font)
        
        # ===== ADD GRID LINES FOR REFERENCE =====
        # Horizontal lines every 50 pixels
        for y in range(0, template.height, 50):
            if y % 100 == 0:
                color = (200, 200, 200)  # Darker for 100px intervals
                draw.line([(0, y), (50, y)], fill=color, width=1)
                draw.text((5, y + 5), str(y), fill='gray', font=font)
            else:
                color = (230, 230, 230)  # Lighter for 50px intervals
            draw.line([(0, y), (template.width, y)], fill=color, width=1)
        
        # Vertical lines every 50 pixels
        for x in range(0, template.width, 50):
            if x % 100 == 0:
                color = (200, 200, 200)
                draw.line([(x, 0), (x, 50)], fill=color, width=1)
                draw.text((x + 5, 5), str(x), fill='gray', font=font)
            else:
                color = (230, 230, 230)
            draw.line([(x, 0), (x, template.height)], fill=color, width=1)
        
        # ===== SAVE THE GUIDED TEMPLATE =====
        template.save(OUTPUT_GUIDE_PATH)
        
        print(f"✅ Created guide: {OUTPUT_GUIDE_PATH}")
        print("\n🎯 COORDINATES SUMMARY:")
        print(f"Photo area: ({photo_x}, {photo_y}) to ({photo_x + photo_width}, {photo_y + photo_height})")
        print(f"QR code area: ({qr_x}, {qr_y}) to ({qr_x + qr_size}, {qr_y + qr_size})")
        print(f"Text start: ({text_x}, {text_y_start})")
        print(f"Line spacing: {line_height} pixels")
        print("\n📖 INSTRUCTIONS:")
        print("1. Open template_with_guides.png")
        print("2. Check if markers align with your template")
        print("3. If not aligned, adjust coordinates in app.py")
        print("4. Red markers = Photo area")
        print("5. Blue markers = QR code area")
        print("6. Green dots = Text starting points")
        
        # Try to open the image automatically
        try:
            template.show()
        except:
            print("\n💡 Open template_with_guides.png manually to view")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def interactive_coordinate_finder():
    """Interactive tool to find coordinates"""
    print("\n🖱️ INTERACTIVE COORDINATE FINDER")
    print("=" * 40)
    
    if not os.path.exists(TEMPLATE_PATH):
        print("Template not found. Please add your template first.")
        return
    
    img = Image.open(TEMPLATE_PATH)
    img.show()
    
    print("\n📐 MANUAL COORDINATE FINDING:")
    print("1. The template image should now be open")
    print("2. Use any image viewer (Paint, Photos, Preview)")
    print("3. Hover your mouse over key positions:")
    print("   - Top-left corner of photo area")
    print("   - Top-left corner of QR code area")
    print("   - Where 'Full Name' should start")
    print("4. Note the X,Y coordinates shown in your image viewer")
    print("\n📝 EXAMPLE COORDINATES YOU MIGHT GET:")
    print("Photo: (120, 260)")
    print("QR Code: (1250, 780)")
    print("Text: (520, 300)")
    
    # Ask user for coordinates
    print("\n📝 ENTER YOUR COORDINATES:")
    try:
        photo_x = int(input("Photo X coordinate: ") or "50")
        photo_y = int(input("Photo Y coordinate: ") or "150")
        qr_x = int(input("QR Code X coordinate: ") or "1100")
        qr_y = int(input("QR Code Y coordinate: ") or "700")
        text_x = int(input("Text X coordinate: ") or "400")
        text_y = int(input("Text Y coordinate: ") or "200")
        
        print("\n✅ YOUR COORDINATES:")
        print(f"Photo paste position: ({photo_x}, {photo_y})")
        print(f"QR paste position: ({qr_x}, {qr_y})")
        print(f"Text start position: ({text_x}, {text_y})")
        
        # Generate code snippet
        print("\n📋 CODE TO COPY TO app.py:")
        print(f"""
# Photo position
template.paste(photo, ({photo_x}, {photo_y}))

# QR code position  
template.paste(qr_crop.resize((300, 300)), ({qr_x}, {qr_y}))

# Text positions
text_start_x = {text_x}
text_start_y = {text_y}
line_height = 50

draw.text((text_start_x, text_start_y), str(info['name']), font=font, fill='black')
draw.text((text_start_x, text_start_y + line_height), f"DOB: {{info['dob']}}", font=font, fill='black')
# ... continue for other fields
        """)
        
    except ValueError:
        print("❌ Please enter numbers only for coordinates")

if __name__ == "__main__":
    print("=" * 50)
    print("FAYDA ID TEMPLATE COORDINATE FINDER")
    print("=" * 50)
    
    print("\nChoose an option:")
    print("1. Create visual guide with markers")
    print("2. Interactive coordinate finder")
    print("3. Both")
    
    choice = input("\nEnter choice (1, 2, or 3): ").strip()
    
    if choice in ["1", "3"]:
        create_coordinate_guide()
    
    if choice in ["2", "3"]:
        interactive_coordinate_finder()
    
    print("\n🎯 NEXT STEPS:")
    print("1. Adjust coordinates in app.py based on findings")
    print("2. Test with a real PDF")
    print("3. Fine-tune if needed")
    print("\nPress Enter to exit...")
    input()