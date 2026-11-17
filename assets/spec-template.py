# -*- coding: utf-8 -*-
"""选题模板：复制到 $LESSON_HOME/specs/<你的选题>.py，改内容即可。

关键约定
- 一个文件一个选题；渲染器按文件名（去掉 .py）作为选题名。
- cards 的顺序就是成片顺序。每张卡要么有 speech（旁白讲解），要么有 source（原声片段）。
  两者都有 = 先定格帧讲一遍，再播原声（推荐）。
- lines 里每个元组：(y 坐标, 文字, 字号, 颜色, 是否英文斜体)。
  画布 1080×1920；正文区 y≈430–1500；不要越过 1500，底部 417px 预留给平台 UI。
- speech 里 ('en', ...) 会按 EN_SLOW 放慢；其它语言代码按原速，并用该语言音色。
- 所有路径都不写在 SPEC 里：src 从 config.env 的 SOURCE_VIDEO 来；只有换素材时才在 SPEC 写 src。
- 不要把 API key、cookie、素材版权内容写进 SPEC。
"""

NAME = 'my_topic'          # 选题名（渲染时用它）；建议与文件名保持一致

SPEC = {
    'lang': 'zh',          # 学习者母语：zh | ja | ko | pt | es | de | fr
    'style': 'v2',         # v1 浅色（老片复现用）/ v2 深色（新片默认）
    'fonts': 'song',       # song = 宋体（新片默认）/ heiti = 黑体（老片）
    'speed': 1.2,          # 整体倍速；1.0 = 原速
    'en_slow': 0.8,        # 英文原句放慢倍数；1.0 = 不放慢
    # 'voice': '...',      # 需要时按选题覆盖音色
    # 'src': '/path/to/interview.mp4',   # 换素材时才写
    # 'limit': 60,         # 只渲前 60 秒，做试听版
    # 'subs': True,        # 给讲解旁白压单行字幕

    'cards': [
        # 开场卡：只讲，不播原声
        dict(n='00', title='开场',
             lines=[(900, 'I stopped apologizing', 62, 'fg', True),
                    (1000, 'for wanting more.', 74, 'green', True),
                    (1150, '我不再为「想要更多」道歉。', 46, 'fg', False)],
             speech=[('zh', '先听这一句。'),
                     ('en', 'I stopped apologizing for wanting more.'),
                     ('zh', '意思是，我不再为自己的野心道歉。')]),

        # 讲解 + 原声：source 用绝对秒数，end 必须卡在句子结尾之后
        dict(n='01', title='先听原句 / 01',
             lines=[(950, 'I stopped apologizing', 56, 'fg', True),
                    (1040, 'for wanting more.', 68, 'green', True),
                    (1220, '我不再为「想要更多」道歉。', 45, 'fg', False)],
             speech=[('zh', '注意 apologize for 这个搭配。'),
                     ('en', 'apologize for wanting more'),
                     ('zh', '为自己想要更多而道歉。')],
             source=(12.40, 15.90)),

        # 只用原声：不加旁白，直接播片段
        dict(n='02', title='原声回放',
             lines=[(470, '原声 · 00:12', 52, 'mute', False)],
             source=(12.40, 15.90)),
    ],
}
