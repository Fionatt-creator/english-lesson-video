# 多语言约定

学习者母语（`lang` / `NATIVE_LANG`）：`zh` `ja` `ko` `pt` `es` `de` `fr`。
英文永远是「被学的语言」，不翻译成别的英文；母语只出现在讲解、笔记、字幕译文里。

## 字体（全部 macOS 自带，无需安装）

| 代码 | 字体 | 断行 |
|---|---|---|
| zh | Songti SC（`song`）/ Heiti SC（`heiti`） | 按标点，无空格 |
| ja | Hiragino Sans | 按标点，无空格 |
| ko | Apple SD Gothic Neo | 按标点，无空格 |
| pt / es / de / fr | Helvetica Neue | 按空格 |

## 音色

- 一个多语种音色就能跑完 7 种语言，填 `ELEVENLABS_VOICE_ID` 即可。
- 想要更地道，用 `ELEVENLABS_VOICE_JA` 这类字段按语言覆盖。
- `model` 用 `eleven_v3`；注意 v3 不接受 `speed` 参数，变速靠 `en_slow` 与 `speed` 后期做。
- 换音色后必须重渲：缓存的 mp3 签名里含 voice id，会自动失效重合成。

## 笔记 md 字段名

解析器同时认中文与各语言写法：

| 中文 | English | 日本語 | 한국어 | PT | ES | DE | FR |
|---|---|---|---|---|---|---|---|
| 原句 | Original | 原文 | 원문 | Original | Original | Original | Original |
| 意思 | Meaning | 意味 | 의미 | Sentido | Significado | Bedeutung | Sens |
| 用法 | Usage | 使い方 | 쓰임 | Uso | Uso | Gebrauch | Usage |
| 迁移 | Transfer | 応用 | 응용 | Transferência | Transferencia | Übertragung | Transfert |

条目头 `**N. \`表达\`** ｜ 时间` 的竖线用全角 `｜` 或半角 `|` 都可以。

## 原声对照数据文件

`<md 同名>.transcript.txt`（兼容旧名 `.原声对照.txt`），每行：

```
mm:ss｜说话人｜英文原话｜译文
```

- `#` 开头为注释；译文里可以再出现 `｜`（只按前三个切）。
- 说话人自定（`Host` / 受访者名），会原样显示。
- 超过一小时写 `1:00:12`。
- 没有这个文件，PDF 就完全不排「原声对照」一节。

## PDF 文案

`scripts/handout.py` 内置 7 套界面文案（标题、跟读练习、原声对照、导读等）。
新增语言时在 `L` 字典里加一项即可，字段齐全就能直接用。
