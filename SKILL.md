---
name: english-lesson-video
description: Turn long interviews or podcasts into vertical English lesson videos with cards, narration, notes PDF and subtitles for any native language. Use for English teaching clips or shadowing lessons.
---

# English Lesson Video

把一段长访谈/播客切成若干「表达」，每条做成 9:16 精讲视频：**卡面 → 母语旁白 + 英文原句 → 原声回放**，
并产出封面、字幕、发帖文案、精讲笔记 PDF（可选整段原声逐句对照）。

学习者母语支持 `zh` `ja` `ko` `pt` `es` `de` `fr`。英文始终是被学的语言。

## 0. 首次配置

```bash
SKILL=~/.trae-cn/skills/english-lesson-video
cp $SKILL/config.example.env $SKILL/config.env
```

只改四类，其余留空即可：

| 变量 | 说明 |
|---|---|
| `ELEVENLABS_API_KEY` | 合成旁白用。只有渲染视频时需要，出稿/出 PDF 不需要 |
| `ELEVENLABS_VOICE_ID` | 多语种音色；要更地道再用 `ELEVENLABS_VOICE_<LANG>` 覆盖 |
| `LESSON_HOME` | 工作目录（自动建 `specs/`、`work/`、输出目录） |
| `SOURCE_VIDEO` | 源视频；单条选题可在 SPEC 里用 `src=` 覆盖 |

品牌四项（`BRAND_NAME` / `BRAND_URL` / `BRAND_TAGLINE` / `LESSON_LOGO`）可全空，空了就不画页眉页脚。

自检：

```bash
cd $SKILL/scripts && python3 engine.py --help
python3 -c "import engine as B; print(B.SERIES, B.TARGET_LANG, bool(B.DEFAULT_VOICE))"
```

**密钥规则**：脚本只从 `config.env` 或环境变量读 key；不要写进 SPEC、不要写进 md、不要提交到公开仓库。
给别人用的版本里只放 `config.example.env`。

## 1. 产出

一个选题固定四件：`<name>.mp4`、`cover.png`、`发帖文案.md`、`精讲笔记.pdf`（+ `<name>.srt`）。

## 2. 流程

| 步 | 做什么 | 命令 / 门槛 |
|---|---|---|
| 1 | 转写全片 | `python3 transcribe.py "$SOURCE_VIDEO"` |
| 2 | 切章 | `split_srt.py` → `fix_srt.py`；不切断句子，广告整段跳过 |
| 3 | 定原声切点 | ASR 词级起点 + 片段二次转写复核；`end` 留到尾音后 0.2–0.4s |
| 4 | 写 SPEC | `cp assets/spec-template.py "$LESSON_HOME/specs/01_x.py"` |
| 5 | 渲染 | `python3 engine.py 01_x`；先加 `'limit': 30` 看样 |
| 6 | 自检 | 1080×1920、文字不越 y=1500、原声不吞字、无长静音 |
| 7 | 字幕 | `python3 make_srt.py 01_x` |
| 8 | 封面 | `python3 covers.py 01_x [--text-only]` |
| 9 | 笔记 PDF | `python3 handout.py <md> <目录> --lang zh` |
| 10 | 交付 | 四件套 + 按平台写发帖文案 |

细节命令、自检方法与坑见 `references/workflow.md`；SPEC 字段见 `references/spec-format.md`；
语言/字体/音色/文案见 `references/languages.md`。

## 3. SPEC 最小示例

```python
NAME = '01_x'
SPEC = {
    'lang': 'zh',
    'cards': [
        dict(n='01', title='先听原句',
             lines=[(950, 'I stopped apologizing', 56, 'fg', True),
                    (1040, 'for wanting more.', 68, 'green', True),
                    (1220, '我不再为「想要更多」道歉。', 45, 'fg', False)],
             speech=[('zh', '注意 apologize for。'),
                     ('en', 'apologize for wanting more'),
                     ('zh', '为自己想要更多而道歉。')],
             source=(12.40, 15.90)),
    ],
}
```

`lines` 是 `(y, 文字, 字号, 颜色, 是否英文斜体)`；`speech` 里 `'en'` 会按 `EN_SLOW` 放慢，
其它语言按原速并用该语言音色；同时给 `source` 就是「先讲、再听原声」。

## 4. 内容硬规则

1. 一句一卡或一个句式一卡，卡面只放这卡要教的那点东西。
2. 英文行斜体、中文行正体；一行不混排两种语言。
3. 原声片段必须覆盖完整句子，宁可多留 0.3 秒。
4. 讲解用学习者母语，例句用英文；母语里不要夹英文术语（除非术语本身是教学点）。
5. 迁移例句必须是原创，不能把访谈原话改头换面当成自己的例句。
6. 原声卡不打讲解字幕；讲解卡开字幕时只打单行。
7. 每张卡旁白 8–25 秒；整条 45–90 秒。
8. 原字幕的转写错误照抄（做对照时），但译文按正确意思译。

## 5. 已知坑

- **无头 Chrome 退出码 2**：GUI Chrome 占着 profile。`handout.py` 已默认用独立 `--user-data-dir`；仍冲突时再加 `HOME=/tmp/chromehome`，但注意这会让 `~/Library/Python` 的包（PIL 等）找不到。
- **外置卷页数**：`mdls -kMDItemNumberOfPages` 常返回 null，用 `/Type /Page` 正则数。
- **`eleven_v3` 不接受 `speed`**：变速靠 `en_slow` 与后期 `speed`。
- **改音色要重渲**：缓存签名含 voice id，会自动失效，但整片要重跑。
- **云盘/外置卷**：`-movflags +faststart` 会写失败，引擎已不加。
- **素材版权**：分发/售卖时不要打包访谈原片、原字幕、成片；只交付方法与脚本。
- **字体**：全部取 macOS 自带；换机器先确认 `LANG_PROFILES` 里的路径存在。

## 6. 依赖

`ffmpeg` / `ffprobe`、`python3`、`Pillow`、`requests`、`faster-whisper`、Google Chrome（出 PDF）。
ElevenLabs key 只影响旁白合成。
