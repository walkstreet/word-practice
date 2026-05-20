import { useEffect, useState } from "react";
import { api } from "../api";

type Stats = {
  total_answered: number;
  correct_count: number;
  wrong_count: number;
  accuracy: number;
};

type Snapshot = {
  id: number;
  total_answered: number;
  correct_count: number;
  wrong_count: number;
  accuracy: string;
  created_at: string;
};

export default function StatsPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [snapshotTotal, setSnapshotTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showBackToTop, setShowBackToTop] = useState(false);
  const pageSize = 50;

  const loadStats = () => {
    setLoading(true);
    api
      .get("/stats")
      .then((res) => {
        setStats(res.data);
        setError("");
      })
      .catch(() => setError("加载统计失败"))
      .finally(() => setLoading(false));
  };

  const loadSnapshots = () => {
    api
      .get("/stats/snapshots", { params: { page, page_size: pageSize } })
      .then((res) => {
        setSnapshots(res.data.list);
        setSnapshotTotal(Number(res.data.total || 0));
        setError("");
      })
      .catch(() => setError("加载快照失败"));
  };

  useEffect(() => {
    loadStats();
  }, []);

  useEffect(() => {
    loadSnapshots();
  }, [page]);

  useEffect(() => {
    const updateVisible = () => {
      setShowBackToTop(window.scrollY > window.innerHeight / 2);
    };
    updateVisible();
    window.addEventListener("scroll", updateVisible);
    return () => window.removeEventListener("scroll", updateVisible);
  }, []);

  const handleResetStats = async () => {
    if (!confirm("确定要清零所有统计数据吗？此操作不可撤销。")) {
      return;
    }
    try {
      setLoading(true);
      await api.delete("/stats");
      setStats({
        total_answered: 0,
        correct_count: 0,
        wrong_count: 0,
        accuracy: 0,
      });
      setError("");
    } catch {
      setError("清零失败");
    } finally {
      setLoading(false);
    }
  };

  const handleSaveSnapshot = async () => {
    try {
      setLoading(true);
      await api.post("/stats/snapshots");
      loadSnapshots();
      setError("");
    } catch {
      setError("保存快照失败");
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteSnapshot = async (id: number) => {
    if (!confirm("确定要删除这个快照吗？")) {
      return;
    }
    try {
      await api.delete(`/stats/snapshots/${id}`);
      loadSnapshots();
    } catch {
      setError("删除快照失败");
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString("zh-CN");
  };

  const totalPages = Math.max(1, Math.ceil(snapshotTotal / pageSize));

  return (
    <div className="card">
      <h2>统计</h2>
      {error ? <p className="error">{error}</p> : null}

      {stats ? (
        <>
          <div className="result">
            <p>总提交数: {stats.total_answered}</p>
            <p>正确数: {stats.correct_count}</p>
            <p>错误数: {stats.wrong_count}</p>
            <p>正确率: {(stats.accuracy * 100).toFixed(2)}%</p>
          </div>

          <div style={{ marginTop: "20px", display: "flex", gap: "10px" }}>
            <button
              onClick={handleSaveSnapshot}
              disabled={loading}
              style={{
                padding: "8px 16px",
                cursor: loading ? "not-allowed" : "pointer",
              }}
            >
              保存当前数据
            </button>
            <button
              onClick={handleResetStats}
              disabled={loading}
              style={{
                padding: "8px 16px",
                cursor: loading ? "not-allowed" : "pointer",
                backgroundColor: "#ff6b6b",
                color: "white",
                border: "none",
                borderRadius: "4px",
              }}
            >
              清零数据
            </button>
          </div>
        </>
      ) : null}

      {snapshots.length > 0 && (
        <div style={{ marginTop: "30px" }}>
          <h3>保存的快照</h3>
          {snapshotTotal > 0 ? (
            <div className="pager" style={{ marginTop: "12px" }}>
              <button
                type="button"
                className="ghost-btn"
                disabled={page <= 1 || loading}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                上一页
              </button>
              <span className="pager-info">
                共 {snapshotTotal} 条 · 每页 {pageSize} 条 · 第 {page} /{" "}
                {totalPages} 页
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
          ) : null}
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              marginTop: "10px",
            }}
          >
            <thead>
              <tr style={{ borderBottom: "2px solid #ccc" }}>
                <th
                  style={{
                    textAlign: "left",
                    padding: "8px",
                    fontWeight: "bold",
                  }}
                >
                  保存时间
                </th>
                <th
                  style={{
                    textAlign: "center",
                    padding: "8px",
                    fontWeight: "bold",
                  }}
                >
                  总提交数
                </th>
                <th
                  style={{
                    textAlign: "center",
                    padding: "8px",
                    fontWeight: "bold",
                  }}
                >
                  正确数
                </th>
                <th
                  style={{
                    textAlign: "center",
                    padding: "8px",
                    fontWeight: "bold",
                  }}
                >
                  错误数
                </th>
                <th
                  style={{
                    textAlign: "center",
                    padding: "8px",
                    fontWeight: "bold",
                  }}
                >
                  正确率
                </th>
                <th
                  style={{
                    textAlign: "center",
                    padding: "8px",
                    fontWeight: "bold",
                  }}
                >
                  操作
                </th>
              </tr>
            </thead>
            <tbody>
              {snapshots.map((snapshot) => (
                <tr
                  key={snapshot.id}
                  style={{ borderBottom: "1px solid #eee" }}
                >
                  <td style={{ padding: "8px" }}>
                    {formatDate(snapshot.created_at)}
                  </td>
                  <td style={{ textAlign: "center", padding: "8px" }}>
                    {snapshot.total_answered}
                  </td>
                  <td style={{ textAlign: "center", padding: "8px" }}>
                    {snapshot.correct_count}
                  </td>
                  <td style={{ textAlign: "center", padding: "8px" }}>
                    {snapshot.wrong_count}
                  </td>
                  <td style={{ textAlign: "center", padding: "8px" }}>
                    {snapshot.accuracy}
                  </td>
                  <td style={{ textAlign: "center", padding: "8px" }}>
                    <button
                      onClick={() => handleDeleteSnapshot(snapshot.id)}
                      style={{
                        padding: "4px 8px",
                        backgroundColor: "#ff6b6b",
                        color: "white",
                        border: "none",
                        borderRadius: "4px",
                        cursor: "pointer",
                        fontSize: "12px",
                      }}
                    >
                      删除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {snapshotTotal > 0 ? (
            <div className="pager" style={{ marginTop: "12px" }}>
              <button
                type="button"
                className="ghost-btn"
                disabled={page <= 1 || loading}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                上一页
              </button>
              <span className="pager-info">
                共 {snapshotTotal} 条 · 每页 {pageSize} 条 · 第 {page} /{" "}
                {totalPages} 页
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
          ) : null}
        </div>
      )}
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
