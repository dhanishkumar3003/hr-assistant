"use client";

import Link from "next/link";
import { FileSearch, Mail, ArrowRight } from "lucide-react";
import AppShell from "@/components/shared/AppShell";

// Minimal landing hub for Module 1 + Module 3, the modules this POC covers.
// The full pipeline dashboard (funnel, gates, aggregation across every
// module) is Module 6's scope — see docs/Module6/Module_6_Unified_HR_Dashboard_PDD.docx.
const CARDS = [
  {
    href: "/resumes",
    icon: FileSearch,
    title: "Resume Repository",
    description: "Upload resumes, watch AI extraction run, and browse structured candidate profiles.",
  },
  {
    href: "/outreach",
    icon: Mail,
    title: "Email Outreach",
    description: "Draft, review, approve and send outreach emails to candidates.",
  },
];

export default function DashboardPage() {
  return (
    <AppShell title="Dashboard">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl">
        {CARDS.map(({ href, icon: Icon, title, description }) => (
          <Link
            key={href}
            href={href}
            className="bg-card border border-border rounded-card shadow-sm p-6 transition duration-300 hover:shadow-md group"
          >
            <div className="w-11 h-11 rounded-card bg-primary/5 flex items-center justify-center mb-4">
              <Icon size={22} className="text-primary" />
            </div>
            <h3 className="text-lg font-semibold text-text-primary mb-2 flex items-center gap-2">
              {title}
              <ArrowRight
                size={16}
                className="text-accent opacity-0 group-hover:opacity-100 transition duration-300"
              />
            </h3>
            <p className="text-sm text-text-secondary leading-relaxed">{description}</p>
          </Link>
        ))}
      </div>
    </AppShell>
  );
}
