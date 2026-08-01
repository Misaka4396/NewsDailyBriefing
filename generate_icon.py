"""
生成应用图标 (icon.ico)
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ASSETS_DIR = Path(__file__).parent / "assets"
OUTPUT_ICO = ASSETS_DIR / "icon.ico"
OUTPUT_PNG = ASSETS_DIR / "icon.png"
SIZE = 256


def generate() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 蓝色渐变背景（用多层同心圆模拟）
    center = SIZE // 2
    for r in range(SIZE // 2, 0, -1):
        ratio = r / (SIZE // 2)
        # 从深蓝到亮蓝
        r_val = int(26 + (57 - 26) * ratio)
        g_val = int(35 + (73 - 35) * ratio)
        b_val = int(126 + (171 - 126) * ratio)
        draw.ellipse(
            [center - r, center - r, center + r, center + r],
            fill=(r_val, g_val, b_val, 255),
        )

    # 白色地球经纬线（简化版）
    import math
    # 水平线
    for y_offset in [-0.35, -0.15, 0.05, 0.25]:
        y = int(center + center * y_offset)
        rx = int(center * math.sqrt(1 - y_offset ** 2) * 0.9)
        if rx > 20:
            draw.arc(
                [center - rx, y - 3, center + rx, y + 3],
                0, 360, fill=(255, 255, 255, 120), width=2,
            )
    # 垂直线
    for x_offset in [-0.3, 0, 0.3]:
        x = int(center + center * x_offset)
        ry = int(center * math.sqrt(1 - x_offset ** 2) * 0.9)
        if ry > 20:
            draw.arc(
                [x - 3, center - ry, x + 3, center + ry],
                0, 360, fill=(255, 255, 255, 120), width=2,
            )

    # 字母 N（News）
    try:
        font = ImageFont.truetype("C:\\Windows\\Fonts\\seguiemj.ttf", SIZE // 3)
    except Exception:
        try:
            font = ImageFont.truetype("C:\\Windows\\Fonts\\segoeui.ttf", SIZE // 3)
        except Exception:
            font = ImageFont.load_default()

    draw.text(
        (center, center),
        "N",
        fill=(255, 255, 255, 255),
        font=font,
        anchor="mm",
    )

    # 保存多尺寸 ICO
    sizes = [256, 128, 64, 48, 32, 16]
    img.save(str(OUTPUT_ICO), format="ICO", sizes=[(s, s) for s in sizes])
    img.save(str(OUTPUT_PNG), format="PNG")

    print(f"图标已生成: {OUTPUT_ICO}")
    print(f"图标已生成: {OUTPUT_PNG}")


if __name__ == "__main__":
    generate()
