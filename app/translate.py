"""轻量离线中英互译。

这是为选中文字提供的基础词句翻译，不联网、不上传文本。它优先匹配常用短语，
再按词翻译；未收录的专名和复杂句式会保留原文，避免伪造含义。
"""
from __future__ import annotations

import re

# 常用阅读、技术与日常词句。单份双向词典可同时服务中译英和英译中。
_PAIRS = {
    "你好": "hello", "谢谢": "thank you", "再见": "goodbye", "请": "please",
    "是": "is", "不是": "is not", "有": "have", "没有": "do not have",
    "我": "I", "我们": "we", "你": "you", "你们": "you", "他": "he", "她": "she", "他们": "they",
    "这": "this", "那": "that", "这里": "here", "那里": "there", "什么": "what", "为什么": "why",
    "如何": "how", "什么时候": "when", "哪里": "where", "谁": "who", "可以": "can", "不能": "cannot",
    "应该": "should", "必须": "must", "可能": "may", "需要": "need", "想要": "want",
    "今天": "today", "明天": "tomorrow", "昨天": "yesterday", "现在": "now", "曾经": "once",
    "时间": "time", "年": "year", "月": "month", "天": "day", "小时": "hour", "分钟": "minute",
    "人": "person", "朋友": "friend", "家人": "family", "孩子": "child", "老师": "teacher", "学生": "student",
    "中国": "China", "城市": "city", "乡村": "village", "家": "home", "学校": "school", "世界": "world",
    "书": "book", "章节": "chapter", "页面": "page", "文字": "text", "内容": "content", "故事": "story",
    "作者": "author", "读者": "reader", "标题": "title", "目录": "table of contents", "书签": "bookmark",
    "阅读": "read", "写作": "write", "说": "say", "告诉": "tell", "听": "listen", "看": "look",
    "知道": "know", "认为": "think", "理解": "understand", "记得": "remember", "忘记": "forget",
    "开始": "start", "结束": "end", "继续": "continue", "停止": "stop", "打开": "open", "关闭": "close",
    "前进": "forward", "返回": "back", "上一个": "previous", "下一个": "next", "第一": "first", "最后": "last",
    "大": "big", "小": "small", "高": "high", "低": "low", "长": "long", "短": "short",
    "新": "new", "旧": "old", "好": "good", "坏": "bad", "正确": "correct", "错误": "error",
    "快": "fast", "慢": "slow", "容易": "easy", "困难": "difficult", "重要": "important", "安全": "safe",
    "美丽": "beautiful", "黑暗": "dark", "明亮": "bright", "安静": "quiet", "温暖": "warm", "寒冷": "cold",
    "爱": "love", "喜欢": "like", "希望": "hope", "害怕": "fear", "快乐": "happy", "悲伤": "sad",
    "生活": "life", "工作": "work", "学习": "study", "问题": "problem", "答案": "answer", "方法": "method",
    "系统": "system", "程序": "program", "软件": "software", "硬件": "hardware", "网络": "network",
    "计算机": "computer", "文件": "file", "数据": "data", "代码": "code", "函数": "function", "用户": "user",
    "设置": "settings", "语言": "language", "翻译": "translation", "复制": "copy", "朗读": "read aloud",
    "隐私": "privacy", "本地": "local", "离线": "offline", "在线": "online", "保存": "save", "删除": "delete",
    "添加": "add", "选择": "select", "搜索": "search", "加载": "load", "速度": "speed", "大小": "size",
    "颜色": "color", "声音": "sound", "图片": "image", "视频": "video", "结果": "result", "功能": "feature",
    "因为": "because", "所以": "so", "但是": "but", "如果": "if", "那么": "then", "或者": "or",
    "和": "and", "也": "also", "在": "in", "从": "from", "到": "to", "与": "with", "为了": "for",
    "的": "of", "了": "", "着": "", "过": "", "吗": "", "很": "very", "更": "more", "最": "most",
    "一个": "a", "一些": "some", "所有": "all", "每个": "each", "没有问题": "no problem",
    "早上好": "good morning", "晚上好": "good evening", "晚安": "good night", "对不起": "sorry",
    "我爱你": "I love you", "我不知道": "I do not know", "请稍等": "please wait",
    "本地阅读器": "local reader", "隐私阅读": "private reading", "阅读进度": "reading progress",
    "上一章": "previous chapter", "下一章": "next chapter", "语音朗读": "read aloud",
    "中英互译": "Chinese-English translation", "不会保存": "will not be saved",
    "隐私阅读不会保存阅读进度": "Private reading does not save reading progress",
}

