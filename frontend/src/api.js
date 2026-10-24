export const ROLE_TOKENS = {
  employee: "employee-token",
  finance: "finance-token",
  research: "research-token",
  hr: "hr-token",
  admin: "admin-token",
};

async function request(path, role, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: { Authorization: `Bearer ${ROLE_TOKENS[role]}`, ...(options.headers || {}) },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`);
  return body;
}

export const api = {
  chat: (role, question, mode) =>
    request("/chat", role, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, mode }),
    }),
  feedback: (role, request_id, rating, comment = "") =>
    request("/feedback", role, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ request_id, rating, comment }),
    }),
  docs: (role) => request("/admin/docs", role),
  upload: (role, file, allowedRoles, title) => {
    const form = new FormData();
    form.append("file", file);
    form.append("allowed_roles", allowedRoles);
    form.append("title", title);
    return request("/admin/upload", role, { method: "POST", body: form });
  },
};
