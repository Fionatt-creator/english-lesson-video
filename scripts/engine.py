"""English Lesson Video · 通用渲染引擎（1080×1920 / 9:16）

把一个长访谈切成若干「表达」，每条做成：卡面 → 旁白（母语讲解 + 英文原句）→ 原声回放。
所有路径、品牌、密钥从 config.env 读；选题从 <LESSON_HOME>/specs/*.py 读。

用法：
    python3 engine.py                 # 渲染 specs/ 下全部选题
    python3 engine.py my_topic        # 只渲染一个
"""

from pathlib import Path
import subprocess as sp, json, hashlib, os, sys, time
from urllib.parse import quote
try:
    import requests
except ImportError:      # 只有合成旁白才需要
    requests = None
from PIL import Image, ImageDraw, ImageFont

# ============================== 配置 ==============================
# 所有路径、品牌、密钥都从 config.env 读；环境变量优先级最高。
# 顺序：$LESSON_CONFIG → <skill>/config.env → ~/.config/english-lesson-video/config.env
def _load_cfg():
    import os as _os
    here = Path(__file__).resolve().parent
    cands = []
    if _os.environ.get('LESSON_CONFIG'):
        cands.append(Path(_os.environ['LESSON_CONFIG']).expanduser())
    cands += [here.parent / 'config.env',
              Path.home() / '.config' / 'english-lesson-video' / 'config.env']
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
    for k, v in _os.environ.items():
        if k.startswith(('LESSON_', 'ELEVENLABS_', 'BRAND_')) or k in (
                'NATIVE_LANG', 'SOURCE_VIDEO', 'SPECS_DIR', 'OUTPUT_SPEED', 'EN_SLOW',
                'ASR_MODEL', 'CHROME_PATH'):
            cfg[k] = v
    return cfg


CFG = _load_cfg()

BASE = Path(__file__).resolve().parent                      # scripts/
SERIES = Path(CFG.get('LESSON_HOME') or Path.cwd()).expanduser().resolve()
DEFAULT_SRC = CFG.get('SOURCE_VIDEO', '')
SRC = DEFAULT_SRC   # 当前正在渲染的选题所用素材；render() 会按选题覆盖


def topic_dir(name):
    """选题目录。先按 `<SERIES>/<选题>` 找；找不到就在系列下按「序号_选题名」匹配，
    最多向下钻两层（兼容按集分目录的归档方式）。都找不到就返回 `<SERIES>/<选题>`，
    渲染时会把目录建出来。engine / covers / make_srt 都走这里，避免各写一套路径。"""
    if not SERIES.is_dir():
        raise SystemExit(f'LESSON_HOME 不存在：{SERIES}（在 config.env 里设置）')
    d = SERIES/name
    if d.is_dir():
        return d
    for p in sorted(SERIES.iterdir()):
        if p.is_dir() and p.name.endswith('_'+name):
            return p
    for sub in sorted(SERIES.iterdir()):
        if not sub.is_dir() or sub.name.startswith(('.', '_')):
            continue
        for mid in sorted(sub.iterdir()):
            if mid.is_dir() and mid.name.endswith('_'+name):
                return mid
    return d

# ---- 画布（1080×1920；上下留白：上 190px，下 417px 避让小红书 UI）----
W, H = 1080, 1920
CHIP_R = 18
TITLE_Y = 318
DIV1_Y, DIV2_Y = 424, 1408
PIP_W, PIP_H, PIP_Y = 810, 456, 470      # 原片画中画（16:9），水平位置由样式的 pip_x 给
BRAND_CY = 1470
LOGO_H = 66
BRAND_NAME = CFG.get('BRAND_NAME', '')
BRAND_URL = CFG.get('BRAND_URL', '')
TAGLINE = CFG.get('BRAND_TAGLINE', '')
# 页脚右侧那行小字：新版**整条页脚都不要**（原先是 logo + 品牌名 + 官网链接，
# 链接被小红书判成站外引流而限流）。去掉页脚连同底部分隔线，下半区全部让给正文：
# 正文下沿从 1380 延到 **1470**（1503 是小红色 UI 安全线，不能再往下压）。
# 已发布的老片在 SPEC 里写 'foot': True 锁住原样（'url' 再决定页脚里放不放官网链接）。
BRAND_TAIL = CFG.get('BRAND_TAGLINE', '')   # 只在老片回放时用得到
SHOW_FOOT = False       # render() 会按选题覆盖（SPEC 的 'foot'）
SHOW_URL = False        # render() 会按选题覆盖（SPEC 的 'url'）
LOGO_SRC = CFG.get('LESSON_LOGO', '')

# ---- 样式预设 ----
# v2（默认，2026-09 起）：深色内容区 + 左右留白 120px。
#     原因：小红书官方按钮是白色，浅底上按钮与画面糊在一起；且视频被缩放显示后，
#     72px 的留白在手机上只剩约 5.6% 屏宽，显得贴边。
# v1（2026-09 之前做的四条）：浅色内容区 + 留白 72px。只为复现旧片保留，新片一律用 v2。
STYLES = {
    'v2': dict(bg='#191918', fg='#F7F7F5', mute='#9A9B98',
               green='#2DCE7B', green2='#6FE3A8', brand='#2DCE7B', line='#33342F',
               surface='#242421', on_brand='#191918', logo_mode='mark', foot_layout='left',
               side=120, pip_x=135),
    'v1': dict(bg='#F7F7F5', fg='#191918', mute='#7D7E7B',
               green='#0A7A47', green2='#12A45E', brand='#2DCE7B', line='#E1E1DC',
               surface='#FFFFFF', on_brand='#191918', logo_mode='badge', foot_layout='split',
               side=72, pip_x=135),
}
DEFAULT_STYLE = 'v2'


