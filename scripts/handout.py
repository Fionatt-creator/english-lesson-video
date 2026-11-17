#!/usr/bin/env python3
"""把「表达详解」Markdown 转成可打印的 A4 PDF 学习资料（多语言）。

用法：
    python3 handout.py <表达详解.md> <输出目录> [--lang zh] [--title 标题]
                       [--sub 副标题] [--practice 跟读练习.txt] [--note 备注]

数据源是表达详解 md（单一真相），本脚本只负责排版：
    解析 `**N. \\`表达\\`** ｜ 时间` 条目 + 原句/意思/用法/迁移 → 生成 HTML → 无头 Chrome 打印 PDF

字段名支持中文（原句/意思/用法/迁移）与各语言写法（Original/Meaning/Usage/Transfer 等），
分隔符 `｜` 与 `|` 都认。

若 md 同目录下有 `<md 同名>.原声对照.txt` 或 `<md 同名>.transcript.txt`
（每行 `mm:ss｜说话人｜英文｜译文`），就在文末多排一节原声对照——整段原话逐句对照；
没有这个文件就一个字不加。

配置（环境变量或 <skill>/config.env）：BRAND_NAME、BRAND_URL、BRAND_TAGLINE、LESSON_LOGO、
NATIVE_LANG、CHROME_PATH。
"""
import base64
import html
import os
import re
import subprocess as sp
import sys
from io import BytesIO
from pathlib import Path

# ---------------------------------------------------------------- 配置
def _load_cfg():
    here = Path(__file__).resolve().parent
    cands = []
    if os.environ.get('LESSON_CONFIG'):
        cands.append(Path(os.environ['LESSON_CONFIG']).expanduser())
    cands += [here.parent / 'config.env', Path.home() / '.config' / 'english-lesson-video' / 'config.env']
    cfg = {}
    for p in cands:
        if p.is_file():
            for line in p.read_text(encoding='utf-8').splitlines():
                s = line.strip()
                if not s or s.startswith('#') or '=' not in s:
                    continue
                k, v = s.split('=', 1)
                cfg[k.strip()] = v.strip().strip('"\'')
            break
    for k, v in os.environ.items():
        if k.startswith(('LESSON_', 'BRAND_', 'NATIVE_LANG', 'CHROME_')):
            cfg[k] = v
    return cfg


