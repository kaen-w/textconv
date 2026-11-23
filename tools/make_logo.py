"""TextConv logo 生成脚本。

设计：把这款工具的输出直接画出来 —— ``('a')``。

含义直白：括号是 SQL 的 IN (...) / 元组的边界，引号是字符串字面量，
金色的是值本身。看得懂 SQL 的人一眼就知道这工具是干什么的。

小尺寸（16/24px）自动退化成 ``'a'``：三个字符塞进 16px 只能是一团糊，
两个引号加一个字母至少还认得出。

用法：
    python tools/make_logo.py     # 输出 PNG / ICO / ICNS / SVG 到 assets/
"""

from __future__ import annotations

import os
import struct
import subprocess
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFont

SIZE = 1024
RADIUS_RATIO = 0.225

INK = (12, 18, 32)        # 深墨蓝底
CREAM = (250, 247, 240)   # 括号
AMBER = (245, 179, 1)     # 值 / 高亮

FONT_PATH = "/System/Library/Fonts/Menlo.ttc"
FONT_INDEX_BOLD = 1

FULL_TEXT_RATIO = 0.30
SMALL_TEXT_RATIO = 0.46

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")


def _tile(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=int(size * RADIUS_RATIO), fill=INK
    )
    return img


def _draw_text(img: Image.Image, size: int, parts, ratio: float) -> None:
    """按片段着色并水平居中：[(文本, 颜色), ...]"""
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_PATH, int(size * ratio), index=FONT_INDEX_BOLD)
    widths = [draw.textlength(text, font=font) for text, _ in parts]
    x = (size - sum(widths)) / 2
    for (text, color), width in zip(parts, widths):
        draw.text((x, size * 0.52), text, font=font, fill=color, anchor="lm")
        x += width


def render(size: int, simplified: bool = False) -> Image.Image:
    img = _tile(size)
    if simplified:
        # 小尺寸用单色：多色在 16px 会互相吃对比度
        _draw_text(img, size, [("'a'", CREAM)], SMALL_TEXT_RATIO)
    else:
        _draw_text(img, size, [("(", CREAM), ("'a'", AMBER), (")", CREAM)], FULL_TEXT_RATIO)
    return img