def apply_style(name=DEFAULT_STYLE):
    """把样式预设铺到模块全局，card() / render() / covers.py 直接读这些全局。"""
    global BG, FG, MUTE, GREEN, GREEN2, BRAND, LINE, SURFACE, SIDE, RIGHT, CHIP, PIP_X
    global ON_BRAND, LOGO_MODE, FOOT_LAYOUT, STYLE
    s = STYLES[name]; STYLE = name
    BG, FG, MUTE = s['bg'], s['fg'], s['mute']
    GREEN, GREEN2, BRAND, LINE, SURFACE = s['green'], s['green2'], s['brand'], s['line'], s['surface']
    SIDE, RIGHT = s['side'], W - s['side']
    CHIP = (SIDE, 190, SIDE + 200, 250)
    PIP_X = s['pip_x']
    ON_BRAND, LOGO_MODE, FOOT_LAYOUT = s['on_brand'], s['logo_mode'], s['foot_layout']


apply_style()

CN = '/System/Library/Fonts/STHeiti Medium.ttc'
EN = '/System/Library/Fonts/HelveticaNeue.ttc'
CN_IDX = EN_IDX = 0        # .ttc 里的字面序号；.ttf 一律 0

# ---- 字体预设（跟样式预设一个思路：换了字体，旧片至少还能按原字体重渲）----
# heiti：2026-09 之前做的片子（黑体 + Helvetica Neue）
# song ：2026-09 起的新片（宋体 + Arial 斜体）。Songti.ttc 里 0=Black 1=Bold 3=Light 6=Regular
FONTS = {
    'heiti': ('/System/Library/Fonts/STHeiti Medium.ttc',
              '/System/Library/Fonts/HelveticaNeue.ttc', 0, 0),
    'song': ('/System/Library/Fonts/Supplemental/Songti.ttc',
             '/System/Library/Fonts/Supplemental/Arial Italic.ttf', 1, 0),
}
DEFAULT_FONTS = 'song'   # 新片默认（2026-09 起）；老片在 SPEC 里显式写 'fonts': 'heiti'
FONTSET = DEFAULT_FONTS
# 页脚网址这类界面元素用的西文字体：不跟着正文字体走，Arial 斜体的网址看着不对
EN_UI = '/System/Library/Fonts/HelveticaNeue.ttc'


def apply_fonts(name=DEFAULT_FONTS):
    global CN, EN, CN_IDX, EN_IDX, FONTSET
    CN, EN, CN_IDX, EN_IDX = FONTS[name]
    FONTSET = name


apply_fonts()

# ---- 多语言 ----
# 旁白/笔记的「母语」可以是 zh/ja/ko/pt/es/de/fr；英文原句始终用英文斜体字体。
# 字体全部取 macOS 自带，不需要额外安装。
LANG_PROFILES = {
    'zh': dict(font='/System/Library/Fonts/Supplemental/Songti.ttc', idx=1),
    'ja': dict(font='/System/Library/Fonts/Hiragino Sans GB.ttc', idx=0),
    'ko': dict(font='/System/Library/Fonts/AppleSDGothicNeo.ttc', idx=0),
    'pt': dict(font='/System/Library/Fonts/HelveticaNeue.ttc', idx=0),
    'es': dict(font='/System/Library/Fonts/HelveticaNeue.ttc', idx=0),
    'de': dict(font='/System/Library/Fonts/HelveticaNeue.ttc', idx=0),
    'fr': dict(font='/System/Library/Fonts/HelveticaNeue.ttc', idx=0),
}
CJK_LANGS = ('zh', 'ja', 'ko')
LATIN_LANGS = ('pt', 'es', 'de', 'fr')
DEFAULT_LANG = CFG.get('NATIVE_LANG', 'zh')
TARGET_LANG = DEFAULT_LANG


def apply_lang(code=DEFAULT_LANG):
    """切换母语：影响非英文文字的字体、字幕断行与默认音色。"""
    global TARGET_LANG
    if code not in LANG_PROFILES:
        raise SystemExit(f'不支持的母语：{code}（可选 {", ".join(LANG_PROFILES)}）')
    TARGET_LANG = code


DEFAULT_VOICE = CFG.get('ELEVENLABS_VOICE_ID', '')
# 按母语选音色：留空则回落到 DEFAULT_VOICE（要求该音色是多语的）
VOICES = {k: CFG.get('ELEVENLABS_VOICE_' + k.upper(), '') for k in LANG_PROFILES}


def voice_for(lang):
    return VOICES.get(lang) or DEFAULT_VOICE
VOICE = DEFAULT_VOICE    # 当前音色；render() 会按选题覆盖（SPEC 里可写 'voice': '<id>'）
DEFAULT_MODEL = CFG.get('ELEVENLABS_MODEL', 'eleven_v3')
MODEL = DEFAULT_MODEL    # 当前模型；同样可按选题覆盖（老片写 'model': LEGACY_MODEL）
# 新片默认音色参数。⚠️ v3 不支持 speed，所以这里不带 speed（老片用 LEGACY_VOICE_SETTINGS）
DEFAULT_VOICE_SETTINGS = {'stability': 0.45, 'similarity_boost': 0.75, 'style': 0.4, 'use_speaker_boost': True}
VOICE_SETTINGS = DEFAULT_VOICE_SETTINGS   # 当前音色参数；render() 会按选题覆盖
# 2026-09 之前那批片子用的（v2 模型 + style 0 + 带 speed）：只在老片 SPEC 里显式引用，不要当默认
LEGACY_MODEL = 'eleven_multilingual_v2'
LEGACY_VOICE_SETTINGS = {'stability': 0.45, 'similarity_boost': 0.75, 'style': 0.0,
                         'use_speaker_boost': True, 'speed': 1.0}
