import { Link } from "@tanstack/react-router";

const NAV_ITEMS = [
  { label: "Inbox", to: "/" },
  { label: "Drafts", to: "/drafts" },
  { label: "Sent", to: "/sent" },
  { label: "Knowledge", to: "/knowledge" },
  { label: "Settings", to: "/settings" },
] as const;

const BASE_ITEM = "block w-full rounded-md px-3 py-2 text-left text-sm";

export default function SideNav() {
  return (
    <nav aria-label="Main" className="w-44 shrink-0 bg-navy-950 p-3">
      <ul className="space-y-1">
        {NAV_ITEMS.map((item) => (
          <li key={item.to}>
            <Link
              to={item.to}
              // Without exact, "/" would match every route and light up permanently.
              activeOptions={{ exact: item.to === "/" }}
              className={`${BASE_ITEM} text-navy-200 hover:bg-navy-900 hover:text-white`}
              activeProps={{ className: `${BASE_ITEM} bg-navy-800 font-semibold text-white` }}
            >
              {item.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
