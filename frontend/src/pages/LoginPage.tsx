import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, saveAuthUsername, setAuthToken } from "../api";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isRegister, setIsRegister] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      if (isRegister) {
        await api.post("/auth/register", { username, password });
      }
      const res = await api.post("/auth/login", { username, password });
      const token = res.data.access_token as string;
      localStorage.setItem("token", token);
      saveAuthUsername(username);
      setAuthToken(token);
      navigate("/practice", { replace: true });
    } catch (err) {
      setError("登录或注册失败，请检查用户名密码");
    }
  };

  return (
    <div className="card">
      <h2>{isRegister ? "注册并登录" : "登录"}</h2>
      <form onSubmit={submit} className="form">
        <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="用户名" />
        <input
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="密码"
          type="password"
        />
        <button type="submit">提交</button>
      </form>
      <button className="link-btn" onClick={() => setIsRegister((v) => !v)}>
        {isRegister ? "已有账号，去登录" : "没有账号，先注册"}
      </button>
      {error ? <p className="error">{error}</p> : null}
    </div>
  );
}