DEFAULT_EN_SLOW = float(CFG.get('EN_SLOW', 0.8))   # 英文旁白放慢倍数；母语保持原速
EN_SLOW = DEFAULT_EN_SLOW   # 可按选题覆盖（'en_slow': 1.0 表示英文也不变速）
DEFAULT_SPEED = float(CFG.get('OUTPUT_SPEED', 1.2))   # 整体倍速：旁白 atempo，段长等比缩短
SPEED = DEFAULT_SPEED   # 可按选题覆盖（老片写 'speed': 1.0 锁原速）
DEFAULT_SPEED_SRC = 1.0 # 访谈原声的倍速：不动——英文本就是学习材料，且英文旁白特意放到 0.8 倍教发音
SPEED_SRC = DEFAULT_SPEED_SRC   # 想让原声一起快，SPEC 里写 'speed_src': 1.2
PART_GAP = 0.22   # 中英分段之间的停顿

# ---- 字幕（带字幕版才启用，SPEC 里写 'subs': True）----
# 位置在画面中下方：放正中间会挡住访谈画面里说话人的表情和手势；
# 贴到底部分隔线又只剩二十几像素，还离小红书底部 UI 太近。
# 具体高度不能拍脑袋——各卡文字位置不一样，SPEC 里可以用 'sub_cy' 覆写，
# 加字幕前先用流程第 5 步的检测脚本，在这个区间里找一条整条空带。
SUB_FS = 40          # 字幕字号
SUB_CY_DEFAULT = 1282   # 字幕中心线默认值
SUB_CY = SUB_CY_DEFAULT
SUB_MAXW = 800       # 单行最大宽度（内容区 840，两侧各留 20）
SUB_BAND = 80        # 字幕条高度：只渲染这一窄条透明 PNG 再叠上去，不搬整张 1080×1920
SUB_TOP = SUB_CY - SUB_BAND // 2   # 字幕条在画面里的位置
SUB_FILL, SUB_STROKE = '#FFFFFF', '#000000'   # 白字 + 1px 黑描边
# 断行处：中文只认标点（认空格的话「2 分 5 秒」会被切成「分 5」这种碎条），
# 英文再加上空格，好在词与词之间断。
SUB_BREAK_ZH = '，。、；：？！…—,.;:?!'
SUB_BREAK_EN = SUB_BREAK_ZH + ' '


def load_key():
    if CFG.get('ELEVENLABS_API_KEY'):
        return CFG['ELEVENLABS_API_KEY']
    for p in [BASE/'.env.elevenlabs', SERIES/'.env.elevenlabs', Path.home()/'.config'/'english-lesson-video'/'config.env']:
        if p.exists():
            for line in p.read_text().splitlines():
                if '=' in line and not line.lstrip().startswith('#'):
                    k, v = line.split('=', 1)
                    if k.strip() == 'ELEVENLABS_API_KEY' and v.strip().strip('"\''):
                        return v.strip().strip('"\'')
    raise SystemExit('未找到 ELEVENLABS_API_KEY：请复制 config.example.env 为 config.env 并填写')


_SESSION = None
HOST = 'https://api.elevenlabs.io/v1/'


def session():
    global _SESSION
    if requests is None:
        raise SystemExit('缺少 requests：请先 pip3 install requests（只有渲染视频才需要）')
    if _SESSION is None:
        _SESSION = requests.Session()
        _SESSION.headers.update({'xi-api-key': load_key()})
    return _SESSION


def request(method, path, **kwargs):
    try:
        r = session().request(method, HOST+path, timeout=120, **kwargs)
    except requests.RequestException as e:
        raise SystemExit('网络请求未完成：'+type(e).__name__)
    if not r.ok:
        try:
            d = r.json().get('detail', {})
            status = d.get('status', 'unknown') if isinstance(d, dict) else 'request_error'
        except Exception:
            status = 'unknown'
        raise SystemExit(f'ElevenLabs HTTP {r.status_code}; status={status}')
    return r


def tts(text, target, tries=4, voice=None):
    voice = voice or VOICE
    sig = target.with_suffix('.sha256')
    payload = {'text': text, 'model_id': MODEL, 'voice_settings': VOICE_SETTINGS}
    signature = hashlib.sha256((voice+json.dumps(payload, ensure_ascii=False)).encode()).hexdigest()
    if not (target.exists() and sig.exists() and sig.read_text() == signature):
        # 实测会偶发 SSL 中断 / 极短的错误响应，一次抖动就能中断整片（缓存按签名命中，重跑不用重合成）。
        for i in range(tries):
            err = None
            try:
                r = request('POST', 'text-to-speech/'+quote(voice, safe=''), params={'output_format': 'mp3_44100_128'}, json=payload)
                if len(r.content) >= 1000:
                    break
                err = f'响应过短（{len(r.content)} 字节）'
            except SystemExit as e:
                err = str(e)
            if i == tries-1:
                raise SystemExit(f'TTS 连续 {tries} 次失败，停止。最后一次：{err}')
            print(f'  {target.stem} 第 {i+1} 次失败（{err}），重试…', flush=True)
            time.sleep(2 * (i+1))
        target.write_bytes(r.content)
        sig.write_text(signature)
    return target


