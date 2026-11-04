import { lazy, Suspense, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Atom, CalendarPlus, Download, FileText, MessagesSquare, Pencil, Trash2 } from "lucide-react";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorBox } from "../components/ui/ErrorBox";
import { Tabs } from "../components/ui/Tabs";
import { ApiError, api, downloadDocumentMd, qs } from "../lib/api";
import { useI18n } from "../lib/i18n";
import { formatSize, useDate } from "../lib/date";
import { useFetch } from "../lib/useFetch";
import type { Document, ProjectItem } from "../lib/types";

const Markdown = lazy(() => import("../components/ui/Markdown"));

export default function DocumentViewPage() {
  const { id } = useParams();
  const { t } = useI18n();
  const { fullDate } = useDate();
  const nav = useNavigate();
  const docId = Number(id);

  const doc = useFetch<Document>(() => api.get(`documents/${docId}`), [docId]);
  const [tab, setTab] = useState("summary");
  const [editing, setEditing] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [addBusy, setAddBusy] = useState(false);
  const [addedCount, setAddedCount] = useState(0);
  const [addError, setAddError] = useState("");
  const [projId, setProjId] = useState("");
  const [saveBusy, setSaveBusy] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [savedNote, setSavedNote] = useState("");
  const [tanyaBusy, setTanyaBusy] = useState(false);

  const projects = useFetch<{ items: ProjectItem[] }>(() => api.get("projects"), []);

  const startRename = () => {
    if (!doc.data) return;
    setNewTitle(doc.data.title);
    setEditing(true);
  };

  const saveRename = async () => {
    if (busy || !newTitle.trim()) return;
    setBusy(true);
    try {
      await api.patch(`documents/${docId}`, { title: newTitle.trim() });
      doc.reload();
      setEditing(false);
    } catch {
      setEditing(false);
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (window.confirm(t("library.deleteConfirm"))) {
      try {
        await api.del(`documents/${docId}`);
        nav("/library", { replace: true });
      } catch {
        // the document stays; nothing more to do here
      }
    }
  };

  if (doc.error) {
    return <ErrorBox code={doc.error} onRetry={doc.reload} />;
  }

  if (doc.loading || !doc.data) {
    return (
      <Card className="sk-card" aria-busy="true">
        <span className="skeleton" />
        <span className="skeleton" />
        <span className="skeleton" />
        <span className="skeleton" />
      </Card>
    );
  }

  const d = doc.data;
  const deadlines = d.extra?.deadlines ?? [];
  const warnings = d.extra?.warnings ?? [];
  const sources = d.source_files ?? [];
  const projectItems = projects.data?.items ?? [];

  // BUG-01: the server sends warning codes, never raw text — map each code
  // to a translated message; unknown codes fall back to a generic note.
  const warnMsg = (code: string): string => {
    const raw = t(`warnings.${code}`);
    return raw === `warnings.${code}` ? t("warnings.other") : raw;
  };

  const saveToProject = async () => {
    if (saveBusy || !projId) return;
    setSaveBusy(true);
    setSaveError("");
    setSavedNote("");
    try {
      await api.post(`projects/${projId}/documents`, { document_id: docId });
      setSavedNote(t("project.saved"));
    } catch (err) {
      setSaveError(err instanceof ApiError ? `errors.${err.code}` : "errors.network_error");
    } finally {
      setSaveBusy(false);
    }
  };

  const addToSchedule = async () => {
    if (addBusy || addedCount > 0) return;
    setAddBusy(true);
    setAddError("");
    try {
      for (const dl of deadlines) {
        await api.post("events", { title: dl.title, start_at: dl.start_at });
      }
      setAddedCount(deadlines.length);
    } catch (err) {
      setAddError(err instanceof ApiError ? `errors.${err.code}` : "errors.network_error");
    } finally {
      setAddBusy(false);
    }
  };

  // "Tanya Orvina": open a chat pre-scoped to this document's project.
  const tanya = async () => {
    if (tanyaBusy) return;
    setTanyaBusy(true);
    try {
      const body: { project_id?: number } = {};
      const pid = doc.data?.project_id;
      if (pid != null) body.project_id = pid;
      const c = await api.post<{ id: number }>("chats", body);
      nav(`/chat/${c.id}`);
    } catch {
      setTanyaBusy(false);
    }
  };

  return (
    <>
      <p className="back">
        <Link to="/library">{t("document.back")}</Link>
      </p>
      <div className="doc-head">
        <div className="doc-head-main">
          <h1 className="doc-title-h">{d.title}</h1>
          <div className="meta">
            {d.subject && <span className="chip">{d.subject}</span>}
            <span className="chip src">{t(`library.kind.${d.kind}`)}</span>
            <span>{fullDate(d.created_at)}</span>
          </div>
        </div>
        <div className="doc-actions">
          <Button
            variant="primary"
            icon={<Atom className="i" size={16} aria-hidden="true" />}
            onClick={() => void tanya()}
            disabled={tanyaBusy}
          >
            {t("document.tanya")}
          </Button>
          <Button
            icon={<MessagesSquare className="i" size={16} aria-hidden="true" />}
            onClick={() => nav(`/forum/ask${qs({ subject: d.subject_id ?? undefined, doc: d.id })}`)}
          >
            {t("document.askForum")}
          </Button>
          <Button icon={<Pencil className="i" size={16} aria-hidden="true" />} onClick={startRename}>
            {t("common.rename")}
          </Button>
          <Button
            icon={<Download className="i" size={16} aria-hidden="true" />}
            onClick={() => void downloadDocumentMd(d.id, d.title).catch(() => {})}
          >
            {t("common.download")}
          </Button>
          <Button variant="danger" icon={<Trash2 className="i" size={16} aria-hidden="true" />} onClick={() => void remove()}>
            {t("common.delete")}
          </Button>
        </div>
      </div>

      {editing && (
        <div className="rename-row">
          <div className="field">
            <label className="field-label" htmlFor="newTitle">
              {t("library.renamePrompt")}
            </label>
            <input
              id="newTitle"
              className="field-input"
              value={newTitle}
              maxLength={150}
              onChange={(e) => setNewTitle(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void saveRename();
              }}
            />
          </div>
          <Button variant="primary" onClick={() => void saveRename()} disabled={busy || !newTitle.trim()}>
            {t("common.save")}
          </Button>
          <Button onClick={() => setEditing(false)} disabled={busy}>
            {t("common.cancel")}
          </Button>
        </div>
      )}

      <Card>
        <Tabs
          tabs={[
            { id: "summary", label: t("document.tabSummary") },
            { id: "sources", label: t("document.tabSources") },
          ]}
          value={tab}
          onChange={setTab}
        />
        {tab === "summary" ? (
          <div style={{ marginTop: 16 }}>
            <Suspense
              fallback={
                <div className="sk-card" aria-busy="true">
                  <span className="skeleton" />
                  <span className="skeleton" />
                  <span className="skeleton" />
                </div>
              }
            >
              <Markdown source={d.content_md} />
            </Suspense>
            {warnings.length > 0 && (
              <div className="warn-box" role="status">
                {warnings.map((w, i) => (
                  <p key={`${w}-${i}`} className="warn-line">
                    {warnMsg(w)}
                  </p>
                ))}
              </div>
            )}
          </div>
        ) : sources.length === 0 ? (
          <EmptyState title={t("document.sourcesEmpty")} />
        ) : (
          <div>
            <p className="field-label" style={{ marginTop: 12 }}>
              {t("document.files")}
            </p>
            {sources.map((s, i) => (
              <div key={`${s.name}-${i}`} className="src-row">
                <FileText className="i" size={16} aria-hidden="true" />
                <span className="name">{s.name}</span>
                {s.size_bytes != null && <span className="size">{formatSize(s.size_bytes)}</span>}
              </div>
            ))}
          </div>
        )}
      </Card>

      {deadlines.length > 0 && (
        <Card title={t("document.deadlines")}>
          <div>
            {deadlines.map((dl, i) => (
              <div key={`${dl.title}-${i}`} className="src-row">
                <span className="name">{dl.title}</span>
                <span className="size">{dl.start_at}</span>
              </div>
            ))}
            <p className="dl-note">{t("document.deadlineNote")}</p>
            {addedCount > 0 ? (
              <p className="dl-note ok">
                {t("document.addedToSchedule", { n: addedCount })}{" "}
                <Link to="/schedule">{t("schedule.view")}</Link>
              </p>
            ) : (
              <Button style={{ marginTop: 12 }} onClick={addToSchedule} disabled={addBusy} icon={<CalendarPlus className="i" size={16} aria-hidden="true" />}>
                {t("document.addSchedule")}
              </Button>
            )}
            {addError && (
              <p className="form-error" role="alert">
                {t(addError)}
              </p>
            )}
          </div>
        </Card>
      )}

      <Card title={t("project.saveTitle")}>
        {projects.error ? (
          <ErrorBox code={projects.error} onRetry={projects.reload} />
        ) : projectItems.length === 0 ? (
          <p className="meta">
            {t("project.saveToProjectEmpty")}{" "}
            <Link to="/library">{t("project.openProject")}</Link>
          </p>
        ) : (
          <div>
            <p className="meta">{t("project.saveHint")}</p>
            <div className="proj-save-row">
              <select
                className="field-input"
                value={projId}
                onChange={(e) => setProjId(e.target.value)}
                aria-label={t("project.saveTitle")}
              >
                <option value="" disabled>
                  {t("project.chooseProject")}
                </option>
                {projectItems.map((p) => (
                  <option key={p.id} value={String(p.id)}>
                    {p.title}
                  </option>
                ))}
              </select>
              <Button disabled={saveBusy || !projId} onClick={() => void saveToProject()}>
                {t("project.save")}
              </Button>
            </div>
            {savedNote && (
              <p className="dl-note ok" role="status">
                {savedNote}
              </p>
            )}
            {saveError && (
              <p className="form-error" role="alert">
                {t(saveError)}
              </p>
            )}
          </div>
        )}
      </Card>
    </>
  );
}
