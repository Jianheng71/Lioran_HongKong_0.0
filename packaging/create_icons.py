from pathlib import Path
import platform
import subprocess

from PIL import Image, ImageDraw

OUTPUT = Path(__file__).parent / "generated-icons"
OUTPUT.mkdir(parents=True, exist_ok=True)

image = Image.new("RGBA", (1024, 1024), "#172554")
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((94, 94, 930, 930), radius=190, fill="#2563eb")
draw.rounded_rectangle((260, 242, 392, 782), radius=54, fill="white")
draw.rounded_rectangle((260, 650, 735, 782), radius=54, fill="white")
draw.ellipse((635, 244, 766, 375), fill="#bfdbfe")
image.save(OUTPUT / "lioran.ico", format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

if platform.system() == "Darwin":
    iconset = OUTPUT / "lioran.iconset"
    iconset.mkdir(exist_ok=True)
    for size in (16, 32, 128, 256, 512):
        image.resize((size, size), Image.Resampling.LANCZOS).save(iconset / f"icon_{size}x{size}.png")
        image.resize((size * 2, size * 2), Image.Resampling.LANCZOS).save(
            iconset / f"icon_{size}x{size}@2x.png"
        )
    subprocess.run(
        ["iconutil", "-c", "icns", str(iconset), "-o", str(OUTPUT / "lioran.icns")],
        check=True,
    )