CFG = _load_cfg()
BRAND = CFG.get('BRAND_NAME', '')
URL = CFG.get('BRAND_URL', '')
TAGLINE = CFG.get('BRAND_TAGLINE', '')
LOGO = CFG.get('LESSON_LOGO', '')
LANG = CFG.get('NATIVE_LANG', 'zh')
CHROME = CFG.get('CHROME_PATH', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')

# ---------------------------------------------------------------- 文案
L = {
    'zh': dict(
        entries='{n} 条', practice='跟读练习', transcript='原声对照',
        tr_count='整章逐句 · {n} 句 · 英中',
        tr_lead='这一段访谈的原话全在这里，按时间顺序排：上英文、下译文。想跟读时先看英文回忆语气，再对一眼译文，检查有没有听漏。',
        meta='共 {n} 条表达 · 按「原句 → 意思 → 用法 → 迁移例句」编排',
        lead='这张笔记把视频里讲过的表达全部收齐，按「原句 → 意思 → 用法 → 迁移例句」四栏编排。建议用法：先看原句回忆视频里的语气，再读用法，最后把迁移例句读出声。带 · 的迁移句可以直接搬到你自己的场景里。',
        transfer='迁移 · ', title='精讲笔记',
        fields={'原句': 'sentence', '意思': 'meaning', '用法': 'usage', '迁移': 'transfer',
                'Original': 'sentence', 'Meaning': 'meaning', 'Usage': 'usage', 'Transfer': 'transfer'},
        skip=('做视频', '选题规划', 'Video plan'),
        font="'PingFang SC','STHeiti','Hiragino Sans GB',sans-serif"),
    'ja': dict(
        entries='{n} 件', practice='音読練習', transcript='原文対訳',
        tr_count='全編 · {n} 文 · 英日',
        tr_lead='この章のインタビュー全文です。時系列に、上に英語、下に日本語訳を並べています。音読の前に英語だけ読んで語調を思い出し、最後に訳を確認して聞き漏らしがないか見直しましょう。',
        meta='全 {n} 表現 · 「原文 → 意味 → 使い方 → 応用例文」の順',
        lead='このノートは動画で扱った表現をすべて収録し、「原文 → 意味 → 使い方 → 応用例文」の4段で整理しています。まず原文で動画の語調を思い出し、次に使い方を読み、最後に応用例文を声に出してください。· 付きの例文は自分の場面にそのまま使えます。',
        transfer='応用 · ', title='学習ノート',
        fields={'原文': 'sentence', '意味': 'meaning', '使い方': 'usage', '応用': 'transfer',
                'Original': 'sentence', 'Meaning': 'meaning', 'Usage': 'usage', 'Transfer': 'transfer'},
        skip=('做视频', '选题规划', 'Video plan'),
        font="'Hiragino Sans','Hiragino Kaku Gothic ProN','YuGothic',sans-serif"),
    'ko': dict(
        entries='{n}개', practice='따라 읽기 연습', transcript='원문 대조',
        tr_count='전체 · {n}문장 · 영한',
        tr_lead='이 장의 인터뷰 원문 전체입니다. 시간 순서대로 위에는 영어, 아래에는 한국어 번역을 두었습니다. 따라 읽기 전에 영어만 보고 말투를 떠올린 뒤, 번역을 확인하며 놓친 부분이 없는지 점검하세요.',
        meta='총 {n}개 표현 · 「원문 → 의미 → 쓰임 → 응용 예문」 순',
        lead='이 노트는 영상에서 다룬 표현을 모두 모아 「원문 → 의미 → 쓰임 → 응용 예문」 네 단계로 정리했습니다. 먼저 원문으로 영상의 말투를 떠올리고, 쓰임을 읽은 뒤, 응용 예문을 소리 내어 읽으세요. · 표시가 있는 예문은 자신의 상황에 바로 쓸 수 있습니다.',
        transfer='응용 · ', title='학습 노트',
        fields={'원문': 'sentence', '의미': 'meaning', '쓰임': 'usage', '응용': 'transfer',
                'Original': 'sentence', 'Meaning': 'meaning', 'Usage': 'usage', 'Transfer': 'transfer'},
        skip=('做视频', '选题规划', 'Video plan'),
        font="'Apple SD Gothic Neo','AppleGothic',sans-serif"),
    'pt': dict(
        entries='{n} itens', practice='Prática de repetição', transcript='Texto original',
        tr_count='Capítulo completo · {n} falas · EN-PT',
        tr_lead='Aqui está o texto completo desta parte da entrevista, em ordem: inglês em cima, tradução embaixo. Antes de repetir em voz alta, leia só o inglês para lembrar o tom; depois confira a tradução e veja o que passou despercebido.',
        meta='{n} expressões · em «original → sentido → uso → transferência»',
        lead='Este material reúne todas as expressões do vídeo em quatro camadas: original, sentido, uso e transferência. Sugestão: leia o original para lembrar o tom do vídeo, depois o uso, e por fim diga a frase de transferência em voz alta. As frases com · podem ir direto para o seu próprio contexto.',
        transfer='Transferência · ', title='Notas de estudo',
        fields={'Original': 'sentence', 'Sentido': 'meaning', 'Uso': 'usage', 'Transferência': 'transfer',
                'Meaning': 'meaning', 'Usage': 'usage', 'Transfer': 'transfer'},
        skip=('做视频', '选题规划', 'Video plan'),
        font="'Helvetica Neue',Arial,sans-serif"),
    'es': dict(
        entries='{n} elementos', practice='Práctica de repetición', transcript='Texto original',
        tr_count='Capítulo completo · {n} frases · EN-ES',
        tr_lead='Aquí está el texto completo de esta parte de la entrevista, en orden: inglés arriba y traducción abajo. Antes de repetir en voz alta, lee solo el inglés para recordar el tono; luego revisa la traducción y comprueba qué se te pasó.',
        meta='{n} expresiones · en «original → significado → uso → transferencia»',
        lead='Estos apuntes reúnen todas las expresiones del vídeo en cuatro capas: original, significado, uso y transferencia. Sugerencia: lee el original para recordar el tono del vídeo, después el uso y por último di la frase de transferencia en voz alta. Las frases con · puedes llevarlas directamente a tu propia situación.',
        transfer='Transferencia · ', title='Apuntes de estudio',
        fields={'Original': 'sentence', 'Significado': 'meaning', 'Uso': 'usage', 'Transferencia': 'transfer',
                'Meaning': 'meaning', 'Usage': 'usage', 'Transfer': 'transfer'},
        skip=('做视频', '选题规划', 'Video plan'),
        font="'Helvetica Neue',Arial,sans-serif"),
    'de': dict(
        entries='{n} Einträge', practice='Nachsprech-Übung', transcript='Originaltext',
        tr_count='Ganzes Kapitel · {n} Sätze · EN-DE',
        tr_lead='Hier steht der vollständige Text dieses Interviewabschnitts, chronologisch: oben Englisch, unten die Übersetzung. Lies vor dem Nachsprechen zuerst nur das Englische, um den Ton zu erinnern, und prüfe danach die Übersetzung, ob du etwas überhört hast.',
        meta='{n} Ausdrücke · gegliedert in «Original → Bedeutung → Gebrauch → Übertragung»',
        lead='Diese Notizen sammeln alle Ausdrücke aus dem Video in vier Schritten: Original, Bedeutung, Gebrauch und Übertragung. Lies zuerst das Original, um den Ton des Videos zu erinnern, dann den Gebrauch und sprich zum Schluss den Übertragungssatz laut aus. Sätze mit · kannst du direkt in deine eigene Situation übernehmen.',
        transfer='Übertragung · ', title='Lernnotizen',
        fields={'Original': 'sentence', 'Bedeutung': 'meaning', 'Gebrauch': 'usage', 'Übertragung': 'transfer',
                'Meaning': 'meaning', 'Usage': 'usage', 'Transfer': 'transfer'},
        skip=('做视频', '选题规划', 'Video plan'),
        font="'Helvetica Neue',Arial,sans-serif"),
    'fr': dict(
        entries='{n} entrées', practice='Exercice de répétition', transcript='Texte original',
        tr_count='Chapitre complet · {n} répliques · EN-FR',
        tr_lead="Voici l'intégralité de cet extrait d'interview, dans l'ordre : l'anglais au-dessus, la traduction en dessous. Avant de répéter à voix haute, lisez d'abord l'anglais pour retrouver le ton, puis vérifiez la traduction pour repérer ce que vous avez manqué.",
        meta='{n} expressions · en « original → sens → usage → transfert »',
        lead="Ces notes rassemblent toutes les expressions de la vidéo en quatre niveaux : original, sens, usage et transfert. Conseil : lisez l'original pour retrouver le ton de la vidéo, puis l'usage, et enfin dites la phrase de transfert à voix haute. Les phrases avec · sont directement réutilisables dans votre propre contexte.",
        transfer='Transfert · ', title="Notes d'étude",
        fields={'Original': 'sentence', 'Sens': 'meaning', 'Usage': 'usage', 'Transfert': 'transfer',
                'Meaning': 'meaning', 'Transfer': 'transfer'},
        skip=('做视频', '选题规划', 'Video plan'),
        font="'Helvetica Neue',Arial,sans-serif"),
}


def labels(lang=None):
    return L.get(lang or LANG, L['zh'])


# ---------------------------------------------------------------- 解析
def parse(md_text, lang=None):
    """返回 [(章节标题, [条目, ...])]；条目 = {n, expr, time, sentence, meaning, usage, transfer}"""
    lb = labels(lang)
    fieldmap = lb['fields']
    sections, cur = [], None
    entry = None
    for raw in md_text.split('\n'):
        line = raw.rstrip()
        if line.startswith('## '):
            title = line[3:].strip()
            if any(k in title for k in lb['skip']):
                cur, entry = None, None
                continue
            cur = (title, [])
            sections.append(cur)
            entry = None
            continue
        if not cur or not line.strip():
            continue
        m = re.match(r'^\*\*(\d+)\.\s*(.+?)\*\*\s*[｜|]\s*(.+?)$', line)
        if m:
            entry = {'n': m.group(1), 'expr': m.group(2).strip(), 'time': m.group(3).strip(),
                     'sentence': '', 'meaning': '', 'usage': '', 'transfer': ''}
            cur[1].append(entry)
            continue
        if entry is None:
            continue
        key = next((v for k, v in fieldmap.items()
                    if line.startswith(k + '：') or line.lower().startswith(k.lower() + ': ')), None)
        if key:
            sep = '：' if '：' in line else ':'
            entry[key] = line.split(sep, 1)[1].strip()
        else:
            for k in ('transfer', 'usage', 'meaning', 'sentence'):
                if entry[k]:
                    entry[k] += ' ' + line.strip()
                    break
    return sections


def _split_row(line):
    f = [x.strip() for x in re.split(r'[｜|]', line)]
    return f if len(f) >= 4 else None


def parse_transcript(path):
    """原声对照：每行 `mm:ss｜说话人｜英文｜译文`；`#` 开头与空行跳过。"""
    rows = []
    for raw in path.read_text(encoding='utf-8').split('\n'):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        f = _split_row(line)
        if not f:
            continue
        rows.append(dict(time=f[0], who=f[1], en=f[2], tr='｜'.join(f[3:])))
    return rows


def find_transcript(md_path):
    for suffix in ('.原声对照.txt', '.transcript.txt'):
        p = md_path.with_name(md_path.stem + suffix)
        if p.exists():
            return p
    return None


# ---------------------------------------------------------------- 排版
def logo_b64():
    if not LOGO:
        return ''
    try:
        from PIL import Image
        im = Image.open(LOGO).convert('RGB').resize((160, 160), Image.LANCZOS)
        b = BytesIO()
        im.save(b, 'PNG')
        return 'data:image/png;base64,' + base64.b64encode(b.getvalue()).decode()
    except Exception:
        return ''


def md_inline(s):
    s = html.escape(s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'`(.+?)`', r'<code>\1</code>', s)
    s = re.sub(r'~~(.+?)~~', r'<del>\1</del>', s)
    return s


CSS = """
@page { size: A4; margin: 16mm 14mm 14mm; }
* { box-sizing: border-box; }
body { margin:0; font-family:__FONT__;
       color:#191918; background:#fff; font-size:10.5pt; line-height:1.55; }
code { font-family:'SF Mono','Menlo',monospace; font-size:0.94em; background:#F1F5F2;
       color:#0A7A47; padding:0.5px 4px; border-radius:3px; }
.hdr { display:flex; align-items:center; gap:10px; padding-bottom:8px; border-bottom:2.5px solid #2DCE7B; }
.hdr img { width:34px; height:34px; border-radius:8px; }
.hdr .b { font-size:11pt; font-weight:600; letter-spacing:.5px; }
.hdr .r { margin-left:auto; font-size:9pt; color:#7D7E7B; }
h1 { font-size:19pt; margin:14px 0 4px; letter-spacing:.5px; }
.sub { color:#7D7E7B; font-size:10pt; margin-bottom:2px; }
.meta { color:#7D7E7B; font-size:9pt; margin-bottom:14px; }
.lead { background:#F4F8F5; border-left:3px solid #2DCE7B; padding:8px 11px;
        font-size:9.5pt; color:#3c4a41; margin-bottom:16px; }
h2 { font-size:12.5pt; margin:20px 0 8px; padding-left:9px; border-left:4px solid #0A7A47;
     page-break-after:avoid; }
h2 .cnt { font-size:9pt; color:#7D7E7B; font-weight:400; margin-left:6px; }
.e { margin:0 0 9px; padding-left:11px; border-left:2px solid #E1E1DC; page-break-inside:avoid; }
.e .t { font-weight:600; font-size:10.5pt; }
.e .t .n { color:#7D7E7B; font-weight:400; margin-right:4px; }
.e .t .time { float:right; color:#0A7A47; font-size:8.5pt; font-weight:400; }
.e .en { color:#0A7A47; font-size:10pt; margin-top:1px; }
.e .cn { color:#4a4a48; font-size:9.5pt; }
.e .use { color:#5d5d5b; font-size:9.5pt; margin-top:2px; }
.e .mig { font-size:9.5pt; margin-top:2px; color:#3c4a41; }
.e .mig::before { content:'__TRANSFER__'; color:#12A45E; font-weight:600; }
.tip { margin:0 0 7px; padding-left:11px; border-left:2px solid #E1E1DC; font-size:9.5pt;
       color:#3c4a41; page-break-inside:avoid; }
.tr { margin:0 0 7px; padding-left:11px; border-left:2px solid #E1E1DC; page-break-inside:avoid; }
.tr .h { font-size:8.5pt; color:#7D7E7B; }
.tr .h .who { color:#0A7A47; font-weight:600; margin-left:7px; }
.tr .en { color:#0A7A47; font-size:10pt; margin-top:1px; }
.tr .cn { color:#4a4a48; font-size:9.5pt; }
.prac { background:#F4F8F5; border-radius:6px; padding:10px 13px; margin-top:8px;
        font-size:10pt; page-break-inside:avoid; }
.prac div { margin:3px 0; }
.ftr { margin-top:18px; padding-top:8px; border-top:1px solid #E1E1DC;
       color:#7D7E7B; font-size:8.5pt; display:flex; }
.ftr span:last-child { margin-left:auto; }
"""


def build_html(sections, title, sub, meta, lead, practice, practice_note='', transcript=None, lang=None):
    lb = labels(lang)
    css = CSS.replace('__FONT__', lb['font']).replace('__TRANSFER__', lb['transfer'])
    parts = []
    for stitle, entries in sections:
        if not entries:
            continue
        parts.append(f'<h2>{md_inline(stitle)}<span class="cnt">{lb["entries"].format(n=len(entries))}</span></h2>')
        for e in entries:
            rows = []
            if e['sentence']:
                rows.append(f'<div class="en">{md_inline(e["sentence"])}</div>')
            if e['meaning']:
                rows.append(f'<div class="cn">{md_inline(e["meaning"])}</div>')
            if e['usage']:
                rows.append(f'<div class="use">{md_inline(e["usage"])}</div>')
            if e['transfer']:
                rows.append(f'<div class="mig">{md_inline(e["transfer"])}</div>')
            parts.append(
                f'<div class="e"><div class="t"><span class="n">{e["n"]}.</span>{md_inline(e["expr"])}'
                f'<span class="time">{md_inline(e["time"])}</span></div>{"".join(rows)}</div>')
    prac = ''
    if practice:
        items = ''.join(f'<div>{md_inline(x)}</div>' for x in practice)
        note = f'<span class="cnt">{html.escape(practice_note)}</span>' if practice_note else ''
        prac = f'<h2>{lb["practice"]}{note}</h2><div class="prac">{items}</div>'
    tr = ''
    if transcript:
        rows = ''.join(
            f'<div class="tr"><div class="h">{md_inline(r["time"])}'
            f'<span class="who">{md_inline(r["who"])}</span></div>'
            f'<div class="en">{md_inline(r["en"])}</div>'
            f'<div class="cn">{md_inline(r["tr"])}</div></div>' for r in transcript)
        tr = (f'<h2>{lb["transcript"]}<span class="cnt">{lb["tr_count"].format(n=len(transcript))}</span></h2>'
              f'<div class="tip">{html.escape(lb["tr_lead"])}</div>{rows}')
    head = ''
    if BRAND or logo_b64():
        head = (f'<div class="hdr"><img src="{logo_b64()}" alt=""><span class="b">{html.escape(BRAND)}</span>'
                f'<span class="r">{html.escape(TAGLINE)}</span></div>')
    foot = ''
    if BRAND or URL:
        foot = (f'<div class="ftr"><span>{html.escape(BRAND)}</span>'
                f'<span>{html.escape(URL)}</span></div>')
    return f"""<!doctype html><html lang="{lang or LANG}"><head><meta charset="utf-8">
<title>{html.escape(title)}</title><style>{css}</style></head><body>
{head}
<h1>{html.escape(title)}</h1><div class="sub">{html.escape(sub)}</div>
<div class="meta">{html.escape(meta)}</div>
<div class="lead">{md_inline(lead)}</div>
{''.join(parts)}{prac}{tr}
{foot}
</body></html>"""


def _arg(args, flag, default=None):
    if flag in args:
        i = args.index(flag)
        if i + 1 < len(args):
            return args[i + 1]
    return default


def main():
    args = sys.argv[1:]
    if len(args) < 2 or args[0].startswith('-'):
        print(__doc__)
        raise SystemExit(1)
    md_path = Path(args[0]).resolve()
    outdir = Path(args[1]).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    lang = _arg(args, '--lang', LANG)
    lb = labels(lang)
    title = _arg(args, '--title', lb['title'])
    sub = _arg(args, '--sub', '')
    practice_note = _arg(args, '--note', '')
    practice = []
    pf = _arg(args, '--practice')
    if pf:
        practice = [l.strip() for l in Path(pf).read_text(encoding='utf-8').split('\n') if l.strip()]

    sections = parse(md_path.read_text(encoding='utf-8'), lang)
    total = sum(len(e) for _, e in sections)
    tr_path = find_transcript(md_path)
    transcript = parse_transcript(tr_path) if tr_path else []
    meta = lb['meta'].format(n=total)
    lead = lb['lead']

    html_path = outdir / (md_path.stem + '.html')
    html_path.write_text(build_html(sections, title, sub, meta, lead, practice,
                                    practice_note, transcript, lang), encoding='utf-8')
    pdf_path = outdir / (re.sub(r'[^\w\u4e00-\u9fa5-]+', '_', title) + '.pdf')
    sp.run([CHROME, '--headless', '--no-sandbox', '--disable-gpu',
            f'--user-data-dir={CFG.get("CHROME_PROFILE", "/tmp/chrome-lesson")}',
            '--disable-dev-shm-usage', '--no-pdf-header-footer',
            f'--print-to-pdf={pdf_path}', html_path.as_uri()], check=True,
           stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    print(f'HTML: {html_path}')
    print(f'PDF : {pdf_path}  ({pdf_path.stat().st_size / 1024:.0f} KB)')
    print(f'entries {total}, sections {len([1 for _, e in sections if e])}, lang {lang}')
    if transcript:
        print(f'transcript: {tr_path.name}, {len(transcript)} lines')


if __name__ == '__main__':
    main()
