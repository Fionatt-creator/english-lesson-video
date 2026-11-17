# SPEC 字段速查

一个选题 = `$LESSON_HOME/specs/<name>.py`，里面给 `SPEC`（或 `SPECS` 字典）。
选题名取 `NAME`，没写才退回文件名。

## 顶层字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `lang` | str | 学习者母语，`zh`/`ja`/`ko`/`pt`/`es`/`de`/`fr`；决定字体、断行、默认音色 |
| `style` | str | `v1` 浅色 / `v2` 深色（默认） |
| `fonts` | str | `song` 宋体（默认）/ `heiti` 黑体 |
| `speed` | float | 整体倍速，默认取 `OUTPUT_SPEED` |
| `en_slow` | float | 英文原句放慢倍数，默认取 `EN_SLOW` |
| `voice` / `model` / `voice_settings` | — | 按选题覆盖 TTS 参数；不写就用 config |
| `src` | path | 换素材时才写，默认 `SOURCE_VIDEO` |
| `foot` / `url` | bool | 页脚与链接，新片一律 `False` |
| `limit` | float | 只渲前 N 秒（试听版） |
| `subs` | bool | 给讲解旁白压单行字幕 |
| `subs_src` + `src_subs` | bool + dict | 给原声片段压双语字幕：`{卡号: [(起, 止, 英文, 译文)]}` |
| `out_dir` / `work` | str | 输出/中间目录，默认等于选题名 |
| `cover` | dict | 封面：`title=[...]`、`sub`、`eyebrow`、`photo_t`、`out` |

## cards

| 字段 | 说明 |
|---|---|
| `n` | 卡号字符串。同一卡拆成 `_a`（讲解）与 `_b`（原声）是渲染器自动做的，不要自己写 |
| `title` | 卡面标题 |
| `lines` | `[(y, 文字, 字号, 颜色, 是否英文斜体), ...]`；y 在 430–1500 之间 |
| `speech` | `[(语言代码, 文本), ...]`；`'en'` 会放慢，其它语言用对应音色 |
| `source` | `(起, 止)` 绝对秒，`止` 必须覆盖整句尾音 |
| `tail` | 旁白卡尾部留白，默认 0.35s |

颜色键：`fg`（主文字）、`mute`（次要）、`green`（主强调）、`green2`（次强调）。

## 规则

- `lines` 的 y 是绝对坐标，不自动排版；同一张卡最多 4–5 行，行距 ≥ 80px。
- 英文行 `italic=True`，中文行 `False`；两种字体分开取，别混排在一行。
- `source` 的切点用 ASR 词级时间定位，切完要复核（见 workflow 第 2 步）。
- 原声卡不加讲解字幕；讲解卡如果开 `subs`，字幕走单行，别超过一行宽度。
- 不要把 key、cookie、版权素材路径写进 SPEC。
