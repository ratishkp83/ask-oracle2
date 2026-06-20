import { NavLink } from "react-router-dom";
import {
  BookText,
  FolderOpen,
  MessageCircleQuestion,
  Plug,
  Settings,
} from "lucide-react";

const ITEMS = [
  { to: "/ask", label: "Ask", icon: MessageCircleQuestion },
  { to: "/reports", label: "Reports", icon: FolderOpen },
  { to: "/dictionary", label: "Data dictionary", icon: BookText },
  { to: "/connections", label: "Connections", icon: Plug },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function LeftRail() {
  return (
    <nav className="flex w-[52px] shrink-0 flex-col items-center gap-1 border-r border-hairline bg-surface pt-3">
      {ITEMS.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          title={label}
          aria-label={label}
          className={({ isActive }) =>
            `flex h-9 w-9 items-center justify-center rounded-[9px] transition-colors ${
              isActive
                ? "bg-brand-weak text-brand"
                : "text-ink-faint hover:bg-surface-sunken hover:text-ink-muted"
            }`
          }
        >
          <Icon className="h-[19px] w-[19px]" />
        </NavLink>
      ))}
    </nav>
  );
}
