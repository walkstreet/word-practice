def normalize_phonetic(raw: str) -> str:
    """导入常见带 /.../；存库时去掉外层斜杠，避免与前端再包一层成 //…//。"""
    return (raw or "").strip().strip("/")
