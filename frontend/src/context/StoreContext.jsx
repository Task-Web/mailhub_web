import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../apiClient";

const StoreContext = createContext();

const EMPTY_STATE = {
  user: { username: "Loading...", email: "", avatar: "" },
  emails: [],
  labels: [],
  drafts: [],
};

export const useStore = () => {
  const context = useContext(StoreContext);
  if (!context) {
    throw new Error("useStore must be used within a StoreProvider");
  }
  return context;
};

export const StoreProvider = ({ children }) => {
  const [state, setState] = useState(EMPTY_STATE);
  const [userId, setUserId] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [error, setError] = useState(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [selectedEmails, setSelectedEmails] = useState([]);
  const [isComposeOpen, setIsComposeOpen] = useState(false);
  const [activeCategory, setActiveCategory] = useState("primary");
  const [isSearchModalOpen, setIsSearchModalOpen] = useState(false);
  const [currentDraftId, setCurrentDraftId] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const knownEmailIds = useRef(new Set());
  const notificationsEnabled = useRef(false);

  const applyMailResponse = useCallback((response) => {
    if (!response || !response.mail) return;
    setState(response.mail);
    setUserId(response.user_id || null);
    if (response.enable_notifications !== undefined) {
      notificationsEnabled.current = !!response.enable_notifications;
    }
  }, []);

  const runAction = useCallback(async (action, after) => {
    setError(null);
    setIsSyncing(true);
    try {
      const response = await action();
      applyMailResponse(response);
      if (after) after(response);
    } catch (err) {
      setError(err.message || "Request failed");
    } finally {
      setIsSyncing(false);
    }
  }, [applyMailResponse]);

  const refreshState = useCallback(async () => {
    setError(null);
    setIsLoading(true);
    try {
      const response = await api.getMailbox();
      applyMailResponse(response);
    } catch (err) {
      setError(err.message || "Failed to load mail state");
    } finally {
      setIsLoading(false);
    }
  }, [applyMailResponse]);

  useEffect(() => {
    refreshState();
  }, [refreshState]);

  // Poll for new emails every 5 seconds (only when notifications are enabled)
  useEffect(() => {
    const interval = setInterval(async () => {
      if (!notificationsEnabled.current) return;
      try {
        const response = await api.getMailbox();
        if (!response || !response.mail) return;
        const emails = response.mail.emails || [];
        const inboxEmails = emails.filter((e) => e.folder === "inbox");
        const newEmails = [];
        inboxEmails.forEach((e) => {
          if (!knownEmailIds.current.has(e.id)) {
            knownEmailIds.current.add(e.id);
            newEmails.push(e);
          }
        });
        if (newEmails.length > 0) {
          setNotifications((prev) => [
            ...prev,
            ...newEmails.map((e) => ({
              id: e.id,
              from: e.from?.name || e.from?.email || "Unknown",
              subject: e.subject || "(no subject)",
              snippet: e.snippet || "",
              timestamp: Date.now(),
            })),
          ]);
        }
        // Sync state so UI updates with new emails
        applyMailResponse(response);
      } catch (_) {
        // Silently ignore poll errors
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [applyMailResponse]);

  // Seed known IDs from initial load
  useEffect(() => {
    if (state.emails && state.emails.length > 0 && knownEmailIds.current.size === 0) {
      state.emails.forEach((e) => knownEmailIds.current.add(e.id));
    }
  }, [state.emails]);

  const dismissNotification = useCallback((notifId) => {
    setNotifications((prev) => prev.filter((n) => n.id !== notifId));
  }, []);

  const updateEmail = useCallback(
    (emailId, updates) =>
      runAction(() => api.updateEmail(emailId, updates)),
    [runAction]
  );

  const bulkUpdateEmails = useCallback(
    (emailIds, updates) =>
      runAction(() => api.bulkUpdate(emailIds, updates), () => setSelectedEmails([])),
    [runAction]
  );

  const deleteEmails = useCallback(
    (emailIds) =>
      runAction(() => api.deleteEmails(emailIds), () => setSelectedEmails([])),
    [runAction]
  );

  const archiveEmails = useCallback(
    (emailIds) =>
      runAction(() => api.archiveEmails(emailIds), () => setSelectedEmails([])),
    [runAction]
  );

  const sendEmail = useCallback(
    (emailData) =>
      runAction(
        () => api.sendMail({ ...emailData, draft_id: currentDraftId }),
        () => setCurrentDraftId(null)
      ),
    [currentDraftId, runAction]
  );

  const saveDraft = useCallback(
    (draftData) => {
      const hasContent = Boolean(
        draftData?.to ||
          draftData?.cc ||
          draftData?.bcc ||
          draftData?.subject ||
          draftData?.body ||
          (draftData?.attachments || []).length > 0
      );

      if (!hasContent && !currentDraftId) return;

      runAction(
        () => api.saveDraft({ ...draftData, draft_id: currentDraftId }),
        (response) => setCurrentDraftId(response?.draft_id || currentDraftId)
      );
    },
    [currentDraftId, runAction]
  );

  const uploadAttachments = useCallback(async (files) => {
    if (!files || files.length === 0) return [];
    setError(null);
    setIsSyncing(true);
    try {
      const response = await api.uploadFiles(files);
      return response?.files || [];
    } catch (err) {
      setError(err.message || "Upload failed");
      throw err;
    } finally {
      setIsSyncing(false);
    }
  }, []);

  const deleteDraft = useCallback(
    (draftId) =>
      runAction(() => api.deleteDraft(draftId), () => setCurrentDraftId(null)),
    [runAction]
  );

  const replyToEmail = useCallback(
    (threadId, body, replyAll = false, attachments = []) =>
      runAction(() =>
        api.replyMail({ thread_id: threadId, body, reply_all: replyAll, attachments })
      ),
    [runAction]
  );

  const toggleStar = useCallback(
    (emailId) => {
      const email = state.emails.find((item) => item.id === emailId);
      if (!email) return;
      updateEmail(emailId, { starred: !email.starred });
    },
    [state.emails, updateEmail]
  );

  const toggleImportant = useCallback(
    (emailId) => {
      const email = state.emails.find((item) => item.id === emailId);
      if (!email) return;
      updateEmail(emailId, { important: !email.important });
    },
    [state.emails, updateEmail]
  );

  const toggleRead = useCallback(
    (emailId, status) => updateEmail(emailId, { read: status }),
    [updateEmail]
  );

  const addLabel = useCallback(
    (emailId, labelId) =>
      runAction(() => api.toggleLabel(emailId, { label_id: labelId, action: "add" })),
    [runAction]
  );

  const removeLabel = useCallback(
    (emailId, labelId) =>
      runAction(() => api.toggleLabel(emailId, { label_id: labelId, action: "remove" })),
    [runAction]
  );

  const toggleLabel = useCallback(
    (emailId, labelId) =>
      runAction(() => api.toggleLabel(emailId, { label_id: labelId, action: "toggle" })),
    [runAction]
  );

  const createLabel = useCallback(
    (name, color) => runAction(() => api.createLabel({ name, color })),
    [runAction]
  );

  const emptyTrash = useCallback(
    () => runAction(() => api.emptyTrash()),
    [runAction]
  );

  const value = useMemo(
    () => ({
      state,
      userId,
      isLoading,
      isSyncing,
      error,
      refreshState,
      searchQuery,
      setSearchQuery,
      selectedEmails,
      setSelectedEmails,
      isComposeOpen,
      setIsComposeOpen,
      activeCategory,
      setActiveCategory,
      isSearchModalOpen,
      setIsSearchModalOpen,
      currentDraftId,
      setCurrentDraftId,
      updateEmail,
      bulkUpdateEmails,
      deleteEmails,
      archiveEmails,
      sendEmail,
      saveDraft,
      uploadAttachments,
      deleteDraft,
      replyToEmail,
      toggleStar,
      toggleImportant,
      toggleRead,
      addLabel,
      removeLabel,
      toggleLabel,
      createLabel,
      emptyTrash,
      notifications,
      dismissNotification,
    }),
    [
      state,
      userId,
      isLoading,
      isSyncing,
      error,
      refreshState,
      searchQuery,
      selectedEmails,
      isComposeOpen,
      activeCategory,
      isSearchModalOpen,
      currentDraftId,
      updateEmail,
      bulkUpdateEmails,
      deleteEmails,
      archiveEmails,
      sendEmail,
      saveDraft,
      uploadAttachments,
      deleteDraft,
      replyToEmail,
      toggleStar,
      toggleImportant,
      toggleRead,
      addLabel,
      removeLabel,
      toggleLabel,
      createLabel,
      emptyTrash,
      notifications,
      dismissNotification,
    ]
  );

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
};
