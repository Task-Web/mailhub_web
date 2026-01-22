import React, { useEffect, useState } from "react";
import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import { StoreProvider, useStore } from "./context/StoreContext";
import Sidebar from "./components/Sidebar";
import Header from "./components/Header";
import EmailList from "./components/EmailList";
import ThreadView from "./components/ThreadView";
import ComposeModal from "./components/ComposeModal";
import ErrorBoundary from "./components/ErrorBoundary";

const COOKIE_NAME = import.meta.env.VITE_COOKIE_NAME || "user_id";
const COOKIE_MAX_AGE = Number(import.meta.env.VITE_COOKIE_MAX_AGE || 60 * 60 * 24 * 30);

// when build on the basesite, the below function should remain unchanged
const applyCookieFromQuery = () => {
  if (typeof window === "undefined") return false;
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

const KeyboardShortcuts = () => {
  const { setIsComposeOpen, selectedEmails, archiveEmails, deleteEmails } = useStore();

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) return;

      switch (event.key.toLowerCase()) {
        case "c":
          event.preventDefault();
          setIsComposeOpen(true);
          break;
        case "/": {
          event.preventDefault();
          const searchInput = document.querySelector('input[placeholder="Search mail"]');
          if (searchInput) {
            searchInput.focus();
            setTimeout(() => {
              searchInput.value = "";
            }, 0);
          }
          break;
        }
        case "e":
          if (selectedEmails.length > 0) {
            event.preventDefault();
            archiveEmails(selectedEmails);
          }
          break;
        case "#":
          if (selectedEmails.length > 0) {
            event.preventDefault();
            deleteEmails(selectedEmails);
          }
          break;
        default:
          break;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [archiveEmails, deleteEmails, selectedEmails, setIsComposeOpen]);

  return null;
};

const Layout = ({ children }) => (
  <div className="flex h-screen w-screen flex-col overflow-hidden bg-[#f6f8fc]">
    <Header />
    <div className="flex flex-1 overflow-hidden">
      <Sidebar />
      <main className="relative flex-1 overflow-hidden p-4 pl-0">{children}</main>
    </div>
    <ComposeModal />
    <KeyboardShortcuts />
  </div>
);

const MailRoutes = () => {
  const { isLoading, error, refreshState } = useStore();

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-[#f6f8fc]">
        <div className="rounded-lg bg-white px-6 py-4 text-sm text-gray-600 shadow">
          Loading mailbox...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-screen items-center justify-center bg-[#f6f8fc]">
        <div className="max-w-md rounded-lg bg-white px-6 py-4 text-sm text-gray-700 shadow">
          <p className="mb-3 font-medium text-gray-900">Mailbox unavailable</p>
          <p className="mb-4 text-gray-500">{error}</p>
          <button
            onClick={refreshState}
            className="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/inbox" replace />} />
        <Route path="/inbox" element={<Layout><EmailList folder="inbox" /></Layout>} />
        <Route path="/starred" element={<Layout><EmailList folder="starred" /></Layout>} />
        <Route path="/important" element={<Layout><EmailList folder="important" /></Layout>} />
        <Route path="/sent" element={<Layout><EmailList folder="sent" /></Layout>} />
        <Route path="/drafts" element={<Layout><EmailList folder="drafts" /></Layout>} />
        <Route path="/spam" element={<Layout><EmailList folder="spam" /></Layout>} />
        <Route path="/trash" element={<Layout><EmailList folder="trash" /></Layout>} />
        <Route path="/all-mail" element={<Layout><EmailList folder="all-mail" /></Layout>} />
        <Route path="/label/:labelId" element={<Layout><EmailList /></Layout>} />
        <Route path="/email/:threadId" element={<Layout><ThreadView /></Layout>} />
      </Routes>
    </HashRouter>
  );
};

function App() {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const redirected = applyCookieFromQuery();
    if (!redirected) setReady(true);
  }, []);

  if (!ready) return null;

  return (
    <ErrorBoundary>
      <StoreProvider>
        <MailRoutes />
      </StoreProvider>
    </ErrorBoundary>
  );
}

export default App;
