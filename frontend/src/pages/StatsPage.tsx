import { useEffect, useState } from "react";
import { api } from "../api";

type Stats = {
  total_answered: number;
  correct_count: number;
  wrong_count: number;
  accuracy: number;
};

export default function StatsPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get("/stats")
      .then((res) => setStats(res.data))
      .catch(() => setError("加载统计失败"));
  }, []);

  return (
    <div className="card">
      <h2>统计</h2>
      {error ? <p className="error">{error}</p> : null}
      {stats ? (
        <div className="result">
          <p>总提交数: {stats.total_answered}</p>
          <p>正确数: {stats.correct_count}</p>
          <p>错误数: {stats.wrong_count}</p>
          <p>正确率: {(stats.accuracy * 100).toFixed(2)}%</p>
        </div>
      ) : null}
    </div>
  );
}
