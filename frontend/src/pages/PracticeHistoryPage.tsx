import { useEffect, useState } from "react";
import { api } from "../api";
import { resolvePosTranslationRows } from "../parsePosTranslation";

type HistoryItem = {
  vocabulary_id: number;
  word: string;
  translation: string;
  part_of_speech?: string;
  senses?: { part_of_speech: string; meaning: string }[] | null;
  question_mask: string;
  user_answer: string;
  correct_answer: string;
  is_correct: boolean;
  created_at: string;
};

export default function PracticeHistoryPage() {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [error, setError] = useState("");

  const formatLocalTime = (raw: string) =>
    new Date(raw).toLocaleString("zh-CN", {
      hour12: false
    });

  useEffect(() => {
    api
      .get("/practice/history")
      .then((res) => setItems(res.data.list || []))
      .catch(() => setError("加载练习历史失败"));
  }, []);

  return (
    <div className="card">
      <h2>练习历史</h2>
      {error ? <p className="error">{error}</p> : null}
      <table>
        <thead>
          <tr>
            <th>时间</th>
            <th>单词</th>
            <th>翻译</th>
            <th>题面</th>
            <th>你的答案</th>
            <th>正确答案</th>
            <th>结果</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, idx) => (
            <tr key={`${item.vocabulary_id}-${idx}`}>
              <td>{formatLocalTime(item.created_at)}</td>
              <td>{item.word}</td>
              <td>
                {resolvePosTranslationRows(
                  item.senses,
                  item.part_of_speech ?? "",
                  item.translation
                )
                  .map((r) => r.meaning)
                  .join("；")}
              </td>
              <td>{item.question_mask}</td>
              <td>{item.user_answer}</td>
              <td>{item.correct_answer}</td>
              <td>{item.is_correct ? "正确" : "错误"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
