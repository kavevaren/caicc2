import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Atom, Folder, Plus, Send, Trash2 } from "lucide-react";
import { AtomLoader } from "../components/atom/AtomLoader";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorBox } from "../components/ui/ErrorBox";
import { ApiError, api } from "../lib/api";
import { useI18n } from "../lib/i18n";
import { useDate } from "../lib/date";
import { useFetch } from "../lib/useFetch";
import type { ChatDetail, ChatItem } from "../lib/types";

const Markdown = lazy(() => import("../components/ui/Markdown"));

/** /chat — the thread list + "Percakapan baru". */
export default function ChatPage() {
  const { t } = useI18n();
  const { relative } = useDate();
  const nav = useNavigate();
  const chats = useFetch<{ items: ChatItem[] }>(() => api.get("chats"), []);
  const [busy, setBusy] = useState(false);

  const newChat = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const c = await api.post<{ id: number }>("chats", {});
      nav(`/chat/${c.id}`);
    } catch {
      setBusy(false);
    }
  };

  const remove = async (chat: ChatItem) => {
    if (window.confirm(t("chat.deleteConfirm"))) {
      try {
        await api.del(`chats/${chat.id}`);
        chats.reload();
      } catch {
        // the thread simply stays
      }
    }
  };

  return (
    <Card title={t("chat.title")}>
      <div className="toolbar">
        <Button
          variant="primary"
          icon={<Plus className="i" size={16} aria-hidden="true" />}
          onClick={() => void newChat()}
          disabled={busy}
        >
          {t("chat.newChat")}
        </Button>
      </div>
      {chats.error ? (
        <ErrorBox code={chats.error} onRetry={chats.reload} />
      ) : chats.loading ? (
        <>
          <span className="skeleton" />
          <span className="skeleton" />
        </>
      ) : chats.data && chats.data.items.length === 0 ? (
        <EmptyState title={t("chat.empty")} body={t("chat.emptyBody")} />
      ) : (
        <ul className="chat-list">
          {(chats.data?.items ?? []).map((c) => (
            <li key={c.id} className="chat-row">
              <Link to={`/chat/${c.id}`} className="chat-main">
                <span className="chat-title">{c.title || t("chat.untitled")}</span>
                <span className="meta">
                  {c.project_title && (
                    <span className="chip">
                      <Folder className="i" size={12} aria-hidden="true" /> {c.project_title}
                    </span>
                  )}
                  <span>{relative(c.updated_at)}</span>
                </span>
              </Link>
              <button
                type="button"
                className="icon-btn danger"
                aria-label={t("chat.delete")}
                onClick={() => void remove(c)}
              >
                <Trash2 className="i" size={16} aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

/**
 * /chat/:id — the mockup chat: threads aside + conversation + composer.
 * Mount this through a keyed wrapper (one mount per chat id) so the local
 * `detail` state resets when the user switches threads.
 */
export function ChatConvoPage() {
  const { id } = useParams();
  const { t } = useI18n();
  const nav = useNavigate();
  const chatId = Number(id);

  const chats = useFetch<{ items: ChatItem[] }>(() => api.get("chats"), []);
  const chat = useFetch<ChatDetail>(() => api.get(`chats/${chatId}`), [chatId]);

  // The detail right after a send (before the next full fetch, if any).
  const [detail, setDetail] = useState<ChatDetail | null>(null);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState("");
  // BUG-15: optimistic send — the user bubble shows and the input clears
  // immediately; on failure the text is marked failed with a retry button.
  const [pending, setPending] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);

  const c = detail ?? chat.data;

  useEffect(() => {
    const box = boxRef.current;
    if (box) box.scrollTop = box.scrollHeight;
  }, [c?.messages.length, sending, pending, failed]);

  const send = async (content: string) => {
    const q = content.trim();
    if (sending || !q) return;
    setSending(true);
    setSendError("");
    setFailed(null);
    setText(""); // the input clears at once, before the answer arrives
    setPending(q); // the optimistic user bubble
    try {
      const d = await api.post<ChatDetail>(`chats/${chatId}/messages`, { content: q });
      setPending(null);
      setDetail(d);
      chats.reload(); // the thread moved to the top with a new title
    } catch (err) {
      setPending(null);
      setFailed(q); // mark failed; the text is restored in the failed bubble
      setSendError(err instanceof ApiError ? `errors.${err.code}` : "errors.network_error");
    } finally {
      setSending(false);
    }
  };

  const newChat = async () => {
    try {
      const n = await api.post<{ id: number }>("chats", {});
      nav(`/chat/${n.id}`);
    } catch {
      // stays on the current chat
    }
  };

  if (chat.error) {
    return <ErrorBox code={chat.error} onRetry={chat.reload} />;
  }

  if (!c) {
    return (
      <Card className="sk-card" aria-busy="true">
        <span className="skeleton" />
        <span className="skeleton" />
        <span className="skeleton" />
      </Card>
    );
  }

  const msgs = c.messages;

  return (
    <div className="chat">
      <aside className="threads" aria-label={t("chat.navAria")}>
        <Button icon={<Plus className="i" size={16} aria-hidden="true" />} onClick={() => void newChat()}>
          {t("chat.newChat")}
        </Button>
        <p className="grp">{t("chat.recent")}</p>
        <ul>
          {(chats.data?.items ?? []).map((x) => (
            <li key={x.id}>
              <Link
                to={`/chat/${x.id}`}
                title={x.title || t("chat.untitled")}
                aria-current={x.id === c.id ? "true" : undefined}
              >
                {x.title || t("chat.untitled")}
              </Link>
            </li>
          ))}
        </ul>
      </aside>

      <div className="convo">
        <div className="convo-h">
          <Link to="/chat" className="convo-back" aria-label={t("chat.back")}>
            <ArrowLeft className="i" aria-hidden="true" />
          </Link>
          <h2>{c.title || t("chat.untitled")}</h2>
          {c.project_id != null && c.project_title && (
            <Link to={`/projects/${c.project_id}`} className="chip ctx-chip">
              <Folder className="i" size={12} aria-hidden="true" /> {c.project_title}
            </Link>
          )}
        </div>

        <div className="msgs" ref={boxRef}>
          <div className="msgs-in">
            {msgs.length === 0 && !sending && (
              <div className="starters">
                <p className="grp">{t("chat.starters")}</p>
                {(["s1", "s2", "s3", "s4"] as const).map((k) => (
                  <button key={k} type="button" onClick={() => void send(t(`chat.${k}`))}>
                    {t(`chat.${k}`)}
                  </button>
                ))}
              </div>
            )}
            {msgs.map((m) =>
              m.role === "user" ? (
                <div key={m.id} className="msg me">
                  <div className="bubble">{m.content_md}</div>
                </div>
              ) : (
                <div key={m.id} className="msg ai">
                  <span className="who" aria-hidden="true">
                    <Atom className="i" size={18} />
                  </span>
                  <div className="body">
                    <Suspense fallback={<span className="skeleton" />}>
                      <Markdown source={m.content_md} />
                    </Suspense>
                  </div>
                </div>
              ),
            )}
            {pending !== null && (
              <div className="msg me">
                <div className="bubble">{pending}</div>
              </div>
            )}
            {failed !== null && (
              <div className="msg me failed-msg">
                <div className="bubble">{failed}</div>
                <Button variant="ghost" className="sm" onClick={() => void send(failed)}>
                  {t("chat.retry")}
                </Button>
              </div>
            )}
            {sending && (
              <div className="msg ai" role="status">
                <span className="who" aria-hidden="true">
                  <Atom className="i" size={18} />
                </span>
                <div className="body">
                  <span className="thinking-label">
                    <AtomLoader size={16} /> {t("chat.thinking")}
                  </span>
                </div>
              </div>
            )}
            {sendError && (
              <p className="form-error" role="alert">
                {t(sendError)}
              </p>
            )}
          </div>
        </div>

        <div className="composer-wrap">
          <form
            className="composer"
            onSubmit={(e) => {
              e.preventDefault();
              void send(text);
            }}
          >
            <label className="sr-only" htmlFor="ask">
              {t("chat.placeholder")}
            </label>
            <textarea
              id="ask"
              rows={1}
              placeholder={t("chat.placeholder")}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  e.currentTarget.form?.requestSubmit();
                }
              }}
            />
            <div className="bar">
              {c.project_id != null && c.project_title && (
                <span className="ctx">
                  <Folder className="i sm" aria-hidden="true" />
                  {t("chat.context", { name: c.project_title })}
                </span>
              )}
              <Button
                type="submit"
                variant="primary"
                className="send"
                disabled={sending || !text.trim()}
                icon={<Send className="i" size={16} aria-hidden="true" />}
                aria-label={t("chat.send")}
              />
            </div>
          </form>
          <p className="hint">{t("chat.hint")}</p>
        </div>
      </div>
    </div>
  );
}
