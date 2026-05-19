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
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showBackToTop, setShowBackToTop] = useState(false);
  const pageSize = 50;

  const formatLocalTime = (raw: string) =>
    new Date(raw).toLocaleString("zh-CN", {
      hour12: false,
    });

  useEffect(() => {
    setLoading(true);
    setError("");
    api
      .get("/wrongbook", { params: { page, page_size: pageSize } })
      .then((res) => {
        setItems(res.data.list || []);
        setTotal(Number(res.data.total || 0));
      })
      .catch(() => setError("加载错题本失败"))
      .finally(() => setLoading(false));
  }, [page]);

  useEffect(() => {
    const updateVisible = () => {
      setShowBackToTop(window.scrollY > window.innerHeight / 2);
    };
    updateVisible();
    window.addEventListener("scroll", updateVisible);
    return () => window.removeEventListener("scroll", updateVisible);
  }, []);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="card">
      <div className="wrongbook-head">
        <h2>错题本</h2>
        <button
          className="primary-btn"
          onClick={() => navigate("/practice?scope=wrongbook")}
          disabled={total === 0 || loading}
        >
          开始错题再练
        </button>
      </div>
      {error ? <p className="error">{error}</p> : null}
      <div className="pager">
        <button
          type="button"
          className="ghost-btn"
          disabled={page <= 1 || loading}
          onClick={() => setPage((p) => Math.max(1, p - 1))}
        >
          上一页
        </button>
        <span className="pager-info">
          共 {total} 条 · 每页 {pageSize} 条 · 第 {page} / {totalPages} 页
        </span>
        <button
          type="button"
          className="ghost-btn"
          disabled={page >= totalPages || loading}
          onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
        >
          下一页
        </button>
      </div>
      <div className="table-wrap">
        <table className="wrongbook-table">
          <thead>
            <tr>
              <th>单词</th>
              <th>词性与释义</th>
              {showPhonetic ? <th className="col-phonetic">音标</th> : null}
              <th className="col-error-count">错误次数</th>
              <th>最近错误时间</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.vocabulary_id}>
                <td>{item.word}</td>
                <td>
                  <div className="sense-stack">
                    {resolvePosTranslationRows(
                      item.senses,
                      item.part_of_speech,
                      item.translation,
                    ).map((row, idx) => (
                      <div
                        className="sense-line"
                        key={`${item.vocabulary_id}-${idx}`}
                      >
                        <span className="sense-pos">{row.pos}</span>
                        <span className="sense-meaning">{row.meaning}</span>
                      </div>
                    ))}
                  </div>
                </td>
                {showPhonetic ? (
                  <td>
                    {item.phonetic ? formatIpaForDisplay(item.phonetic) : "-"}
                  </td>
                ) : null}
                <td>{item.wrong_count}</td>
                <td>{formatLocalTime(item.last_wrong_at)}</td>
              </tr>
            ))}
            {items.length === 0 && !loading ? (
              <tr>
                <td
                  colSpan={showPhonetic ? 5 : 4}
                  style={{ textAlign: "center", padding: "24px 0" }}
                >
                  当前无错题
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
      <div className="pager">
        <button
          type="button"
          className="ghost-btn"
          disabled={page <= 1 || loading}
          onClick={() => setPage((p) => Math.max(1, p - 1))}
        >
          上一页
        </button>
        <span className="pager-info">
          共 {total} 条 · 每页 {pageSize} 条 · 第 {page} / {totalPages} 页
        </span>
        <button
          type="button"
          className="ghost-btn"
          disabled={page >= totalPages || loading}
          onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
        >
          下一页
        </button>
      </div>
      {showBackToTop ? (
        <button
          type="button"
          className="ghost-btn back-to-top-fixed"
          onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
        >
          返回顶部
        </button>
      ) : null}
    </div>
  );
}
