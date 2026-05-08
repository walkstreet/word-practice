"""Structured multi-sense vocabulary: normalize, flatten for search, API helpers."""


def normalize_sense_dicts(raw: list) -> list[dict] | None:
    if not raw or not isinstance(raw, list):
        return None
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        pos = str(item.get("part_of_speech") or item.get("pos") or "").strip()
        meaning = str(item.get("meaning") or "").strip()
        if not meaning:
            continue
        out.append({"part_of_speech": pos, "meaning": meaning})
    return out or None


def flatten_senses_to_legacy(senses: list[dict]) -> tuple[str, str]:
    """Build translation / part_of_speech strings for search and legacy clients."""
    parts: list[str] = []
    pos_labels: list[str] = []
    for s in senses:
        pos = (s.get("part_of_speech") or "").strip()
        meaning = (s.get("meaning") or "").strip()
        if not meaning:
            continue
        if pos:
            parts.append(f"{pos} {meaning}".strip())
            pos_labels.append(pos)
        else:
            parts.append(meaning)
    translation = "；".join(parts)
    part_of_speech = "；".join(pos_labels) if pos_labels else ""
    return translation, part_of_speech


def to_sense_out_list(raw):
    from app.schemas import VocabSenseOut

    normalized = normalize_sense_dicts(raw)
    if not normalized:
        return None
    return [VocabSenseOut(part_of_speech=s["part_of_speech"], meaning=s["meaning"]) for s in normalized]

