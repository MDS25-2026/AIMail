import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";

import SideNav from "./SideNav";

/** App chrome shared by every dashboard route: brand header plus the nav rail. */
export default function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen flex-col bg-slate-100">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
        <div className="flex items-baseline gap-2">
          <span className="text-lg font-semibold tracking-tight text-navy-900">AIMail</span>
          <span className="text-xs text-slate-400">AI inbox assistant</span>
        </div>
        <Link to="/extension" className="text-sm font-medium text-blue-600 hover:text-blue-700">
          Extension panel preview
        </Link>
      </header>

      <main className="flex min-h-0 flex-1">
        <SideNav />
        {children}
      </main>
    </div>
  );
}
