let csrf = "";
export function setCsrf(value: string) {
  csrf = value;
}
export async function api<T>(
  path: string,
  method = "GET",
  data?: unknown,
): Promise<T> {
  const res = await fetch("/api" + path, {
    method,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
    ...(data !== undefined ? { body: JSON.stringify(data) } : {}),
  });
  const result = await res.json();
  if (!res.ok) {
    if (res.status === 401 && !path.includes("login"))
      window.dispatchEvent(new Event("session-expired"));
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "入力内容を確認してください",
    );
  }
  return result;
}
export type User = { id: string; name: string; role: string };
export type Ticket = {
  id: string;
  title: string;
  body: string;
  customer: string;
  category: string;
  priority: string;
  status: string;
  assignee_id: string | null;
  version: number;
  created_at: string;
};
export type Article = {
  id: string;
  title: string;
  body: string;
  category: string;
  version: number;
  active: boolean;
  updated_at: string;
};
export type Source = {
  id: string;
  title: string;
  version: number;
  excerpt: string;
  score: number;
};
export type Draft = {
  id: string;
  status: string;
  original: string;
  reviewed_text: string | null;
  sources: Source[];
  warning: string;
  provider: string;
  model: string;
  reviewer: string | null;
  review_note: string | null;
  stale: boolean;
  created_at: string;
};
export type Audit = {
  id: string;
  actor: string;
  action: string;
  created_at: string;
  detail: Record<string, unknown>;
};
export type Detail = { ticket: Ticket; drafts: Draft[]; history: Audit[] };
export type Preview = {
  question: string;
  sources: Source[];
  provider: string;
  ticket_version: number;
  source_digest: string;
};
export type Me = { user: User; tenant: string; csrf: string; provider: string };
