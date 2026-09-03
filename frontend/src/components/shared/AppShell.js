import Sidebar from "@/components/shared/Sidebar";
import TopBar from "@/components/shared/TopBar";

export default function AppShell({ title, children }) {
  return (
    <div className="min-h-screen flex bg-background">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <TopBar title={title} />
        <main className="flex-1 p-8">{children}</main>
      </div>
    </div>
  );
}
