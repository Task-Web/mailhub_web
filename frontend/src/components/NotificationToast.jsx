import React, { useEffect } from "react";
import { useStore } from "../context/StoreContext";

const AUTO_DISMISS_MS = 6000;

const NotificationToast = () => {
  const { notifications, dismissNotification } = useStore();

  useEffect(() => {
    if (notifications.length === 0) return;
    const oldest = notifications[0];
    const age = Date.now() - oldest.timestamp;
    const remaining = Math.max(AUTO_DISMISS_MS - age, 0);
    const timer = setTimeout(() => dismissNotification(oldest.id), remaining);
    return () => clearTimeout(timer);
  }, [notifications, dismissNotification]);

  if (notifications.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2" style={{ maxWidth: 360 }}>
      {notifications.map((n) => (
        <div
          key={n.id}
          className="animate-slide-in flex items-start gap-3 rounded-lg bg-white px-4 py-3 shadow-lg ring-1 ring-black/5"
        >
          <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-100 text-blue-600">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
              <path d="M3 4a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v1.1l-7 4.5-7-4.5V4Z" />
              <path d="M3 7.05l6.625 4.263a.75.75 0 0 0 .75 0L17 7.05V14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7.05Z" />
            </svg>
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-gray-900">{n.from}</p>
            <p className="truncate text-sm text-gray-700">{n.subject}</p>
            {n.snippet && (
              <p className="mt-0.5 truncate text-xs text-gray-400">{n.snippet}</p>
            )}
          </div>
          <button
            onClick={() => dismissNotification(n.id)}
            className="ml-1 shrink-0 rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
            aria-label="Dismiss"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
              <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
            </svg>
          </button>
        </div>
      ))}
    </div>
  );
};

export default NotificationToast;
