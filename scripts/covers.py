#!/usr/bin/env python3
"""封面生成（1080×1440，3:4）：上人像、下标题。配色/字体跟随该选题的 SPEC。

用法：
    python3 covers.py <spec_name> [--text-only] [--out 目录]

SPEC 里的封面字段：
    cover=dict(title=['第一行', '第二行'], eyebrow='可选小字', photo_t=12.5)
没给 cover 就退回用 title / 第一张卡的 source 起点。
"""
import subprocess as sp
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine as B  # noqa: E402

W, H = 1080, 1440
SIDE, RIGHT = 72, 1008
PHOTO_H = 760
HEAD_Y = 950
SUB_Y = 1220
PANEL = (SIDE, 880, RIGHT, 1290)


def grab(t):
    src = B.SRC or B.DEFAULT_SRC
    if not src:
        raise SystemExit('SPEC 里没有 src，config.env 里也没设 SOURCE_VIDEO')
    out = Path('/tmp') / f'cover_{Path(src).stem}_{int(t)}.png'
    sp.run(['ffmpeg', '-y', '-v', 'error', '-ss', str(t), '-i', src,
            '-frames:v', '1', '-vf', f'scale={W}:-1', str(out)], check=True)
    return Image.open(out).convert('RGB')


def fit(d, lines, maxw, start, minimum=40):
    """按最宽那行自动缩号。"""
    size = start
    while size > minimum and max(B.ui_w(l, size) for l in lines) > maxw:
        size -= 2
    return size


def draw_text(im, lines, title=True):
    d = ImageDraw.Draw(im)
    size = fit(d, lines, RIGHT - SIDE, 100 if title else 44, 40 if title else 28)
    lh = int(size * 1.18)
    y = HEAD_Y if title else SUB_Y
    for l in lines:
        B.text(d, (SIDE, y), l, size, B.FG)
        y += lh
    return im


def brand_bar(im):
    if not B.BRAND_NAME:
        return im
    d = ImageDraw.Draw(im)
    B.text(d, (SIDE, 1330), B.BRAND_NAME, 44, B.BRAND)
    if B.TAGLINE:
        B.text_r(d, RIGHT, 1334, B.TAGLINE, 28, B.MUTE)
    return im


def cover(name, spec, text_only=False):
    cov = spec.get('cover') or {}
    title = cov.get('title') or [spec.get('title', name)]
    if isinstance(title, str):
        title = [title]
    im = Image.new('RGB', (W, H), B.BG)
    if not text_only:
        t = cov.get('photo_t')
        if t is None:
            cards = [c for c in spec.get('cards', []) if c.get('source')]
            t = cards[0]['source'][0] if cards else 0
        photo = grab(t).crop((0, 0, W, min(PHOTO_H, 760)))
        im.paste(photo, (0, 0))
        if photo.height < PHOTO_H:
            im.paste(photo.resize((W, PHOTO_H)), (0, 0))
        d = ImageDraw.Draw(im)
        d.rectangle((SIDE, 800, SIDE + 200, 860), fill=B.BRAND)
        ey = cov.get('eyebrow') or ''
        if ey:
            B.text_mid(d, SIDE + 20, 830, ey, 30, B.ON_BRAND)
    else:
        d = ImageDraw.Draw(im)
        d.rounded_rectangle(PANEL, radius=24, fill=B.SURFACE)
    im = draw_text(im, title, title=True)
    sub = cov.get('sub') or []
    if isinstance(sub, str):
        sub = [sub]
    if sub:
        im = draw_text(im, sub, title=False)
    im = brand_bar(im)
    out = Path(cov.get('out') or (B.topic_dir(name) / 'cover.png'))
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    if not args:
        raise SystemExit(__doc__)
    B.load_specs()
    for name in args:
        spec = B.SPECS.get(name)
        if not spec:
            raise SystemExit(f'没有这个选题：{name}')
        B.apply_style(spec.get('style', B.DEFAULT_STYLE))
        B.apply_fonts(spec.get('fonts', B.DEFAULT_FONTS))
        B.apply_lang(spec.get('lang', B.DEFAULT_LANG))
        B.SRC = spec.get('src', B.DEFAULT_SRC)
        print(cover(name, spec, text_only='--text-only' in sys.argv), flush=True)


if __name__ == '__main__':
    main()
