# english-lesson-video

把一段长访谈或播客切成若干「表达」，每条做成一条 9:16 英语精讲视频：
**卡面 → 母语旁白 + 英文原句 → 原声回放**，并产出封面、字幕、发帖文案和精讲笔记 PDF。

学习者的母语支持 `zh` `ja` `ko` `pt` `es` `de` `fr`，英文始终是被学的那门语言。
这是一个给 AI Agent 用的技能（Skill），不是开箱即用的 App：Agent 读 `SKILL.md` 里的流程与硬规则，
调用 `scripts/` 下的脚本完成渲染。

## 安装

```bash
git clone https://github.com/Fionatt-creator/xiaohongshu-explain-video.git \
  ~/.trae-cn/skills/english-lesson-video
```

目录名必须是 `english-lesson-video`，与 `SKILL.md` 里的 `name` 一致。
（仓库地址暂时还叫 `xiaohongshu-explain-video`，改名不影响使用。）

## 配置

```bash
cd ~/.trae-cn/skills/english-lesson-video
cp config.example.env config.env
```

只改四类，其余留空即可：

| 变量 | 说明 |
|---|---|
| `ELEVENLABS_API_KEY` | 合成旁白用。只有渲染视频时需要，出 PDF 不需要 |
| `ELEVENLABS_VOICE_ID` | 多语种音色；要更地道再用 `ELEVENLABS_VOICE_<LANG>` 覆盖 |
| `LESSON_HOME` | 工作目录（自动建 `specs/`、`work/`、输出目录） |
| `SOURCE_VIDEO` | 源视频；单条选题可在 SPEC 里用 `src=` 覆盖 |

`BRAND_NAME` / `BRAND_URL` / `BRAND_TAGLINE` / `LESSON_LOGO` 可全空，空了就不画页眉页脚。
配置优先级：环境变量 > `--config` 指定文件 > 本目录 `config.env` > `~/.config/english-lesson-video/config.env`。

**密钥只放在 `config.env` 或环境变量里**，不要写进 SPEC、md，也不要提交到仓库。

## 一条视频的产出

`<name>.mp4`、`cover.png`、`发帖文案.md`、`精讲笔记.pdf`，外加 `<name>.srt`。

## 流程

| 步 | 做什么 |
|---|---|
| 1 | `transcribe.py` 转写全片 |
| 2 | `split_srt.py` + `fix_srt.py` 切章，不切断句子 |
| 3 | 定原声切点：ASR 词级起点 + 片段二次转写复核 |
| 4 | 按 `assets/spec-template.py` 写 SPEC |
| 5 | `engine.py <name>` 渲染 |
| 6 | 自检：1080×1920、文字不越界、原声不吞字 |
| 7 | `make_srt.py` 出字幕 |
| 8 | `covers.py` 出封面 |
| 9 | `handout.py` 出精讲笔记 PDF |
| 10 | 四件套交付 |

完整命令与自检方法见 `references/workflow.md`；SPEC 字段见 `references/spec-format.md`；
多语言字体/断行/音色/文案见 `references/languages.md`。

## 依赖

```bash
pip3 install requests Pillow faster-whisper
```

另外需要 `ffmpeg` / `ffprobe` 和 Google Chrome（出 PDF 用）。
字体全部取 macOS 自带；换系统先确认 `LANG_PROFILES` 里的字体路径存在。

## 目录

```
SKILL.md                 Agent 入口：配置、流程、内容硬规则、已知坑
config.example.env       配置模板
scripts/engine.py        渲染引擎（卡面 + 旁白 + 原声拼接）
scripts/transcribe.py    全片转写
scripts/split_srt.py     按语义切章
scripts/fix_srt.py       字幕修正
scripts/make_srt.py      成片字幕
scripts/covers.py        封面
scripts/handout.py       精讲笔记 PDF
references/              流程、SPEC 格式、多语言细节
assets/spec-template.py  SPEC 模板
```

## 版权

分发或售卖时不要打包访谈原片、原字幕和成片，只交付方法与脚本。
