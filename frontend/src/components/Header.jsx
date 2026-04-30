import React, { useState } from "react";
import { Search, SlidersHorizontal, X } from "lucide-react";
import { useStore } from "../context/StoreContext";

const AdvancedSearchModal = () => {
  const { isSearchModalOpen, setIsSearchModalOpen, setSearchQuery } = useStore();
  const [localQuery, setLocalQuery] = useState({
    from: "",
    to: "",
    subject: "",
    hasAttachment: false,
  });

  if (!isSearchModalOpen) return null;

  const handleSearch = () => {
    const parts = [];
    if (localQuery.from) parts.push(`from:${localQuery.from}`);
    if (localQuery.to) parts.push(`to:${localQuery.to}`);
    if (localQuery.subject) parts.push(`subject:${localQuery.subject}`);
    if (localQuery.hasAttachment) parts.push("has:attachment");
    setSearchQuery(parts.join(" "));
    setIsSearchModalOpen(false);
  };

  return (
    <div className="absolute left-0 right-0 top-16 z-50 mx-auto w-[600px] rounded-b-lg border border-gray-200 bg-white p-6 shadow-xl">
      <div className="mb-4 grid grid-cols-[100px_1fr] items-center gap-4">
        <label className="text-sm font-medium text-gray-600">From</label>
        <input
          className="border-b border-gray-200 py-1 text-sm outline-none"
          value={localQuery.from}
          onChange={(e) => setLocalQuery({ ...localQuery, from: e.target.value })}
        />

        <label className="text-sm font-medium text-gray-600">To</label>
        <input
          className="border-b border-gray-200 py-1 text-sm outline-none"
          value={localQuery.to}
          onChange={(e) => setLocalQuery({ ...localQuery, to: e.target.value })}
        />

        <label className="text-sm font-medium text-gray-600">Subject</label>
        <input
          className="border-b border-gray-200 py-1 text-sm outline-none"
          value={localQuery.subject}
          onChange={(e) => setLocalQuery({ ...localQuery, subject: e.target.value })}
        />

        <div className="col-start-2 flex items-center gap-2">
          <input
            type="checkbox"
            id="has-attach"
            checked={localQuery.hasAttachment}
            onChange={(e) => setLocalQuery({ ...localQuery, hasAttachment: e.target.checked })}
          />
          <label htmlFor="has-attach" className="text-sm text-gray-600">
            Has attachment
          </label>
        </div>
      </div>

      <div className="mt-6 flex justify-end gap-2">
        <button
          onClick={() => setIsSearchModalOpen(false)}
          className="rounded px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100"
        >
          Cancel
        </button>
        <button
          onClick={handleSearch}
          className="rounded bg-blue-600 px-6 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          Search
        </button>
      </div>
    </div>
  );
};

const Header = () => {
  const { searchQuery, setSearchQuery, state, setIsSearchModalOpen, isSyncing, error } = useStore();

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-gray-200 bg-white px-4">
      <div className="flex w-60 items-center gap-4">
        <div className="flex items-center gap-2 pl-2">
          <span className="text-xl font-semibold text-mailhub-text">MailHub</span>
        </div>
      </div>

      <div className="relative flex-1 max-w-3xl">
        <div className="flex items-center rounded-full bg-[#eaf1fb] px-4 py-3 transition-all focus-within:bg-white focus-within:shadow-md">
          <Search size={20} className="mr-3 text-gray-500" />
          <input
            type="text"
            placeholder="Search mail"
            className="w-full border-none bg-transparent text-gray-700 outline-none placeholder:text-gray-600"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {searchQuery ? (
            <button
              onClick={() => setSearchQuery("")}
              className="ml-2 rounded-full p-1 hover:bg-gray-200"
            >
              <X size={18} className="text-gray-600" />
            </button>
          ) : (
            <button
              onClick={() => setIsSearchModalOpen((prev) => !prev)}
              className="ml-2 rounded-full p-1 hover:bg-gray-200"
            >
              <SlidersHorizontal size={18} className="text-gray-600" />
            </button>
          )}
        </div>
        <AdvancedSearchModal />
      </div>

      <div className="flex w-60 items-center justify-end gap-2">
        {error && <span className="text-xs text-red-600">Sync issue</span>}
        {!error && isSyncing && <span className="text-xs text-gray-500">Syncing...</span>}
        <div className="ml-2">
          <img
            src={state.user.avatar}
            alt="Profile"
            className="h-8 w-8 rounded-full border border-gray-200"
          />
        </div>
      </div>
    </header>
  );
};

export default Header;
