import { useEffect, useMemo, useState } from "react";
import { api } from "./apiClient";

const defaultPayload = `{
  "meta": {
    "created_at": "2024-04-01T12:00:00+00:00",
    "updated_at": "2024-04-01T12:30:00+00:00",
    "version": 1,
    "type": "unrestricted"
  },
  "data": {
    "examples": {
      "huggingface_file": {
        "url": "https://huggingface.co/datasets/adlsdztony/osworld-v2/blob/main/email_031.tar.gz",
        "note": "Optional reference link"
      }
    },
    "uploads": []
  },
  "note": "Optional note about this state"
}`;

const COOKIE_NAME = import.meta.env.VITE_COOKIE_NAME || "user_id";
const COOKIE_MAX_AGE = Number(import.meta.env.VITE_COOKIE_MAX_AGE || 60 * 60 * 24 * 30);

// this function checks the URL for a "cookie" query parameter,
// sets the cookie accordingly, and reloads the page without the query parameter
// when build on the basesite, the below function should remain unchanged
const applyCookieFromQuery = () => {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  const override = url.searchParams.get("cookie");
  if (!override) return false;
  let cookie = `${COOKIE_NAME}=${encodeURIComponent(override)}; Path=/; SameSite=Lax`;
  if (Number.isFinite(COOKIE_MAX_AGE) && COOKIE_MAX_AGE > 0) {
    cookie += `; Max-Age=${Math.floor(COOKIE_MAX_AGE)}`;
  }
  document.cookie = cookie;
  const redirectUrl = url.origin;
  if (window.location.href !== redirectUrl) {
    window.location.replace(redirectUrl);
    return true;
  }
  return false;
};

const dataFields = [
  {
    title: "data",
    description: "Object. Free-form container for experiment data and UI features.",
  },
  {
    title: "data.examples",
    description: "Object. Example references used by the UI.",
  },
  {
    title: "data.examples.huggingface_file.url",
    description: "String. Example dataset URL; /blob/ links are converted to /resolve/.",
  },
  {
    title: "data.examples.huggingface_file.note",
    description: "String. Human note about the example file.",
  },
  {
    title: "data.uploads",
    description: "Array<Upload>. Base64 data URLs stored for the current user.",
  },
  {
    title: "data.uploads[].filename",
    description: "String. Original file name.",
  },
  {
    title: "data.uploads[].content_type",
    description: "String. MIME type (falls back to application/octet-stream).",
  },
  {
    title: "data.uploads[].size",
    description: "Number. File size in bytes.",
  },
  {
    title: "data.uploads[].content_base64",
    description: "String. Data URL, e.g. data:application/pdf;base64,...",
  },
  {
    title: "data.uploads[].uploaded_at",
    description: "String. ISO 8601 timestamp.",
  },
  {
    title: "data.experiment",
    description: "Object. Example experiment metadata (optional).",
  },
  {
    title: "data.experiment.step",
    description: "Number. Example step indicator (optional).",
  },
  {
    title: "data.experiment.status",
    description: "String. Example status label (optional).",
  },
];

const exampleState = `{
  "meta": {
    "created_at": "2024-04-01T12:00:00+00:00",
    "updated_at": "2024-04-01T12:30:00+00:00",
    "version": 2,
    "type": "unrestricted"
  },
  "data": {
    "experiment": { "step": 1, "status": "draft" },
    "uploads": []
  },
  "note": "Seeded default data"
}`;

