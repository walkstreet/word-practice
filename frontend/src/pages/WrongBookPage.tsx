import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useUiPreferences } from "../uiPreferences";
import { formatIpaForDisplay } from "../ipaDisplay";
import { resolvePosTranslationRows } from "../parsePosTranslation";

type WrongBookItem = {
  vocabulary_id: number;
  word: string;
  translation: string;
  phonetic: string;
  part_of_speech: string;
  senses?: { part_of_speech: string; meaning: string }[] | null;
  wrong_count: number;
  last_wrong_at: string;
};

export default function WrongBookPage() {
  const navigate = useNavigate();
  const { showPhonetic } = useUiPreferences();
  const [items, setItems] = useState<WrongBookItem[]>([]);
  const [error, setError] = useState("");

  const formatLocalTime = (raw: string) =>
    new Date(raw).toLocaleString("zh-CN", {
      hour12: false
    });

  useEffect(() => {
    api
      .get("/wrongbook")
      .then((res) => setItems(res.data.list || []))
      .catch(() => setError("加载错题本失败"));
  }, []);

  return (
    <div className="card">
      <div className="wrongbook-head">
        <h2>错题本</h2>
        <button onClick={() => navigate("/practice?scope=wrongbook")} disabled={items.length === 0}>
          开始错题再练
        </button>
      </div>
      {error ? <p className="error">{error}</p> : null}
      <table>
        <thead>
          <tr>
            <th>单词</th>
            <th>词性与释义</th>
            {showPhonetic ? <th>音标</th> : null}
            <th>错误次数</th>
            <th>最近错误时间</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.vocabulary_id}>
              <td>{item.word}</td>
              <td>
                <div className="sense-stack">
                  {resolvePosTranslationRows(item.senses, item.part_of_speech, item.translation).map((row, idx) => (
                    <div className="sense-line" key={`${item.vocabulary_id}-${idx}`}>
                      <span className="sense-pos">{row.pos}</span>
                      <span className="sense-meaning">{row.meaning}</span>
                    </div>
                  ))}
                </div>
              </td>
              {showPhonetic ? <td>{item.phonetic ? formatIpaForDisplay(item.phonetic) : "-"}</td> : null}
              <td>{item.wrong_count}</td>
              <td>{formatLocalTime(item.last_wrong_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
