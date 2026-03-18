import React, { useEffect, useRef, useState } from "react";
import { Image, Link as LinkIcon, Maximize2, Minimize2, Paperclip, Smile, Trash2, X } from "lucide-react";
import { useStore } from "../context/StoreContext";

const ComposeModal = () => {
  const {
    isComposeOpen,
    setIsComposeOpen,
    sendEmail,
    saveDraft,
    deleteDraft,
    currentDraftId,
    setCurrentDraftId,
    uploadAttachments,
  } = useStore();
  const [isMinimized, setIsMinimized] = useState(false);
  const [isMaximized, setIsMaximized] = useState(false);

  const [to, setTo] = useState("");
  const [cc, setCc] = useState("");
  const [bcc, setBcc] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [attachments, setAttachments] = useState([]);

  const [showCc, setShowCc] = useState(false);
  const [showBcc, setShowBcc] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  const fileInputRef = useRef(null);
  const dragCounterRef = useRef(0);

  useEffect(() => {
    if (!isComposeOpen) return undefined;
    const timer = setTimeout(() => {
      saveDraft({ to, cc, bcc, subject, body, attachments });
    }, 2000);
    return () => clearTimeout(timer);
  }, [to, cc, bcc, subject, body, attachments, isComposeOpen, saveDraft]);

  if (!isComposeOpen) return null;

  const handleSend = () => {
    if (!to) return alert("Please add a recipient");
    sendEmail({
      to,
      cc: showCc ? cc : "",
      bcc: showBcc ? bcc : "",
      subject,
      body,
      attachments,
    });
    closeModal({ saveDraft: false });
  };

  const closeModal = ({ saveDraft: shouldSaveDraft } = { saveDraft: true }) => {
    if (shouldSaveDraft && (to || subject || body || attachments.length > 0)) {
      saveDraft({ to, cc, bcc, subject, body, attachments });
    }

    setIsComposeOpen(false);
    setTo("");
    setCc("");
    setBcc("");
    setShowCc(false);
    setShowBcc(false);
    setSubject("");
    setBody("");
    setAttachments([]);
    setIsMinimized(false);
    setIsMaximized(false);
    setCurrentDraftId(null);
  };

  const handleFileSelect = async (event) => {
    const files = Array.from(event.target.files);
    if (files.length === 0) return;

    try {
      const uploaded = await uploadAttachments(files);
      setAttachments((prev) => [...prev, ...uploaded]);
    } catch (err) {
      alert(err.message || "Failed to upload attachments.");
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const removeAttachment = (id) => {
    setAttachments((prev) => prev.filter((attachment) => attachment.id !== id));
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

    try {
      const uploaded = await uploadAttachments(files);
      setAttachments((prev) => [...prev, ...uploaded]);
    } catch (err) {
      alert(err.message || "Failed to upload attachments.");
    }
  };

  const modalClasses = isMaximized
    ? "fixed inset-4 z-50 flex flex-col rounded-lg bg-white shadow-2xl relative"
    : `fixed bottom-0 right-20 z-50 flex flex-col rounded-t-lg border border-gray-300 bg-white shadow-xl transition-all duration-200 relative ${
        isMinimized ? "h-12 w-64" : "h-[500px] w-[500px]"
      }`;

  return (
    <div
      className={modalClasses}
      onDragEnter={handleDragEnter}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <div
        className="flex cursor-pointer select-none items-center justify-between rounded-t-lg bg-[#f2f6fc] px-4 py-2"
        onClick={() => !isMaximized && setIsMinimized(!isMinimized)}
      >
        <span className="text-sm font-medium text-gray-700">New Message</span>
        <div className="flex items-center gap-2">
          <button
            onClick={(event) => {
              event.stopPropagation();
              setIsMinimized(!isMinimized);
            }}
            className="rounded p-1 hover:bg-gray-200"
          >
            <Minimize2 size={14} />
          </button>
          <button
            onClick={(event) => {
              event.stopPropagation();
              setIsMaximized(!isMaximized);
              setIsMinimized(false);
            }}
            className="rounded p-1 hover:bg-gray-200"
          >
            <Maximize2 size={14} />
          </button>
          <button
            onClick={(event) => {
              event.stopPropagation();
              closeModal({ saveDraft: true });
            }}
            className="rounded p-1 hover:bg-gray-200"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {!isMinimized && (
        <>
          {isDragging && (
            <div className="absolute inset-0 z-10 flex items-center justify-center rounded-lg bg-blue-50/80 backdrop-blur-sm border-2 border-dashed border-blue-400 pointer-events-none">
              <div className="flex flex-col items-center gap-2 text-blue-600">
                <Paperclip size={32} />
                <span className="text-sm font-medium">Drop files to attach</span>
              </div>
            </div>
          )}
          <div className="flex flex-1 flex-col overflow-y-auto">
            <div className="border-b border-gray-100 px-4 py-2">
              <div className="flex items-center">
                <span
                  className="w-12 cursor-pointer text-sm text-gray-500"
                  onClick={() => document.getElementById("to-input").focus()}
                >
                  To
                </span>
                <input
                  id="to-input"
                  type="text"
                  className="flex-1 py-1 text-sm outline-none"
                  value={to}
                  onChange={(event) => setTo(event.target.value)}
                />
                <div className="flex gap-2 text-sm text-gray-500">
                  {!showCc && (
                    <button
                      onClick={() => setShowCc(true)}
                      className="hover:text-gray-800 hover:underline"
                    >
                      Cc
                    </button>
                  )}
                  {!showBcc && (
                    <button
                      onClick={() => setShowBcc(true)}
                      className="hover:text-gray-800 hover:underline"
                    >
                      Bcc
                    </button>
                  )}
                </div>
              </div>
            </div>

            {showCc && (
              <div className="flex items-center border-b border-gray-100 px-4 py-2">
                <span className="w-12 text-sm text-gray-500">Cc</span>
                <input
                  type="text"
                  className="flex-1 py-1 text-sm outline-none"
                  value={cc}
                  onChange={(event) => setCc(event.target.value)}
                />
              </div>
            )}

            {showBcc && (
              <div className="flex items-center border-b border-gray-100 px-4 py-2">
                <span className="w-12 text-sm text-gray-500">Bcc</span>
                <input
                  type="text"
                  className="flex-1 py-1 text-sm outline-none"
                  value={bcc}
                  onChange={(event) => setBcc(event.target.value)}
                />
              </div>
            )}

            <div className="border-b border-gray-100 px-4 py-2">
              <input
                type="text"
                placeholder="Subject"
                className="w-full py-1 text-sm outline-none placeholder:text-gray-500"
                value={subject}
                onChange={(event) => setSubject(event.target.value)}
              />
            </div>

            <textarea
              className="flex-1 resize-none p-4 text-sm outline-none whitespace-pre-wrap"
              value={body}
              onChange={(event) => setBody(event.target.value)}
            />

            {attachments.length > 0 && (
              <div className="border-t border-gray-100 bg-gray-50 px-4 py-2">
                <div className="flex flex-wrap gap-2">
                  {attachments.map((att) => (
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
                        onClick={() => removeAttachment(att.id)}
                        className="rounded p-1 text-gray-400 hover:text-red-500"
                        title="Remove attachment"
                      >
                        <X size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="flex items-center justify-between border-t border-gray-100 p-4">
            <div className="flex items-center gap-2">
              <button
                onClick={handleSend}
                className="rounded-full bg-[#0b57d0] px-6 py-2 text-sm font-medium text-white hover:bg-[#0b57d0]/90"
              >
                Send
              </button>

              <div className="mx-1 h-6 w-px bg-gray-200"></div>

              <input
                type="file"
                multiple
                className="hidden"
                ref={fileInputRef}
                onChange={handleFileSelect}
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                className="relative rounded p-2 text-gray-500 hover:bg-gray-100"
                title="Attach files"
              >
                <Paperclip size={18} />
              </button>

              <button className="rounded p-2 text-gray-500 hover:bg-gray-100">
                <LinkIcon size={18} />
              </button>
              <button className="rounded p-2 text-gray-500 hover:bg-gray-100">
                <Smile size={18} />
              </button>
              <button className="rounded p-2 text-gray-500 hover:bg-gray-100">
                <Image size={18} />
              </button>
            </div>
            <button
              onClick={() => {
                if (currentDraftId) deleteDraft(currentDraftId);
                closeModal({ saveDraft: false });
              }}
              className="rounded p-2 text-gray-500 hover:bg-gray-100"
            >
              <Trash2 size={18} />
            </button>
          </div>
        </>
      )}
    </div>
  );
};

export default ComposeModal;
