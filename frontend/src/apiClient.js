const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000/api";

async function request(path, options = {}) {
  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  const headers = {
    ...(options.headers || {}),
  };
  if (!isFormData && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    headers,
    ...options,
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    const message = errorBody.detail || response.statusText || "Request failed";
    throw new Error(message);
  }

  return response.json();
}

export const api = {
  baseUrl: API_BASE,
  getInfo: () => request("/info"),
  getMailState: () => request("/mail/state"),
  sendMail: (payload) => request("/mail/send", { method: "POST", body: JSON.stringify(payload) }),
  replyMail: (payload) => request("/mail/reply", { method: "POST", body: JSON.stringify(payload) }),
  saveDraft: (payload) => request("/mail/draft", { method: "POST", body: JSON.stringify(payload) }),
  deleteDraft: (draftId) => request(`/mail/draft/${draftId}`, { method: "DELETE" }),
  updateEmail: (emailId, updates) =>
    request(`/mail/email/${emailId}`, { method: "PATCH", body: JSON.stringify({ updates }) }),
  bulkUpdate: (emailIds, updates) =>
    request("/mail/bulk", {
      method: "POST",
      body: JSON.stringify({ email_ids: emailIds, updates }),
    }),
  archiveEmails: (emailIds) =>
    request("/mail/archive", { method: "POST", body: JSON.stringify({ email_ids: emailIds }) }),
  deleteEmails: (emailIds) =>
    request("/mail/delete", { method: "POST", body: JSON.stringify({ email_ids: emailIds }) }),
  emptyTrash: () => request("/mail/empty-trash", { method: "POST" }),
  createLabel: (payload) => request("/mail/labels", { method: "POST", body: JSON.stringify(payload) }),
  toggleLabel: (emailId, payload) =>
    request(`/mail/email/${emailId}/labels`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  uploadFiles: (files) => {
    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));
    return request("/files", { method: "POST", body: formData });
  },
  listFiles: () => request("/files"),
};
