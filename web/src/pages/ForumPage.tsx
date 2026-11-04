import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Hourglass, MessagesSquare, Plus, Search } from "lucide-react";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorBox } from "../components/ui/ErrorBox";
import { api, qs } from "../lib/api";
import { usePageAction } from "../lib/pageAction";
import { useI18n } from "../lib/i18n";
import { useDate } from "../lib/date";
import { useFetch } from "../lib/useFetch";
import type { ChatItem, QuestionList, Subject } from "../lib/types";

type Tab = "community" | "chat" | "ask" | "answer" | "faq";

const SOON: Tab[] = ["ask", "answer", "faq"];

/**
 * Forum (redesign §6): segmented tabs. "Komunitas" = the existing question
 * list as cards; "Chat" = the Tanya conversations; the other tabs show a
 * "Segera hadir" empty state (the features are cut from scope).
 */
export default function ForumPage() {
  const { t } = useI18n();
  const { relative } = useDate();
  const nav = useNavigate();

  const [tab, setTab] = useState<Tab>("community");
  const [q, setQ] = useState("");
  const [qd, setQd] = useState("");
  const [subject, setSubject] = useState(0);
  const [page, setPage] = useState(1);

  useEffect(() => {
    const id = setTimeout(() => setQd(q), 300);
    return () => clearTimeout(id);
  }, [q]);

  useEffect(() => {
    setPage(1);
  }, [qd, subject]);

  const list = useFetch<QuestionList>(
    () => api.get(`questions${qs({ q: qd || undefined, subject: subject || undefined, page })}`),
    [qd, subject, page],
  );
  const subjects = useFetch<{ items: Subject[] }>(() => api.get("subjects"), []);
  const chats = useFetch<{ items: ChatItem[] }>(() => (tab === "chat" ? api.get("chats") : Promise.resolve({ items: [] as ChatItem[] })), [tab]);

  const items = list.data?.items ?? [];
  const pages = list.data?.pages ?? 1;
  const empty = list.data?.total === 0;

  usePageAction(
    <Button variant="primary" icon={<Plus className="i" size={16} aria-hidden="true" />} onClick={() => nav("/forum/ask")}>
      {t("forum.ask")}
    </Button>,
  );

  return (
    <div className="forum-grid">
      <div className="forum-main">
        <div className="ftabs" role="tablist" aria-label={t("forum.title")}>
          <button type="button" role="tab" aria-selected={tab === "community"} onClick={() => setTab("community")}>
            {t("forum.tabCommunity")}
          </button>
          <button type="button" role="tab" aria-selected={tab === "chat"} onClick={() => setTab("chat")}>
            {t("forum.tabChat")}
          </button>
          <button type="button" role="tab" aria-selected={tab === "ask"} onClick={() => setTab("ask")}>
            {t("forum.tabAsk")}
          </button>
          <button type="button" role="tab" aria-selected={tab === "answer"} onClick={() => setTab("answer")}>
            {t("forum.tabAnswer")}
          </button>
          <button type="button" role="tab" aria-selected={tab === "faq"} onClick={() => setTab("faq")}>
            {t("forum.tabFaq")}
          </button>
        </div>

        {SOON.includes(tab) ? (
          <Card>
            <div className="soon">
              <span className="soon-ic" aria-hidden="true">
                <Hourglass size={26} />
              </span>
              <h3>{t("forum.soonTitle")}</h3>
              <p>{t("forum.soonBody")}</p>
            </div>
          </Card>
        ) : tab === "chat" ? (
          chats.error ? (
            <ErrorBox code={chats.error} onRetry={chats.reload} />
          ) : chats.loading ? (
            <Card className="sk-card" aria-busy="true">
              <span className="skeleton" />
              <span className="skeleton" />
            </Card>
          ) : (chats.data?.items ?? []).length === 0 ? (
            <Card>
              <EmptyState
                title={t("forum.chatEmpty")}
                body={t("forum.chatEmptyBody")}
                action={
                  <Link to="/library" className="btn">
                    {t("forum.chatEmptyCta")}
                  </Link>
                }
              />
            </Card>
          ) : (
            <Card>
              <ul className="chat-list">
                {(chats.data?.items ?? []).map((c) => (
                  <li key={c.id} className="chat-row">
                    <span className="avatar" aria-hidden="true">
                      <MessagesSquare size={18} />
                    </span>
                    <Link className="chat-main" to={`/chat/${c.id}`}>
                      <span className="chat-title">{c.title}</span>
                      <span className="meta">
                        {c.project_title && <span className="chip ctx-chip">{c.project_title}</span>}
                        <span>{relative(c.updated_at)}</span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </Card>
          )
        ) : (
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

            {list.error ? (
              <ErrorBox code={list.error} onRetry={list.reload} />
            ) : list.loading ? (
              <Card className="sk-card" aria-busy="true">
                <span className="skeleton" />
                <span className="skeleton" />
                <span className="skeleton" />
              </Card>
            ) : empty && !qd && subject === 0 ? (
              <Card>
                <EmptyState
                  title={t("forum.empty")}
                  body={t("forum.emptyBody")}
                  action={
                    <Link to="/forum/ask" className="btn">
                      {t("forum.emptyCta")}
                    </Link>
                  }
                />
              </Card>
            ) : empty ? (
              <Card>
                <EmptyState title={t("forum.noResults")} />
              </Card>
            ) : (
              <Card>
                <ul className="q-list">
                  {items.map((qt) => (
                    <li key={qt.id}>
                      <Link className="q-card" to={`/forum/q/${qt.id}`}>
                        <span className="q-count">
                          <b>{qt.answers_count}</b>
                          <span>{t("forum.answersWord")}</span>
                        </span>
                        <span className="q-main">
                          <span className="q-chips">
                            {qt.subject && <span className="chip">{qt.subject}</span>}
                            {qt.answers_count > 0 && <span className="chip answered">{t("forum.answered")}</span>}
                          </span>
                          <span className="q-title">{qt.title}</span>
                          <span className="q-meta">
                            {qt.author.display_name || qt.author.username} · {relative(qt.created_at)}
                          </span>
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
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
        )}
      </div>

      <div className="forum-side">
        <Card title={t("forum.yourCommunity")}>
          <div className="soon" style={{ padding: "24px 8px" }}>
            <span className="soon-ic" aria-hidden="true">
              <Hourglass size={22} />
            </span>
            <p>{t("forum.soonBody")}</p>
          </div>
        </Card>
      </div>
    </div>
  );
}
