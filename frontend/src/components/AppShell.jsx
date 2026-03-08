import { NavLink } from "react-router-dom";
import { BriefcaseBusiness, ChartColumn, KanbanSquare, Settings, User } from "lucide-react";

const navItems = [
  { to: "/", label: "Dashboard", icon: ChartColumn },
  { to: "/jobs", label: "Jobs Feed", icon: BriefcaseBusiness },
  { to: "/applications", label: "Applications", icon: KanbanSquare },
  { to: "/profile", label: "Profile & CV", icon: User },
  { to: "/settings", label: "Settings", icon: Settings },
];

export const AppShell = ({ children }) => {
  return (
    <div className="min-h-screen bg-app-bg text-slate-100" data-testid="app-shell-layout">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_15%_15%,rgba(59,130,246,0.18),transparent_38%),radial-gradient(circle_at_85%_10%,rgba(147,51,234,0.15),transparent_30%)]" />

      <div className="relative mx-auto flex w-full max-w-[1600px] flex-col md:flex-row">
        <aside
          className="md:sticky md:top-0 md:h-screen md:w-72 md:border-r md:border-white/10 md:bg-white/[0.03] md:backdrop-blur-xl"
          data-testid="sidebar-navigation"
        >
          <div className="border-b border-white/10 p-6">
            <p className="font-mono text-xs tracking-[0.25em] text-blue-300" data-testid="brand-label">
              AUTOAPPLY
            </p>
            <h1 className="mt-3 text-2xl font-semibold text-white" data-testid="brand-title">
              Command Center
            </h1>
            <p className="mt-2 text-sm text-slate-400" data-testid="brand-subtitle">
              Autonomous job hunt orchestration.
            </p>
          </div>

          <nav className="flex flex-wrap gap-2 p-4 md:flex-col" data-testid="sidebar-links">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  data-testid={`nav-link-${item.label.toLowerCase().replace(/\s+/g, "-")}`}
                  className={({ isActive }) =>
                    `group flex flex-1 items-center gap-3 rounded-xl border px-4 py-3 text-sm transition-all duration-300 md:flex-none ${
                      isActive
                        ? "border-blue-400/60 bg-blue-500/20 text-blue-100"
                        : "border-white/10 bg-white/[0.02] text-slate-300 hover:border-white/20 hover:bg-white/[0.06]"
                    }`
                  }
                >
                  <Icon size={16} />
                  <span>{item.label}</span>
                </NavLink>
              );
            })}
          </nav>
        </aside>

        <main className="w-full flex-1 p-4 sm:p-6 lg:p-10" data-testid="main-content-area">
          {children}
        </main>
      </div>
    </div>
  );
};