def speech(name, parts):
    """逐段合成：中文原速，英文按 EN_SLOW 放慢，再拼接成整段旁白。

    合成前先把相邻的同语种片段合并。原来是「中文碎句 + 英文 + 中文碎句」逐段送 TTS，
    每段中文都是半句话，TTS 按句子给语调，半句的语调必然不对（听感就是中文很怪）。
    合并后中文回到完整句子，英文仍然只对 en 段做 atempo，两边都不受影响。
    """
    merged = []
    for lang, t in parts:
        if merged and merged[-1][0] == lang:
            merged[-1] = (lang, merged[-1][1] + t)
        else:
            merged.append((lang, t))
    files = []
    for i, (lang, t) in enumerate(merged):
        mp3 = tts(t, OUT/f'{name}_{i}.mp3', voice=voice_for(lang))
        af = 'loudnorm=I=-18:TP=-1.5:LRA=11'
        if lang == 'en':
            af += f',atempo={EN_SLOW}'      # 英文先按 EN_SLOW 放慢
        if SPEED != 1.0:
            af += f',atempo={SPEED}'        # 再整体提速（1.2 倍速版就是这里起作用）
        # ElevenLabs 有时会返回带 2–3 秒尾部静音的短片段（实测一条片子里 106 片有 7 片，
        # 合计 17 秒干等），直接拼进来会出现半句之间停两秒半。反向后掐头＝掐尾。
        # ⚠️ start_duration 是「要看到多长的连续有声才停止掐」，不是「只掐超过多久的静音」：
        #    取 0.35 会把最后 0.4 秒的语音一起削掉（听感就是中文末字被吞、然后直接进英文）。
        #    取 0.05 且阈值放到 -55dB，实测与真实语音末尾只差 0.05 秒，而那 0.05 秒本就低于 -45dB。
        af += ',areverse,silenceremove=start_periods=1:start_duration=0.05:start_threshold=-55dB,areverse'
        af += f',apad=pad_dur={PART_GAP}'
        w = OUT/f'{name}_{i}.wav'
        sp.run(['ffmpeg', '-y', '-v', 'error', '-i', str(mp3), '-af', af, '-ar', '48000', '-ac', '2', str(w)], check=True)
        files.append(w)
    out = OUT/f'{name}.wav'
    if len(files) == 1:
        sp.run(['ffmpeg', '-y', '-v', 'error', '-i', str(files[0]), '-c:a', 'pcm_s16le', str(out)], check=True)
    else:
        lst = OUT/f'{name}_parts.txt'
        lst.write_text(''.join(f"file '{p}'\n" for p in files))
        sp.run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(lst), '-c:a', 'pcm_s16le', str(out)], check=True)
    print(name, '配音就绪', flush=True)
    # info = 每段的（语种, 文本, 时长），给字幕算时间轴用；时长含尾部 PART_GAP 的静音
    return out, [(lang, t, duration(w)) for (lang, t), w in zip(merged, files)]


def run(args):
    sp.run(args, check=True, stdout=sp.DEVNULL, stderr=sp.PIPE)


