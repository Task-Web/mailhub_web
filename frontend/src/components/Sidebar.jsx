import React, { useState } from "react";
import { AlertCircle, AlertOctagon, File, Inbox, Mail, Plus, Send, Star, Tag, Trash2 } from "lucide-react";
import { NavLink } from "react-router-dom";
import { useStore } from "../context/StoreContext";
import { cn } from "../lib/utils";

const Sidebar = () => {
  const { state, setIsComposeOpen, createLabel } = useStore();
  const [isAddingLabel, setIsAddingLabel] = useState(false);
  const [labelName, setLabelName] = useState("");
  const [labelColor, setLabelColor] = useState("#9ca3af");

  const navItems = [
    {
      icon: Inbox,
      label: "Inbox",
      path: "/inbox",
      count: state.emails.filter((email) => email.folder === "inbox" && !email.read).length,
    },
    {
      icon: Star,
      label: "Starred",
      path: "/starred",
      count: state.emails.filter((email) => email.starred).length,
    },
    {
      icon: AlertCircle,
      label: "Important",
      path: "/important",
      count: state.emails.filter((email) => email.important).length,
    },
    { icon: Send, label: "Sent", path: "/sent" },
    { icon: File, label: "Drafts", path: "/drafts" },
    { icon: AlertOctagon, label: "Spam", path: "/spam" },
    { icon: Trash2, label: "Trash", path: "/trash" },
    { icon: Mail, label: "All Mail", path: "/all-mail" },
  ];

  const handleCreateLabel = () => {
    if (!labelName.trim()) return;
    createLabel(labelName.trim(), labelColor);
    setLabelName("");
    setLabelColor("#9ca3af");
    setIsAddingLabel(false);
  };

  return (
    <div className="flex h-full w-64 flex-col py-4 pr-4">
      <div className="mb-6 pl-4">
        <button
          onClick={() => setIsComposeOpen(true)}
          className="flex items-center gap-3 rounded-2xl bg-[#c2e7ff] px-6 py-4 font-medium text-gray-800 transition-shadow hover:shadow-md"
        >
          <Plus size={24} />
          Compose
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              cn(
                "mb-1 flex items-center justify-between rounded-r-full px-6 py-1.5 text-sm font-medium",
                isActive ? "bg-[#d3e3fd] text-[#001d35]" : "text-gray-700 hover:bg-gray-100"
              )
            }
          >
            <div className="flex items-center gap-4">
              <item.icon size={20} />
              {item.label}
            </div>
            {item.count > 0 && <span className="text-xs font-bold">{item.count}</span>}
          </NavLink>
        ))}

        <div className="mt-6 px-6">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-medium text-gray-500">Labels</h3>
            <button
              className="text-gray-500 hover:text-gray-700"
              onClick={() => setIsAddingLabel((prev) => !prev)}
              aria-label="Add label"
            >
              <Plus size={16} />
            </button>
          </div>

          {isAddingLabel && (
            <div className="mb-3 rounded-lg border border-gray-200 bg-white p-3 shadow-sm">
              <label className="mb-2 block text-xs font-medium uppercase tracking-wide text-gray-500">
                Label name
              </label>
              <input
                className="mb-2 w-full rounded-md border border-gray-200 px-2 py-1 text-sm outline-none focus:border-blue-400"
                value={labelName}
                onChange={(e) => setLabelName(e.target.value)}
                placeholder="Label name"
              />
              <div className="mb-3 flex items-center gap-2">
                <span className="text-xs text-gray-500">Color</span>
                <input
                  type="color"
                  className="h-6 w-8 cursor-pointer border border-gray-200"
                  value={labelColor}
                  onChange={(e) => setLabelColor(e.target.value)}
                />
              </div>
              <div className="flex justify-end gap-2">
                <button
                  onClick={() => setIsAddingLabel(false)}
                  className="rounded px-2 py-1 text-xs text-gray-500 hover:bg-gray-100"
                >
                  Cancel
                </button>
                <button
                  onClick={handleCreateLabel}
                  className="rounded bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-700"
                >
                  Create
                </button>
              </div>
            </div>
          )}

          {state.labels.map((label) => (
            <NavLink
              key={label.id}
              to={`/label/${label.id}`}
              className={({ isActive }) =>
                cn(
                  "rounded-r-full py-1.5 text-sm",
                  "flex items-center gap-4 -mx-6 px-6",
                  isActive ? "bg-[#d3e3fd] text-[#001d35]" : "text-gray-700 hover:bg-gray-100"
                )
              }
            >
              <Tag size={18} style={{ fill: label.color, stroke: "none" }} />
              {label.name}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
};

export default Sidebar;
