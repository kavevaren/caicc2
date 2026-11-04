import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Download, FileText, MoreVertical, Pencil, Plus, Search, Trash2 } from "lucide-react";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorBox } from "../components/ui/ErrorBox";
import { ApiError, api, downloadDocumentMd, qs } from "../lib/api";
import { usePageAction } from "../lib/pageAction";
import { useI18n } from "../lib/i18n";
import { useDate } from "../lib/date";
import { useFetch } from "../lib/useFetch";
import type { Document, DocumentList, ProjectDetail, ProjectDoc, ProjectItem, Subject } from "../lib/types";

/**
 * Perpustakaan (redesign §5): search + subject chips, folder-shaped project
 * cards (two paper titles each, "Kosong" when empty), a dashed
 * "Proyek baru" card, and the "Diperbarui terakhir" table.
 */
export default function LibraryPage() {
  const { t } = useI18n();
  const { relative } = useDate();
  const nav = useNavigate();

  const [q, setQ] = useState("");
  const [qd, setQd] = useState("");
  const [subject, setSubject] = useState(0);
  const [page, setPage] = useState(1);
  const [menuFor, setMenuFor] = useState<number | null>(null);

  useEffect(() => {
    const id = setTimeout(() => setQd(q), 300);
    return () => clearTimeout(id);
  }, [q]);

  useEffect(() => {
    setPage(1);
  }, [qd, subject]);

  const docs = useFetch<DocumentList>(
    () => api.get(`documents${qs({ q: qd || undefined, subject: subject || undefined, kind: "summary", page })}`),
    [qd, subject, page],
  );
  const subjects = useFetch<{ items: Subject[] }>(() => api.get("subjects"), []);
  const projects = useFetch<{ items: ProjectItem[] }>(() => api.get("projects"), []);

  // The projects list carries no paper titles: fetch each project detail once
  // (there are few projects) to show up to two titles per folder card.
  const projKey = projects.data ? projects.data.items.map((p) => p.id).join(",") : "";
  const projDocs = useFetch<Record<number, ProjectDoc[]>>(async () => {
    const list = projects.data?.items ?? [];
    const out: Record<number, ProjectDoc[]> = {};
    await Promise.all(
      list.map(async (p) => {
        try {
          const d = await api.get<ProjectDetail>(`projects/${p.id}`);
          out[p.id] = d.docs;
        } catch {
          out[p.id] = [];
        }
      }),
    );
    return out;
  }, [projKey]);

  const [creating, setCreating] = useState(false);
  const [projTitle, setProjTitle] = useState("");
  const [projBusy, setProjBusy] = useState(false);
  const [projError, setProjError] = useState("");

  const createProject = async () => {
    if (projBusy || !projTitle.trim()) return;
    setProjBusy(true);
    setProjError("");
    try {
      await api.post("projects", { title: projTitle.trim() });
      setCreating(false);
      setProjTitle("");
      projects.reload();
    } catch (err) {
      setProjError(err instanceof ApiError ? `errors.${err.code}` : "errors.network_error");
    } finally {
      setProjBusy(false);
    }
  };

  useEffect(() => {
    if (menuFor === null) return;
    const close = () => setMenuFor(null);
    document.addEventListener("click", close);
    return () => document.removeEventListener("click", close);
  }, [menuFor]);

  const act = async (doc: Document, action: "open" | "rename" | "download" | "delete") => {
    setMenuFor(null);
    if (action === "open") nav(`/library/${doc.id}`);
    if (action === "rename") {
      const name = window.prompt(t("library.renamePrompt"), doc.title);
      if (name && name.trim()) {
        try {
          await api.patch(`documents/${doc.id}`, { title: name.trim() });
          docs.reload();
        } catch {
          // the toast-less lean app shows errors per page; a failed rename just keeps the old title
        }
      }
    }
    if (action === "download") {
      try {
        await downloadDocumentMd(doc.id, doc.title);
      } catch {
        // ignore: the browser surfaces a failed fetch as no download
      }
    }
    if (action === "delete") {
      if (window.confirm(t("library.deleteConfirm"))) {
        try {
          await api.del(`documents/${doc.id}`);
          if (docs.data && docs.data.items.length === 1 && page > 1) setPage(page - 1);
          else docs.reload();
        } catch {
          // ownership or network failure: the row simply stays
        }
      }
    }
  };

  const items = docs.data?.items ?? [];
  const pages = docs.data?.pages ?? 1;
  const empty = docs.data?.total === 0;

  usePageAction(
    <Button
      variant="primary"
      icon={<Plus className="i" size={16} aria-hidden="true" />}
      onClick={() => {
        setCreating(true);
        setProjError("");
      }}
    >
      {t("project.new")}
    </Button>,
  );

  const menu = (doc: Document) => (
    <div className="menu-wrap">
      <button
        type="button"
        className="menu-btn"
        aria-label={t("common.open")}
        aria-expanded={menuFor === doc.id}
        onClick={(e) => {
          e.stopPropagation();
          setMenuFor(menuFor === doc.id ? null : doc.id);
        }}
      >
        <MoreVertical className="i" aria-hidden="true" />
      </button>
      {menuFor === doc.id && (
        <div className="menu-pop" onClick={(e) => e.stopPropagation()}>
          <button type="button" onClick={() => void act(doc, "open")}>
            {t("library.menuOpen")}
          </button>
          <button type="button" onClick={() => void act(doc, "rename")}>
            <Pencil className="i" size={14} aria-hidden="true" />
            {t("library.menuRename")}
          </button>
          <button type="button" onClick={() => void act(doc, "download")}>
            <Download className="i" size={14} aria-hidden="true" />
            {t("library.menuDownload")}
          </button>
          <button type="button" className="danger" onClick={() => void act(doc, "delete")}>
            <Trash2 className="i" size={14} aria-hidden="true" />
            {t("library.menuDelete")}
          </button>
        </div>
      )}
    </div>
  );

  return (
    <>
      <div className="toolbar">
        <div className="search">
          <Search className="i" aria-hidden="true" />
          <input
            className="field-input"
            placeholder={t("common.search")}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            aria-label={t("common.search")}
          />
        </div>
        <div className="chips-row" role="group" aria-label={t("summarize.subject")}>
          <button type="button" className="chip-btn" aria-pressed={subject === 0} onClick={() => setSubject(0)}>
            {t("common.all")}
          </button>
          {(subjects.data?.items ?? []).map((s) => (
            <button
              key={s.id}
              type="button"
              className="chip-btn"
              aria-pressed={subject === s.id}
              onClick={() => setSubject(s.id)}
            >
              {s.name}
            </button>
          ))}
        </div>
      </div>

      <Card title={t("project.title")}>
        <p className="meta">{t("project.sectionMeta")}</p>
        {projects.error ? (
          <ErrorBox code={projects.error} onRetry={projects.reload} />
        ) : (
          <>
            {creating && (
              <form
                className="proj-new-form"
                onSubmit={(e) => {
                  e.preventDefault();
                  void createProject();
                }}
              >
                <input
                  className="field-input"
                  value={projTitle}
                  onChange={(e) => setProjTitle(e.target.value)}
                  placeholder={t("project.namePlaceholder")}
                  aria-label={t("project.namePlaceholder")}
                  maxLength={150}
                  autoFocus
                />
                <div className="form-actions">
                  <Button variant="primary" type="submit" disabled={projBusy || !projTitle.trim()}>
                    {t("project.create")}
                  </Button>
                  <Button
                    type="button"
                    onClick={() => {
                      setCreating(false);
                      setProjTitle("");
                      setProjError("");
                    }}
                  >
                    {t("project.cancel")}
                  </Button>
                </div>
                {projError && (
                  <p className="form-error" role="alert">
                    {t(projError)}
                  </p>
                )}
              </form>
            )}
            <div className="projects-grid">
              {(projects.data?.items ?? []).map((p, i) => {
                const papers = projDocs.data?.[p.id] ?? [];
                return (
                  <Link key={p.id} to={`/projects/${p.id}`} className="folder-card">
                    <span className={`fc-tab c${i % 4}`} aria-hidden="true" />
                    <span className="fc-papers" aria-hidden="true">
                      {papers.length === 0 ? (
                        <span className="fc-empty">{t("project.emptyFolder")}</span>
                      ) : (
                        papers.slice(0, 2).map((doc) => (
                          <span key={doc.id} className="fc-paper">
                            {doc.title}
                          </span>
                        ))
                      )}
                    </span>
                    <span className="fc-name">{p.title}</span>
                    <span className="fc-meta">{t("project.docs", { n: p.doc_count })} · {t("project.updated", { time: relative(p.updated_at) })}</span>
                  </Link>
                );
              })}
              <button type="button" className="folder-card new" onClick={() => setCreating(true)}>
                <span className="fc-plus" aria-hidden="true">
                  <Plus size={20} />
                </span>
                <b>{t("project.new")}</b>
                <span className="fc-meta">{t("project.newHint")}</span>
              </button>
            </div>
          </>
        )}
      </Card>

      {docs.error ? (
        <ErrorBox code={docs.error} onRetry={docs.reload} />
      ) : docs.loading ? (
        <Card className="sk-card" aria-busy="true">
          <span className="skeleton" />
          <span className="skeleton" />
          <span className="skeleton" />
          <span className="skeleton" />
        </Card>
      ) : empty && !qd ? (
        <Card>
          <EmptyState
            title={t("library.empty")}
            body={t("library.emptyBody")}
            action={
              <Link to="/summarize" className="btn btn-primary">
                {t("library.emptyCta")}
              </Link>
            }
          />
        </Card>
      ) : empty ? (
        <Card>
          <EmptyState title={t("library.noResults")} />
        </Card>
      ) : (
        <Card title={t("library.tableTitle")}>
          <table className="lib-table">
            <thead>
              <tr>
                <th>{t("library.titleCol")}</th>
                <th>{t("library.projectCol")}</th>
                <th>{t("library.formCol")}</th>
                <th>{t("library.updatedCol")}</th>
                <th aria-hidden="true" />
              </tr>
            </thead>
            <tbody>
              {items.map((doc) => (
                <tr key={doc.id}>
                  <td>
                    <span className="lt-title">
                      <span className="lt-ic" aria-hidden="true">
                        <FileText className="i" />
                      </span>
                      <Link to={`/library/${doc.id}`}>{doc.title}</Link>
                    </span>
                  </td>
                  <td className="lt-cell">{doc.project ?? "—"}</td>
                  <td className="lt-cell">
                    <span className={`chip${doc.kind === "summary" ? " kelas" : ""}`}>{t(`library.kind.${doc.kind}`)}</span>
                  </td>
                  <td className="lt-cell">{relative(doc.updated_at ?? doc.created_at)}</td>
                  <td>{menu(doc)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {pages > 1 && (
            <div className="pager">
              <Button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                {t("common.prev")}
              </Button>
              <span className="count">{t("common.pageOf", { page, pages })}</span>
              <Button disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>
                {t("common.next")}
              </Button>
            </div>
          )}
        </Card>
      )}
    </>
  );
}
