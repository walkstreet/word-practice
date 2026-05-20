import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useUiPreferences } from "../uiPreferences";
import { displayGroupName, GROUP_FILTER_ALL, GROUP_FILTER_UNGROUPED } from "../vocabGroups";

type GroupStat = {
  name: string;
  count: number;
};

export default function SettingsPage() {
  const { practiceVocabGroup, setPracticeVocabGroup } = useUiPreferences();
  const [groupDraft, setGroupDraft] = useState(practiceVocabGroup);
  const [groups, setGroups] = useState<GroupStat[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [manageError, setManageError] = useState("");
  const [createName, setCreateName] = useState("");
  const [renameFrom, setRenameFrom] = useState("");
  const [renameTo, setRenameTo] = useState("");
  const [deleteFrom, setDeleteFrom] = useState("");
  const [deleteTarget, setDeleteTarget] = useState(GROUP_FILTER_UNGROUPED);
  const [saving, setSaving] = useState(false);
  const [manageOpen, setManageOpen] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");

  const loadGroups = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.get("/vocab/groups");
      const list = Array.isArray(res.data?.list) ? (res.data.list as GroupStat[]) : [];
      setGroups(list);
    } catch {
      setError("加载分组失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadGroups();
  }, []);

  const namedGroups = useMemo(
    () =>
      groups
        .map((group) => (group.name || "").trim())
        .filter(Boolean)
        .sort((a, b) => a.localeCompare(b, "zh-CN")),
    [groups],
  );

  const options = useMemo(() => {
    const named = groups
      .map((group) => (group.name || "").trim())
      .filter(Boolean)
      .sort((a, b) => a.localeCompare(b, "zh-CN"));
    const extras = [practiceVocabGroup, groupDraft]
      .map((x) => (x || "").trim())
      .filter(
        (x) =>
          !!x &&
          x !== GROUP_FILTER_ALL &&
          x !== GROUP_FILTER_UNGROUPED &&
          !named.includes(x),
      );
    return [GROUP_FILTER_ALL, GROUP_FILTER_UNGROUPED, ...named, ...extras];
  }, [groups, practiceVocabGroup, groupDraft]);

  useEffect(() => {
    setGroupDraft(practiceVocabGroup);
  }, [practiceVocabGroup]);

  useEffect(() => {
    if (renameFrom && !namedGroups.includes(renameFrom)) {
      setRenameFrom(namedGroups[0] || "");
    }
    if (deleteFrom && !namedGroups.includes(deleteFrom)) {
      setDeleteFrom(namedGroups[0] || "");
    }
  }, [namedGroups.join("|"), renameFrom, deleteFrom]);

  const savePracticeGroup = () => {
    setPracticeVocabGroup(groupDraft);
    setSaveMessage("已保存");
    window.setTimeout(() => setSaveMessage(""), 1500);
  };

  const submitCreate = async () => {
    if (!createName.trim()) {
      setManageError("请输入分组名");
      return;
    }
    setSaving(true);
    setManageError("");
    try {
      await api.post("/vocab/groups", { name: createName.trim() });
      setCreateName("");
      await loadGroups();
    } catch (err: unknown) {
      const detail =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
          : undefined;
      setManageError(typeof detail === "string" ? detail : "新增分组失败");
    } finally {
      setSaving(false);
    }
  };

  const submitRename = async () => {
    if (!renameFrom.trim()) {
      setManageError("请选择要重命名的分组");
      return;
    }
    if (!renameTo.trim()) {
      setManageError("请输入新分组名");
      return;
    }
    setSaving(true);
    setManageError("");
    try {
      await api.post("/vocab/groups/rename", {
        from_name: renameFrom.trim(),
        to_name: renameTo.trim(),
      });
      setRenameTo("");
      await loadGroups();
    } catch (err: unknown) {
      const detail =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
          : undefined;
      setManageError(typeof detail === "string" ? detail : "重命名失败");
    } finally {
      setSaving(false);
    }
  };

  const submitDelete = async () => {
    if (!deleteFrom.trim()) {
      setManageError("请选择要删除的分组");
      return;
    }
    setSaving(true);
    setManageError("");
    try {
      await api.post("/vocab/groups/delete", {
        name: deleteFrom.trim(),
        target: deleteTarget,
      });
      await loadGroups();
    } catch (err: unknown) {
      const detail =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
          : undefined;
      setManageError(typeof detail === "string" ? detail : "删除分组失败");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="card settings-card">
      <h2>设置</h2>
      <div className="settings-section">
        <h3 className="settings-section-title">做题设置</h3>
        <p className="settings-desc">选择普通练习的词汇范围（错题再练不受影响）。</p>
        <label className="settings-field">
          做题词汇组别
          <select
            className="app-select"
            value={groupDraft}
            onChange={(e) => {
              setGroupDraft(e.target.value);
              setSaveMessage("");
            }}
          >
            {options.map((value) => (
              <option key={value} value={value}>
                {displayGroupName(value)}
              </option>
            ))}
          </select>
        </label>
        <div className="settings-actions settings-actions-inline">
          <button
            type="button"
            className="primary-btn"
            onClick={savePracticeGroup}
            disabled={groupDraft === practiceVocabGroup}
          >
            保存设置
          </button>
          {groupDraft !== practiceVocabGroup ? <span className="settings-meta">有未保存修改</span> : null}
          {saveMessage ? <span className="success">{saveMessage}</span> : null}
        </div>
      </div>
      <div className="settings-section">
        <h3 className="settings-section-title">分组管理</h3>
        <div className="settings-actions settings-actions-inline">
          <button
            type="button"
            className="primary-btn"
            onClick={() => setManageOpen(true)}
          >
            管理分组
          </button>
        </div>
        <div className="settings-group-list">
          <strong>当前分组：</strong>
          <span>
            {groups.length > 0
              ? groups.map((group) => `${displayGroupName(group.name)}(${group.count})`).join("、")
              : "暂无分组"}
          </span>
        </div>
      </div>
      {loading ? <p className="settings-meta">分组加载中…</p> : null}
      {error ? <p className="error">{error}</p> : null}
      {manageError ? <p className="error">{manageError}</p> : null}

      {manageOpen ? (
        <div
          className="modal-backdrop"
          role="presentation"
          onMouseDown={() => setManageOpen(false)}
        >
          <div
            className="modal-panel modal-wide settings-manage-modal"
            role="dialog"
            aria-labelledby="settings-group-manage-title"
            onMouseDown={(e) => e.stopPropagation()}
          >
            <div className="modal-head">
              <h3 id="settings-group-manage-title">分组管理</h3>
              <button
                type="button"
                className="modal-close"
                onClick={() => setManageOpen(false)}
                aria-label="关闭"
              >
                ×
              </button>
            </div>
            <div className="settings-group-grid">
              <label className="settings-field">
                新增分组
                <div className="settings-inline-row">
                  <input
                    value={createName}
                    onChange={(e) => setCreateName(e.target.value)}
                    placeholder="如 CET6 / 商务英语"
                  />
                  <button
                    type="button"
                    className="ghost-btn"
                    onClick={submitCreate}
                    disabled={saving}
                  >
                    新增
                  </button>
                </div>
              </label>

              <label className="settings-field">
                重命名分组
                <div className="settings-inline-row settings-inline-row-wide">
                  <select
                    className="app-select"
                    value={renameFrom}
                    onChange={(e) => setRenameFrom(e.target.value)}
                    disabled={namedGroups.length === 0 || saving}
                  >
                    <option value="">请选择</option>
                    {namedGroups.map((name) => (
                      <option key={`rename-${name}`} value={name}>
                        {name}
                      </option>
                    ))}
                  </select>
                  <input
                    value={renameTo}
                    onChange={(e) => setRenameTo(e.target.value)}
                    placeholder="新分组名"
                  />
                  <button
                    type="button"
                    className="ghost-btn"
                    onClick={submitRename}
                    disabled={namedGroups.length === 0 || saving}
                  >
                    保存
                  </button>
                </div>
              </label>

              <label className="settings-field">
                删除分组并迁移词条
                <div className="settings-inline-row settings-inline-row-wide">
                  <select
                    className="app-select"
                    value={deleteFrom}
                    onChange={(e) => setDeleteFrom(e.target.value)}
                    disabled={namedGroups.length === 0 || saving}
                  >
                    <option value="">请选择</option>
                    {namedGroups.map((name) => (
                      <option key={`delete-${name}`} value={name}>
                        {name}
                      </option>
                    ))}
                  </select>
                  <select
                    className="app-select"
                    value={deleteTarget}
                    onChange={(e) => setDeleteTarget(e.target.value)}
                    disabled={saving}
                  >
                    <option value={GROUP_FILTER_UNGROUPED}>迁移到未分组</option>
                    {namedGroups
                      .filter((name) => name !== deleteFrom)
                      .map((name) => (
                        <option key={`target-${name}`} value={name}>
                          迁移到 {name}
                        </option>
                      ))}
                  </select>
                  <button
                    type="button"
                    className="ghost-btn danger"
                    onClick={submitDelete}
                    disabled={namedGroups.length === 0 || saving}
                  >
                    删除
                  </button>
                </div>
              </label>
            </div>
            {manageError ? <p className="error">{manageError}</p> : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
