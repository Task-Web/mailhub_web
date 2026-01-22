import React, { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Archive,
  CheckSquare,
  Inbox,
  Mail,
  MoreVertical,
  Square,
  Star,
  Tag,
  Trash2,
} from "lucide-react";
import { useStore } from "../context/StoreContext";
import { cn, formatDate } from "../lib/utils";

const EmailRow = ({ email, isSelected, toggleSelect, labelMap }) => {
  const navigate = useNavigate();
  const { toggleStar, toggleImportant, toggleRead, archiveEmails, deleteEmails } = useStore();

  const handleRowClick = (event) => {
    if (event.target.closest("button") || event.target.closest("input")) return;
    navigate(`/email/${email.threadId}`);
    if (!email.read) toggleRead(email.id, true);
  };

  return (
    <div
      onClick={handleRowClick}
      className={cn(
        "group relative z-0 flex cursor-pointer items-center border-b border-gray-100 px-4 py-2 hover:shadow-md",
        email.read ? "bg-white" : "bg-[#f2f6fc]",
        isSelected && "bg-[#c2dbff]"
      )}
    >
      <div className="mr-4 flex w-12 flex-shrink-0 items-center gap-2">
        <button onClick={() => toggleSelect(email.id)} className="text-gray-400 hover:text-gray-600">
          {isSelected ? <CheckSquare size={20} className="text-black" /> : <Square size={20} />}
        </button>
        <button
          onClick={(event) => {
            event.stopPropagation();
            toggleStar(email.id);
          }}
          className={cn(
            "hover:text-yellow-400",
            email.starred ? "text-yellow-400 fill-current" : "text-gray-400"
          )}
        >
          <Star size={20} fill={email.starred ? "currentColor" : "none"} />
        </button>
      </div>

      <div className="mr-2 flex-shrink-0">
        <button
          onClick={(event) => {
            event.stopPropagation();
            toggleImportant(email.id);
          }}
          className={cn(
            email.important ? "text-yellow-500" : "text-gray-300 hover:text-gray-400"
          )}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path
              d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z"
              fill={email.important ? "#F4B400" : "none"}
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>

      <div className={cn("w-48 truncate pr-4 flex-shrink-0", !email.read && "font-bold text-black")}>
        {email.from.name}
      </div>

      <div className="flex flex-1 items-center min-w-0">
        <div className="truncate text-sm text-gray-600">
          <span className={cn("text-gray-900", !email.read && "font-bold")}>
            {email.subject}
          </span>
          <span className="mx-2 text-gray-400">-</span>
          <span>{email.snippet}</span>
        </div>
        <div className="ml-2 flex gap-1">
          {email.labels.map((labelId) => {
            const label = labelMap.get(labelId);
            return label ? (
              <div
                key={labelId}
                className="h-2 w-2 rounded-full"
                style={{ backgroundColor: label.color }}
                title={label.name}
              />
            ) : null;
          })}
        </div>
      </div>

      <div className="w-24 flex-shrink-0 text-right text-xs font-medium text-gray-500 group-hover:hidden">
        {formatDate(email.timestamp)}
      </div>

      <div className="hidden w-24 items-center justify-end gap-2 bg-inherit pl-2 group-hover:flex">
        <button
          className="rounded p-1 text-gray-600 hover:bg-gray-200"
          onClick={(event) => {
            event.stopPropagation();
            archiveEmails([email.id]);
          }}
        >
          <Archive size={16} />
        </button>
        <button
          className="rounded p-1 text-gray-600 hover:bg-gray-200"
          onClick={(event) => {
            event.stopPropagation();
            deleteEmails([email.id]);
          }}
        >
          <Trash2 size={16} />
        </button>
        <button
          className="rounded p-1 text-gray-600 hover:bg-gray-200"
          onClick={(event) => {
            event.stopPropagation();
            toggleRead(email.id, !email.read);
          }}
        >
          <Mail size={16} />
        </button>
      </div>
    </div>
  );
};

