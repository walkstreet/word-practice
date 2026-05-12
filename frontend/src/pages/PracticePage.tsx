import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { formatIpaForDisplay } from "../ipaDisplay";
import { resolvePosTranslationRows } from "../parsePosTranslation";
import { cancelSpeech, speakEnglishWord } from "../speakWord";
import { useUiPreferences } from "../uiPreferences";

type MaskSegment = { cells: string[] } | { literal: string };

type Question = {
  question_id: string;
  vocabulary_id: number;
  word: string;
  translation: string;
  phonetic: string;
  part_of_speech: string;
  senses?: { part_of_speech: string; meaning: string }[] | null;
  masked_word: string;
  masked_segments?: MaskSegment[] | string[][] | null;
  hint: { wordLength: number; missingCount: number };
};

function normalizeMaskSegments(
  raw: Question["masked_segments"],
): MaskSegment[] | null {
  if (!raw?.length) {
    return null;
  }
  const head = raw[0];
  if (Array.isArray(head)) {
    return (raw as string[][]).map((cells) => ({ cells }));
  }
  return raw as MaskSegment[];
}

type JudgeResult = {
  is_correct: boolean;
  correct_answer: string;
  message: string;
  wrong_blank_indexes: number[];
};

const STATS_RESET_THRESHOLD_MS = 60 * 60 * 1000;
const LAST_PRACTICE_INPUT_KEY = "wp_last_practice_input_time";

function getLastPracticeInputTime(): Date | null {
  const raw = localStorage.getItem(LAST_PRACTICE_INPUT_KEY);
  if (!raw) {
    return null;
  }
  const timestamp = Date.parse(raw);
  return Number.isNaN(timestamp) ? null : new Date(timestamp);
}

function saveLastPracticeInputTime() {
  localStorage.setItem(LAST_PRACTICE_INPUT_KEY, new Date().toISOString());
}

