"""Create the reproducible app icon using geometric primitives."""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    image = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((8, 8, 248, 248), radius=56, fill="#171e2a")
    for top, fill in [(139, "#36685f"), (103, "#5cb499"), (67, "#8ee3c5")]:
        draw.rounded_rectangle((52, top, 204, top + 54), radius=12, fill=fill)
        for left in [70, 113, 156]:
            draw.rounded_rectangle((left, top + 14, left + 29, top + 39), radius=4, fill="#171e2a")
    image.save(ROOT / "assets" / "parquet-info.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == "__main__":
    main()
