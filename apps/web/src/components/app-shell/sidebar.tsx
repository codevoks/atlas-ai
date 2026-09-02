"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  AskIcon,
  DocumentsIcon,
  EvaluationIcon,
  MembersIcon,
  OverviewIcon,
  ResearchIcon,
  SearchIcon,
  SecurityIcon,
} from "@/components/icons";

interface NavItem {
  href: string;
  label: string;
  icon: (props: { className?: string }) => React.ReactElement;
  exact?: boolean;
}

interface SidebarProps {
  workspaceId: string;
  workspaceName: string;
  role: string;
  canAdminister: boolean;
  userName: string;
  userEmail: string;
  onSignOut: () => Promise<void>;
}

export function Sidebar({
  workspaceId,
  workspaceName,
  role,
  canAdminister,
  userName,
  userEmail,
  onSignOut,
}: SidebarProps) {
  const pathname = usePathname();
  const base = `/workspaces/${workspaceId}`;

  const primaryItems: NavItem[] = [
    { href: base, label: "Overview", icon: OverviewIcon, exact: true },
    { href: `${base}/documents`, label: "Documents", icon: DocumentsIcon },
    { href: `${base}/search`, label: "Search", icon: SearchIcon },
    { href: `${base}/ask`, label: "Ask", icon: AskIcon },
  ];
  const workflowItems: NavItem[] = [
    { href: `${base}/research`, label: "Research", icon: ResearchIcon },
    { href: `${base}/evaluation`, label: "Evaluation", icon: EvaluationIcon },
  ];
  const adminItems: NavItem[] = [
    ...(canAdminister ? [{ href: `${base}/security`, label: "Security", icon: SecurityIcon }] : []),
    { href: `${base}/members`, label: "Members", icon: MembersIcon },
  ];

  function isActive(item: NavItem): boolean {
    if (item.exact) return pathname === item.href;
    return pathname === item.href || pathname.startsWith(`${item.href}/`);
  }

  function renderGroup(label: string, items: NavItem[]) {
    return (
      <div className="app-nav-group">
        <p className="app-nav-label">{label}</p>
        {items.map((item) => {
          const Icon = item.icon;
          const active = isActive(item);
          return (
            <Link
              className={`app-nav-link${active ? " active" : ""}`}
              href={item.href}
              key={item.href}
            >
              <Icon className="nav-icon" />
              {item.label}
            </Link>
          );
        })}
      </div>
    );
  }

  return (
    <aside className="app-sidebar">
      <div className="app-sidebar-header">
        <Link className="brand" href="/dashboard">
          <span className="brand-mark">A</span>
          Atlas
        </Link>
      </div>
      <div className="app-sidebar-nav">
        <p
          className="text-xs"
          style={{
            padding: "0 10px 4px",
            color: "var(--ink-faint)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
          title={workspaceName}
        >
          {workspaceName}
        </p>
        {renderGroup("Workspace", primaryItems)}
        {renderGroup("Intelligence", workflowItems)}
        {renderGroup(role === "owner" || role === "admin" ? "Administration" : "Access", adminItems)}
      </div>
      <div className="app-sidebar-footer">
        <div className="app-user-row">
          <span className="avatar">{initials(userName)}</span>
          <span>
            <strong>{userName}</strong>
            <small>{userEmail}</small>
          </span>
        </div>
        <form action={onSignOut}>
          <button className="button ghost" style={{ width: "100%", justifyContent: "flex-start" }} type="submit">
            Sign out
          </button>
        </form>
      </div>
    </aside>
  );
}

function initials(name: string): string {
  return name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}
