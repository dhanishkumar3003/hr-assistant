"use client";

import { Bell } from "lucide-react";
import { getCurrentUser } from "@/lib/auth";
import { useState } from "react";

export default function TopBar({ title }) {
  const [user] = useState(() => (typeof window === "undefined" ? null : getCurrentUser()));

  const initials = (user?.name || "HR")
    .split(" ")
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <header className="h-20 flex items-center justify-between px-8 border-b border-border bg-card">
      <h1 className="text-2xl font-bold text-text-primary">{title}</h1>

      <div className="flex items-center gap-6">
        <button
          type="button"
          aria-label="Notifications"
          className="text-text-secondary hover:text-text-primary transition duration-300"
        >
          <Bell size={20} />
        </button>

        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-full bg-primary text-white flex items-center justify-center font-bold text-sm">
            {initials}
          </div>
          <div className="text-sm">
            <p className="font-semibold text-text-primary">{user?.name || "HR User"}</p>
            <p className="text-text-secondary text-xs">HR</p>
          </div>
        </div>
      </div>
    </header>
  );
}
