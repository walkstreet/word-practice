from datetime import datetime
from typing import Any, Dict, List, Optional

import unicodedata

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VocabSenseBase(BaseModel):
    model_config = ConfigDict(extra="ignore")

    part_of_speech: str = ""
    meaning: str = ""

    @model_validator(mode="before")
    @classmethod
    def normalize_sense_fields(cls, data):
        if not isinstance(data, dict):
            return data
        pos = data.get("part_of_speech")
        if pos is None:
            pos = data.get("pos")
        if pos is None:
            pos = ""
        elif not isinstance(pos, str):
            pos = str(pos)
        mean = data.get("meaning")
        if mean is None:
            mean = ""
        elif not isinstance(mean, str):
            mean = str(mean)
        return {**data, "part_of_speech": pos.strip(), "meaning": mean.strip()}


class VocabSenseIn(VocabSenseBase):
    @model_validator(mode="after")
    def meaning_required_when_used(self):
        if not (self.meaning or "").strip():
            raise ValueError("each sense must have non-empty meaning")
        return self


class VocabSenseOut(VocabSenseBase):
    pass


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str


class ImportResponse(BaseModel):
    total: int
    success: int
    failed: int = Field(description="因校验错误未写入的行数（重复跳过不计入，见 duplicated_skipped）")
    duplicated_skipped: int
    errors: List[dict]
    duplicate_skips: List[dict] = Field(
        default_factory=list,
        description="因与库内或本批前方词条重复而跳过的行（line 与 CSV 行号一致时从 2 起）",
    )
    request_words: List[str] = Field(
        default_factory=list,
        description="本次请求按顺序收到的 word（便于核对 Dify 实际发出的条数与拼写）",
    )
    inserted: List[dict] = Field(
        default_factory=list,
        description="本次新插入的词条：line、id、word（用于在 DB 中定位；若为空则说明无新插入）",
    )


class DifyVocabImportItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    word: str = ""
    translation: str = ""
    phonetic: str = ""
    part_of_speech: str = ""
    senses: Optional[List[VocabSenseIn]] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_null_strings(cls, data):
        if not isinstance(data, dict):
            return data
        out = {**data}
        for key in ("word", "translation", "phonetic", "part_of_speech"):
            if out.get(key) is None:
                out[key] = ""
            elif isinstance(out[key], str):
                pass
            else:
                out[key] = str(out[key])
        return out

    @model_validator(mode="after")
    def word_and_content(self):
        w = unicodedata.normalize("NFKC", (self.word or "").strip())
        if not w:
            raise ValueError("word is required")
        object.__setattr__(self, "word", w)

        has_senses = bool(self.senses)
        has_flat = bool((self.translation or "").strip())
        if has_senses and not has_flat:
            return self
        if has_flat and not has_senses:
            return self
        if has_senses and has_flat:
            raise ValueError("use either senses[] or translation, not both")
        raise ValueError("provide senses[] or translation")


class DifyVocabImportBatch(BaseModel):
    """Dify HTTP 节点可能发 JSON 数组或 {\"items\": [...]}，两种都接受。"""

    items: List[DifyVocabImportItem]

    @model_validator(mode="before")
    @classmethod
    def list_or_object(cls, data):
        if isinstance(data, list):
            return {"items": data}
        return data


class VocabularyUpdateBody(DifyVocabImportItem):
    """编辑词条：字段规则与 Dify 导入单项相同（word + senses 或 translation）。"""


class VocabularyItem(BaseModel):
    id: int
    word: str
    translation: str
    phonetic: str
    part_of_speech: str
    senses: Optional[List[VocabSenseOut]] = None


class VocabularyListResponse(BaseModel):
    total: int
    list: List[VocabularyItem]


class VocabularyBatchDeleteBody(BaseModel):
    ids: List[int]


class VocabularyBatchDeleteResponse(BaseModel):
    deleted: int
    """实际删除的词条数（已存在的 id）。"""
    not_found: int
    """请求里在库中不存在的 id 数。"""


class NextQuestionResponse(BaseModel):
    question_id: str
    vocabulary_id: int
    word: str
    translation: str
    phonetic: str
    part_of_speech: str
    senses: Optional[List[VocabSenseOut]] = None
    masked_word: str
    masked_segments: Optional[List[Dict[str, Any]]] = None
    hint: dict


class SubmitRequest(BaseModel):
    question_id: str
    vocabulary_id: int
    missing_letters: str


class SubmitResponse(BaseModel):
    is_correct: bool
    correct_answer: str
    message: str
    wrong_blank_indexes: List[int]


class WrongBookItem(BaseModel):
    vocabulary_id: int
    word: str
    translation: str
    phonetic: str
    part_of_speech: str
    senses: Optional[List[VocabSenseOut]] = None
    wrong_count: int
    last_wrong_at: datetime


class WrongBookResponse(BaseModel):
    total: int
    list: List[WrongBookItem]


class StatsResponse(BaseModel):
    total_answered: int
    correct_count: int
    wrong_count: int
    accuracy: float


class PracticeHistoryItem(BaseModel):
    vocabulary_id: int
    word: str
    translation: str
    phonetic: str
    part_of_speech: str
    senses: Optional[List[VocabSenseOut]] = None
    question_mask: str
    user_answer: str
    correct_answer: str
    is_correct: bool
    created_at: datetime


class PracticeHistoryResponse(BaseModel):
    total: int
    list: List[PracticeHistoryItem]
