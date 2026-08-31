/**
 * Static chrome for now — only Inbox is functional. Wire the rest up when the
 * Drafts / Knowledge / Settings surfaces exist.
 */
const NAV_ITEMS = ["Inbox", "Drafts", "Knowledge", "Settings"] as const;

export default function SideNav({ active = "Inbox" }: { active?: string }) {
  return (
    <nav aria-label="Main" className="w-44 shrink-0 bg-navy-950 p-3">
      <ul className="space-y-1">
        {NAV_ITEMS.map((item) => (
          <li key={item}>
            <button
              type="button"
              aria-current={item === active ? "page" : undefined}
              className={`w-full rounded-md px-3 py-2 text-left text-sm ${
                item === active
                  ? "bg-navy-800 font-semibold text-white"
                  : "text-navy-200 hover:bg-navy-900 hover:text-white"
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
