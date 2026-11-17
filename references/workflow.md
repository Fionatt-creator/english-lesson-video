# 完整工作流（10 步）

所有命令都在技能目录下执行：

```bash
SKILL=~/.trae-cn/skills/english-lesson-video
S=$SKILL/scripts
cp $SKILL/config.example.env $SKILL/config.env      # 只需一次
```

`LESSON_HOME` 是工作目录，脚本会自动建 `specs/`、`work/` 和每个选题的输出目录。

## 0. 自检

```bash
cd $S && python3 engine.py --help
python3 - <<'PY'
import engine as B
print('home   ', B.SERIES)
print('lang   ', B.TARGET_LANG)
print('voice  ', B.DEFAULT_VOICE or '(未配置)')
print('source ', B.DEFAULT_SRC or '(未配置)')
PY
```

`LESSON_HOME` 不存在会直接报错；密钥只在真正合成旁白时读取，所以纯看稿/出 PDF 不需要 key。

## 1. 转写与章节切分

```bash
python3 $S/transcribe.py "$SOURCE_VIDEO"          # 产出逐词 json / 粗略 srt
python3 $S/split_srt.py segments/whole.srt          # 按内容切章，不改句子
python3 $S/fix_srt.py segments/03-xxx.srt           # 修断行、合并被切开的句子
```

切章原则：不切断句子；遇到广告、串场、跑题整段跳过；一章 2–6 分钟。

## 2. 定位原声切点

- 用 ASR 的词级时间戳找句子真正的起点与尾音，不要按字幕块粗切。
- 切完把片段单独再转写一次，确认首尾都在句内。
- `source=(start, end)` 的 `end` 要留到最后一个词的尾音之后 0.2–0.4s。

## 3. 写 SPEC

复制模板：

```bash
cp $SKILL/assets/spec-template.py "$LESSON_HOME/specs/01_my_topic.py"
```

字段见 `references/spec-format.md`。一个选题 6–12 张卡最常见：开场 → 原句拆解 → 句式 → 迁移 → 跟读。

## 4. 渲染

```bash
cd $S && python3 engine.py 01_my_topic
```

- 成片在 `$LESSON_HOME/01_my_topic/01_my_topic.mp4`。
- 旁白 mp3 缓存在 `$LESSON_HOME/work/<name>/elevenlabs/`，改文本/音色会自动重合成。
- 想先看 30 秒：SPEC 里加 `'limit': 30`。

## 5. 自检

```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 "$LESSON_HOME/01_my_topic/01_my_topic.mp4"
ffmpeg -v error -ss 3 -i "$LESSON_HOME/01_my_topic/01_my_topic.mp4" -frames:v 1 /tmp/a.png
```

看四件事：画布 1080×1920；文字没越过 y=1500；原声卡首尾没吞字；旁白与原声之间无长静音。
旁边有 `_说明.json`，记录了本次全部参数，复现问题先看它。

## 6. 字幕

```bash
cd $S && python3 make_srt.py 01_my_topic      # 产出 01_my_topic.srt
```

字幕按「旁白文本 × 全片 ASR」做逐字对齐；对不上会自动剪出该段二次转写。

## 7. 封面

```bash
cd $S && python3 covers.py 01_my_topic                 # 人像 + 标题
cd $S && python3 covers.py 01_my_topic --text-only     # 纯文字版
```

封面字段写在 SPEC 的 `cover` 里。

## 8. 笔记与 PDF

笔记 md 放在选题目录，格式：

```markdown
## 章节标题
**01. `take it`** ｜ 00:12
原句：When you have an opportunity, always take it.
意思：有机会就抓住。
用法：take it 指「接下这个机会」。
迁移：When you have an opportunity to speak English, take it.
```

然后：

```bash
python3 $S/handout.py "$LESSON_HOME/01_my_topic/表达详解.md" "$LESSON_HOME/01_my_topic" \
  --lang zh --title "精讲笔记 · 01" --sub "访谈原声 · 逐句拆解"
```

- 同目录放 `<md 同名>.transcript.txt` 就会在末尾多排「原声对照」；没有就一字不加。
- `--lang ja/ko/pt/es/de/fr` 切换整套界面文案。
- 无头 Chrome 与 GUI Chrome 抢 profile 时，`handout.py` 已用独立 profile（`CHROME_PROFILE` 可改）；
  不要用 `HOME=...` 绕，那会让 `~/Library/Python` 下的 PIL 等包失联。
- 外置卷上 `mdls -kMDItemNumberOfPages` 常返回 null，数页用：

```bash
python3 -c "import re,sys;print(len(re.findall(rb'/Type\s*/Page[^s]',open(sys.argv[1],'rb').read())))" x.pdf
```

## 9. 交付

一次交付固定四件：成片 mp4、封面 png、发帖文案 md、精讲笔记 PDF（+ 字幕 srt）。
发帖文案按平台写，不要带 skill 里的品牌假设；标题、首句、话题标签分开放。

## 10. 回归

改过引擎或字体后，抽 2–3 条老选题重渲，逐字节比对「除新增内容外」的 HTML/PDF 是否变化。
新增能力必须是「不触发就完全不出现在产物里」，避免老片被动改动。
