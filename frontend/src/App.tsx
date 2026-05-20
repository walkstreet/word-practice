import { NavLink, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { clearAuthUsername, loadAuthUsername, loadToken, setAuthToken } from "./api";
import LoginPage from "./pages/LoginPage";
import VocabBookPage from "./pages/VocabBookPage";
import PracticePage from "./pages/PracticePage";
import PracticeHistoryPage from "./pages/PracticeHistoryPage";
import WrongBookPage from "./pages/WrongBookPage";
import StatsPage from "./pages/StatsPage";
import SettingsPage from "./pages/SettingsPage";
import { UiPreferencesProvider, useUiPreferences } from "./uiPreferences";

function Layout({ children }: { children: JSX.Element }) {
  const navigate = useNavigate();
  const token = loadToken();
  const username = loadAuthUsername();
  const { showPhonetic, toggleShowPhonetic } = useUiPreferences();

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  const logout = () => {
    localStorage.removeItem("token");
    clearAuthUsername();
    setAuthToken(null);
    navigate("/login", { replace: true });
  };

  return (
    <div className="container">
      <header className="header">
        <div className="header-bar">
          <h1 className="brand">Word Practice</h1>
          <div className="header-account">
            {username ? (
              <span className="nav-user" title={username}>
                {username}
              </span>
            ) : null}
            <button type="button" className="ghost-btn ghost-btn-compact" onClick={logout}>
              退出
            </button>
          </div>
        </div>
        <nav className="nav-wrap">
          <div className="nav-links">
            <NavLink to="/practice" className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
              练习
            </NavLink>
            <NavLink to="/vocab" className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
              单词本
            </NavLink>
            <NavLink to="/wrongbook" className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
              错题本
            </NavLink>
            <NavLink to="/history" className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
              练习历史
            </NavLink>
            <NavLink to="/stats" className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
              统计
            </NavLink>
            <NavLink to="/settings" className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
              设置
            </NavLink>
          </div>
          <div className="nav-actions">
            <button type="button" className="ghost-btn" onClick={toggleShowPhonetic}>
              音标: {showPhonetic ? "开" : "关"}
            </button>
          </div>
        </nav>
      </header>
      <main>{children}</main>
    </div>
  );
}

export default function App() {
  const token = loadToken();
  setAuthToken(token);

  return (
    <UiPreferencesProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/practice" element={<Layout><PracticePage /></Layout>} />
        <Route path="/vocab" element={<Layout><VocabBookPage /></Layout>} />
        <Route path="/import" element={<Navigate to="/vocab" replace />} />
        <Route path="/wrongbook" element={<Layout><WrongBookPage /></Layout>} />
        <Route path="/history" element={<Layout><PracticeHistoryPage /></Layout>} />
        <Route path="/stats" element={<Layout><StatsPage /></Layout>} />
        <Route path="/settings" element={<Layout><SettingsPage /></Layout>} />
        <Route path="*" element={<Navigate to={token ? "/practice" : "/login"} replace />} />
      </Routes>
    </UiPreferencesProvider>
  );
}
