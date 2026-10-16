import React, { useEffect, useState, useRef, FormEvent } from "react";
import { createRoot } from "react-dom/client";
import {
  api,
  setCsrf,
  User,
  Ticket,
  Article,
  Draft,
  Audit,
  Detail,
  Preview,
  Me,
} from "./api";
import "./style.css";
const statusNames: Record<string, string> = {
  open: "未対応",
  in_progress: "対応中",
  resolved: "完了",
  draft: "承認待ち",
  approved: "承認済み",
  rejected: "差戻し",
  blocked: "根拠不足",
  failed: "生成失敗",
  generating: "生成中",
};
const roleNames: Record<string, string> = {
  admin: "管理者",
  agent: "担当者",
  reviewer: "レビュアー",
};
const fmt = (s: string) =>
  new Date(s).toLocaleString("ja-JP", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Tokyo",
  });
function Icon({ name }: { name: string }) {
  const paths: Record<string, React.ReactNode> = {
    inbox: (
      <>
        <path d="m4 4-2 12v4h20v-4L20 4Z" />
        <path d="M2 15h6l2 3h4l2-3h6" />
      </>
    ),
    book: (
      <>
        <path d="M3 3h7l2 2 2-2h7v17h-7l-2 2-2-2H3Z" />
        <path d="M12 5v17M6 8h3M15 8h3M6 12h3M15 12h3" />
      </>
    ),
    clock: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 6v6l4 2" />
      </>
    ),
    spark: (
      <>
        <path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z" />
        <path d="M20 2v4M18 4h4" />
      </>
    ),
    search: (
      <>
        <circle cx="10" cy="10" r="6" />
        <path d="m15 15 6 6" />
      </>
    ),
    plus: <path d="M12 5v14M5 12h14" />,
    arrow: <path d="m9 5 7 7-7 7" />,
    check: <path d="m5 12 4 4L20 5" />,
    logout: (
      <>
        <path d="M9 3H3v18h6M13 7l5 5-5 5M8 12h13" />
      </>
    ),
  };
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.65"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name] || paths.inbox}
    </svg>
  );
}
function Badge({ status }: { status: string }) {
  return (
    <span className={"badge " + status}>{statusNames[status] || status}</span>
  );
}
function App() {
  const [me, setMe] = useState<Me | null>(null),
    [boot, setBoot] = useState(true),
    [page, setPage] = useState("inbox"),
    [tickets, setTickets] = useState<Ticket[]>([]),
    [articles, setArticles] = useState<Article[]>([]),
    [users, setUsers] = useState<User[]>([]),
    [audit, setAudit] = useState<Audit[]>([]),
    [selected, setSelected] = useState(""),
    [detail, setDetail] = useState<Detail | null>(null),
    [query, setQuery] = useState(""),
    [filter, setFilter] = useState("all"),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [modal, setModal] = useState<"ticket" | "article" | null>(null),
    [editing, setEditing] = useState<Article | null>(null),
    [preview, setPreview] = useState<Preview | null>(null),
    [consent, setConsent] = useState(false),
    [activeDraft, setActiveDraft] = useState(""),
    [reviewText, setReviewText] = useState(""),
    [reviewNote, setReviewNote] = useState(""),
    [checked, setChecked] = useState(false),
    [note, setNote] = useState(""),
    [revisions, setRevisions] = useState<
      Record<
        string,
        { version: number; body: string; title: string; created_at: string }[]
      >
    >({});
  const pendingGeneration = useRef<{
    ticket: string;
    digest: string;
    key: string;
  } | null>(null);
  const epoch = useRef(0),
    requestNo = useRef(0);
  const canReview = me?.user.role !== "agent";
  useEffect(() => {
    if (!modal) return;
    const previous = document.activeElement as HTMLElement | null;
    const handle = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) {
        setModal(null);
        return;
      }
      if (event.key !== "Tab") return;
      const elements = Array.from(
        document.querySelectorAll<HTMLElement>(
          ".modal button:not(:disabled), .modal input:not(:disabled), .modal select:not(:disabled), .modal textarea:not(:disabled)",
        ),
      );
      const first = elements[0],
        last = elements[elements.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", handle);
    return () => {
      document.removeEventListener("keydown", handle);
      previous?.focus();
    };
  }, [modal, busy]);

  function clear() {
    epoch.current++;
    setMe(null);
    setPage("inbox");
    setFilter("all");
    setQuery("");
    setNotice("");
    setReviewText("");
    setTickets([]);
    setArticles([]);
    setUsers([]);
    setAudit([]);
    setDetail(null);
    setSelected("");
    setPreview(null);
    setModal(null);
    setRevisions({});
    setNote("");
    pendingGeneration.current = null;
    setCsrf("");
  }
  async function establish() {
    const m = await api<Me>("/me");
    setCsrf(m.csrf);
    setMe(m);
    return m;
  }
  useEffect(() => {
    establish()
      .catch(() => {})
      .finally(() => setBoot(false));
    const expire = () => {
      clear();
      setError("セッションが終了しました。再ログインしてください。");
    };
    window.addEventListener("session-expired", expire);
    return () => window.removeEventListener("session-expired", expire);
  }, []);
  async function load() {
    const e = epoch.current;
    const [t, a, u] = await Promise.all([
      api<Ticket[]>("/tickets"),
      api<Article[]>("/articles"),
      api<User[]>("/users"),
    ]);
    if (e !== epoch.current) return;
    setTickets(t);
    setArticles(a);
    setUsers(u);
    setSelected((s) => s || t[0]?.id || "");
  }
  useEffect(() => {
    if (me) load().catch((e) => setError(e.message));
  }, [me]);
  async function show(id: string) {
    const n = ++requestNo.current,
      e = epoch.current;
    const d = await api<Detail>("/tickets/" + id);
    if (n === requestNo.current && e === epoch.current) {
      setDetail(d);
      setActiveDraft(d.drafts[0]?.id || "");
    }
  }
  useEffect(() => {
    setDetail(null);
    setNote("");
    setPreview(null);
    setConsent(false);
    setChecked(false);
    setReviewNote("");
    if (selected && me) show(selected).catch((e) => setError(e.message));
  }, [selected]);
  useEffect(() => {
    const d = detail?.drafts.find((x) => x.id === activeDraft);
    setReviewText(d?.reviewed_text || d?.original || "");
    setChecked(false);
    setReviewNote("");
  }, [detail?.drafts, activeDraft]);
  useEffect(() => {
    if (page === "audit" && me && canReview) {
      const e = epoch.current;
      api<Audit[]>("/audit")
        .then((a) => {
          if (e === epoch.current) setAudit(a);
        })
        .catch((e) => setError(e.message));
    }
  }, [page, me]);
  async function run(fn: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "処理できませんでした");
    } finally {
      setBusy(false);
    }
  }
  async function login(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    await run(async () => {
      await api("/login", "POST", Object.fromEntries(f));
      await establish();
      setNotice("");
    });
  }
  const filtered = tickets.filter(
    (t) =>
      (filter === "all" || t.status === filter) &&
      [t.title, t.customer, t.category].join(" ").includes(query),
  );
  const draft = detail?.drafts.find((d) => d.id === activeDraft);
  async function saveForm(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget),
      v = Object.fromEntries(f);
    await run(async () => {
      if (modal === "ticket") {
        const t = await api<Ticket>("/tickets", "POST", v);
        await load();
        setSelected(t.id);
        setPage("inbox");
      } else {
        await api(
          "/articles" + (editing ? "/" + editing.id : ""),
          editing ? "PUT" : "POST",
          {
            ...v,
            active: f.get("active") === "on",
            version: editing?.version ?? null,
          },
        );
        await load();
      }
      setModal(null);
      setNotice("保存しました");
    });
  }
  async function changeTicket(status: string, assignee_id: string | null) {
    if (!detail) return;
    await run(async () => {
      await api("/tickets/" + detail.ticket.id, "PATCH", {
        version: detail.ticket.version,
        status,
        assignee_id,
      });
      await load();
      await show(detail.ticket.id);
      setPreview(null);
      setNotice("問い合わせを更新しました");
    });
  }
  async function generate() {
    if (!detail || !preview) return;
    if (
      pendingGeneration.current?.ticket !== detail.ticket.id ||
      pendingGeneration.current?.digest !== preview.source_digest
    ) {
      pendingGeneration.current = {
        ticket: detail.ticket.id,
        digest: preview.source_digest,
        key: crypto.randomUUID(),
      };
    }
    await run(async () => {
      await api("/tickets/" + detail.ticket.id + "/drafts", "POST", {
        version: preview.ticket_version,
        source_digest: preview.source_digest,
        consent,
        request_key: pendingGeneration.current!.key,
      });
      pendingGeneration.current = null;
      setPreview(null);
      setConsent(false);
      await show(detail.ticket.id);
      setNotice("生成結果を保存しました。内容と根拠をご確認ください。");
    });
  }
  async function review(action: string) {
    if (!draft || !detail) return;
    await run(async () => {
      await api("/drafts/" + draft.id + "/review", "POST", {
        action,
        text: reviewText,
        note: reviewNote,
        checked,
      });
      await show(detail.ticket.id);
      setNotice(
        action === "approved"
          ? "返信案を承認しました。お客様への送信は行っていません。"
          : "差戻しを記録しました",
      );
    });
  }
  if (boot) return <main className="loading">RELAY Desk を開いています…</main>;
  if (!me)
    return (
      <main className="login">
        <section className="login-brand">
          <div className="wordmark">
            <span className="logo">r</span>RELAY<span>Desk</span>
          </div>
          <div>
            <p className="eyebrow">SUPPORT, WITH CONTEXT.</p>
            <h1>
              その返信に、
              <br />
              確かな根拠を。
            </h1>
            <p>
              問い合わせとナレッジをつなぎ、
              <br />
              チームで、よりよい回答へ。
            </p>
          </div>
          <small>PORTFOLIO EDITION · 架空のサポート窓口</small>
        </section>
        <section className="login-form">
          <p className="eyebrow">WELCOME BACK</p>
          <h2>ワークスペースにログイン</h2>
          <p className="muted">チームの問い合わせ対応をここから。</p>
          <form onSubmit={login}>
            <label>
              メールアドレス
              <input
                name="email"
                type="email"
                autoComplete="username"
                defaultValue="admin@example.test"
                required
              />
            </label>
            <label>
              パスワード
              <input
                name="password"
                type="password"
                autoComplete="current-password"
                required
              />
            </label>
            <button className="primary" disabled={busy}>
              ログイン <Icon name="arrow" />
            </button>
          </form>
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <div className="login-note">
            初期設定時に指定したデモ用パスワードを使用します。
            <br />
            実在するお客様の情報は入力しないでください。
          </div>
        </section>
      </main>
    );
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="wordmark">
          <span className="logo">r</span>RELAY<span>Desk</span>
        </div>
        <div className="workspace">
          <span className="workspace-icon">A</span>
          <div>
            青葉ストア<small>サポートワークスペース</small>
          </div>
        </div>
        <p className="nav-label">WORKSPACE</p>
        <nav>
          {[
            ["inbox", "inbox", "問い合わせ"],
            ["knowledge", "book", "ナレッジ"],
            ...(canReview ? [["audit", "clock", "操作履歴"]] : []),
          ].map(([id, icon, label]) => (
            <button
              key={id}
              className={page === id ? "nav active" : "nav"}
              onClick={() => {
                setPage(id);
                setQuery("");
              }}
            >
              <Icon name={icon} />
              {label}
              {id === "inbox" && (
                <span className="nav-count">
                  {tickets.filter((t) => t.status !== "resolved").length}
                </span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="ai-mode">
            <Icon name="spark" />
            <div>
              {me.provider === "demo"
                ? "サンプル生成モード"
                : me.provider === "openai"
                  ? "OpenAI 接続モード"
                  : "AI 無効"}
              <small>
                {me.provider === "demo"
                  ? "外部へのデータ送信なし"
                  : "生成前に送信内容を確認"}
              </small>
            </div>
          </div>
          <div className="account">
            <span className="avatar">{me.user.name[0]}</span>
            <div>
              {me.user.name}
              <small>{roleNames[me.user.role]}</small>
            </div>
            <button
              title="ログアウト"
              aria-label="ログアウト"
              disabled={busy}
              onClick={() =>
                run(async () => {
                  await api("/logout", "POST", {});
                  clear();
                })
              }
            >
              <Icon name="logout" />
            </button>
          </div>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <span>
            ワークスペース <span className="slash">/</span>{" "}
            {page === "inbox"
              ? "問い合わせ"
              : page === "knowledge"
                ? "ナレッジ"
                : "操作履歴"}
          </span>
          <span className="portfolio">
            PORTFOLIO <span className="dot" /> 架空データ
          </span>
        </header>
        {(error || notice) && (
          <div
            className={"toast " + (error ? "error" : "success")}
            role={error ? "alert" : "status"}
          >
            {error || notice}
            <button
              aria-label="通知を閉じる"
              onClick={() => {
                setError("");
                setNotice("");
              }}
            >
              ×
            </button>
          </div>
        )}
        <section className="page-head">
          <div>
            <p className="eyebrow">
              {page === "inbox"
                ? "TEAM INBOX"
                : page === "knowledge"
                  ? "KNOWLEDGE BASE"
                  : "ACTIVITY LOG"}
            </p>
            <h1>
              {page === "inbox"
                ? "問い合わせ"
                : page === "knowledge"
                  ? "チームのナレッジ"
                  : "操作履歴"}
            </h1>
            <p className="muted">
              {page === "inbox"
                ? "一つひとつの声に、チームで向き合う。"
                : page === "knowledge"
                  ? "回答の根拠となる資料を、いつも最新に。"
                  : "誰が、いつ、何を変更したかを確認できます。"}
            </p>
          </div>
          {page !== "audit" && (page === "inbox" || canReview) && (
            <button
              className="primary"
              onClick={() => {
                setEditing(null);
                setModal(page === "inbox" ? "ticket" : "article");
              }}
            >
              <Icon name="plus" />
              {page === "inbox" ? "問い合わせを登録" : "資料を追加"}
            </button>
          )}
        </section>
        {page === "inbox" && (
          <>
            <section className="stats">
              {[
                [
                  "未対応",
                  tickets.filter((t) => t.status === "open").length,
                  "orange",
                ],
                [
                  "対応中",
                  tickets.filter((t) => t.status === "in_progress").length,
                  "purple",
                ],
                [
                  "完了",
                  tickets.filter((t) => t.status === "resolved").length,
                  "green",
                ],
              ].map(([label, n, c]) => (
                <div key={label}>
                  <span className={"stat-dot " + c} />
                  <span>{label}</span>
                  <strong>{n}</strong>
                  <small>件</small>
                </div>
              ))}
              <div className="stats-tip">
                <Icon name="spark" />
                <span>AIが下書き、人が最終確認</span>
              </div>
            </section>
            <section className="desk">
              <div className="ticket-list">
                <div className="list-tools">
                  <div className="search">
                    <Icon name="search" />
                    <input
                      aria-label="問い合わせを検索"
                      placeholder="件名・お客様名で検索"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                    />
                  </div>
                  <div className="filters">
                    {[
                      ["all", "すべて"],
                      ["open", "未対応"],
                      ["in_progress", "対応中"],
                      ["resolved", "完了"],
                    ].map(([v, l]) => (
                      <button
                        key={v}
                        className={filter === v ? "selected" : ""}
                        onClick={() => setFilter(v)}
                      >
                        {l}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="list-caption">
                  {filtered.length} 件の問い合わせ <span>新しい順</span>
                </div>
                {filtered.map((t) => (
                  <button
                    className={
                      "ticket-card " + (selected === t.id ? "current" : "")
                    }
                    key={t.id}
                    disabled={busy}
                    onClick={() => setSelected(t.id)}
                  >
                    <div className="card-meta">
                      <span>{t.category}</span>
                      <time>{fmt(t.created_at)}</time>
                    </div>
                    <h3>{t.title}</h3>
                    <p>{t.body}</p>
                    <div className="card-foot">
                      <Badge status={t.status} />
                      {t.priority === "high" && (
                        <span className="urgent">優先</span>
                      )}
                      <span className="customer">{t.customer}</span>
                    </div>
                  </button>
                ))}
                {!filtered.length && (
                  <p className="empty">該当する問い合わせはありません。</p>
                )}
              </div>
              <div className="ticket-detail">
                {!detail ? (
                  <div className="empty">
                    {selected
                      ? "問い合わせを読み込み中…"
                      : "問い合わせを登録して始めましょう。"}
                  </div>
                ) : (
                  <>
                    <div className="detail-heading">
                      <div className="detail-id">
                        INQUIRY · {detail.ticket.id.slice(0, 8).toUpperCase()}{" "}
                        <Badge status={detail.ticket.status} />
                      </div>
                      <h2>{detail.ticket.title}</h2>
                      <div className="sender">
                        <span className="avatar soft">
                          {detail.ticket.customer.slice(-1)}
                        </span>
                        <div>
                          {detail.ticket.customer}
                          <small>
                            {fmt(detail.ticket.created_at)} · Web受付 /
                            架空データ
                          </small>
                        </div>
                      </div>
                      <div className="assignment">
                        <label>
                          担当
                          <select
                            aria-label="担当者"
                            value={detail.ticket.assignee_id || ""}
                            disabled={busy}
                            onChange={(e) =>
                              changeTicket(
                                detail.ticket.status,
                                e.target.value || null,
                              )
                            }
                          >
                            <option value="">未割当</option>
                            {users.map((u) => (
                              <option value={u.id} key={u.id}>
                                {u.name}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label>
                          状況
                          <select
                            aria-label="対応状況"
                            value={detail.ticket.status}
                            disabled={busy}
                            onChange={(e) =>
                              changeTicket(
                                e.target.value,
                                detail.ticket.assignee_id,
                              )
                            }
                          >
                            {["open", "in_progress", "resolved"].map((s) => (
                              <option value={s} key={s}>
                                {statusNames[s]}
                              </option>
                            ))}
                          </select>
                        </label>
                      </div>
                    </div>
                    <div className="message">
                      <p className="section-label">お問い合わせ内容</p>
                      <p>{detail.ticket.body}</p>
                    </div>
                    <section className="reply">
                      <div className="reply-title">
                        <span className="spark-icon">
                          <Icon name="spark" />
                        </span>
                        <div>
                          <h3>返信アシスタント</h3>
                          <small>資料を根拠に、返信の下書きを作成</small>
                        </div>
                        <span className="beta">AI ASSIST</span>
                      </div>
                      <div className="reply-body">
                        {!preview && (
                          <button
                            className="generate-btn"
                            disabled={
                              busy || detail.ticket.status === "resolved"
                            }
                            onClick={() =>
                              run(async () => {
                                setPreview(
                                  await api<Preview>(
                                    "/tickets/" + detail.ticket.id + "/preview",
                                  ),
                                );
                                setConsent(false);
                              })
                            }
                          >
                            <Icon name="spark" />
                            送信内容・参照資料を確認
                          </button>
                        )}
                        {preview && (
                          <div className="preview">
                            <h4>生成前の確認</h4>
                            <p>
                              {preview.provider === "demo"
                                ? "サンプルモード：以下を使って定型文を生成します。"
                                : "以下の問い合わせ本文と資料の抜粋をOpenAIへ送信します。氏名欄は送信しませんが、本文内の個人情報にもご注意ください。"}
                            </p>
                            <details>
                              <summary>送信する問い合わせ本文</summary>
                              <pre>{preview.question}</pre>
                            </details>
                            <p className="section-label">
                              参照候補 · {preview.sources.length} 件
                            </p>
                            {preview.sources.map((s) => (
                              <details key={s.id}>
                                <summary>
                                  {s.title} <small>v{s.version}</small>
                                </summary>
                                <pre>{s.excerpt}</pre>
                              </details>
                            ))}
                            {!preview.sources.length && (
                              <p className="warning">
                                根拠資料が見つからないため、返信案は生成せず保留します。
                              </p>
                            )}
                            <label className="checkbox">
                              <input
                                type="checkbox"
                                checked={consent}
                                onChange={(e) => setConsent(e.target.checked)}
                              />
                              内容と送信先を確認しました
                            </label>
                            <div className="actions">
                              <button
                                className="primary"
                                disabled={busy || !consent}
                                onClick={generate}
                              >
                                {busy ? "生成中…" : "下書きを生成"}
                              </button>
                              <button
                                onClick={() => setPreview(null)}
                                disabled={busy}
                              >
                                キャンセル
                              </button>
                            </div>
                          </div>
                        )}
                        {!!detail.drafts.length && (
                          <label className="draft-picker">
                            下書き履歴
                            <select
                              aria-label="下書き履歴"
                              value={activeDraft}
                              onChange={(e) => setActiveDraft(e.target.value)}
                            >
                              {detail.drafts.map((d, i) => (
                                <option value={d.id} key={d.id}>
                                  #{detail.drafts.length - i} ·{" "}
                                  {statusNames[d.status]} · {fmt(d.created_at)}
                                </option>
                              ))}
                            </select>
                          </label>
                        )}
                        {draft ? (
                          <>
                            <div className="draft-meta">
                              <Badge status={draft.status} />
                              <small>
                                {draft.provider === "demo"
                                  ? "サンプル生成 / LLM未使用"
                                  : draft.model || "AI生成"}{" "}
                                · {fmt(draft.created_at)}
                              </small>
                            </div>
                            {draft.status === "generating" && (
                              <div className="warning">
                                <p>
                                  生成の完了待ちです。画面を更新して状態を確認できます。
                                </p>
                                <div className="actions">
                                  <button
                                    disabled={busy}
                                    onClick={() =>
                                      run(async () => {
                                        await show(detail.ticket.id);
                                      })
                                    }
                                  >
                                    状態を更新
                                  </button>
                                  {canReview && (
                                    <button
                                      disabled={busy}
                                      onClick={() =>
                                        run(async () => {
                                          await api(
                                            "/drafts/" + draft.id + "/recover",
                                            "POST",
                                            {},
                                          );
                                          await show(detail.ticket.id);
                                          setNotice("中断状態を記録しました");
                                        })
                                      }
                                    >
                                      2分以上停止した生成を復旧
                                    </button>
                                  )}
                                </div>
                              </div>
                            )}
                            {draft.warning && (
                              <p className="warning">{draft.warning}</p>
                            )}
                            {draft.stale && draft.status === "draft" && (
                              <p className="error">
                                元の記録が更新されています。承認するには生成し直してください。
                              </p>
                            )}
                            {draft.original && (
                              <>
                                <label className="reply-editor">
                                  返信案
                                  <textarea
                                    aria-label="返信案"
                                    rows={9}
                                    value={reviewText}
                                    readOnly={
                                      draft.status !== "draft" || !canReview
                                    }
                                    onChange={(e) =>
                                      setReviewText(e.target.value)
                                    }
                                  />
                                </label>
                                <details>
                                  <summary>生成時の原文</summary>
                                  <pre>{draft.original}</pre>
                                </details>
                              </>
                            )}
                            {!!draft.sources.length && (
                              <div className="sources">
                                <h4>
                                  <Icon name="book" />
                                  根拠資料 <span>{draft.sources.length}</span>
                                </h4>
                                {draft.sources.map((s, i) => (
                                  <details key={s.id}>
                                    <summary>
                                      <span className="source-number">
                                        {i + 1}
                                      </span>
                                      {s.title}
                                      <small>v{s.version}</small>
                                    </summary>
                                    <pre>{s.excerpt}</pre>
                                    <p className="muted">
                                      生成時点の抜粋を保存しています。スコア{" "}
                                      {s.score}{" "}
                                      は文字の類似度で、回答の正しさを表しません。
                                    </p>
                                  </details>
                                ))}
                              </div>
                            )}
                            {draft.status === "draft" && canReview && (
                              <div className="review">
                                <label>
                                  確認メモ
                                  <input
                                    aria-label="確認メモ"
                                    value={reviewNote}
                                    onChange={(e) =>
                                      setReviewNote(e.target.value)
                                    }
                                    placeholder="適用条件・修正した点など"
                                    maxLength={1000}
                                  />
                                </label>
                                <label className="checkbox">
                                  <input
                                    type="checkbox"
                                    checked={checked}
                                    onChange={(e) =>
                                      setChecked(e.target.checked)
                                    }
                                  />
                                  根拠資料と返信内容を確認しました
                                </label>
                                <div className="actions">
                                  <button
                                    className="primary"
                                    disabled={
                                      busy ||
                                      !checked ||
                                      draft.stale ||
                                      reviewNote.trim().length < 2 ||
                                      !reviewText.trim()
                                    }
                                    onClick={() => review("approved")}
                                  >
                                    <Icon name="check" />
                                    承認する
                                  </button>
                                  <button
                                    disabled={
                                      busy ||
                                      reviewNote.trim().length < 2 ||
                                      !reviewText.trim()
                                    }
                                    onClick={() => review("rejected")}
                                  >
                                    差し戻す
                                  </button>
                                </div>
                                <small>
                                  承認は保存のみです。お客様へのメール送信機能はありません。
                                </small>
                              </div>
                            )}
                            {draft.reviewer && (
                              <p className="reviewed">
                                {draft.reviewer} が{statusNames[draft.status]} ·{" "}
                                {draft.review_note}
                              </p>
                            )}
                            {!canReview && draft.status === "draft" && (
                              <p className="warning">
                                管理者またはレビュアーによる確認をお待ちください。
                              </p>
                            )}
                          </>
                        ) : (
                          !preview && (
                            <div className="reply-empty">
                              <div className="mini-line" />
                              <div className="mini-line short" />
                              <p>
                                ナレッジをもとに下書きを作り、
                                <br />
                                チームの確認を経て回答へ。
                              </p>
                            </div>
                          )
                        )}
                      </div>
                    </section>
                    <section className="internal-note">
                      <h3>チーム内メモ</h3>
                      <p className="muted">
                        お客様への送信やAI入力には含まれません。
                      </p>
                      <textarea
                        aria-label="チーム内メモ"
                        value={note}
                        onChange={(e) => setNote(e.target.value)}
                        rows={3}
                        maxLength={4000}
                        placeholder="確認事項や引き継ぎ内容を残す"
                      />
                      <button
                        disabled={busy || note.trim().length < 2}
                        onClick={() =>
                          run(async () => {
                            await api(
                              "/tickets/" + detail.ticket.id + "/notes",
                              "POST",
                              { text: note },
                            );
                            setNote("");
                            const updated = await api<Detail>(
                              "/tickets/" + detail.ticket.id,
                            );
                            setDetail((current) =>
                              current?.ticket.id === updated.ticket.id
                                ? { ...current, history: updated.history }
                                : current,
                            );
                            setNotice("チーム内メモを保存しました");
                          })
                        }
                      >
                        メモを保存
                      </button>
                    </section>
                    <details className="history">
                      <summary>
                        この問い合わせの操作履歴 · {detail.history.length} 件
                      </summary>
                      {detail.history.map((a) => (
                        <p key={a.id}>
                          {fmt(a.created_at)}　{a.actor} ·{" "}
                          {a.action === "ticket.note" ? "内部メモ" : a.action}
                          {typeof a.detail.text === "string" && (
                            <span className="note-text">{a.detail.text}</span>
                          )}
                        </p>
                      ))}
                    </details>
                  </>
                )}
              </div>
            </section>
          </>
        )}
        {page === "knowledge" && (
          <section className="knowledge">
            <div className="knowledge-bar">
              <div className="search">
                <Icon name="search" />
                <input
                  aria-label="資料を検索"
                  placeholder="資料名・本文を検索"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </div>
              <span>{articles.length} 件の資料 · 非公開資料はAI検索対象外</span>
            </div>
            <div className="article-grid">
              {articles
                .filter((a) => (a.title + a.body).includes(query))
                .map((a) => (
                  <article key={a.id} className="article-card">
                    <div className="article-top">
                      <span className="book-icon">
                        <Icon name="book" />
                      </span>
                      <span>{a.active ? "公開中" : "非公開"}</span>
                      <small>v{a.version}</small>
                    </div>
                    <p className="eyebrow">{a.category}</p>
                    <h2>{a.title}</h2>
                    <p>{a.body}</p>
                    <details
                      onToggle={(e) => {
                        if (e.currentTarget.open)
                          run(async () => {
                            const history = await api<
                              {
                                version: number;
                                body: string;
                                title: string;
                                created_at: string;
                              }[]
                            >("/articles/" + a.id + "/revisions");
                            setRevisions((r) => ({ ...r, [a.id]: history }));
                          });
                      }}
                    >
                      <summary>版の履歴を見る</summary>
                      {(revisions[a.id] || []).map((r) => (
                        <div className="revision" key={r.version}>
                          <strong>
                            v{r.version} · {r.title}
                          </strong>
                          <small>{fmt(r.created_at)}</small>
                          <pre>{r.body}</pre>
                        </div>
                      ))}
                    </details>
                    <footer>
                      <small>更新 {fmt(a.updated_at)}</small>
                      {canReview && (
                        <button
                          onClick={() => {
                            setEditing(a);
                            setModal("article");
                          }}
                        >
                          編集 <Icon name="arrow" />
                        </button>
                      )}
                    </footer>
                  </article>
                ))}
            </div>
            {!articles.length && (
              <p className="empty">
                資料を追加して、回答の根拠を整えましょう。
              </p>
            )}
          </section>
        )}
        {page === "audit" && (
          <section className="audit">
            <p className="muted">最新150件 / 時刻は日本時間です。</p>
            <table>
              <thead>
                <tr>
                  <th>日時</th>
                  <th>操作者</th>
                  <th>操作</th>
                  <th>詳細</th>
                </tr>
              </thead>
              <tbody>
                {audit.map((a) => (
                  <tr key={a.id}>
                    <td>{fmt(a.created_at)}</td>
                    <td>{a.actor}</td>
                    <td>{a.action}</td>
                    <td>
                      <details>
                        <summary>表示</summary>
                        <pre>{JSON.stringify(a.detail, null, 2)}</pre>
                      </details>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}
        <footer className="page-footer">
          RELAY Desk · 根拠をつなぐ、対応をつなぐ。
          <span>v0.2 / Portfolio edition</span>
        </footer>
      </main>
      {modal && (
        <div className="modal-backdrop">
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="modal-title"
            className="modal"
          >
            <header>
              <h2 id="modal-title">
                {modal === "ticket"
                  ? "問い合わせを登録"
                  : editing
                    ? "資料を編集"
                    : "資料を追加"}
              </h2>
              <button
                aria-label="閉じる"
                disabled={busy}
                onClick={() => setModal(null)}
              >
                ×
              </button>
            </header>
            <form onSubmit={saveForm}>
              <label>
                {modal === "ticket" ? "件名" : "資料名"}
                <input
                  autoFocus
                  name="title"
                  defaultValue={editing?.title || ""}
                  minLength={2}
                  maxLength={150}
                  required
                />
              </label>
              {modal === "ticket" && (
                <label>
                  お客様名（架空）
                  <input name="customer" maxLength={100} required />
                </label>
              )}
              <label>
                カテゴリ
                <select
                  name="category"
                  defaultValue={editing?.category || "その他"}
                >
                  {["配送", "請求", "アカウント", "その他"].map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </label>
              {modal === "ticket" && (
                <label>
                  優先度
                  <select name="priority">
                    <option value="normal">通常</option>
                    <option value="high">優先</option>
                  </select>
                </label>
              )}
              <label>
                {modal === "ticket" ? "お問い合わせ内容" : "資料本文"}
                <textarea
                  name="body"
                  rows={7}
                  defaultValue={editing?.body || ""}
                  minLength={modal === "ticket" ? 5 : 10}
                  maxLength={modal === "ticket" ? 6000 : 12000}
                  required
                />
              </label>
              {modal === "article" && (
                <label className="checkbox">
                  <input
                    name="active"
                    type="checkbox"
                    defaultChecked={editing?.active ?? true}
                  />
                  AIが参照できる資料として公開する
                </label>
              )}
              {error && (
                <p className="error" role="alert">
                  {error}
                </p>
              )}
              <button className="primary" disabled={busy}>
                保存する
              </button>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