def _png_bytes(img: Image.Image) -> bytes:
    import io

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def write_ico(path: str, entries) -> None:
    """自己拼 ICO：不同尺寸可以用不同画法，Pillow 的 save 只能缩放同一张图。"""
    blobs = [(size, _png_bytes(img)) for size, img in entries]
    header = struct.pack("<HHH", 0, 1, len(blobs))
    offset = 6 + 16 * len(blobs)
    directory = b""
    for size, blob in blobs:
        w = 0 if size >= 256 else size
        directory += struct.pack("<BBBBHHII", w, w, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
    with open(path, "wb") as fh:
        fh.write(header + directory + b"".join(blob for _, blob in blobs))


def export_pngs(master: Image.Image) -> None:
    for px in (1024, 512, 256, 128, 64, 32, 24, 16):
        path = os.path.join(ASSETS, "logo.png" if px == 1024 else f"logo-{px}.png")
        if px <= 24:
            render(px, simplified=True).save(path)
        else:
            master.resize((px, px), Image.LANCZOS).save(path)
        print(f"  [ok] {os.path.relpath(path, ROOT)}")

    tray = os.path.join(ASSETS, "logo-tray.png")
    render(32, simplified=True).save(tray)
    print(f"  [ok] {os.path.relpath(tray, ROOT)}")


def export_ico(master: Image.Image) -> None:
    path = os.path.join(ASSETS, "textconv.ico")
    entries = [(16, render(16, simplified=True)), (24, render(24, simplified=True))]
    for px in (32, 48, 64, 128, 256):
        entries.append((px, master.resize((px, px), Image.LANCZOS)))
    write_ico(path, entries)
    print(f"  [ok] {os.path.relpath(path, ROOT)}")


def export_icns(master: Image.Image) -> None:
    if sys.platform != "darwin":
        return
    iconset = os.path.join(ASSETS, "TextConv.iconset")
    os.makedirs(iconset, exist_ok=True)
    mapping = {
        "icon_16x16.png": (16, True), "icon_16x16@2x.png": (32, False),
        "icon_32x32.png": (32, False), "icon_32x32@2x.png": (64, False),
        "icon_128x128.png": (128, False), "icon_128x128@2x.png": (256, False),
        "icon_256x256.png": (256, False), "icon_256x256@2x.png": (512, False),
        "icon_512x512.png": (512, False), "icon_512x512@2x.png": (1024, False),
    }
    for name, (px, simplified) in mapping.items():
        if px <= 32:
            img = render(px, simplified=simplified)
        else:
            img = master.resize((px, px), Image.LANCZOS)
        img.save(os.path.join(iconset, name))
    target = os.path.join(ASSETS, "TextConv.icns")
    subprocess.run(["iconutil", "-c", "icns", iconset, "-o", target], check=True)
    for name in mapping:
        os.unlink(os.path.join(iconset, name))
    os.rmdir(iconset)
    print(f"  [ok] {os.path.relpath(target, ROOT)}")


# ---------------------------------------------------------------- 菜单栏图标
# 三个候选，用 --menubar 选择：clipboard / document / bubble
MENUBAR_SS = 8


def _menubar_canvas():
    size = 22 * MENUBAR_SS
    return Image.new("RGBA", (size, size), (0, 0, 0, 0)), size


def _menubar_clipboard():
    img, size = _menubar_canvas()
    d = ImageDraw.Draw(img)
    u = size / 22.0
    ink = (0, 0, 0, 255)
    d.rounded_rectangle([4.2*u, 3.4*u, 17.8*u, 20.4*u], radius=2.4*u, outline=ink, width=int(1.7*u))
    d.rounded_rectangle([8.2*u, 1.6*u, 13.8*u, 5.0*u], radius=1.2*u, fill=ink)
    for i, y in enumerate((8.0, 11.2, 14.4)):
        width_units = 5.6 if i < 2 else 4.0
        d.rounded_rectangle([7.2*u, (y-0.75)*u, (7.2+width_units)*u, (y+0.75)*u], radius=0.75*u, fill=ink)
    return img


def _menubar_document():
    img, size = _menubar_canvas()
    d = ImageDraw.Draw(img)
    u = size / 22.0
    ink = (0, 0, 0, 255)
    stroke = int(1.7 * u)
    pts = [(9.2*u, 2.6*u), (14.0*u, 2.6*u), (17.6*u, 6.2*u),
           (17.6*u, 20.2*u), (4.4*u, 20.2*u), (4.4*u, 2.6*u)]
    d.line(pts + [pts[0]], fill=ink, width=stroke, joint="curve")
    d.line([(14.0*u, 2.6*u), (14.0*u, 6.2*u), (17.6*u, 6.2*u)], fill=ink, width=stroke, joint="curve")
    for x in (7.3, 10.9):
        d.rounded_rectangle([x*u, 8.6*u, (x+2.2)*u, 12.2*u], radius=1.1*u, fill=ink)
        d.polygon([(x*u, 11.8*u), ((x+2.2)*u, 11.8*u),
                   ((x+0.5)*u, 15.1*u), ((x-0.7)*u, 13.8*u)], fill=ink)
    return img


def _menubar_bubble():
    img, size = _menubar_canvas()
    d = ImageDraw.Draw(img)
    u = size / 22.0
    ink = (0, 0, 0, 255)
    stroke = int(1.7 * u)
    d.rounded_rectangle([3.4*u, 3.2*u, 18.6*u, 15.8*u], radius=3.6*u, outline=ink, width=stroke)
    d.polygon([(6.8*u, 15.4*u), (9.4*u, 15.4*u), (6.2*u, 19.8*u), (6.0*u, 17.2*u)], fill=ink)
    for i, y in enumerate((7.4, 10.2, 13.0)):
        width_units = 9.4 if i < 2 else 6.0
        d.rounded_rectangle([6.1*u, (y-0.85)*u, (6.1+width_units)*u, (y+0.85)*u], radius=0.85*u, fill=ink)
    return img


def _menubar_document_ts():
    """折角文档 + TS。

    关键是给字母腾空间：边框收到 1.4、页面放宽到 4.0~18.0，
    字母用 Helvetica Neue Condensed Black（窄体粗字），
    同样宽度下能比常规粗体大一号，17pt 下 T/S 才不会糊成一块。
    """
    img, size = _menubar_canvas()
    d = ImageDraw.Draw(img)
    u = size / 22.0
    ink = (0, 0, 0, 255)
    stroke = int(1.4 * u)

    left, top, right, bottom = 4.0 * u, 2.4 * u, 18.0 * u, 20.4 * u
    fold = 3.6 * u
    points = [
        (left + 4.8 * u, top), (right - fold, top), (right, top + fold),
        (right, bottom), (left, bottom), (left, top),
    ]
    d.line(points + [points[0]], fill=ink, width=stroke, joint="curve")
    d.line([(right - fold, top), (right - fold, top + fold), (right, top + fold)],
           fill=ink, width=stroke, joint="curve")

    font = ImageFont.truetype("/System/Library/Fonts/HelveticaNeue.ttc", int(size * 0.42), index=9)
    box = d.textbbox((0, 0), "TS", font=font)
    width, height = box[2] - box[0], box[3] - box[1]
    cx = (left + right) / 2
    cy = (top + bottom) / 2 + 0.4 * u
    d.text((cx - width / 2 - box[0], cy - height / 2 - box[1]), "TS", font=font, fill=ink)
    return img


def _menubar_tile_ts():
    """实心圆角块 + 镂空 TS —— 字母占满，17pt 下也清楚。

    和菜单栏里 WPS / 有道那种块状图标是同一套视觉语言：
    template 渲染时块是前景色，字母是镂空的（透出菜单栏底色）。
    """
    size = 22 * MENUBAR_SS
    tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(tile)
    u = size / 22.0
    draw.rounded_rectangle([u, u, size - u, size - u], radius=0.22 * size, fill=(0, 0, 0, 255))

    font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", int(size * 0.47), index=1)
    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    box = md.textbbox((0, 0), "TS", font=font)
    width, height = box[2] - box[0], box[3] - box[1]
    md.text(((size - width) / 2 - box[0], (size - height) / 2 - box[1]), "TS", font=font, fill=255)

    tile.putalpha(ImageChops.subtract(tile.getchannel("A"), mask))
    return tile


MENUBAR_STYLES = {
    "clipboard": _menubar_clipboard,
    "tile_ts": _menubar_tile_ts,
    "document": _menubar_document,
    "document_ts": _menubar_document_ts,
    "bubble": _menubar_bubble,
}

DEFAULT_MENUBAR = "document_ts"


def export_menubar(style: str = DEFAULT_MENUBAR) -> None:
    """菜单栏图标：单色模板图（只取 alpha），颜色由系统菜单栏明暗决定。"""
    builder = MENUBAR_STYLES.get(style)
    if builder is None:
        raise SystemExit(f"未知的菜单栏样式：{style}（可选：{', '.join(MENUBAR_STYLES)}）")
    img = builder()
    master = img.resize((44, 44), Image.LANCZOS)
    master.save(os.path.join(ASSETS, "menubar.png"))
    img.resize((88, 88), Image.LANCZOS).save(os.path.join(ASSETS, "menubar@2x.png"))
    print(f"  ✓ {os.path.relpath(os.path.join(ASSETS, 'menubar.png'), ROOT)} ({style})")


def export_svg() -> None:
    """矢量版：同一段文本，等宽字体渲染，方便改字改色。"""
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <rect width="512" height="512" rx="{int(512 * RADIUS_RATIO)}" fill="#0c1220"/>
  <text x="256" y="306" text-anchor="middle"
        font-family="'SF Mono', Menlo, Consolas, monospace"
        font-size="150" font-weight="700">
    <tspan fill="#faf7f0">(</tspan><tspan fill="#f5b301">'a'</tspan><tspan fill="#faf7f0">)</tspan>
  </text>
</svg>
"""
    path = os.path.join(ASSETS, "logo.svg")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"  [ok] {os.path.relpath(path, ROOT)}")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    style = DEFAULT_MENUBAR
    if "--menubar" in argv:
        style = argv[argv.index("--menubar") + 1]

    os.makedirs(ASSETS, exist_ok=True)
    master = render(SIZE)
    print("生成 TextConv logo：")
    export_pngs(master)
    export_ico(master)
    export_icns(master)
    export_menubar(style)
    export_svg()
    print("完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
