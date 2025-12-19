"""
Generate placeholder images for Secret Santa app
"""
from PIL import Image, ImageDraw, ImageFont
import os

# Create images directory
os.makedirs("images", exist_ok=True)

# Colors
RED = (230, 57, 70)
GOLD = (255, 215, 0)
GREEN = (45, 106, 79)
DARK_GREEN = (27, 67, 50)
CREAM = (255, 248, 220)

def create_santa_mode_image():
    """Create Santa mode card image"""
    img = Image.new('RGB', (400, 400), DARK_GREEN)
    draw = ImageDraw.Draw(img)

    # Draw a simple Santa hat shape
    # Hat body (red triangle)
    draw.polygon([(100, 300), (300, 300), (200, 100)], fill=RED)
    # Hat trim (white rectangle)
    draw.rectangle([(100, 300), (300, 320)], fill=(255, 255, 255))
    # Hat pompom (white circle)
    draw.ellipse([(180, 80), (220, 120)], fill=(255, 255, 255))

    # Add text
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 40)
    except:
        font = ImageFont.load_default()

    draw.text((200, 350), "SANTA MODE", fill=CREAM, anchor="mm", font=font)

    img.save("images/santa_mode.png")
    print("Created santa_mode.png")

def create_receiver_mode_image():
    """Create Receiver mode card image"""
    img = Image.new('RGB', (400, 400), DARK_GREEN)
    draw = ImageDraw.Draw(img)

    # Draw a simple gift box
    # Box body (red rectangle)
    draw.rectangle([(120, 180), (280, 320)], fill=RED)
    # Box lid (darker red)
    draw.rectangle([(100, 150), (300, 180)], fill=(200, 40, 50))
    # Ribbon vertical
    draw.rectangle([(190, 150), (210, 320)], fill=GOLD)
    # Ribbon horizontal
    draw.rectangle([(100, 235), (300, 255)], fill=GOLD)
    # Bow
    draw.ellipse([(170, 110), (230, 170)], fill=GOLD)

    # Add text
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 36)
    except:
        font = ImageFont.load_default()

    draw.text((200, 360), "RECEIVER MODE", fill=CREAM, anchor="mm", font=font)

    img.save("images/receiver_mode.png")
    print("Created receiver_mode.png")

def create_ornament(color, filename):
    """Create ornament image with given color"""
    img = Image.new('RGBA', (60, 60), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Ornament hook (gold)
    draw.rectangle([(27, 5), (33, 15)], fill=GOLD)
    # Ornament ball
    draw.ellipse([(10, 15), (50, 55)], fill=color)
    # Highlight
    draw.ellipse([(15, 20), (25, 30)], fill=(255, 255, 255, 100))

    img.save(f"images/{filename}")
    print(f"Created {filename}")

def create_envelope():
    """Create envelope icon"""
    img = Image.new('RGBA', (80, 80), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Envelope body (cream)
    draw.rectangle([(10, 25), (70, 60)], fill=CREAM)
    # Envelope flap (red)
    draw.polygon([(10, 25), (40, 40), (70, 25)], fill=RED)
    # Border
    draw.rectangle([(10, 25), (70, 60)], outline=DARK_GREEN, width=2)
    draw.polygon([(10, 25), (40, 40), (70, 25)], outline=DARK_GREEN, width=2)

    img.save("images/envelope.png")
    print("Created envelope.png")

def create_background_pattern():
    """Create tileable background pattern"""
    img = Image.new('RGBA', (100, 100), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw small snowflakes
    for x in [20, 80]:
        for y in [20, 80]:
            # Simple snowflake (asterisk)
            draw.line([(x, y-8), (x, y+8)], fill=(255, 255, 255, 30), width=2)
            draw.line([(x-8, y), (x+8, y)], fill=(255, 255, 255, 30), width=2)
            draw.line([(x-6, y-6), (x+6, y+6)], fill=(255, 255, 255, 30), width=2)
            draw.line([(x-6, y+6), (x+6, y-6)], fill=(255, 255, 255, 30), width=2)

    img.save("images/background_pattern.png")
    print("Created background_pattern.png")

def create_header_image():
    """Create festive header with Christmas elements"""
    img = Image.new('RGB', (1200, 150), DARK_GREEN)
    draw = ImageDraw.Draw(img)

    # Draw Christmas ornaments across the top
    y_pos = 75
    for x in range(100, 1200, 200):
        # Ornament string
        draw.line([(x, 20), (x, y_pos-30)], fill=GOLD, width=3)
        # Ornament ball
        color = [RED, GOLD, GREEN][int(x/200) % 3]
        draw.ellipse([(x-25, y_pos-55), (x+25, y_pos-5)], fill=color)
        # Highlight
        draw.ellipse([(x-15, y_pos-45), (x-5, y_pos-35)], fill=(255, 255, 255, 150))

    # Add snowflakes
    for i in range(15):
        import random
        x = random.randint(50, 1150)
        y = random.randint(30, 120)
        size = random.randint(3, 6)
        draw.line([(x, y-size), (x, y+size)], fill=(255, 255, 255), width=2)
        draw.line([(x-size, y), (x+size, y)], fill=(255, 255, 255), width=2)

    img.save("images/header.png")
    print("Created header.png")

def create_footer_image():
    """Create festive footer with Christmas border"""
    img = Image.new('RGB', (1200, 100), DARK_GREEN)
    draw = ImageDraw.Draw(img)

    # Draw wavy garland at top
    for x in range(0, 1200, 40):
        y = 20 + int(10 * (1 if (x // 40) % 2 == 0 else -1))
        draw.ellipse([(x-15, y-15), (x+15, y+15)], fill=GREEN)
        # Add berries
        if x % 80 == 0:
            draw.ellipse([(x-5, y-5), (x+5, y+5)], fill=RED)

    # Add text at bottom
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 16)
    except:
        font = ImageFont.load_default()

    text = "🎄 Happy Holidays! 🎁"
    draw.text((600, 60), text, fill=GOLD, anchor="mm", font=font)

    img.save("images/footer.png")
    print("Created footer.png")

if __name__ == "__main__":
    print("Generating placeholder images...")
    create_santa_mode_image()
    create_receiver_mode_image()
    create_ornament(RED, "ornament_red.png")
    create_ornament(GOLD, "ornament_gold.png")
    create_ornament(GREEN, "ornament_green.png")
    create_envelope()
    create_background_pattern()
    create_header_image()
    create_footer_image()
    print("All images created successfully!")