const EmailList = ({ folder = "inbox" }) => {
  const {
    state,
    searchQuery,
    activeCategory,
    setActiveCategory,
    selectedEmails,
    setSelectedEmails,
    bulkUpdateEmails,
    deleteEmails,
    archiveEmails,
    emptyTrash,
    toggleLabel,
  } = useStore();
  const { labelId } = useParams();
  const [showLabelPicker, setShowLabelPicker] = useState(false);

  const labelMap = useMemo(
    () => new Map(state.labels.map((label) => [label.id, label])),
    [state.labels]
  );

  const filteredEmails = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    const tokens = query ? query.split(/\s+/) : [];
    const filters = {
      from: null,
      to: null,
      subject: null,
      hasAttachment: false,
      isStarred: false,
      isImportant: false,
    };
    const freeTokens = [];

    tokens.forEach((token) => {
      if (token.startsWith("from:")) {
        filters.from = token.replace("from:", "");
      } else if (token.startsWith("to:")) {
        filters.to = token.replace("to:", "");
      } else if (token.startsWith("subject:")) {
        filters.subject = token.replace("subject:", "");
      } else if (token === "has:attachment") {
        filters.hasAttachment = true;
      } else if (token === "is:starred") {
        filters.isStarred = true;
      } else if (token === "is:important") {
        filters.isImportant = true;
      } else if (token) {
        freeTokens.push(token);
      }
    });

    const freeText = freeTokens.join(" ");

    return state.emails
      .filter((email) => {
        if (query) {
          if (filters.hasAttachment && (!email.attachments || email.attachments.length === 0))
            return false;
          if (
            filters.from &&
            ![email.from.name, email.from.email]
              .filter(Boolean)
              .some((value) => value.toLowerCase().includes(filters.from))
          )
            return false;
          if (
            filters.to &&
            !(email.to || []).some((recipient) =>
              [recipient.name, recipient.email]
                .filter(Boolean)
                .some((value) => value.toLowerCase().includes(filters.to))
            )
          )
            return false;
          if (filters.subject && !email.subject.toLowerCase().includes(filters.subject)) return false;
          if (filters.isStarred && !email.starred) return false;
          if (filters.isImportant && !email.important) return false;

          if (!freeText) return true;
          return (
            email.subject.toLowerCase().includes(freeText) ||
            email.from.name.toLowerCase().includes(freeText) ||
            (email.body || "").toLowerCase().includes(freeText)
          );
        }

        if (labelId) {
          return email.labels.includes(labelId) && email.folder !== "trash";
        }

        if (folder === "starred") return email.starred && email.folder !== "trash";
        if (folder === "important") return email.important && email.folder !== "trash";

        if (folder === "inbox") {
          if (email.folder !== "inbox") return false;
          return email.category === activeCategory;
        }

        if (folder === "all-mail") {
          return email.folder !== "trash" && email.folder !== "spam";
        }

        return email.folder === folder;
      })
      .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
  }, [state.emails, searchQuery, labelId, folder, activeCategory]);

  const threads = useMemo(() => {
    const threadMap = new Map();
    filteredEmails.forEach((email) => {
      if (!threadMap.has(email.threadId)) {
        threadMap.set(email.threadId, []);
      }
      threadMap.get(email.threadId).push(email);
    });

    return Array.from(threadMap.values()).map((threadEmails) => {
      threadEmails.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
      return threadEmails[0];
    });
  }, [filteredEmails]);

  const toggleSelect = (id) => {
    setSelectedEmails((prev) =>
      prev.includes(id) ? prev.filter((emailId) => emailId !== id) : [...prev, id]
    );
  };

  const toggleSelectAll = () => {
    setSelectedEmails((prev) =>
      prev.length === threads.length ? [] : threads.map((email) => email.id)
    );
  };

  return (
    <div className="flex h-full flex-1 flex-col overflow-hidden rounded-tl-2xl bg-white shadow-sm">
      <div className="flex h-12 items-center gap-4 border-b border-gray-200 px-4">
        <button onClick={toggleSelectAll} className="rounded p-1 text-gray-600 hover:bg-gray-100">
          {selectedEmails.length > 0 && selectedEmails.length === threads.length ? (
            <CheckSquare size={20} />
          ) : (
            <Square size={20} />
          )}
        </button>

        {selectedEmails.length > 0 ? (
          <div className="flex items-center gap-2">
            <button
              onClick={() => archiveEmails(selectedEmails)}
              className="rounded-full p-2 text-gray-600 hover:bg-gray-100"
              title="Archive"
            >
              <Archive size={18} />
            </button>
            <button
              onClick={() => deleteEmails(selectedEmails)}
              className="rounded-full p-2 text-gray-600 hover:bg-gray-100"
              title="Delete"
            >
              <Trash2 size={18} />
            </button>
            <button
              onClick={() => bulkUpdateEmails(selectedEmails, { read: true })}
              className="rounded-full p-2 text-gray-600 hover:bg-gray-100"
              title="Mark as read"
            >
              <Mail size={18} />
            </button>
            <div className="relative">
              <button
                onClick={() => setShowLabelPicker(!showLabelPicker)}
                className="rounded-full p-2 text-gray-600 hover:bg-gray-100"
                title="Labels"
              >
                <Tag size={18} />
              </button>
              {showLabelPicker && (
                <div className="absolute left-0 top-10 z-50 w-48 rounded border border-gray-200 bg-white py-2 shadow-xl">
                  <div className="border-b border-gray-100 px-3 pb-2 text-xs font-medium text-gray-500">
                    Apply label:
                  </div>
                  {state.labels.map((label) => (
                    <div
                      key={label.id}
                      onClick={() => {
                        selectedEmails.forEach((emailId) => toggleLabel(emailId, label.id));
                        setShowLabelPicker(false);
                      }}
                      className="flex cursor-pointer items-center gap-2 px-4 py-2 text-sm hover:bg-gray-100"
                    >
                      <Tag size={14} style={{ fill: label.color, stroke: "none" }} />
                      {label.name}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : (
          <button className="rounded p-2 text-gray-600 hover:bg-gray-100">
            <MoreVertical size={18} />
          </button>
        )}

        {folder === "trash" && (
          <button
            onClick={emptyTrash}
            className="ml-auto text-sm font-medium text-blue-600 hover:underline"
          >
            Empty Trash Now
          </button>
        )}
      </div>

      {folder === "inbox" && !searchQuery && !labelId && (
        <div className="flex border-b border-gray-200">
          {[
            { id: "primary", icon: Inbox, label: "Primary", color: "border-red-500 text-red-600" },
            { id: "social", icon: Tag, label: "Social", color: "border-blue-500 text-blue-600" },
            {
              id: "promotions",
              icon: Tag,
              label: "Promotions",
              color: "border-green-500 text-green-600",
            },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveCategory(tab.id)}
              className={cn(
                "flex flex-1 items-center gap-3 border-b-2 px-4 py-3 transition-colors hover:bg-gray-50",
                activeCategory === tab.id
                  ? `${tab.color} bg-gray-50`
                  : "border-transparent text-gray-500"
              )}
            >
              <tab.icon size={18} />
              <span className="text-sm font-medium">{tab.label}</span>
            </button>
          ))}
        </div>
      )}

      <div className="flex-1 overflow-y-auto">
        {threads.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-gray-500">
            <div className="mb-4 rounded-full bg-gray-100 p-8">
              <Inbox size={48} className="text-gray-300" />
            </div>
            <p className="text-lg">Your {folder} is empty</p>
          </div>
        ) : (
          threads.map((email) => (
            <EmailRow
              key={email.id}
              email={email}
              isSelected={selectedEmails.includes(email.id)}
              toggleSelect={toggleSelect}
              labelMap={labelMap}
            />
          ))
        )}
      </div>
    </div>
  );
};

export default EmailList;
