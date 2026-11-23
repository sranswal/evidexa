import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def create_thumbnail(output_path="assets/youtube_thumbnail.png"):
    W, H = 1280, 720
    base = Image.new("RGBA", (W, H), (11, 15, 25, 255))
    draw = ImageDraw.Draw(base)

    # 1. Subtle diagonal gradient background
    for y in range(H):
        ratio = y / H
        r = int(10 + ratio * 8)
        g = int(14 + ratio * 14)
        b = int(24 + ratio * 22)
        draw.line([(0, y), (W, y)], fill=(r, g, b, 255))

    # Ambient radial cyan/blue glow in top-left and center-right
    glow_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)
    # Cyan glow behind title
    glow_draw.ellipse([(-100, -100), (500, 500)], fill=(14, 165, 233, 45))
    # Indigo glow behind right UI card
    glow_draw.ellipse([(650, 80), (1350, 700)], fill=(99, 102, 241, 40))
    # Amber glow near prize badge
    glow_draw.ellipse([(80, 30), (450, 150)], fill=(245, 158, 11, 30))
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(80))
    base = Image.alpha_composite(base, glow_layer)

    # 2. Sleek decorative grid dots / subtle tech accents
    grid_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    grid_draw = ImageDraw.Draw(grid_layer)
    for gx in range(40, W, 48):
        for gy in range(40, H, 48):
            grid_draw.point((gx, gy), fill=(255, 255, 255, 18))
    base = Image.alpha_composite(base, grid_layer)

    # 3. Fonts setup
    font_bold = "C:/Windows/Fonts/segoeuib.ttf"
    font_semibold = "C:/Windows/Fonts/seguisb.ttf"
    font_regular = "C:/Windows/Fonts/segoeui.ttf"
    if not os.path.exists(font_bold):
        font_bold = "C:/Windows/Fonts/arialbd.ttf"
        font_semibold = "C:/Windows/Fonts/arialbd.ttf"
        font_regular = "C:/Windows/Fonts/arial.ttf"

    f_badge = ImageFont.truetype(font_bold, 18)
    f_brand = ImageFont.truetype(font_bold, 64)
    f_sub = ImageFont.truetype(font_bold, 28)
    f_desc = ImageFont.truetype(font_semibold, 20)
    f_pill = ImageFont.truetype(font_bold, 16)
    f_url = ImageFont.truetype(font_bold, 17)

    # 4. Right side: Floating UI Card with Screenshot of Forensic Tampering
    ui_ss_path = "assets/screenshots/02_visual_forensics.png"
    if os.path.exists(ui_ss_path):
        ss_img = Image.open(ui_ss_path).convert("RGBA")
        # Crop or scale to card size: 620 x 480
        cw, ch = 600, 460
        ss_resized = ss_img.resize((cw, ch), Image.Resampling.LANCZOS)

        # Rounded corner mask for UI card
        mask = Image.new("L", (cw, ch), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([(0, 0), (cw, ch)], radius=18, fill=255)

        # Create card container with drop shadow
        card_x, card_y = 630, 130
        shadow_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sh_draw = ImageDraw.Draw(shadow_layer)
        sh_draw.rounded_rectangle([(card_x - 10, card_y - 6), (card_x + cw + 10, card_y + ch + 14)], radius=24, fill=(0, 0, 0, 180))
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(18))
        base = Image.alpha_composite(base, shadow_layer)

        # Paste the UI screenshot into base
        card_holder = Image.new("RGBA", (cw, ch), (15, 23, 42, 255))
        card_holder.paste(ss_resized, (0, 0), mask)
        base.paste(card_holder, (card_x, card_y), mask)

        # Card Border glow
        border_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        b_draw = ImageDraw.Draw(border_layer)
        b_draw.rounded_rectangle([(card_x, card_y), (card_x + cw, card_y + ch)], radius=18, outline=(56, 189, 248, 160), width=2)
        base = Image.alpha_composite(base, border_layer)

        # Floating Pill badge on the screenshot: "LIVE TAMPERING HEATMAP"
        ht_pill = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        hp_draw = ImageDraw.Draw(ht_pill)
        px1, py1, px2, py2 = card_x + 20, card_y + ch - 54, card_x + 270, card_y + ch - 16
        hp_draw.rounded_rectangle([(px1, py1), (px2, py2)], radius=10, fill=(15, 23, 42, 230), outline=(239, 68, 68, 220), width=2)
        hp_draw.ellipse([(px1 + 14, py1 + 13), (px1 + 24, py1 + 23)], fill=(239, 68, 68, 255))
        hp_draw.text((px1 + 34, py1 + 9), "FORGERY DETECTED: 89%", fill=(255, 255, 255, 255), font=f_pill)
        base = Image.alpha_composite(base, ht_pill)

    # 5. Top Hackathon Winner Ribbon / Badge (Left Side)
    bx1, by1, bx2, by2 = 60, 60, 560, 102
    draw = ImageDraw.Draw(base)
    # Glassy amber badge
    draw.rounded_rectangle([(bx1, by1), (bx2, by2)], radius=12, fill=(245, 158, 11, 35), outline=(245, 158, 11, 200), width=2)
    draw.text((bx1 + 18, by1 + 10), "🏆 3RD PRIZE WINNER  |  DATAOPS HACKATHON", fill=(251, 191, 36, 255), font=f_badge)

    # 6. Main Brand Title
    tx, ty = 60, 126
    # Title shadow
    draw.text((tx + 3, ty + 3), "EVIDEXA", fill=(0, 0, 0, 220), font=f_brand)
    # Title main
    draw.text((tx, ty), "EVIDEXA", fill=(255, 255, 255, 255), font=f_brand)

    # 7. Subtitle / Value Proposition
    sy = ty + 82
    draw.text((tx, sy), "AI DOCUMENT FORENSICS", fill=(56, 189, 248, 255), font=f_sub)
    draw.text((tx, sy + 38), "& FRAUD DETECTION", fill=(241, 245, 249, 255), font=f_sub)

    # Short Punchy Explainer
    ey = sy + 90
    draw.text((tx, ey), "Next-Gen Investigation Platform for Tamper-Evident", fill=(148, 163, 184, 255), font=f_desc)
    draw.text((tx, ey + 28), "Document Auditing & Court-Defensible Dossiers", fill=(148, 163, 184, 255), font=f_desc)

    # 8. Feature Capability Pills
    py_start = ey + 75
    features = [
        ("⚡ Hybrid OCR (En + Hi)", (34, 197, 94)),
        ("🔬 ELA & Copy-Move Heatmaps", (249, 115, 22)),
        ("🕸️ Contextual Evidence Graph", (168, 85, 247)),
        ("⚖️ SHA-256 Audit Dossiers", (59, 130, 246)),
    ]

    for i, (label, col) in enumerate(features):
        fx = tx + (i % 2) * 260
        fy = py_start + (i // 2) * 44
        # draw small pill
        draw.rounded_rectangle([(fx, fy), (fx + 245, fy + 34)], radius=8, fill=(15, 23, 42, 220), outline=col + (180,), width=1)
        draw.text((fx + 12, fy + 7), label, fill=(241, 245, 249, 255), font=f_pill)

    # 9. Bottom URL / Call to Action Strip
    ux1, uy1, ux2, uy2 = 60, 615, 560, 665
    draw.rounded_rectangle([(ux1, uy1), (ux2, uy2)], radius=12, fill=(14, 165, 233, 30), outline=(56, 189, 248, 220), width=2)
    draw.text((ux1 + 18, uy1 + 13), "🚀 TRY LIVE DEMO:  try-evidexa.vercel.app", fill=(255, 255, 255, 255), font=f_url)

    # Save output
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    base.convert("RGB").save(output_path, "PNG", quality=95)
    print(f"Generated thumbnail successfully: {output_path} (Size: {base.size})")

if __name__ == "__main__":
    create_thumbnail("assets/youtube_thumbnail.png")
