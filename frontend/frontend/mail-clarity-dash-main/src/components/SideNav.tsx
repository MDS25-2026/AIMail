/**
 * Static chrome for now — only Inbox is functional. Wire the rest up when the
 * Drafts / Knowledge / Settings surfaces exist.
 */
const NAV_ITEMS = ["Inbox", "Drafts", "Knowledge", "Settings"] as const;

export default function SideNav({ active = "Inbox" }: { active?: string }) {
  return (
    <nav aria-label="Main" className="w-44 shrink-0 border-r border-slate-200 bg-white p-3">
      <ul className="space-y-1">
        {NAV_ITEMS.map((item) => (
          <li key={item}>
            <button
              type="button"
              aria-current={item === active ? "page" : undefined}
              className={`w-full rounded-md px-3 py-2 text-left text-sm ${
                item === active
                  ? "bg-slate-100 font-semibold text-slate-900"
                  : "text-slate-600 hover:bg-slate-50"
              }`}
            >
              {item}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
