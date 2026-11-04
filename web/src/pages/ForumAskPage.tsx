import { lazy, Suspense, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Select } from "../components/ui/Select";
import { Tabs } from "../components/ui/Tabs";
import { ApiError, api } from "../lib/api";
import { useI18n } from "../lib/i18n";
import { useFetch } from "../lib/useFetch";
import type { Document, Question, Subject } from "../lib/types";

const Markdown = lazy(() => import("../components/ui/Markdown"));

export default function ForumAskPage() {
  const { t } = useI18n();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const preSubject = Number(params.get("subject")) || 0;
  const docId = Number(params.get("doc")) || 0;

  const subjects = useFetch<{ items: Subject[] }>(() => api.get("subjects"), []);
  // "Tanya di Forum" from DocumentView: preselect the subject and link the document.
  const doc = useFetch<Document>(() => (docId ? api.get(`documents/${docId}`) : Promise.resolve(null as unknown as Document)), [docId]);

  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [subject, setSubject] = useState(preSubject);
  const [mode, setMode] = useState("write");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  // BUG-14: per-field feedback when the subject is still empty.
  const [subjectErr, setSubjectErr] = useState("");

  useEffect(() => {
    if (doc.data && !body) {
      setBody(`[${doc.data.title}](#/library/${doc.data.id})`);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [doc.data]);

  const len = title.trim().length;
  const titleValid = len >= 10 && len <= 150;

  const submit = async () => {
    if (busy) return;
    setError("");
    if (!titleValid) {
      setError(t("forum.titleInvalid"));
      return;
    }
    if (!subject) {
      setSubjectErr(t("forum.subjectRequired"));
      return;
    }
    setBusy(true);
    try {
      const q = await api.postForm<Question>("questions", {
        title: title.trim(),
        body_md: body,
        subject_id: String(subject),
      });
      nav(`/forum/q/${q.id}`, { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? `errors.${err.code}` : "errors.network_error");
      setBusy(false);
    }
  };

  return (
    <>
      <p className="back">
        <Link to="/forum">{t("forum.back")}</Link>
      </p>
      <Card title={t("forum.askTitle")}>
        <div className="field">
          <div className="field-head">
            <label className="field-label" htmlFor="q-title">
              {t("forum.askTitleLabel")}
            </label>
            <span className={`field-counter ${titleValid || !title ? "" : "bad"}`} aria-hidden="true">
              {len}/150
            </span>
          </div>
          <input
            id="q-title"
            className="field-input"
            placeholder={t("forum.askTitlePlaceholder")}
            value={title}
            maxLength={150}
            onChange={(e) => setTitle(e.target.value)}
          />
          {!titleValid && title && (
            <p className="field-error">{t("forum.titleInvalid")}</p>
          )}
        </div>
        <Select
          id="q-subject"
          label={t("summarize.subject")}
          value={String(subject)}
          error={subjectErr || undefined}
          onChange={(e) => {
            setSubject(Number(e.target.value));
            setSubjectErr("");
          }}
        >
          <option value="0" disabled>
            {t("forum.pickSubject")}
          </option>
          {(subjects.data?.items ?? []).map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </Select>
        <Tabs
          tabs={[
            { id: "write", label: t("forum.tabWrite") },
            { id: "preview", label: t("forum.tabPreview") },
          ]}
          value={mode}
          onChange={setMode}
        />
        {mode === "write" ? (
          <textarea
            className="field-input q-body"
            placeholder={t("forum.askBodyPlaceholder")}
            value={body}
            onChange={(e) => setBody(e.target.value)}
            aria-label={t("forum.askBody")}
          />
        ) : (
          <div className="md-preview">
            {body ? (
              <Suspense
                fallback={
                  <div className="sk-card" aria-busy="true">
                    <span className="skeleton" />
                    <span className="skeleton" />
                  </div>
                }
              >
                <Markdown source={body} />
              </Suspense>
            ) : (
              <p className="field-hint">{t("forum.previewEmpty")}</p>
            )}
          </div>
        )}
        {error && (
          <p className="form-error" role="alert">
            {t(error)}
          </p>
        )}
        <div className="form-actions">
          <Button variant="primary" onClick={() => void submit()} disabled={busy || !titleValid}>
            {t("forum.submit")}
          </Button>
          <Button onClick={() => nav("/forum")} disabled={busy}>
            {t("common.cancel")}
          </Button>
        </div>
      </Card>
    </>
  );
}