def duration(p):
    return float(sp.check_output(['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(p)]))


def font(size, en=False, lang=None):
    """en=True 取英文斜体；lang 指定某语言字体；不给就用当前母语。"""
    if en:
        return ImageFont.truetype(EN, size, index=EN_IDX)
    code = lang or TARGET_LANG
    if code == 'zh':
        return ImageFont.truetype(CN, size, index=CN_IDX)
    p = LANG_PROFILES.get(code, LANG_PROFILES['zh'])
    if p is LANG_PROFILES['zh']:
        return ImageFont.truetype(CN, size, index=CN_IDX)
    return ImageFont.truetype(p['font'], size, index=p['idx'])


def ui_font(size):
    """界面元素用的西文字体（页脚网址）：固定 Helvetica Neue，不随正文字体预设变。"""
    return ImageFont.truetype(EN_UI, size)


def ui_w(s, size):
    return ui_font(size).getlength(s)


def text_ui_mid(d, x, cy, s, size, color):
    """网址这类界面元素：固定西文字体 + 垂直居中（不跟着 Arial 斜体走）。"""
    f = ui_font(size)
    asc, desc = f.getmetrics()
    d.text((x, cy-(asc+desc)//2), s, font=f, fill=color)


def C(role):
    """颜色角色 → 当前样式的实际颜色。
    SPECS 里只写 'fg' / 'green' 这类角色名，不写十六进制，否则会在 import 时
    被绑定到某个样式上（旧片用 v1、新片用 v2，同一份 SPEC 要能两边都对）。"""
    return {'fg': FG, 'green': GREEN, 'green2': GREEN2, 'mute': MUTE, 'brand': BRAND}.get(role, role)


def text(d, xy, s, size=38, color=None, en=False):
    d.text(xy, s, font=font(size, en), fill=color or FG)


def text_r(d, right_x, y, s, size=38, color=None, en=False):
    d.text((right_x-font(size, en).getlength(s), y), s, font=font(size, en), fill=color or FG)


def text_mid(d, left_x, cy, s, size=38, color=None, en=False):
    f = font(size, en)
    asc, desc = f.getmetrics()
    d.text((left_x, cy-(asc+desc)//2), s, font=f, fill=color or FG)


_logo = None
_logo_mode = None


def logo_rgba():
    """logo 原图是「深色圆角方徽 + 白色图形」，外圈纯黑是画布底（一律抠掉）。
    badge 模式（浅底）：连徽章本体一起保留；mark 模式（深底）：只留白色图形，
    因为徽章的深色在深底上看不见、只会留一圈若有若无的方边。"""
    global _logo, _logo_mode
    if _logo is None or _logo_mode != LOGO_MODE:
        im = Image.open(LOGO_SRC).convert('RGB')
        if LOGO_MODE == 'mark':     # 深色→透明，白色→不透明
            a = im.convert('L').point(lambda v: 0 if v <= 40 else (255 if v >= 190 else round((v-40)*255/150)))
        else:                        # 只抠掉外圈纯黑画布，徽章保留
            a = im.convert('L').point(lambda v: 0 if v <= 10 else (255 if v >= 26 else round((v-10)*255/16)))
        im = im.convert('RGBA')
        im.putalpha(a)
        _logo = im.resize((round(im.width*LOGO_H/im.height), LOGO_H), Image.LANCZOS)
        _logo_mode = LOGO_MODE
    return _logo


def card(n, title, lines, still=None):
    im = Image.new('RGB', (W, H), BG); d = ImageDraw.Draw(im)
    d.rounded_rectangle(CHIP, radius=CHIP_R, fill=BRAND)
    if BRAND_NAME:
        text_mid(d, CHIP[0]+20, (CHIP[1]+CHIP[3])//2, BRAND_NAME, 36, ON_BRAND)
    if TAGLINE:
        text_r(d, RIGHT, 205, TAGLINE, 32, MUTE)
    ts = 62                      # 标题过长时自动缩号，避免顶到右边界
    while ts > 34 and font(ts).getlength(title) > RIGHT-SIDE:
        ts -= 2
    text(d, (SIDE, TITLE_Y), title, ts)
    d.line((SIDE, DIV1_Y, RIGHT, DIV1_Y), fill=LINE, width=3)
    if still:   # 「先讲解、再听原声」的卡：讲解阶段用定格帧占住画中画位置，避免出现空洞
        im.paste(Image.open(still).convert('RGB'), (PIP_X, PIP_Y))
    for y, s, size, col, en in lines:
        text(d, (SIDE, y), s, size, C(col), en)
    # 页脚品牌条（只有老片画）：底部分隔线 + logo + 品牌名 + 右侧小字。
    # 新片整条不画，下半区让给正文（正文下沿 1380 → 1470）。
    if SHOW_FOOT:
        d.line((SIDE, DIV2_Y, RIGHT, DIV2_Y), fill=LINE, width=3)
        lg = logo_rgba()
        im.paste(lg, (SIDE, BRAND_CY-lg.height//2), lg)
        name_x = SIDE+lg.width+20
        text_mid(d, name_x, BRAND_CY, BRAND_NAME, 48, GREEN)
        tail_x = name_x + font(48).getlength(BRAND_NAME) + 24
        if SHOW_URL:
            if FOOT_LAYOUT != 'left':   # v1 浅色版：网址右对齐
                tail_x = RIGHT - ui_w(BRAND_URL, 32)
            text_ui_mid(d, tail_x, BRAND_CY, BRAND_URL, 32, MUTE)
        else:
            text_mid(d, tail_x, BRAND_CY, BRAND_TAIL, 30, MUTE)
    p = WORK/(n+'.png'); im.save(p); return p


def grab_still(start, name):
    """抽原声片段起点的那一帧，缩到画中画尺寸，给「先讲解」那段当占位。"""
    out = WORK/f'{name}_still.png'
    run(['ffmpeg', '-y', '-v', 'error', '-ss', str(start), '-i', SRC, '-frames:v', '1',
         '-vf', f'scale={PIP_W}:{PIP_H}', str(out)])
    return out


def wrap1(s, f, maxw, breaks):
    """按像素宽度把一句话切成若干条单行字幕，优先在标点/空格处断，免得断在半句中间。"""
    lines, cur = [], ''
    for ch in s:
        if f.getlength(cur + ch) <= maxw:
            cur += ch
            continue
        i = max(cur.rfind(p) for p in breaks)
        if i < len(cur) * 0.5:      # 断点太靠前（后半截会拖成长行）就不迁就标点
            i = cur.rfind(' ') if ' ' in breaks else -1
        if i <= 0:
            i = len(cur) - 1
        lines.append(cur[:i+1].strip())
        cur = cur[i+1:] + ch        # ch 就是触发换行的那个字，补到下一行开头
    if cur.strip():
        lines.append(cur.strip())
    return lines or ['']


def sub_cues(s, lang, dur):
    """一句话 → [(字幕条, 起, 止)]，时间按字数比例摊到这句的实际时长上。

    没有词级时间戳，只能按长度近似；但字幕是「边听边读」，宁可略早不可略晚，
    所以把尾部那次 PART_GAP 静音从可用时长里扣掉。"""
    latin = lang == 'en' or lang in LATIN_LANGS
    f = font(SUB_FS, lang == 'en', None if latin else lang)
    lines = []
    for l in wrap1(s, f, SUB_MAXW, SUB_BREAK_EN if latin else SUB_BREAK_ZH):
        # 中文句接在英文后面时，开头会挂一个逗号，显示时去掉
        lines.append(l.lstrip('，,。.、；;：: ') or l)
    scale = sum(len(l) for l in lines) or 1
    span = max(dur - PART_GAP, 0.6)
    t, cues = 0.0, []
    for i, l in enumerate(lines):
        d = span * len(l) / scale
        # 最后一条一直挂到本段末尾（含尾部那 0.22s 静音）：字幕停在上一句直到下一句出现，
        # 否则每段之间会闪断一下
        cues.append((l, t, dur if i == len(lines) - 1 else t + d))
        t += d
    return cues


def sub_png(name, s, lang):
    """把一条字幕画成透明 PNG（只画 SUB_BAND 高的一条）：白字 + 1px 黑描边，居中。"""
    im = Image.new('RGBA', (W, SUB_BAND), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = font(SUB_FS, lang == 'en', None if lang in ('en',) + LATIN_LANGS else lang)
    x0, y0, _, y1 = f.getbbox(s)
    d.text(((W - f.getlength(s)) / 2 - x0, SUB_BAND // 2 - (y0 + y1) / 2), s,
           font=f, fill=SUB_FILL, stroke_width=1, stroke_fill=SUB_STROKE)
    p = WORK/f'sub_{name}.png'
    im.save(p)
    return p


def src_sub_png(n, i, en, cn):
    """原声字幕：英文原句（Arial Italic，最多两行）+ 中文直译（宋体一行），
    透明窄条 PNG；返回 (PNG 路径, 叠放顶 y)——底沿固定在画中画内 y=916。"""
    f_en, f_cn = font(34, True), font(30, False)
    maxw = 1000
    en_lines = [en]
    if f_en.getlength(en) > maxw:
        words = en.split(' ')
        best, bl = None, 10 ** 9
        for k in range(2, len(words) - 1):
            a, b = ' '.join(words[:k]), ' '.join(words[k:])
            w = max(f_en.getlength(a), f_en.getlength(b))
            if w <= maxw and w < bl:
                best, bl = (a, b), w
        en_lines = list(best) if best else [en]
    hs = [46] * len(en_lines) + [44]
    h = 14 + sum(hs)
    im = Image.new('RGBA', (W, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    y = 7
    for ln in en_lines:
        x0, y0, _, y1 = f_en.getbbox(ln)
        d.text(((W - f_en.getlength(ln)) / 2 - x0, y + (46 - (y1 - y0)) / 2 - y0), ln,
               font=f_en, fill='#FFFFFF', stroke_width=2, stroke_fill='#000000')
        y += 46
    x0, y0, _, y1 = f_cn.getbbox(cn)
    d.text(((W - f_cn.getlength(cn)) / 2 - x0, y + (44 - (y1 - y0)) / 2 - y0), cn,
           font=f_cn, fill='#F0F0EC', stroke_width=2, stroke_fill='#000000')
    p = WORK / f'sub_{n}_src{i}.png'
    im.save(p)
    return p, 916 - h


def build_subs(n, info, card=None):
    """一段旁白（含中英分段）→ [(字幕 PNG, 叠放 y, 起, 止)]，时间轴相对本段视频。
    卡片可用 'sub_cy' 覆盖本卡字幕中心线（如把字幕叠进画中画窗口内）。"""
    sub_top = (card.get('sub_cy', SUB_CY) if card else SUB_CY) - SUB_BAND // 2
    subs, t = [], 0.0
    for i, (lang, txt, dur) in enumerate(info):
        for j, (s, a, b) in enumerate(sub_cues(txt, lang, dur)):
            subs.append((sub_png(f'{n}_{i}_{j}', s, lang), sub_top, t + a, t + b))
        t += dur + 0.001    # 每段错开 1ms：上一段末条挂到段尾，不错开的话边界那一帧会两条叠着画
    return subs


segments = []


def segment(n, img, aud=None, source=None, start=None, end=None, tail=0.35, subs=None):
    """subs = [(字幕 PNG, 叠放 y, 起, 止)]：按时间窗叠上去。
    必须叠在画中画之后——画中画是后贴的，先画在卡上会被它盖住。"""
    out = WORK/f'{n}.mp4'
    subs = subs or []
    if source:
        raw = end-start                    # 原声片段本身的长度（取素材用）
        dur = raw/SPEED_SRC                # 原声段在成片里占多长（SPEED_SRC=1 就是原速）
        args = ['ffmpeg', '-y', '-v', 'error', '-loop', '1', '-framerate', '30', '-i', str(img),
                '-ss', str(start), '-t', str(raw), '-i', SRC]
        if aud:
            args += ['-i', str(aud)]
        args += sum([['-loop', '1', '-framerate', '30', '-i', str(p)] for p, _, _, _ in subs], [])
        # 原声一起提速时，画面也得跟着 setpts，否则声画对不上、画面还会提前播完
        pts = f'setpts=PTS/{SPEED_SRC},' if SPEED_SRC != 1.0 else ''
        af_src = f'atempo={SPEED_SRC},' if SPEED_SRC != 1.0 else ''
        fc = f'[1:v]{pts}scale={PIP_W}:{PIP_H},setsar=1[v];[0:v][v]overlay={PIP_X}:{PIP_Y}:shortest=1[o0]'
        base = 3 if aud else 2       # 输入：0 卡面、1 原片、[2 旁白]、其后才是字幕
        for i, (_, py, t0, t1) in enumerate(subs):
            fc += f";[o{i}][{base+i}:v]overlay=0:{py}:enable='between(t,{t0:.2f},{t1:.2f})'[o{i+1}]"
        args += ['-filter_complex', fc,
                 '-map', f'[o{len(subs)}]', '-map', '2:a' if aud else '1:a']
    else:
        dur = duration(aud)+tail if aud else 1.0
        af_src = ''
        args = ['ffmpeg', '-y', '-v', 'error', '-loop', '1', '-framerate', '30', '-i', str(img)]
        if aud:
            args += ['-i', str(aud)]
        else:
            args += ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo']
        args += sum([['-loop', '1', '-framerate', '30', '-i', str(p)] for p, _, _, _ in subs], [])
        if subs:
            fc = ''
            for i, (_, py, t0, t1) in enumerate(subs):
                fc += (f"[0:v]" if i == 0 else f'[o{i}]')
                fc += f"[{2+i}:v]overlay=0:{py}:enable='between(t,{t0:.2f},{t1:.2f})'[o{i+1}];"
            args += ['-filter_complex', fc.rstrip(';'), '-map', f'[o{len(subs)}]', '-map', '1:a']
        else:
            args += ['-map', '0:v', '-map', '1:a']
    args += ['-af', af_src + 'apad,alimiter=limit=0.95', '-t', str(dur), '-r', '30', '-c:v', 'libx264', '-preset', 'fast',
             '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-ar', '48000', '-ac', '2',
             '-movflags', '+faststart', str(out)]
    run(args); segments.append((out, dur)); print(n, round(dur, 2), flush=True)

# ============================== 通用补丁 ==============================
PATCH = {}


def patch_cards(cards, patch=None):
    """按卡号覆盖原声区间 / 旁白 / 卡面文字（派生版用）。"""
    patch = PATCH if patch is None else patch
    return [dict(c, **patch[c['n']]) if c['n'] in patch else c for c in cards]


def render(name):
    global WORK, OUT, SRC, VOICE, VOICE_SETTINGS, SUB_CY, SUB_TOP, MODEL, EN_SLOW, SHOW_URL, SHOW_FOOT
    global SPEED, SPEED_SRC
    spec = SPECS[name]
    SHOW_FOOT = spec.get('foot', False)  # 页脚：新片一律不画，下半区让给正文
    SHOW_URL = spec.get('url', False)    # 页脚里要不要放官网链接（只有老片）
    SPEED = spec.get('speed', DEFAULT_SPEED)             # 整体倍速（旁白）
    SPEED_SRC = spec.get('speed_src', DEFAULT_SPEED_SRC)  # 原声倍速，默认原速
    apply_style(spec.get('style', DEFAULT_STYLE))   # 按选题套样式预设（新片默认 v2 深色）
    apply_fonts(spec.get('fonts', DEFAULT_FONTS))   # 字体预设同样按选题走
    apply_lang(spec.get('lang', DEFAULT_LANG))      # 母语：字体、断行、音色
    VOICE = spec.get('voice', DEFAULT_VOICE)        # 音色也可按选题覆盖
    MODEL = spec.get('model', DEFAULT_MODEL)        # 模型同理（v3 不支持 speed 参数，SPEC 里别写）
    VOICE_SETTINGS = spec.get('voice_settings', DEFAULT_VOICE_SETTINGS)
    EN_SLOW = spec.get('en_slow', DEFAULT_EN_SLOW)  # 英文变速倍数，1.0 = 不变速
    SUB_CY = spec.get('sub_cy', SUB_CY_DEFAULT)     # 字幕高度也按选题定（各卡文字位置不同）
    SUB_TOP = SUB_CY - SUB_BAND // 2
    global SRC
    SRC = spec.get('src', DEFAULT_SRC)
    # 中间产物目录默认跟选题同名；派生版（加字幕、换音色试听…）可以用 'work' 指到主片目录，
    # 这样直接复用已合成的旁白——TTS 不保证同文本同结果，重合成会让「只多了字幕」的对照组失真。
    WORK = SERIES/'work'/spec.get('work', name)
    WORK.mkdir(parents=True, exist_ok=True)
    OUT = WORK/'elevenlabs'
    OUT.mkdir(parents=True, exist_ok=True)
    dest = topic_dir(spec.get('out_dir', name))   # 一个选题一个文件夹；派生版可用 out_dir 落回主片目录
    dest.mkdir(parents=True, exist_ok=True)
    segments.clear()

    limit = spec.get('limit')       # 只要前 N 秒：做「试听版」用，渲到时长够了就停
    SUBS = spec.get('subs', False)  # 带字幕版：把讲解旁白打成单行字幕，压在画中画视频底部
    total = 0.0
    for c in spec['cards']:
        a, info = speech(c['n'], c['speech']) if c.get('speech') else (None, [])
        subs = build_subs(c['n'], info, c) if (SUBS and info) else []
        s = c.get('source')
        # 原声字幕（'subs_src' + 'src_subs'）：{卡号: [(绝对起, 绝对止, 英文, 中文), ...]}
        src_subs = spec.get('src_subs', {}).get(c['n']) if spec.get('subs_src') else None
        src_sub_list = None
        if s and src_subs:
            start0 = s[0]
            src_sub_list = []
            for i, (sa, sb, en, cn) in enumerate(src_subs):
                ra, rb = max(sa - start0, 0.0), min(sb - start0, s[1] - start0)
                if rb - ra > 0.15:
                    pp, py = src_sub_png(c['n'], i, en, cn)
                    src_sub_list.append((pp, py, ra, rb))
        if s and a:
            # 「先讲解、再听原声」：同一张卡拆两段——先用定格帧 + 旁白讲，再播原声
            start, end = s
            pa = card(c['n']+'_a', c['title'], c['lines'], still=grab_still(start, c['n']))
            segment(c['n']+'_a', pa, a, tail=0.25, subs=subs)
            pb = card(c['n']+'_b', c['title'], c['lines'])
            segment(c['n']+'_b', pb, source=True, start=start, end=end, subs=src_sub_list)
        elif s:
            start, end = s
            p = card(c['n'], c['title'], c['lines'])
            segment(c['n'], p, source=True, start=start, end=end, subs=src_sub_list)
        else:
            p = card(c['n'], c['title'], c['lines'])
            segment(c['n'], p, a, tail=c.get('tail', 0.35), subs=subs)
        total = sum(d for _, d in segments)
        if limit and total >= limit:
            print(f'  达到 {limit}s 上限，停在卡 {c["n"]}（累计 {total:.1f}s）', flush=True)
            break

    lst = WORK/'concat.txt'
    lst.write_text(''.join(f"file '{p}'\n" for p, d in segments))
    out = dest/f'{name}.mp4'
    # 注意：这块盘（云盘/外置卷）上 -movflags +faststart 会写失败，故不加
    run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(lst), '-c', 'copy', str(out)])
    (dest/f'{name}_说明.json').write_text(json.dumps({
        'output': str(out),
        'duration': duration(out),
        'canvas': f'{W}x{H} (9:16)',
        'voice_id': VOICE,
        'model': MODEL,
        'voice_settings': VOICE_SETTINGS,   # 记下来，否则换过参数就复现不了
        'en_slow': EN_SLOW,                 # 英文变速倍数（1.0 = 不放慢）
        'speed': SPEED,                     # 整体倍速：旁白 atempo，段长等比缩短
        'speed_src': SPEED_SRC,             # 访谈原声倍速（1.0 = 原速，默认不动）
        'subtitles': (f'讲解旁白字幕（白字 + 1px 黑描边，字号 {SUB_FS}，单行，中心线 y={SUB_CY}，'
                      f'画面中下方；原声片段不打字幕）' if SUBS else '无'),
        'source': SRC,
        'style': f'{STYLE}（{BG} 底，左右留白 {SIDE}px，页脚{FOOT_LAYOUT}对齐）',
        'fonts': f'{FONTSET}（中文 {CN.split("/")[-1]} 第 {CN_IDX} 号字面；西文 {EN.split("/")[-1]}'
                 + (f'；页脚网址固定 {EN_UI.split("/")[-1]}）' if (SHOW_FOOT and SHOW_URL) else '）'),
        'palette': {'底': BG, '主文字': FG, '次要文字': MUTE, '主强调': GREEN, '次强调': GREEN2,
                    '品牌绿原色': BRAND, '分隔线': LINE,
                    '来源': CFG.get('BRAND_NAME') or 'default palette'},
        'segments': [{'file': p.name, 'duration': d} for p, d in segments],
        'source_clips': [{'card': c['n'], 'start': c['source'][0], 'end': c['source'][1]}
                         for c in spec['cards'] if c.get('source')],
        'notes': [
            f'画布 {W}×{H}（9:16）；上留白 190px、下留白 417px，避开平台顶部/底部 UI。',
            '原片切点用本地语音识别逐词定位，并对切出片段二次识别复核。',
            f'画中画缩放到 {PIP_W}×{PIP_H}。',
            f'旁白使用 Voice ID {VOICE}（{MODEL}），母语 {TARGET_LANG}；'
            + (f'英文按 {EN_SLOW} 倍放慢。' if EN_SLOW != 1.0 else '英文原速。'),
            (f'整体倍速 {SPEED}（旁白 atempo；访谈原声 {SPEED_SRC} 倍）。' if SPEED != 1.0 or SPEED_SRC != 1.0
             else '整体原速（未做倍速）。'),
            f'左右留白 {SIDE}px。',
            '迁移例句为原创练习，非访谈原话。',
        ],
    }, ensure_ascii=False, indent=2))
    print('DONE', out, duration(out), flush=True)


# ============================== 选题装载 ==============================
# 每个选题一个 .py，放在 <LESSON_HOME>/specs/ 下。文件里给 SPEC（或 SPECS 字典）。
SPECS = {}
SPECS_DIR = Path(CFG.get('SPECS_DIR') or (SERIES / 'specs'))


def load_specs(path=None):
    d = Path(path) if path else SPECS_DIR
    if not d.is_dir():
        return SPECS
    for f in sorted(d.glob('*.py')):
        ns = {'__name__': f'lesson_spec_{f.stem}', 'Path': Path}
        exec(compile(f.read_text(encoding='utf-8'), str(f), 'exec'), ns)
        if 'SPEC' in ns:
            SPECS[ns.get('NAME') or f.stem] = ns['SPEC']
        for k, v in (ns.get('SPECS') or {}).items():
            SPECS[k] = v
    return SPECS


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__)
        return
    load_specs()
    names = [a for a in argv if not a.startswith('-')] or list(SPECS)
    for n in names:
        if n not in SPECS:
            raise SystemExit(f'没有这个选题：{n}（已有：{", ".join(SPECS) or "空"}）')
        render(n)


if __name__ == '__main__':
    main()
