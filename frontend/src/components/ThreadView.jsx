import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Archive,
  ArrowLeft,
  CornerUpLeft,
  FileText,
  Mail,
  MoreVertical,
  Paperclip,
  Reply,
  Star,
  Trash2,
  X,
} from "lucide-react";
import { api } from "../apiClient";
import { useStore } from "../context/StoreContext";
import { cn, formatDate } from "../lib/utils";

const isImageAttachment = (attachment) => {
  const type = (attachment?.type || "").toLowerCase();
  if (!type) return false;
  if (type.startsWith("image/")) return true;
  return ["png", "jpg", "jpeg", "gif", "webp", "bmp", "svg"].includes(type);
};

const isDataUrl = (url) => typeof url === "string" && url.startsWith("data:");

const isSameOrigin = (url) => {
  try {
    return new URL(url, window.location.href).origin === window.location.origin;
  } catch (err) {
    return false;
  }
};

const normalizeExternalUrl = (url) => {
  if (!url) return "";
  const trimmed = url.trim();
  if (trimmed.startsWith("//")) return `https:${trimmed}`;
  return trimmed;
};

const proxyBase = api.baseUrl.replace(/\/$/, "");

const buildProxyUrl = (url) => {
  const normalized = normalizeExternalUrl(url);
  if (!normalized) return "";
  return `${proxyBase}/proxy?url=${encodeURIComponent(normalized)}`;
};

const isProxyUrl = (url) => {
  const normalized = normalizeExternalUrl(url);
  if (!normalized) return false;
  return normalized.startsWith(`${proxyBase}/proxy?`);
};