_ZH_TO_EN = dict(_PAIRS)
_EN_TO_ZH: dict[str, str] = {}
for zh, en in _PAIRS.items():
    if en and en.lower() not in _EN_TO_ZH:
        _EN_TO_ZH[en.lower()] = zh

_CJK_RE = re.compile(r"[\u3400-\u9fff]")
_WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?|\s+|[^A-Za-z\s]+")


def _zh_to_en(text: str) -> tuple[str, int]:
    out = text
    hits = 0
    # 长词优先，避免“下一章”先被“下一个”或“章”拆散。
    for zh in sorted(_ZH_TO_EN, key=len, reverse=True):
        if zh not in out:
            continue
        count = out.count(zh)
        out = out.replace(zh, f" {_ZH_TO_EN[zh]} ")
        hits += count
    out = re.sub(r"\s+([,.;:!?，。；：！？])", r"\1", out)
    out = re.sub(r"[，、]", ", ", out)
    out = re.sub(r"。", ". ", out)
    out = re.sub(r"；", "; ", out)
    out = re.sub(r"：", ": ", out)
    out = re.sub(r"！", "! ", out)
    out = re.sub(r"？", "? ", out)
    out = re.sub(r"\s+", " ", out).strip()
    if out:
        out = out[0].upper() + out[1:]
    return out, hits


def _en_to_zh(text: str) -> tuple[str, int]:
    out = text
    hits = 0
    # 先处理多词短语，并用占位符保护，随后再翻单词。
    protected: dict[str, str] = {}
    phrases = [x for x in _EN_TO_ZH if " " in x]
    for idx, phrase in enumerate(sorted(phrases, key=len, reverse=True)):
        pattern = re.compile(rf"\b{re.escape(phrase)}\b", re.I)
        if not pattern.search(out):
            continue
        key = f"\u0000{idx}\u0000"
        out, count = pattern.subn(key, out)
        protected[key] = _EN_TO_ZH[phrase]
        hits += count

    parts = []
    for token in _WORD_RE.findall(out):
        if token.startswith("\u0000"):
            parts.append(token)
            continue
        if re.fullmatch(r"[A-Za-z]+(?:'[A-Za-z]+)?", token):
            got = _EN_TO_ZH.get(token.lower())
            if got:
                parts.append(got)
                hits += 1
            else:
                parts.append(token)
        else:
            parts.append(token)
    out = "".join(parts)
    for key, value in protected.items():
        out = out.replace(key, value)
    out = re.sub(r"\s+([，。；：！？,.!?;:])", r"\1", out)
    out = re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", out)
    out = re.sub(r"\s+", " ", out).strip()
    return out, hits


def translate(text: str) -> dict:
    source = re.sub(r"\s+", " ", str(text or "")).strip()[:2000]
    if not source:
        return {"text": "", "direction": "", "hits": 0, "limited": True}
    cjk = len(_CJK_RE.findall(source))
    letters = len(re.findall(r"[A-Za-z]", source))
    if cjk >= max(1, letters // 3):
        result, hits = _zh_to_en(source)
        direction = "中 → 英"
    else:
        result, hits = _en_to_zh(source)
        direction = "英 → 中"
    limited = hits == 0 or bool(_CJK_RE.search(result) if direction == "中 → 英" else re.search(r"\b[A-Za-z]{3,}\b", result))
    return {"text": result or source, "direction": direction, "hits": hits, "limited": limited}
