import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { formatIpaForDisplay } from "../ipaDisplay";
import { resolvePosTranslationRows } from "../parsePosTranslation";

type SenseEditRow = { part_of_speech: string; meaning: string };

type VocabRow = {
  id: number;
  word: string;
  translation: string;
  phonetic: string;
  part_of_speech: string;
  senses?: { part_of_speech: string; meaning: string }[] | null;
};

type ImportResult = {
  total: number;
  success: number;
  failed: number;
  duplicated_skipped: number;
  errors: Array<{ line: number; reason: string; word?: string }>;
  duplicate_skips?: Array<{
    line: number;
    word: string;
    dedup_key?: string;
    reason: string;
    existing_id?: number;
    existing_word?: string;
  }>;
  request_words?: string[];
  inserted?: Array<{ line: number; id: number; word: string }>;
};

const SAMPLE_CSV_URL = "/sample-vocab.csv";

export default function VocabBookPage() {
  const [items, setItems] = useState<VocabRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [listError, setListError] = useState("");

  const [modalOpen, setModalOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [importError, setImportError] = useState("");

  const [editOpen, setEditOpen] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [editWord, setEditWord] = useState("");
  const [editPhonetic, setEditPhonetic] = useState("");
  const [editStructured, setEditStructured] = useState(false);
  const [editSenses, setEditSenses] = useState<SenseEditRow[]>([]);
  const [editTranslation, setEditTranslation] = useState("");
  const [editPartOfSpeech, setEditPartOfSpeech] = useState("");
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState("");
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(() => new Set());
  const [batchDeleting, setBatchDeleting] = useState(false);
  const headerCheckboxRef = useRef<HTMLInputElement>(null);

  const pageSize = 100;
  const pageIds = items.map((i) => i.id);
  const allOnPageSelected = pageIds.length > 0 && pageIds.every((id) => selectedIds.has(id));
  const someOnPageSelected = pageIds.some((id) => selectedIds.has(id));

  const loadList = useCallback(async () => {
    setLoading(true);
    setListError("");
    try {
      const res = await api.get("/vocab", { params: { page, page_size: pageSize, q: q.trim() || undefined } });
      setItems(res.data.list || []);
      setTotal(Number(res.data.total) || 0);
    } catch (err: unknown) {
      const detail =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: unknown }; status?: number } }).response?.data?.detail
          : undefined;
      const msg =
        typeof detail === "string"
          ? detail
          : Array.isArray(detail)
            ? detail.map((d: { msg?: string }) => d.msg || "").filter(Boolean).join("；") || "加载单词本失败"
            : "加载单词本失败";
      setListError(msg);
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [page, q]);

  useEffect(() => {
    loadList();
  }, [loadList]);

  useEffect(() => {
    const el = headerCheckboxRef.current;
    if (el) {
      el.indeterminate = someOnPageSelected && !allOnPageSelected;
    }
  }, [someOnPageSelected, allOnPageSelected, items.length]);

  const toggleSelectOne = (id: number) => {
    setSelectedIds((prev) => {
      const n = new Set(prev);
      if (n.has(id)) {
        n.delete(id);
      } else {
        n.add(id);
      }
      return n;
    });
  };

  const toggleSelectAllOnPage = () => {
    setSelectedIds((prev) => {
      const n = new Set(prev);
      if (allOnPageSelected) {
        pageIds.forEach((id) => n.delete(id));
      } else {
        pageIds.forEach((id) => n.add(id));
      }
      return n;
    });
  };

  const batchDelete = async () => {
    const ids = [...selectedIds];
    if (ids.length === 0) {
      return;
    }
    if (!window.confirm(`确定删除选中的 ${ids.length} 条词条？相关的练习记录与错题本会一并清除。`)) {
      return;
    }
    setBatchDeleting(true);
    setListError("");
    try {
      await api.post("/vocab/batch-delete", { ids });
      setSelectedIds(new Set());
      await loadList();
    } catch (err: unknown) {
      const detail =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
          : undefined;
      const msg = typeof detail === "string" ? detail : "批量删除失败";
      setListError(msg);
    } finally {
      setBatchDeleting(false);
    }
  };

  const openEdit = (item: VocabRow) => {
    setEditId(item.id);
    setEditWord(item.word);
    setEditPhonetic(item.phonetic || "");
    setEditError("");
    if (item.senses && item.senses.length > 0) {
      setEditStructured(true);
      setEditSenses(
        item.senses.map((s) => ({
          part_of_speech: s.part_of_speech || "",
          meaning: s.meaning || ""
        }))
      );
      setEditTranslation("");
      setEditPartOfSpeech("");
    } else {
      setEditStructured(false);
      setEditSenses([{ part_of_speech: "", meaning: "" }]);
      setEditTranslation(item.translation);
      setEditPartOfSpeech(item.part_of_speech || "");
    }
    setEditOpen(true);
  };

  const closeEdit = () => {
    setEditOpen(false);
    setEditId(null);
    setEditError("");
    setEditSaving(false);
  };

  const submitEdit = async (e: FormEvent) => {
    e.preventDefault();
    if (editId == null) {
      return;
    }
    const wordTrim = editWord.trim();
    if (!wordTrim) {
      setEditError("单词不能为空");
      return;
    }
    const validSenses = editStructured
      ? editSenses.filter((s) => (s.meaning || "").trim()).map((s) => ({
          part_of_speech: (s.part_of_speech || "").trim(),
          meaning: (s.meaning || "").trim()
        }))
      : [];
    if (editStructured && validSenses.length === 0) {
      setEditError("请至少填写一条义项（释义）");
      return;
    }
    if (!editStructured && !editTranslation.trim()) {
      setEditError("请填写释义");
      return;
    }
    setEditSaving(true);
    setEditError("");
    const payload = editStructured
      ? { word: wordTrim, phonetic: editPhonetic, senses: validSenses }
      : {
          word: wordTrim,
          phonetic: editPhonetic,
          translation: editTranslation.trim(),
          part_of_speech: editPartOfSpeech.trim()
        };
    try {
      await api.patch(`/vocab/${editId}`, payload);
      closeEdit();
      await loadList();
    } catch (err: unknown) {
      const res = err && typeof err === "object" && "response" in err ? (err as { response?: { data?: { detail?: unknown }; status?: number } }).response : undefined;
      const status = res?.status;
      const detail = res?.data?.detail;
      let msg = "保存失败";
      if (status === 409) {
        msg = typeof detail === "string" ? detail : "该单词已存在，与别的条目冲突";
      } else if (typeof detail === "string") {
        msg = detail;
      } else if (Array.isArray(detail)) {
        msg = detail.map((d: { msg?: string }) => d.msg || "").filter(Boolean).join("；") || msg;
      }
      setEditError(msg);
    } finally {
      setEditSaving(false);
    }
  };

  const deleteItem = async (item: VocabRow) => {
    if (!window.confirm(`确定删除「${item.word}」？相关的练习记录与错题本会一并清除。`)) {
      return;
    }
    setDeletingId(item.id);
    setListError("");
    try {
      await api.delete(`/vocab/${item.id}`);
      setSelectedIds((prev) => {
        const n = new Set(prev);
        n.delete(item.id);
        return n;
      });
      await loadList();
    } catch (err: unknown) {
      const detail =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
          : undefined;
      const msg = typeof detail === "string" ? detail : "删除失败";
      setListError(msg);
    } finally {
      setDeletingId(null);
    }
  };

  const closeModal = () => {
    setModalOpen(false);
    setFile(null);
    setImportResult(null);
    setImportError("");
  };

  const submitImport = async (e: FormEvent) => {
    e.preventDefault();
    if (!file) {
      setImportError("请先选择 CSV 文件");
      return;
    }
    setImportError("");
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await api.post("/vocab/import", formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });
      setImportResult(res.data);
      await loadList();
    } catch {
      setImportError("导入失败，请检查 CSV 是否包含 word、translation 列");
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="card vocab-book">
      <div className="vocab-book-head">
        <h2>单词本</h2>
        <div className="vocab-book-actions">
          <input
            className="search-input"
            type="search"
            placeholder="搜索单词或释义…"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setPage(1);
            }}
          />
          <button
            type="button"
            className="ghost-btn danger"
            disabled={selectedIds.size === 0 || batchDeleting || deletingId !== null || loading}
            onClick={() => batchDelete()}
          >
            {batchDeleting ? "删除中…" : `删除选中${selectedIds.size > 0 ? ` (${selectedIds.size})` : ""}`}
          </button>
          <button type="button" className="primary-btn" onClick={() => setModalOpen(true)}>
            导入 CSV
          </button>
        </div>
      </div>
      <p className="vocab-meta">
        共 {total} 条 · 每页 {pageSize} 条 · 第 {page} / {totalPages} 页
        {selectedIds.size > 0 ? ` · 已选 ${selectedIds.size} 条` : ""}
        {loading ? " · 加载中…" : ""}
      </p>
      {listError ? <p className="error">{listError}</p> : null}

      <div className="table-wrap">
        <table className="vocab-table">
          <thead>
            <tr>
              <th className="col-check">
                <input
                  ref={headerCheckboxRef}
                  type="checkbox"
                  className="table-checkbox"
                  checked={allOnPageSelected}
                  onChange={toggleSelectAllOnPage}
                  disabled={items.length === 0 || batchDeleting || deletingId !== null}
                  title="全选本页"
                  aria-label="全选本页"
                />
              </th>
              <th className="col-word">单词</th>
              <th className="col-ipa">音标</th>
              <th className="col-senses">词性与释义</th>
              <th className="col-actions">操作</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 && !loading ? (
              <tr>
                <td colSpan={5} style={{ textAlign: "center", color: "#6b7280" }}>
                  暂无词条，请点击「导入 CSV」添加
                </td>
              </tr>
            ) : null}
            {items.map((item) => {
              const rows = resolvePosTranslationRows(item.senses, item.part_of_speech, item.translation);
              return (
                <tr key={item.id}>
                  <td className="col-check">
                    <input
                      type="checkbox"
                      className="table-checkbox"
                      checked={selectedIds.has(item.id)}
                      onChange={() => toggleSelectOne(item.id)}
                      disabled={batchDeleting || deletingId !== null}
                      aria-label={`选择 ${item.word}`}
                    />
                  </td>
                  <td className="col-word">{item.word}</td>
                  <td className="col-ipa">{item.phonetic ? formatIpaForDisplay(item.phonetic) : "—"}</td>
                  <td className="col-senses">
                    <div className="sense-stack">
                      {rows.map((row, idx) => (
                        <div className="sense-line" key={`${item.id}-${idx}`}>
                          <span className="sense-pos">{row.pos}</span>
                          <span className="sense-meaning">{row.meaning}</span>
                        </div>
                      ))}
                    </div>
                  </td>
                  <td className="col-actions">
                    <div className="vocab-row-actions">
                      <button
                        type="button"
                        className="ghost-btn"
                        onClick={() => openEdit(item)}
                        disabled={deletingId !== null || batchDeleting}
                      >
                        编辑
                      </button>
                      <button
                        type="button"
                        className="ghost-btn danger"
                        onClick={() => deleteItem(item)}
                        disabled={deletingId !== null || batchDeleting}
                      >
                        {deletingId === item.id ? "删除中…" : "删除"}
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {total > 0 ? (
        <div className="pager">
          <button type="button" className="ghost-btn" disabled={page <= 1 || loading} onClick={() => setPage((p) => p - 1)}>
            上一页
          </button>
          <span className="pager-info">
            {page} / {totalPages}
          </span>
          <button
            type="button"
            className="ghost-btn"
            disabled={page >= totalPages || loading}
            onClick={() => setPage((p) => p + 1)}
          >
            下一页
          </button>
        </div>
      ) : null}

      {editOpen ? (
        <div className="modal-backdrop" role="presentation" onMouseDown={closeEdit}>
          <div
            className="modal-panel modal-wide"
            role="dialog"
            aria-labelledby="edit-vocab-title"
            onMouseDown={(e) => e.stopPropagation()}
          >
            <div className="modal-head">
              <h3 id="edit-vocab-title">编辑词条</h3>
              <button type="button" className="modal-close" onClick={closeEdit} aria-label="关闭">
                ×
              </button>
            </div>
            <form className="vocab-edit-grid modal-form" onSubmit={submitEdit}>
              <label>
                单词
                <input value={editWord} onChange={(e) => setEditWord(e.target.value)} required />
              </label>
              <label>
                音标（可含或不含 /…/）
                <input value={editPhonetic} onChange={(e) => setEditPhonetic(e.target.value)} placeholder="如 əˈbɪlɪti" />
              </label>
              {editStructured ? (
                <div>
                  <span style={{ fontSize: 13, color: "#4b5364" }}>多义项</span>
                  {editSenses.map((row, idx) => (
                    <div className="vocab-edit-sense-row" key={`sense-${editId}-${idx}`}>
                      <input
                        placeholder="词性 n."
                        value={row.part_of_speech}
                        onChange={(e) => {
                          const next = [...editSenses];
                          next[idx] = { ...next[idx], part_of_speech: e.target.value };
                          setEditSenses(next);
                        }}
                      />
                      <input
                        placeholder="释义"
                        value={row.meaning}
                        onChange={(e) => {
                          const next = [...editSenses];
                          next[idx] = { ...next[idx], meaning: e.target.value };
                          setEditSenses(next);
                        }}
                      />
                      <button
                        type="button"
                        className="ghost-btn"
                        disabled={editSenses.length <= 1}
                        onClick={() => setEditSenses((s) => s.filter((_, i) => i !== idx))}
                      >
                        删
                      </button>
                    </div>
                  ))}
                  <div className="vocab-edit-sense-actions">
                    <button
                      type="button"
                      className="ghost-btn"
                      onClick={() => setEditSenses((s) => [...s, { part_of_speech: "", meaning: "" }])}
                    >
                      添加义项
                    </button>
                    <button
                      type="button"
                      className="ghost-btn"
                      onClick={() => {
                        const merged = editSenses
                          .filter((s) => (s.meaning || "").trim())
                          .map((s) =>
                            (s.part_of_speech || "").trim()
                              ? `${(s.part_of_speech || "").trim()} ${(s.meaning || "").trim()}`
                              : (s.meaning || "").trim()
                          )
                          .join("；");
                        setEditStructured(false);
                        setEditTranslation(merged);
                        setEditPartOfSpeech("");
                        setEditSenses([{ part_of_speech: "", meaning: "" }]);
                      }}
                    >
                      改为整段释义
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <label>
                    词性（可选，CSV 风格可用分号分隔）
                    <input value={editPartOfSpeech} onChange={(e) => setEditPartOfSpeech(e.target.value)} placeholder="n." />
                  </label>
                  <label>
                    释义
                    <textarea
                      rows={4}
                      value={editTranslation}
                      onChange={(e) => setEditTranslation(e.target.value)}
                      placeholder="整段翻译 / 多词性可写 n. …；v. …"
                    />
                  </label>
                  <button
                    type="button"
                    className="ghost-btn"
                    onClick={() => {
                      setEditStructured(true);
                      setEditSenses(
                        editTranslation.trim()
                          ? [{ part_of_speech: editPartOfSpeech.trim() || "", meaning: editTranslation.trim() }]
                          : [{ part_of_speech: "", meaning: "" }]
                      );
                      setEditTranslation("");
                      setEditPartOfSpeech("");
                    }}
                  >
                    改为多义项编辑
                  </button>
                </>
              )}
              {editError ? <p className="error">{editError}</p> : null}
              <div className="modal-actions">
                <button type="button" className="ghost-btn" onClick={closeEdit} disabled={editSaving}>
                  取消
                </button>
                <button type="submit" className="primary-btn" disabled={editSaving}>
                  {editSaving ? "保存中…" : "保存"}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}

      {modalOpen ? (
        <div className="modal-backdrop" role="presentation" onMouseDown={closeModal}>
          <div className="modal-panel" role="dialog" aria-labelledby="import-title" onMouseDown={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <h3 id="import-title">导入词汇</h3>
              <button type="button" className="modal-close" onClick={closeModal} aria-label="关闭">
                ×
              </button>
            </div>
            <p className="modal-desc">
              CSV 第一行为表头，至少包含 <code>word</code>、<code>translation</code>；可选 <code>phonetic</code>、
              <code>part_of_speech</code>（或 <code>pos</code>）。多词性时可在 translation 中按「n. …；v. …」分段书写。
            </p>
            <p className="modal-sample">
              <a href={SAMPLE_CSV_URL} download="sample-vocab.csv">
                下载样例 CSV
              </a>
            </p>
            <form className="modal-form" onSubmit={submitImport}>
              <input
                type="file"
                accept=".csv"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
              {importError ? <p className="error">{importError}</p> : null}
              {importResult ? (
                <div className="result modal-result">
                  <p>总数: {importResult.total}</p>
                  <p>新增: {importResult.success}</p>
                  <p>失败行数: {importResult.errors?.length ?? 0}</p>
                  <p>重复跳过: {importResult.duplicated_skipped}</p>
                  {importResult.inserted && importResult.inserted.length > 0 ? (
                    <p className="import-inserted">
                      本次新增：
                      {importResult.inserted.map((x) => (
                        <span key={`${x.id}-${x.word}`}>
                          {" "}
                          <code>
                            id={x.id}「{x.word}」
                          </code>
                        </span>
                      ))}
                    </p>
                  ) : null}
                  {importResult.request_words && importResult.request_words.length > 0 ? (
                    <p className="import-request-words">
                      请求单词顺序：<code>{importResult.request_words.join(" · ")}</code>
                    </p>
                  ) : null}
                  {importResult.errors && importResult.errors.length > 0 ? (
                    <ul className="import-duplicate-list import-error-list">
                      {importResult.errors.map((e, i) => (
                        <li key={`err-${e.line}-${i}`}>
                          行 {e.line}
                          {e.word ? `「${e.word}」` : ""} — {e.reason}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                  {importResult.duplicate_skips && importResult.duplicate_skips.length > 0 ? (
                    <ul className="import-duplicate-list">
                      {importResult.duplicate_skips.map((d, i) => (
                        <li key={`${d.line}-${i}`}>
                          行 {d.line}「{d.word}」{d.dedup_key && d.dedup_key !== d.word ? `（键 ${d.dedup_key}）` : ""} —{" "}
                          {d.reason === "already in vocabulary"
                            ? `库中已有 (#${d.existing_id ?? "?"}「${d.existing_word ?? ""}」)`
                            : "本批重复"}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              ) : null}
              <div className="modal-actions">
                <button type="button" className="ghost-btn" onClick={closeModal}>
                  取消
                </button>
                <button type="submit" className="primary-btn">
                  开始导入
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  );
}