const shouldProxyUrl = (url) => {
  const normalized = normalizeExternalUrl(url);
  if (!normalized || isProxyUrl(normalized)) return false;
  if (!/^https?:\/\//i.test(normalized)) return false;
  return !isSameOrigin(normalized);
};

const resolveAttachmentUrl = (url) => {
  if (!url) return "";
  if (url.startsWith("data:")) return url;
  const normalized = normalizeExternalUrl(url);
  if (shouldProxyUrl(normalized)) return buildProxyUrl(normalized);
  if (normalized.startsWith("http://") || normalized.startsWith("https://")) return normalized;
  let origin = window.location.origin;
  try {
    origin = new URL(api.baseUrl, window.location.href).origin;
  } catch (err) {
    origin = window.location.origin;
  }
  if (url.startsWith("/")) return `${origin}${url}`;
  return `${origin}/${url}`;
};

const rewriteCssUrls = (value) => {
  if (!value) return value;
  const httpRegex = /url\((['"]?)(https?:\/\/[^'")]+)\1\)/gi;
  const protocolRegex = /url\((['"]?)(\/\/[^'")]+)\1\)/gi;
  let next = value.replace(httpRegex, (match, quote, url) => {
    if (!shouldProxyUrl(url)) return match;
    return `url(${quote}${buildProxyUrl(url)}${quote})`;
  });
  next = next.replace(protocolRegex, (match, quote, url) => {
    const normalized = normalizeExternalUrl(url);
    if (!shouldProxyUrl(normalized)) return match;
    return `url(${quote}${buildProxyUrl(normalized)}${quote})`;
  });
  return next;
};

const buildEmailDocument = (html) => {
  if (!html || typeof DOMParser === "undefined") return html || "";
  try {
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, "text/html");

    const updateAttr = (element, attr) => {
      const value = element.getAttribute(attr);
      if (!value) return;
      const normalized = normalizeExternalUrl(value);
      if (shouldProxyUrl(normalized)) {
        element.setAttribute(attr, buildProxyUrl(normalized));
      } else if (normalized && normalized !== value && /^https?:\/\//i.test(normalized)) {
        element.setAttribute(attr, normalized);
      }
    };

    const updateSrcset = (element) => {
      const value = element.getAttribute("srcset");
      if (!value) return;
      const next = value
        .split(",")
        .map((entry) => entry.trim())
        .filter(Boolean)
        .map((entry) => {
          const parts = entry.split(/\s+/, 2);
          const url = normalizeExternalUrl(parts[0]);
          const descriptor = parts[1];
          const nextUrl = shouldProxyUrl(url) ? buildProxyUrl(url) : url;
          return descriptor ? `${nextUrl} ${descriptor}` : nextUrl;
        })
        .join(", ");
      if (next) element.setAttribute("srcset", next);
    };

    [
      ["img", ["src", "srcset"]],
      ["source", ["src", "srcset"]],
      ["video", ["src", "poster"]],
      ["audio", ["src"]],
      ["track", ["src"]],
      ["iframe", ["src"]],
      ["embed", ["src"]],
      ["object", ["data"]],
      ["link[rel=\"stylesheet\"]", ["href"]],
    ].forEach(([selector, attrs]) => {
      doc.querySelectorAll(selector).forEach((element) => {
        attrs.forEach((attr) => {
          if (attr === "srcset") {
            updateSrcset(element);
          } else {
            updateAttr(element, attr);
          }
        });
      });
    });

    if (!doc.querySelector("base[target]")) {
      const base = doc.createElement("base");
      base.setAttribute("target", "_blank");
      base.setAttribute("rel", "noopener noreferrer");
      (doc.head || doc.documentElement).prepend(base);
    }

    doc.querySelectorAll("[style]").forEach((element) => {
      const style = element.getAttribute("style");
      const next = rewriteCssUrls(style);
      if (next !== style) {
        element.setAttribute("style", next);
      }
    });

    doc.querySelectorAll("style").forEach((element) => {
      const css = element.textContent;
      const next = rewriteCssUrls(css);
      if (next !== css) {
        element.textContent = next;
      }
    });

    return `<!doctype html>\n${doc.documentElement.outerHTML}`;
  } catch (err) {
    return html;
  }
};

const triggerDownload = (url, filename) => {
  if (!url) return;
  const link = document.createElement("a");
  link.href = url;
  if (filename && (isDataUrl(url) || isSameOrigin(url))) {
    link.download = filename;
  }
  link.rel = "noopener";
  link.target = "_blank";
  document.body.appendChild(link);
  link.click();
  link.remove();
};

const EmailBody = ({ html }) => {
  const iframeRef = useRef(null);
  const [height, setHeight] = useState("0px");
  const srcDoc = useMemo(() => buildEmailDocument(html), [html]);

  const resizeIframe = useCallback(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;
    try {
      const doc = iframe.contentDocument;
      if (!doc) return;
      // Reset height first so scrollHeight reflects actual content size,
      // not the previous (potentially larger) viewport.
      iframe.style.height = "0px";
      const body = doc.body;
      const documentElement = doc.documentElement;
      const nextHeight = Math.max(
        body?.scrollHeight || 0,
        body?.offsetHeight || 0,
        documentElement?.scrollHeight || 0,
        documentElement?.offsetHeight || 0
      );
      if (nextHeight) setHeight(`${nextHeight}px`);
    } catch (err) {
      // Ignore cross-origin access errors (should not happen with srcdoc).
    }
  }, []);

  useEffect(() => {
    resizeIframe();
  }, [srcDoc, resizeIframe]);

  const handleLoad = useCallback(() => {
    resizeIframe();
    const iframe = iframeRef.current;
    if (!iframe) return;
    try {
      const doc = iframe.contentDocument;
      if (!doc) return;
      doc.addEventListener("toggle", () => {
        // Small delay to let the browser layout the expanded content.
        requestAnimationFrame(resizeIframe);
      }, true);
    } catch (err) {
      // Ignore cross-origin access errors.
    }
  }, [resizeIframe]);

  return (
    <iframe
      ref={iframeRef}
      title="email-body"
      srcDoc={srcDoc}
      className="block w-full border-0"
      style={{ height }}
      onLoad={handleLoad}
      scrolling="no"
    />
  );
};

const ThreadView = () => {
  const { threadId } = useParams();
  const navigate = useNavigate();
  const {
    state,
    toggleStar,
    replyToEmail,
    archiveEmails,
    deleteEmails,
    bulkUpdateEmails,
    uploadAttachments,
  } = useStore();
  const [replyBody, setReplyBody] = useState("");
  const [replyAttachments, setReplyAttachments] = useState([]);
  const [isReplying, setIsReplying] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [expandedEmails, setExpandedEmails] = useState(new Set());
  const replyRef = useRef(null);
  const replyFileInputRef = useRef(null);
  const dragCounterRef = useRef(0);

  const threadEmails = useMemo(
    () =>
      state.emails
        .filter((email) => email.threadId === threadId)
        .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp)),
    [state.emails, threadId]
  );

  const labelMap = useMemo(
    () => new Map(state.labels.map((label) => [label.id, label])),
    [state.labels]
  );

  useEffect(() => {
    if (!threadEmails.length) return;
    const unreadIds = threadEmails.filter((email) => !email.read).map((email) => email.id);
    if (unreadIds.length) {
      bulkUpdateEmails(unreadIds, { read: true });
    }
  }, [bulkUpdateEmails, threadEmails]);

  useEffect(() => {
    if (!threadEmails.length) return;
    setExpandedEmails(new Set([threadEmails[threadEmails.length - 1].id]));
  }, [threadId]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggleEmailExpanded = (emailId) => {
    setExpandedEmails((prev) => {
      const next = new Set(prev);
      if (next.has(emailId)) {
        next.delete(emailId);
      } else {
        next.add(emailId);
      }
      return next;
    });
  };

  useEffect(() => {
    if (isReplying && replyRef.current) {
      replyRef.current.focus();
    }
  }, [isReplying]);

  const handleReplyFileSelect = async (event) => {
    const files = Array.from(event.target.files);
    if (files.length === 0) return;

    try {
      const uploaded = await uploadAttachments(files);
      setReplyAttachments((prev) => [...prev, ...uploaded]);
    } catch (err) {
      alert(err.message || "Failed to upload attachments.");
    } finally {
      if (replyFileInputRef.current) replyFileInputRef.current.value = "";
    }
  };

  const removeReplyAttachment = (id) => {
    setReplyAttachments((prev) => prev.filter((attachment) => attachment.id !== id));
  };

  const handleDragEnter = (event) => {
    event.preventDefault();
    event.stopPropagation();
    dragCounterRef.current += 1;
    if (event.dataTransfer.types.includes("Files")) {
      setIsDragging(true);
    }
  };

  const handleDragOver = (event) => {
    event.preventDefault();
    event.stopPropagation();
  };

  const handleDragLeave = (event) => {
    event.preventDefault();
    event.stopPropagation();
    dragCounterRef.current -= 1;
    if (dragCounterRef.current === 0) {
      setIsDragging(false);
    }
  };

  const handleDrop = async (event) => {
    event.preventDefault();
    event.stopPropagation();
    dragCounterRef.current = 0;
    setIsDragging(false);

    const files = Array.from(event.dataTransfer.files);
    if (files.length === 0) return;

    setIsReplying(true);

    try {
      const uploaded = await uploadAttachments(files);
      setReplyAttachments((prev) => [...prev, ...uploaded]);
    } catch (err) {
      alert(err.message || "Failed to upload attachments.");
    }
  };

  const clearReplyComposer = () => {
    setReplyBody("");
    setReplyAttachments([]);
    if (replyFileInputRef.current) replyFileInputRef.current.value = "";
  };

  const handleReplyBoxClick = (event) => {
    // Check if user is selecting text - don't trigger compose in that case
    const selection = window.getSelection();
    if (selection && selection.toString().trim().length > 0) {
      return;
    }
    // Also don't trigger if clicking on a button or input
    if (event.target.tagName === "BUTTON" || event.target.tagName === "INPUT" || event.target.tagName === "TEXTAREA") {
      return;
    }
    setIsReplying(true);
  };

  if (threadEmails.length === 0) {
    return <div className="p-8 text-center">Thread not found</div>;
  }

  const subject = threadEmails[0].subject;
  const lastEmail = threadEmails[threadEmails.length - 1];
  const threadIds = threadEmails.map((email) => email.id);
  const folderLabel = (lastEmail.folder || "inbox")
    .replace("-", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

  const handleReply = async () => {
    if (!replyBody.trim() && replyAttachments.length === 0) return;
    const prevCount = threadEmails.length;
    await replyToEmail(threadId, replyBody, false, replyAttachments);
    clearReplyComposer();
    setIsReplying(false);
  };

  // Auto-expand newly added emails (e.g. after sending a reply).
  const prevCountRef = useRef(threadEmails.length);
  useEffect(() => {
    if (threadEmails.length > prevCountRef.current) {
      const newLast = threadEmails[threadEmails.length - 1];
      setExpandedEmails((prev) => new Set([...prev, newLast.id]));
    }
    prevCountRef.current = threadEmails.length;
  }, [threadEmails]);

  return (
    <div className="flex h-full flex-1 flex-col overflow-hidden rounded-tl-2xl bg-white shadow-sm">
      <div className="flex h-16 items-center gap-4 border-b border-gray-200 px-4">
        <button
          onClick={() => navigate(-1)}
          className="rounded-full p-2 text-gray-600 hover:bg-gray-100"
        >
          <ArrowLeft size={20} />
        </button>
        <div className="flex flex-1 items-center gap-2">
          <button
            className="rounded-full p-2 text-gray-600 hover:bg-gray-100"
            onClick={() => archiveEmails(threadIds)}
          >
            <Archive size={18} />
          </button>
          <button
            className="rounded-full p-2 text-gray-600 hover:bg-gray-100"
            onClick={() => deleteEmails(threadIds)}
          >
            <Trash2 size={18} />
          </button>
          <button
            className="rounded-full p-2 text-gray-600 hover:bg-gray-100"
            onClick={() => bulkUpdateEmails(threadIds, { read: true })}
          >
            <Mail size={18} />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-normal text-gray-800">{subject}</h1>
          <div className="flex items-center gap-2">
            <div className="rounded bg-gray-200 px-2 py-1 text-xs">{folderLabel}</div>
            {(lastEmail.labels || []).map((labelId) => {
              const label = labelMap.get(labelId);
              return label ? (
                <div
                  key={labelId}
                  className="rounded px-2 py-1 text-xs"
                  style={{ backgroundColor: `${label.color}33`, color: label.color }}
                >
                  {label.name}
                </div>
              ) : null;
            })}
          </div>
        </div>

        <div className="space-y-4">
          {threadEmails.map((email, index) => {
            const isExpanded = expandedEmails.has(email.id);
            return (
              <div
                key={email.id}
                className={cn(
                  "overflow-hidden rounded-lg border border-gray-200",
                  index === threadEmails.length - 1 ? "bg-white" : "bg-gray-50"
                )}
              >
                <div
                  className="flex cursor-pointer items-start gap-4 p-4"
                  onClick={() => toggleEmailExpanded(email.id)}
                >
                  <img src={email.from.avatar} alt="" className="h-10 w-10 rounded-full" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-gray-900">{email.from.name}</span>
                      <div className="flex items-center gap-4 text-sm text-gray-500">
                        <span>{formatDate(email.timestamp)}</span>
                        {isExpanded && (
                          <>
                            <button
                              onClick={(event) => {
                                event.stopPropagation();
                                toggleStar(email.id);
                              }}
                            >
                              <Star
                                size={18}
                                className={cn(email.starred ? "text-yellow-400 fill-current" : "text-gray-400")}
                              />
                            </button>
                            <button
                              onClick={(event) => {
                                event.stopPropagation();
                                setIsReplying(true);
                              }}
                            >
                              <CornerUpLeft size={18} />
                            </button>
                            <MoreVertical size={18} />
                          </>
                        )}
                      </div>
                    </div>
                    {isExpanded ? (
                      <div className="truncate text-sm text-gray-500">
                        to {(email.to || []).map((recipient) => recipient.name).join(", ")}
                      </div>
                    ) : (
                      <div className="truncate text-sm text-gray-500">
                        {email.snippet || email.body?.replace(/<[^>]*>/g, "").slice(0, 100)}
                      </div>
                    )}
                  </div>
                </div>

                {isExpanded && (
                  <>
                    <div className="px-16 pb-8">
                      <EmailBody html={email.body} />
                    </div>

                    {email.attachments && email.attachments.length > 0 && (
                      <div className="flex gap-4 px-16 pb-8">
                        {email.attachments.map((att) => {
                          const attachmentUrl = resolveAttachmentUrl(att.url);
                          return (
                            <button
                              key={att.id}
                              type="button"
                              onClick={() => triggerDownload(attachmentUrl, att.name)}
                              className="w-48 rounded border p-2 text-left hover:bg-gray-50"
                            >
                              {isImageAttachment(att) ? (
                                <div className="mb-2 h-24 overflow-hidden rounded bg-gray-100">
                                  {attachmentUrl ? (
                                    <img
                                      src={attachmentUrl}
                                      alt={att.name || "attachment"}
                                      className="h-full w-full object-cover"
                                    />
                                  ) : (
                                    <div className="flex h-full items-center justify-center text-xs text-gray-400">
                                      No preview
                                    </div>
                                  )}
                                </div>
                              ) : (
                                <div className="mb-2 flex h-24 items-center justify-center rounded bg-gray-100">
                                  <FileText size={32} className="text-gray-400" />
                                </div>
                              )}
                              <div className="truncate text-sm font-medium">{att.name}</div>
                              <div className="text-xs text-gray-500">{att.size || "2.4 MB"}</div>
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </>
                )}
              </div>
            );
          })}
        </div>

        <div className="mt-8 flex items-start gap-4">
          <img src={state.user.avatar} alt="" className="h-10 w-10 rounded-full" />
          <div
            className={cn(
              "relative flex-1 rounded-lg border border-gray-300 shadow-sm transition-all",
              isDragging ? "border-blue-400 border-2" : "",
              isReplying ? "h-auto" : "h-12 overflow-hidden"
            )}
            onClick={handleReplyBoxClick}
            onDragEnter={handleDragEnter}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            {!isReplying ? (
              <div className="flex cursor-text items-center gap-2 p-3 text-gray-500">
                {isDragging ? (
                  <div className="flex items-center gap-2 text-blue-600">
                    <Paperclip size={18} />
                    <span className="text-sm font-medium">Drop files to attach</span>
                  </div>
                ) : (
                  <><Reply size={18} /> Reply</>
                )}
              </div>
            ) : (
              <div className="p-4">
                {isDragging && (
                  <div className="absolute inset-0 z-10 flex items-center justify-center rounded-lg bg-blue-50/80 backdrop-blur-sm border-2 border-dashed border-blue-400 pointer-events-none">
                    <div className="flex flex-col items-center gap-2 text-blue-600">
                      <Paperclip size={24} />
                      <span className="text-sm font-medium">Drop files to attach</span>
                    </div>
                  </div>
                )}
                <div className="mb-2 flex items-center gap-2 text-sm text-gray-500">
                  <CornerUpLeft size={16} />
                  <span>Replying to {lastEmail.from.name}</span>
                </div>
                <textarea
                  ref={replyRef}
                  className="min-h-[100px] w-full resize-none outline-none whitespace-pre-wrap"
                  placeholder="Type your reply..."
                  value={replyBody}
                  onChange={(e) => setReplyBody(e.target.value)}
                />
                {replyAttachments.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {replyAttachments.map((att) => (
                      <div
                        key={att.id}
                        className="group flex items-center gap-2 rounded border border-gray-200 bg-white p-2 text-sm"
                      >
                        <div className="flex flex-col">
                          <span className="max-w-[150px] truncate font-medium" title={att.name}>
                            {att.name}
                          </span>
                          <span className="text-xs text-gray-500">{att.size}</span>
                        </div>
                        <button
                          onClick={() => removeReplyAttachment(att.id)}
                          className="rounded p-1 text-gray-400 hover:text-red-500"
                          title="Remove attachment"
                        >
                          <X size={14} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                <div className="mt-4 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={handleReply}
                      className="rounded-full bg-blue-600 px-6 py-2 font-medium text-white hover:bg-blue-700"
                    >
                      Send
                    </button>
                    <input
                      type="file"
                      multiple
                      className="hidden"
                      ref={replyFileInputRef}
                      onChange={handleReplyFileSelect}
                    />
                    <button
                      onClick={() => replyFileInputRef.current?.click()}
                      className="rounded p-2 text-gray-500 hover:bg-gray-100"
                      title="Attach files"
                    >
                      <Paperclip size={18} />
                    </button>
                  </div>
                  <button
                    onClick={() => {
                      clearReplyComposer();
                      setIsReplying(false);
                    }}
                    className="rounded p-2 text-gray-500 hover:bg-gray-100"
                  >
                    <Trash2 size={18} />
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ThreadView;