export default function PracticePage() {
  const [searchParams] = useSearchParams();
  const { showPhonetic } = useUiPreferences();
  const [question, setQuestion] = useState<Question | null>(null);
  const [missingLetters, setMissingLetters] = useState<string[]>([]);
  const [activeBlankIndex, setActiveBlankIndex] = useState(0);
  const [result, setResult] = useState<JudgeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const scope = searchParams.get("scope") === "wrongbook" ? "wrongbook" : "all";

  const loadQuestion = async () => {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await api.get("/practice/next", { params: { scope } });
      const nextQuestion = res.data as Question;
      setQuestion(nextQuestion);
      setMissingLetters(Array(nextQuestion.hint.missingCount).fill(""));
      setActiveBlankIndex(0);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (scope === "wrongbook" && detail === "Wrong book is empty") {
        setError("错题本为空，暂时无法进行错题再练");
      } else {
        setError("获取题目失败，请先导入词汇");
      }
      setQuestion(null);
      setMissingLetters([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const maybeResetStats = async () => {
      const lastInputTime = getLastPracticeInputTime();
      if (!lastInputTime) {
        return;
      }
      const now = new Date();
      if (now.getTime() - lastInputTime.getTime() <= STATS_RESET_THRESHOLD_MS) {
        return;
      }
      if (
        window.confirm(
          "检测到距上次练习输入已超过 1 小时，是否清空当前统计数据？此操作会删除练习记录。",
        )
      ) {
        try {
          await api.delete("/stats");
        } catch {
          setError("清空统计失败，请稍后再试");
        }
      }
    };

    maybeResetStats().finally(() => {
      loadQuestion();
    });
  }, [scope]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    return () => cancelSpeech();
  }, [question?.question_id]);

  useEffect(() => {
    if (!result) {
      return;
    }
    const timer = window.setTimeout(() => {
      loadQuestion();
    }, 2200);
    return () => window.clearTimeout(timer);
  }, [result]); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = async () => {
    if (!question) {
      return;
    }
    const compactMissing = missingLetters.join("");
    if (compactMissing.length !== question.hint.missingCount) {
      return;
    }

    setLoading(true);
    setError("");
    try {
      const res = await api.post("/practice/submit", {
        question_id: question.question_id,
        vocabulary_id: question.vocabulary_id,
        missing_letters: compactMissing,
      });
      setResult(res.data);
      saveLastPracticeInputTime();
    } catch {
      setError("提交失败，请稍后再试");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!question || loading || !!result) {
      return;
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Enter") {
        const isReady = missingLetters.every((letter) => !!letter);
        if (isReady) {
          event.preventDefault();
          submit();
        }
        return;
      }

      if (event.key === "Backspace") {
        event.preventDefault();
        setMissingLetters((prev) => {
          const next = [...prev];
          if (next[activeBlankIndex]) {
            next[activeBlankIndex] = "";
            return next;
          }

          const previousIndex = Math.max(0, activeBlankIndex - 1);
          next[previousIndex] = "";
          setActiveBlankIndex(previousIndex);
          return next;
        });
        return;
      }

      if (/^[a-zA-Z\-'.]$/.test(event.key)) {
        event.preventDefault();
        const letter = event.key;
        setMissingLetters((prev) => {
          const next = [...prev];
          next[activeBlankIndex] = letter;
          return next;
        });
        setActiveBlankIndex((prev) =>
          Math.min(prev + 1, question.hint.missingCount - 1),
        );
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [question, loading, result, activeBlankIndex, missingLetters]);

  const segments = normalizeMaskSegments(question?.masked_segments ?? null);

  const tokens = !segments ? question?.masked_word.split(" ") || [] : [];
  const blankMap: number[] = [];
  if (!segments) {
    tokens.forEach((token, index) => {
      if (token === "_") {
        blankMap.push(index);
      }
    });
  }

  const rows = resolvePosTranslationRows(
    question?.senses,
    question?.part_of_speech || "",
    question?.translation || "",
  );

  return (
    <div className="card">
      <h2>单词练习</h2>
      {question ? (
        <>
          <div className="word-panel">
            {showPhonetic ? (
              <p className="word-meta word-meta-row">
                <span className="word-meta-ipa">
                  {question.phonetic
                    ? formatIpaForDisplay(question.phonetic)
                    : "音标待补充"}
                </span>
                <button
                  type="button"
                  className="speak-word-btn"
                  title="朗读单词"
                  aria-label="朗读单词"
                  disabled={!question.word?.trim()}
                  onClick={() => speakEnglishWord(question.word)}
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                    width="18"
                    height="18"
                    aria-hidden
                  >
                    <path d="M13.5 4.5c-.68 0-1.35.22-1.9.63L7.88 8H5v8h2.88l3.72 2.87c.55.41 1.22.63 1.9.63 1.38 0 2.5-1.12 2.5-2.5V7c0-1.38-1.12-2.5-2.5-2.5z" />
                    <path d="M17.45 8.55a1 1 0 0 1 1.41 0 3.5 3.5 0 0 1 0 4.95 1 1 0 0 1-1.41-1.41 1.5 1.5 0 0 0 0-2.12 1 1 0 0 1 0-1.42z" />
                  </svg>
                </button>
              </p>
            ) : null}
            {rows.map((row, index) => (
              <div className="meta-translation-row" key={`meta-row-${index}`}>
                <span className="pos-text">{row.pos}</span>
                <span className="translation-text">{row.meaning}</span>
              </div>
            ))}
            {result ? (
              <p
                className={`practice-result ${result.is_correct ? "success" : "error"}`}
              >
                {result.message}
              </p>
            ) : null}
          </div>
          <div className={`masked-board${segments ? " phrase-board" : ""}`}>
            {segments
              ? (() => {
                  let runningBlank = 0;
                  return segments.map((segment, segIdx) => {
                    if ("literal" in segment) {
                      return (
                        <span
                          key={`phrase-lit-${segIdx}`}
                          className="phrase-literal"
                        >
                          {segment.literal}
                        </span>
                      );
                    }
                    const cells = segment.cells;
                    return (
                      <span
                        key={`phrase-seg-${segIdx}`}
                        className="phrase-word-group"
                      >
                        {cells.map((token, tokenIndex) => {
                          if (token !== "_") {
                            return (
                              <span
                                key={`char-${segIdx}-${tokenIndex}`}
                                className="masked-cell"
                              >
                                {token}
                              </span>
                            );
                          }
                          const blankIndex = runningBlank++;
                          const isActive =
                            blankIndex === activeBlankIndex &&
                            !result &&
                            !loading;
                          const display = missingLetters[blankIndex] || "_";
                          const isWrong =
                            !!result &&
                            !result.is_correct &&
                            result.wrong_blank_indexes.includes(blankIndex);
                          return (
                            <button
                              key={`blank-${segIdx}-${tokenIndex}`}
                              type="button"
                              className={`masked-cell blank ${isActive ? "active" : ""} ${isWrong ? "wrong" : ""}`}
                              disabled={!!result || loading}
                              onClick={() => setActiveBlankIndex(blankIndex)}
                            >
                              {display}
                            </button>
                          );
                        })}
                      </span>
                    );
                  });
                })()
              : tokens.map((token, tokenIndex) => {
                  if (token !== "_") {
                    return (
                      <span key={`char-${tokenIndex}`} className="masked-cell">
                        {token}
                      </span>
                    );
                  }

                  const blankIndex = blankMap.findIndex(
                    (idx) => idx === tokenIndex,
                  );
                  const isActive =
                    blankIndex === activeBlankIndex && !result && !loading;
                  const display = missingLetters[blankIndex] || "_";
                  const isWrong =
                    !!result &&
                    !result.is_correct &&
                    result.wrong_blank_indexes.includes(blankIndex);

                  return (
                    <button
                      key={`blank-${tokenIndex}`}
                      type="button"
                      className={`masked-cell blank ${isActive ? "active" : ""} ${isWrong ? "wrong" : ""}`}
                      disabled={!!result || loading}
                      onClick={() => setActiveBlankIndex(blankIndex)}
                    >
                      {display}
                    </button>
                  );
                })}
          </div>
          <div className="actions">
            <button
              onClick={submit}
              disabled={
                missingLetters.some((letter) => !letter) || !!result || loading
              }
            >
              提交
            </button>
          </div>
          <p className="bottom-hint">
            请直接键盘输入填空，Backspace 删除，Enter 提交
          </p>
        </>
      ) : null}
      {error ? <p className="error">{error}</p> : null}
    </div>
  );
}
