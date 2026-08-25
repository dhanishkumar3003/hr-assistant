import Link from "next/link";
import {
  FileSearch,
  MessageSquareText,
  Mail,
  Mic,
  BrainCircuit,
  LayoutDashboard,
  ArrowRight,
} from "lucide-react";

const features = [
  {
    icon: FileSearch,
    title: "Resume Repository",
    description: "Upload resumes anytime — parsed and structured automatically for instant search.",
  },
  {
    icon: MessageSquareText,
    title: "Conversational Assistant",
    description: "Ask for what you need in plain language. The assistant filters and ranks candidates for you.",
  },
  {
    icon: Mail,
    title: "Outreach, Your Way",
    description: "Every email is drafted for you and sent only after your approval.",
  },
  {
    icon: Mic,
    title: "AI Voice Interviews",
    description: "Candidates answer resume-based questions by voice — no clicking, no typing.",
  },
  {
    icon: BrainCircuit,
    title: "Technical Screening",
    description: "Difficulty-scaled technical questions, generated and scored by AI.",
  },
  {
    icon: LayoutDashboard,
    title: "One Dashboard",
    description: "Track every candidate's status and make the final call, all in one place.",
  },
];

export default function HomePage() {
  return (
    <div className="min-h-screen bg-background">
      {/* Nav */}
      <nav className="h-14 flex items-center justify-between px-8 lg:px-16 bg-card border-b border-border">
        <div className="flex items-center gap-2">
          <div className="w-9 h-9 rounded-full bg-primary text-white flex items-center justify-center font-bold text-sm">
            HR
          </div>
          <span className="text-lg font-semibold text-text-primary">HR Assistant</span>
        </div>
        <Link
          href="/login"
          className="h-10 px-6 flex items-center bg-primary text-white rounded-button font-medium transition duration-300 hover:bg-accent"
        >
          Sign in
        </Link>
      </nav>

      {/* Hero */}
      <section className="px-8 lg:px-16 py-24 max-w-5xl mx-auto text-center">
        <p className="text-accent font-semibold text-sm tracking-wide uppercase mb-4">
          AI-Driven Hiring
        </p>
        <h1 className="text-4xl lg:text-6xl font-bold text-text-primary leading-tight mb-6">
          Hire faster, without
          <br />
          losing the human touch.
        </h1>
        <p className="text-lg text-text-secondary max-w-2xl mx-auto mb-10">
          From resume to offer — one conversational assistant filters candidates,
          runs AI interviews, and keeps you in control of every decision that matters.
        </p>
        <Link
          href="/login"
          className="inline-flex items-center gap-2 h-14 px-8 bg-primary text-white rounded-button font-medium text-lg transition duration-300 hover:bg-accent"
        >
          Go to Dashboard
          <ArrowRight size={20} />
        </Link>
      </section>

      {/* Features */}
      <section className="px-8 lg:px-16 pb-24 max-w-6xl mx-auto">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map(({ icon: Icon, title, description }) => (
            <div
              key={title}
              className="bg-card border border-border rounded-card shadow-sm p-6 transition duration-300 hover:shadow-md"
            >
              <div className="w-11 h-11 rounded-card bg-primary/5 flex items-center justify-center mb-4">
                <Icon size={22} className="text-primary" />
              </div>
              <h3 className="text-lg font-semibold text-text-primary mb-2">{title}</h3>
              <p className="text-sm text-text-secondary leading-relaxed">{description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="px-8 lg:px-16 py-8 border-t border-border text-center text-sm text-text-secondary">
        HR Assistant POC
      </footer>
    </div>
  );
}