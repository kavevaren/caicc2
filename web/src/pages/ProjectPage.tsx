import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ChevronDown, ChevronUp, Download, FileText, Folder, MessageCircle, Pencil, Plus, Trash2, X } from "lucide-react";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { ErrorBox } from "../components/ui/ErrorBox";
import { ApiError, api, downloadProjectMd, qs } from "../lib/api";
import { useI18n } from "../lib/i18n";
import { useDate } from "../lib/date";
import { useFetch } from "../lib/useFetch";
import type { Document, ProjectDetail } from "../lib/types";

export default function ProjectPage() {
  const { id } = useParams();
  const { t } = useI18n();
  const { relative } = useDate();
  const nav = useNavigate();
  const projId = Number(id);

  const proj = useFetch<ProjectDetail>(() => api.get(`projects/${projId}`), [projId]);
  const docs = useFetch<{ items: Document[] }>(() => api.get(`documents${qs({ kind: "summary" })}`), []);

  const [picking, setPicking] = useState(false);
  const [selected, setSelected] = useState<number[]>([]);
  const [addBusy, setAddBusy] = useState(false);
  const [addError, setAddError] = useState("");
  const [exportBusy, setExportBusy] = useState(false);
  const [askBusy, setAskBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [renameBusy, setRenameBusy] = useState(false);

  if (proj.error) {
    return <ErrorBox code={proj.error} onRetry={proj.reload} />;
  }

  if (proj.loading || !proj.data) {
    return (
      <Card className="sk-card" aria-busy="true">
        <span className="skeleton" />
        <span className="skeleton" />
        <span className="skeleton" />
        <span className="skeleton" />
      </Card>
    );
  }

  const p = proj.data;
  const inProject = new Set(p.docs.map((d) => d.id));
  const candidates = (docs.data?.items ?? []).filter((d) => !inProject.has(d.id));

  const togglePick = (docId: number) => {
    setSelected((s) => (s.includes(docId) ? s.filter((x) => x !== docId) : [...s, docId]));
  };

  const startRename = () => {
    setNewTitle(p.title);
    setEditing(true);
  };

  const saveRename = async () => {
    if (renameBusy || !newTitle.trim()) return;
    setRenameBusy(true);
    try {
      await api.patch(`projects/${projId}`, { title: newTitle.trim() });
      proj.reload();
      setEditing(false);
    } catch {
      setEditing(false);
    } finally {
      setRenameBusy(false);
    }
  };

  const move = async (docId: number, dir: -1 | 1) => {
    const ids = p.docs.map((d) => d.id);
    const i = ids.indexOf(docId);
    const j = i + dir;
    if (j < 0 || j >= ids.length) return;
    [ids[i], ids[j]] = [ids[j], ids[i]];
    try {
      await api.post(`projects/${projId}/order`, { document_ids: ids });
      proj.reload();
    } catch {
      // the order stays; no toast in the lean app
    }
  };

  const removeDoc = async (docId: number) => {
    try {
      await api.del(`projects/${projId}/documents/${docId}`);
      proj.reload();
    } catch {
      // the row simply stays
    }
  };

  const addSelected = async () => {
    if (addBusy || selected.length === 0) return;
    setAddBusy(true);
    setAddError("");
    try {
      for (const docId of selected) {
        await api.post(`projects/${projId}/documents`, { document_id: docId });
      }
      setSelected([]);
      setPicking(false);
      proj.reload();
    } catch (err) {
      setAddError(err instanceof ApiError ? `errors.${err.code}` : "errors.network_error");
    } finally {
      setAddBusy(false);
    }
  };

  const exportMd = async () => {
    setExportBusy(true);
    try {
      await downloadProjectMd(projId, p.title);
    } catch {
      // the browser surfaces a failed fetch as no download
    } finally {
      setExportBusy(false);
    }
  };

  const askProject = async () => {
    if (askBusy) return;
    setAskBusy(true);
    try {
      const c = await api.post<{ id: number }>("chats", { project_id: projId });
      nav(`/chat/${c.id}`);
    } catch {
      setAskBusy(false);
    }
  };

  const removeProject = async () => {
    if (window.confirm(t("project.deleteConfirm"))) {
      try {
        await api.del(`projects/${projId}`);
        nav("/library", { replace: true });
      } catch {
        // the project stays
      }
    }
  };

  return (
    <div className="proj-open">
      {/* BUG-19: the project detail page had no way back to the library */}
      <p className="back">
        <Link to="/library">{t("project.back")}</Link>
      </p>
      <Card>
        <div className="proj-head">
          <span className="proj-folder" aria-hidden="true">
            <Folder className="i" />
          </span>
          {editing ? (
            <form
              className="proj-rename"
              onSubmit={(e) => {
                e.preventDefault();
                void saveRename();
              }}
            >
              <input
                className="field-input"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                aria-label={t("project.namePlaceholder")}
                maxLength={150}
                autoFocus
              />
              <Button type="submit" disabled={renameBusy || !newTitle.trim()}>
                {t("project.create")}
              </Button>
              <Button
                type="button"
                variant="ghost"
                onClick={() => setEditing(false)}
                icon={<X className="i" size={16} aria-hidden="true" />}
              />
            </form>
          ) : (
            <>
              <h2>{p.title}</h2>
              {p.subject && <span className="chip">{p.subject}</span>}
              <button type="button" className="icon-btn" onClick={startRename} aria-label={t("library.menuRename")}>
                <Pencil className="i" size={16} aria-hidden="true" />
              </button>
            </>
          )}
          <Button variant="primary" className="proj-add" icon={<Plus className="i" size={16} aria-hidden="true" />} onClick={() => setPicking((v) => !v)}>
            {t("project.addSummary")}
          </Button>
        </div>

        {picking && (
          <div className="proj-picker">
            {candidates.length === 0 ? (
              <p className="meta">{t("project.pickerEmpty")}</p>
            ) : (
              <ul className="pick-list">
                {candidates.map((d) => (
                  <li key={d.id}>
                    <label className="pick-row">
                      <input
                        type="checkbox"
                        checked={selected.includes(d.id)}
                        onChange={() => togglePick(d.id)}
                        aria-label={d.title}
                      />
                      <span className="pick-name">{d.title}</span>
                      {d.subject && <span className="chip">{d.subject}</span>}
                    </label>
                  </li>
                ))}
              </ul>
            )}
            <div className="form-actions">
              <Button disabled={addBusy || selected.length === 0} onClick={() => void addSelected()}>
                {t("project.addSelected")} ({selected.length})
              </Button>
              <Button
                variant="ghost"
                onClick={() => {
                  setPicking(false);
                  setSelected([]);
                  setAddError("");
                }}
              >
                {t("project.cancel")}
              </Button>
            </div>
            {addError && (
              <p className="form-error" role="alert">
                {t(addError)}
              </p>
            )}
          </div>
        )}

        {p.docs.length === 0 ? (
          <p className="meta proj-empty">{t("project.emptyDocs")}</p>
        ) : (
          <ul className="pdoc-list">
            {p.docs.map((d, i) => (
              <li key={d.id} className="pdoc-row">
                <span className="kind-ic" aria-hidden="true">
                  <FileText className="i" />
                </span>
                <div className="doc-main">
                  <Link className="doc-title" to={`/library/${d.id}`}>
                    {d.title}
                  </Link>
                  <div className="meta">
                    {d.subject && <span className="chip">{d.subject}</span>}
                    <span>{t("project.updated", { time: relative(d.added_at) })}</span>
                  </div>
                </div>
                <div className="pdoc-actions">
                  <button type="button" className="icon-btn" aria-label={t("project.moveUp")} disabled={i === 0} onClick={() => void move(d.id, -1)}>
                    <ChevronUp className="i" size={16} aria-hidden="true" />
                  </button>
                  <button type="button" className="icon-btn" aria-label={t("project.moveDown")} disabled={i === p.docs.length - 1} onClick={() => void move(d.id, 1)}>
                    <ChevronDown className="i" size={16} aria-hidden="true" />
                  </button>
                  <button type="button" className="icon-btn danger" aria-label={t("project.remove")} onClick={() => void removeDoc(d.id)}>
                    <X className="i" size={16} aria-hidden="true" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title={t("project.statsTitle")} className="side-stat">
        <div className="s">
          <span className="meta">{t("project.statsDocs")}</span>
          <b>{p.docs.length}</b>
        </div>
        <div className="s">
          <span className="meta">{t("project.statsSubject")}</span>
          <span className="s-val">{p.subject ?? "—"}</span>
        </div>
        <div className="s">
          <span className="meta">{t("project.statsUpdated")}</span>
          <span className="s-val">{relative(p.updated_at)}</span>
        </div>
        <Button
          icon={<MessageCircle className="i" size={16} aria-hidden="true" />}
          onClick={() => void askProject()}
          disabled={askBusy}
        >
          {t("project.ask")}
        </Button>
        <Button icon={<Download className="i" size={16} aria-hidden="true" />} onClick={() => void exportMd()} disabled={exportBusy || p.docs.length === 0}>
          {t("project.export")}
        </Button>
        <Button variant="danger" icon={<Trash2 className="i" size={16} aria-hidden="true" />} onClick={() => void removeProject()}>
          {t("project.delete")}
        </Button>
      </Card>
    </div>
  );
}
