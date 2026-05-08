import random
import re

import unicodedata

from app.config import settings

_ALT_SPLIT_RE = re.compile(r"[／/｜|]")
# 练习用词边界：仅连续英文字母、数字、撇号、连字符算「可挖空」的词；其余（空格、…、句号等）仅占位展示。


def normalize_word(word: str) -> str:
    """词库去重键：NFKC + strip，区分大小写（China 与 china 为两条）。"""
    return unicodedata.normalize("NFKC", (word or "").strip())


def pick_primary_answer(word: str) -> str:
    """多答案词条（如 gray/grey）只取第一个备选用于练习与判题。"""
    raw = unicodedata.normalize("NFKC", (word or "").strip())
    if not raw:
        return ""
    parts = [p.strip() for p in _ALT_SPLIT_RE.split(raw) if p.strip()]
    return parts[0] if parts else raw


def phrase_ordered_parts(primary: str) -> list[tuple[str, str]]:
    """拆成交替的 word / literal：literal 含空白、省略号等，不参与挖空与输入。"""
    raw = unicodedata.normalize("NFKC", (primary or "").strip())
    if not raw:
        return []
    pieces = [p for p in re.split(r"([A-Za-z0-9'`\-]+)", raw) if p]
    parts: list[tuple[str, str]] = []
    for p in pieces:
        kind = "word" if re.fullmatch(r"[A-Za-z0-9'`\-]+", p) else "literal"
        if parts and parts[-1][0] == "literal" and kind == "literal":
            prev = parts[-1][1]
            parts[-1] = ("literal", prev + p)
        else:
            parts.append((kind, p))
    return parts


def assemble_surface(ordered_parts: list[tuple[str, str]], word_slots: list[str]) -> str:
    """按原文 literal 位置拼回整段展示串（word_slots 与 word 片段一一对应）。"""
    wi = 0
    chunks: list[str] = []
    for kind, text in ordered_parts:
        if kind == "word":
            chunks.append(word_slots[wi])
            wi += 1
        else:
            chunks.append(text)
    if wi != len(word_slots):
        raise ValueError("word_slots does not match ordered word count")
    return "".join(chunks)


def compact_phrase(words: list[str]) -> str:
    """仅连接可挖空的词片段（字母词），不含字面量中的标点或空格。"""
    return "".join(words)


def choose_missing_positions(word: str) -> list[int]:
    length = len(word)
    if length <= 1:
        return []

    # Hide configured ratio of characters, while keeping at least one visible character.
    missing_count = int(round(length * settings.word_missing_ratio))
    missing_count = max(1, min(missing_count, length - 1))

    candidate_positions = list(range(length))
    random.shuffle(candidate_positions)
    selected = sorted(candidate_positions[:missing_count])
    return selected


def build_masked_word(word: str, missing_positions: list[int]) -> str:
    chars = []
    missing_set = set(missing_positions)
    for idx, ch in enumerate(word):
        chars.append("_" if idx in missing_set else ch)
    return " ".join(chars)


def build_masked_segment_payload(
    ordered_parts: list[tuple[str, str]],
    missing_positions: list[int],
) -> list[dict[str, object]]:
    """前端遮罩：word 为 {"cells":[...]}，literal 为 {"literal":"..."}。"""
    missing_set = set(missing_positions)
    cursor = 0
    out: list[dict[str, object]] = []
    for kind, text in ordered_parts:
        if kind == "literal":
            out.append({"literal": text})
            continue
        row: list[str] = []
        for ch in text:
            row.append("_" if cursor in missing_set else ch)
            cursor += 1
        out.append({"cells": row})
    return out


def segments_payload_to_mask_string(payload: list[dict[str, object]]) -> str:
    """写入练习记录的遮罩串。"""
    chunks: list[str] = []
    for seg in payload:
        if "literal" in seg:
            chunks.append(f'«{seg["literal"]}»')
        else:
            cells = seg.get("cells")
            if isinstance(cells, list):
                chunks.append(" ".join(str(c) for c in cells))
    return " | ".join(chunks)
