"""Optional editable share-art source. Requires Pillow; never run as part of the web build."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FONT = Path("C:/Windows/Fonts/segoeui.ttf")
FONT_BOLD = Path("C:/Windows/Fonts/seguisb.ttf")


def main():
    image = Image.new("RGB", (1200, 630), "#080b12")
    draw = ImageDraw.Draw(image)
    ink, muted, blue, line = "#edf0f8", "#a2adbf", "#a0b9ff", "#273248"
    def font(size, bold=False):
        return ImageFont.truetype(str(FONT_BOLD if bold else FONT), size)
    draw.line([(58, 76), (58, 51), (78, 67), (98, 51), (98, 76)], fill=blue, width=4)
    draw.text((112, 46), "Mass Outreach", fill=ink, font=font(28, True))
    draw.text((930, 58), "PRODUCT VISION", fill=muted, font=font(13))
    draw.line((58, 110, 1142, 110), fill=line, width=1)
    draw.text((54, 147), "The future of", fill=ink, font=font(94))
    draw.text((54, 247), "networking.", fill=blue, font=font(94))
    draw.text((60, 388), "Your experience. The right people. A better first conversation.", fill=muted, font=font(24))
    draw.rounded_rectangle((59, 468, 350, 527), radius=8, fill="#b6c9ff")
    draw.text((81, 481), "Explore early access", fill="#10182c", font=font(23, True))
    draw.line((59, 570, 1142, 570), fill=line, width=1)
    draw.text((60, 586), "PERSONAL BY DESIGN. HUMAN BY DEFAULT.", fill=muted, font=font(13))
    image.save(ROOT / "public" / "social-card.png", optimize=True)


if __name__ == "__main__":
    main()
