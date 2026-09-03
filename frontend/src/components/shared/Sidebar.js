"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FileSearch, Mail, LayoutDashboard } from "lucide-react";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/resumes", label: "Resume Repository", icon: FileSearch },
  { href: "/outreach", label: "Email Outreach", icon: Mail },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-72 shrink-0 bg-primary text-white p-8 flex flex-col gap-8 min-h-screen">
      <div className="flex items-center gap-2">
        <div className="w-9 h-9 rounded-full bg-white text-primary flex items-center justify-center font-bold text-sm">
          HR
        </div>
        <span className="text-lg font-semibold">HR Assistant</span>
      </div>

      <nav className="flex flex-col gap-1">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname?.startsWith(`${href}/`);
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 p-4 rounded-card text-sm font-medium transition duration-300 ${
                active ? "bg-white/10" : "opacity-70 hover:opacity-100 hover:bg-white/5"
              }`}
            >
              <Icon size={18} />
              {label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
