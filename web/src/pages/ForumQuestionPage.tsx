import { lazy, Suspense, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Pencil, Trash2 } from "lucide-react";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Select } from "../components/ui/Select";
import { ErrorBox } from "../components/ui/ErrorBox";
import { ApiError, api } from "../lib/api";
import { useI18n } from "../lib/i18n";
import { useDate } from "../lib/date";
import { useFetch } from "../lib/useFetch";
import type { Answer, Me, QuestionDetail, Subject } from "../lib/types";

const Markdown = lazy(() => import("../components/ui/Markdown"));

export default function ForumQuestionPage() {
  const { id } = useParams();
  const { t } = useI18n();
  const { relative } = useDate();
  const nav = useNavigate();
  const qid = Number(id);

  const q = useFetch<QuestionDetail>(() => api.get(`questions/${qid}`), [qid]);
  const me = useFetch<Me>(() => api.get("me"), []);
  const subjects = useFetch<{ items: Subject[] }>(() => api.get("subjects"), []);

  const [ansBody, setAnsBody] = useState("");
  const [ansBusy, setAnsBusy] = useState(false);
  const [ansError, setAnsError] = useState("");

  const [editQ, setEditQ] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editBody, setEditBody] = useState("");
  const [editSubject, setEditSubject] = useState(0);
  const [editBusy, setEditBusy] = useState(false);

  const [editAns, setEditAns] = useState<number | null>(null);
  const [editAnsBody, setEditAnsBody] = useState("");
  const [editAnsBusy, setEditAnsBusy] = useState(false);

  const data = q.data;
  const isOwner = !!(me.data && data && me.data.user.username === data.author.username);
  const myAnswers = (a: Answer) => !!me.data && a.author.username === me.data.user.username;

  const startEditQuestion = () => {
    if (!data) return;
    setEditTitle(data.title);
    setEditBody(data.body_md ?? "");
    setEditSubject(data.subject_id ?? 0);
    setEditQ(true);
  };

  const saveQuestion = async () => {
    if (editBusy || !data) return;
    const title = editTitle.trim();
    if (title.length < 10 || title.length > 150 || !editSubject) return;
    setEditBusy(true);
    try {
      await api.patch(`questions/${data.id}`, { title, body_md: editBody, subject_id: editSubject });
      q.reload();
      setEditQ(false);
    } finally {
      setEditBusy(false);
    }
  };

  const deleteQuestion = async () => {
    if (!data) return;
    if (!window.confirm(t("forum.deleteQuestion"))) return;
    try {
      await api.del(`questions/${data.id}`);
      nav("/forum", { replace: true });
    } catch {
      // it stays; the list is the source of truth
    }
  };

  const submitAnswer = async () => {
    if (ansBusy || !ansBody.trim()) return;
    setAnsBusy(true);
    setAnsError("");
    try {
      await api.postForm(`questions/${qid}/answers`, { body_md: ansBody.trim() });
      setAnsBody("");
      q.reload();
    } catch (err) {
      setAnsError(err instanceof ApiError ? `errors.${err.code}` : "errors.network_error");
    } finally {
      setAnsBusy(false);
    }
  };

  const startEditAnswer = (a: Answer) => {
    setEditAns(a.id);
    setEditAnsBody(a.body_md);
  };

  const saveAnswer = async (a: Answer) => {
    if (editAnsBusy || !editAnsBody.trim()) return;
    setEditAnsBusy(true);
    try {
      await api.patch(`answers/${a.id}`, { body_md: editAnsBody.trim() });
      setEditAns(null);
      q.reload();
    } finally {
      setEditAnsBusy(false);
    }
  };

  const deleteAnswer = async (a: Answer) => {
    if (!window.confirm(t("forum.deleteAnswer"))) return;
    try {
      await api.del(`answers/${a.id}`);
      q.reload();
    } catch {
      // it stays
    }
  };

  if (q.error) return <ErrorBox code={q.error} onRetry={q.reload} />;
  if (q.loading || !data) {
    return (
      <Card className="sk-card" aria-busy="true">
        <span className="skeleton" />
        <span className="skeleton" />
        <span className="skeleton" />
      </Card>
    );
  }

  const titleLen = editTitle.trim().length;
  const titleOk = titleLen >= 10 && titleLen <= 150;

  return (
    <>
      <p className="back">
        <Link to="/forum">{t("forum.back")}</Link>
      </p>
      <Card>
        <div className="q-head">
          <h2 className="q-title-h">{data.title}</h2>
          <div className="meta">
            {data.subject && <span className="chip">{data.subject}</span>}
            <span>{data.author.display_name || data.author.username}</span>
            <span>{relative(data.created_at)}</span>
            {data.answers_count === 0 && <span className="q-none">{t("forum.noAnswers")}</span>}
          </div>
          {isOwner && !editQ && (
            <div className="q-actions">
              <Button icon={<Pencil className="i" size={16} aria-hidden="true" />} onClick={startEditQuestion}>
                {t("common.rename")}
              </Button>
              <Button variant="danger" icon={<Trash2 className="i" size={16} aria-hidden="true" />} onClick={() => void deleteQuestion()}>
                {t("common.delete")}
              </Button>
            </div>
          )}
        </div>

        {editQ ? (
          <div className="q-edit">
            <div className="field">
              <div className="field-head">
                <label className="field-label" htmlFor="e-title">
                  {t("forum.askTitleLabel")}
                </label>
                <span className={`field-counter ${titleOk ? "" : "bad"}`} aria-hidden="true">
                  {titleLen}/150
                </span>
              </div>
              <input
                id="e-title"
                className="field-input"
                value={editTitle}
                maxLength={150}
                onChange={(e) => setEditTitle(e.target.value)}
              />
            </div>
            <Select
              id="e-subject"
              label={t("summarize.subject")}
              value={String(editSubject)}
              onChange={(e) => setEditSubject(Number(e.target.value))}
            >
              {(subjects.data?.items ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </Select>
            <textarea
              className="field-input q-body"
              value={editBody}
              onChange={(e) => setEditBody(e.target.value)}
              aria-label={t("forum.askBody")}
            />
            <div className="form-actions">
              <Button variant="primary" onClick={() => void saveQuestion()} disabled={editBusy || !titleOk || !editSubject}>
                {t("common.save")}
              </Button>
              <Button onClick={() => setEditQ(false)} disabled={editBusy}>
                {t("common.cancel")}
              </Button>
            </div>
          </div>
        ) : (
          data.body_md && (
            <Suspense
              fallback={
                <div className="sk-card" aria-busy="true">
                  <span className="skeleton" />
                  <span className="skeleton" />
                </div>
              }
            >
              <Markdown source={data.body_md} />
            </Suspense>
          )
        )}
      </Card>

      <h3 className="section-title">{t("forum.answersTitle", { n: data.answers_count })}</h3>
      {data.answers.length === 0 ? (
        <Card>
          <p className="q-none empty-answers">{t("forum.answersEmpty")}</p>
        </Card>
      ) : (
        data.answers.map((a) => (
          <Card key={a.id} className="ans-card">
            <div className="meta">
              <span className="ans-author">{a.author.display_name || a.author.username}</span>
              <span>{relative(a.created_at)}</span>
            </div>
            {editAns === a.id ? (
              <div className="q-edit">
                <textarea
                  className="field-input q-body"
                  value={editAnsBody}
                  onChange={(e) => setEditAnsBody(e.target.value)}
                  aria-label={t("forum.editAnswer")}
                />
                <div className="form-actions">
                  <Button variant="primary" onClick={() => void saveAnswer(a)} disabled={editAnsBusy || !editAnsBody.trim()}>
                    {t("common.save")}
                  </Button>
                  <Button onClick={() => setEditAns(null)} disabled={editAnsBusy}>
                    {t("common.cancel")}
                  </Button>
                </div>
              </div>
            ) : (
              <Suspense fallback={<div className="sk-card" aria-busy="true"><span className="skeleton" /></div>}>
                <Markdown source={a.body_md} />
              </Suspense>
            )}
            {editAns !== a.id && myAnswers(a) && (
              <div className="q-actions ans-actions">
                <Button icon={<Pencil className="i" size={16} aria-hidden="true" />} onClick={() => startEditAnswer(a)}>
                  {t("forum.editAnswer")}
                </Button>
                <Button variant="danger" icon={<Trash2 className="i" size={16} aria-hidden="true" />} onClick={() => void deleteAnswer(a)}>
                  {t("common.delete")}
                </Button>
              </div>
            )}
          </Card>
        ))
      )}

      <Card>
        <label className="field-label" htmlFor="ans-body">
          {t("forum.answerPlaceholderLabel")}
        </label>
        <textarea
          id="ans-body"
          className="field-input q-body"
          placeholder={t("forum.answerPlaceholder")}
          value={ansBody}
          onChange={(e) => setAnsBody(e.target.value)}
        />
        {ansError && (
          <p className="form-error" role="alert">
            {t(ansError)}
          </p>
        )}
        <div className="form-actions">
          <Button variant="primary" onClick={() => void submitAnswer()} disabled={ansBusy || !ansBody.trim()}>
            {t("forum.answerSubmit")}
          </Button>
        </div>
      </Card>
    </>
  );
}