function StateManage() {
  const [activeTab, setActiveTab] = useState("manage");
  const [state, setState] = useState(null);
  const [editor, setEditor] = useState(defaultPayload);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const userId = useMemo(() => state?.user_id || "pending cookie", [state]);
  const lastUpdated = state?.state?.meta?.updated_at || "not synced yet";

  const handleError = (err) => {
    console.error(err);
    setError(err.message || "Request failed");
  };

  const refreshState = async ({ syncEditor = true } = {}) => {
    try {
      setLoading(true);
      const next = await api.getState();
      setState(next);
      if (syncEditor) {
        setEditor(JSON.stringify(next.state || {}, null, 2));
      }
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const redirected = applyCookieFromQuery();
    if (redirected) return;
    refreshState();
  }, []);

  const parseEditor = () => {
    try {
      return JSON.parse(editor);
    } catch (err) {
      throw new Error("Editor content is not valid JSON.");
    }
  };

  const handleSave = async () => {
    setMessage("");
    setError("");
    try {
      setLoading(true);
      const payload = parseEditor();
      if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
        throw new Error("State must be a JSON object.");
      }
      const hasEnvelope = Object.prototype.hasOwnProperty.call(payload, "data");
      const nextData = hasEnvelope ? payload.data : payload;
      if (!nextData || typeof nextData !== "object" || Array.isArray(nextData)) {
        throw new Error("State must include a data object.");
      }
      const hasNote = Object.prototype.hasOwnProperty.call(payload, "note");
      const nextNote = hasNote ? payload.note : undefined;
      const hasMeta = Object.prototype.hasOwnProperty.call(payload, "meta");
      const nextMeta = hasMeta ? payload.meta : undefined;
      const next = await api.replaceState(nextData, nextNote, nextMeta);
      setState(next);
      setEditor(JSON.stringify(next.state || {}, null, 2));
      setMessage("State saved.");
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async () => {
    setMessage("");
    setError("");
    try {
      setLoading(true);
      const next = await api.resetState();
      setState(next);
      setEditor(JSON.stringify(next.state || {}, null, 2));
      setMessage("State reset.");
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  };

  const downloadState = () => {
    setMessage("");
    setError("");
    try {
      const payload = parseEditor();
      const fileNameBase = state?.user_id ? `state-${state.user_id}` : "state";
      const blob = new Blob([JSON.stringify(payload, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${fileNameBase}.json`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      handleError(err);
    }
  };

  return (
    <div
      className="relative h-screen min-h-screen overflow-hidden bg-[var(--page-bg)] text-slate-900"
      style={{
        "--page-bg": "#f7f6f1",
        "--paper": "rgba(255,255,255,0.88)",
        "--line": "rgba(15,23,42,0.08)",
        "--accent": "#0f766e",
        "--accent-soft": "rgba(13,148,136,0.12)",
      }}
    >
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage:
            "radial-gradient(circle at 12% 18%, rgba(15,118,110,0.12), transparent 45%)," +
            "radial-gradient(circle at 85% 5%, rgba(8,145,178,0.1), transparent 40%)," +
            "linear-gradient(90deg, rgba(15,23,42,0.04) 1px, transparent 1px)," +
            "linear-gradient(180deg, rgba(15,23,42,0.04) 1px, transparent 1px)",
          backgroundSize: "auto, auto, 140px 140px, 140px 140px",
        }}
      />

      <div className="relative mx-auto flex h-full max-w-6xl flex-col gap-6 px-6 py-10">
        <header className="flex flex-col gap-6 rounded-3xl border border-[var(--line)] bg-[var(--paper)] p-6 shadow-[0_24px_60px_rgba(15,23,42,0.08)] backdrop-blur motion-safe:animate-fade-in">
          <div className="flex flex-col gap-2">
            <h1 className="font-display text-3xl text-slate-900 md:text-4xl">State console</h1>
          </div>
          <div className="flex flex-wrap gap-2 text-xs text-slate-600">
            <span className="rounded-full border border-[var(--line)] px-3 py-1">
              User cookie: {userId}
            </span>
            <span className="rounded-full border border-[var(--line)] px-3 py-1">
              API base: {api.baseUrl}
            </span>
            <span className="rounded-full border border-[var(--line)] px-3 py-1">
              Last update: {lastUpdated}
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {[
              { id: "docs", label: "State docs" },
              { id: "manage", label: "Manage state" },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`rounded-full border px-4 py-2 text-sm font-medium transition ${
                  activeTab === tab.id
                    ? "border-[var(--accent)] bg-[var(--accent-soft)] text-slate-900"
                    : "border-[var(--line)] text-slate-600 hover:border-slate-300"
                }`}
                aria-pressed={activeTab === tab.id}
              >
                {tab.label}
              </button>
            ))}
            <a
              className="rounded-full border border-[var(--line)] px-4 py-2 text-sm font-medium text-slate-600 transition hover:border-slate-300"
              href="/"
            >
              Back to home
            </a>
          </div>
        </header>

        {activeTab === "docs" ? (
          <section className="flex min-h-0 flex-1 flex-col gap-4 overflow-hidden">
            <div className="grid min-h-0 flex-1 gap-4 overflow-auto lg:grid-cols-[1.2fr_0.8fr]">
              <article
                className="rounded-3xl border border-[var(--line)] bg-[var(--paper)] p-5 shadow-[0_16px_40px_rgba(15,23,42,0.06)] motion-safe:animate-rise-in"
                style={{ animationDelay: "240ms" }}
              >
                <h2 className="font-display text-lg text-slate-900">Data field reference</h2>
                <p className="mt-2 text-sm text-slate-600">
                  Focus on the data payload. Meta and note are secondary.
                </p>
                <div className="mt-4 grid gap-3 text-sm text-slate-700">
                  {dataFields.map((field, index) => (
                    <div
                      key={field.title}
                      className="rounded-2xl border border-[var(--line)] bg-white/70 p-3"
                      style={{ animationDelay: `${index * 70}ms` }}
                    >
                      <div className="font-mono text-xs text-slate-500">{field.title}</div>
                      <p className="mt-1 text-sm text-slate-700">{field.description}</p>
                    </div>
                  ))}
                </div>
              </article>

              <article
                className="rounded-3xl border border-[var(--accent)] bg-[var(--accent-soft)] p-5 text-sm text-slate-700 shadow-[0_16px_40px_rgba(15,23,42,0.06)] motion-safe:animate-rise-in"
                style={{ animationDelay: "320ms" }}
              >
                <h2 className="font-display text-lg text-slate-900">Full example</h2>
                <p className="mt-2 text-sm text-slate-700">
                  This example mirrors the full envelope returned by the backend.
                </p>
                <pre className="mt-4 max-h-[360px] overflow-auto rounded-2xl border border-[var(--line)] bg-white/80 p-4 font-mono text-xs text-slate-700">
                  {exampleState}
                </pre>
                <p className="mt-4 text-sm text-slate-700">
                  Any site built on basesite must keep the /state-manage interface with both the
                  documentation and the live editor. This page is the canonical place to inspect
                  and update per-user state.
                </p>
              </article>
            </div>
          </section>
        ) : (
          <section className="flex flex-1 flex-col gap-4">
            <article className="flex min-h-0 flex-1 flex-col rounded-3xl border border-[var(--line)] bg-[var(--paper)] p-5 shadow-[0_16px_40px_rgba(15,23,42,0.06)] motion-safe:animate-rise-in">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="font-display text-lg text-slate-900">Edit in one JSON view</h2>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => refreshState()}
                    disabled={loading}
                    className="rounded-full border border-[var(--line)] px-3 py-1 text-xs font-semibold text-slate-600 transition hover:border-slate-300"
                  >
                    Refresh from server
                  </button>
                </div>
              </div>

              <div className="mt-4 flex min-h-0 flex-1 flex-col gap-3">
                <label className="flex min-h-0 flex-1 flex-col gap-2 text-sm text-slate-600">
                  <span>Full state JSON</span>
                  <textarea
                    className="min-h-0 w-full flex-1 rounded-2xl border border-[var(--line)] bg-white/80 px-4 py-3 font-mono text-xs text-slate-800 outline-none ring-1 ring-transparent transition focus:ring-emerald-400/40"
                    value={editor}
                    onChange={(event) => setEditor(event.target.value)}
                    spellCheck={false}
                  />
                </label>
                <div className="min-h-[24px] text-sm">
                  {error && <p className="text-rose-500">{error}</p>}
                  {!error && message && <p className="text-emerald-600">{message}</p>}
                </div>
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={handleSave}
                  disabled={loading}
                  className="rounded-full bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white transition hover:translate-y-[-1px]"
                >
                  Save
                </button>
                <button
                  type="button"
                  onClick={downloadState}
                  disabled={loading}
                  className="rounded-full border border-[var(--line)] px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300"
                >
                  Download JSON
                </button>
                <button
                  type="button"
                  onClick={handleReset}
                  disabled={loading}
                  className="rounded-full border border-[var(--line)] px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300"
                >
                  Reset state
                </button>
              </div>
            </article>
          </section>
        )}
      </div>
    </div>
  );
}

export default StateManage;
