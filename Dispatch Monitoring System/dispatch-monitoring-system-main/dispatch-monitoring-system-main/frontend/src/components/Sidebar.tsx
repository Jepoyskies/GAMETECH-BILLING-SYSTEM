import { useState } from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  ClipboardList,
  Wifi,
  Tv,
  Headphones,
  Contact,
  Settings,
  ScrollText,
  LogOut,
  ChevronLeft,
  ChevronRight,
  HardDrive,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import ConfirmModal from "./ConfirmModal";
import gametechLogo from "../assets/gametech.png";
import "../styles/Sidebar.css";

function buildNavItems(isSuperAdmin: boolean): Array<{ to: string; label: string; icon: React.ElementType } | { divider: true }> {
  const items: Array<{ to: string; label: string; icon: React.ElementType } | { divider: true }> = [
    { to: "/", label: "Dashboard", icon: LayoutDashboard },
    { to: "/dispatches", label: "Dispatch Log", icon: ClipboardList },
    { divider: true },
    { to: "/internet-install", label: "Internet Install", icon: Wifi },
    { to: "/cignal-install", label: "Cignal Play", icon: Tv },
    { to: "/client-concerns", label: "Client Concerns", icon: Headphones },
    { to: "/customers", label: "Customer", icon: Contact },
    { divider: true },
    { to: "/staff", label: "Management", icon: Settings },
    { to: "/audit-log", label: "Audit Log", icon: ScrollText },
    ...(isSuperAdmin ? [{ to: "/backups" as const, label: "Backups" as const, icon: HardDrive }] : []),
  ];
  return items;
}

export default function Sidebar({
  onCollapseChange,
}: {
  onCollapseChange?: (collapsed: boolean) => void;
} = {}) {
  const { user, logout, isSuperAdmin } = useAuth();
  const navItems = buildNavItems(isSuperAdmin);
  const [collapsed, setCollapsed] = useState(() => {
    const saved = localStorage.getItem("sidebarCollapsed");
    return saved === "true";
  });
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);

  const toggleCollapsed = () => {
    const next = !collapsed;
    setCollapsed(next);
    localStorage.setItem("sidebarCollapsed", String(next));
    onCollapseChange?.(next);
  };

  return (
    <aside className={`sidebar ${collapsed ? "collapsed" : ""}`}>
      <div className="sidebar-header">
        <div className="sidebar-title">
          <div className="sidebar-logo-row">
            <img
              src={gametechLogo}
              alt="Gametech"
              style={{
                width: "35px",
                height: "auto",
                flexShrink: 0,
                display: "inline-block",
                verticalAlign: "middle",
                marginRight: "0.3rem",
                marginLeft: "-2px",
                marginTop: "-5px",
              }}
            />
            <div className="sidebar-brand-group">
              <span className="sidebar-brand">Dispatch</span>
              <span className="sidebar-sub">monitoring</span>
            </div>
          </div>
        </div>
        <button
          type="button"
          className="sidebar-toggle"
          onClick={toggleCollapsed}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>
      <nav className="sidebar-nav">
        {navItems.map((item, index) => {
          const isDivider = "divider" in item;
          return isDivider ? (
            <div key={index} className="sidebar-divider" />
          ) : (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                isActive ? "sidebar-link active" : "sidebar-link"
              }
              title={collapsed ? item.label : undefined}
            >
              <item.icon size={18} className="sidebar-link-icon" />
              <span className="sidebar-link-text">{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      {user && (
        <div className="sidebar-user">
          <div className="sidebar-user-info">
            <span className="sidebar-user-name">{user.name}</span>
            <span className="sidebar-user-role">
              {user.role === "SUPERADMIN" ? "Super Admin" : "CSR Admin"}
            </span>
          </div>
          <div className="sidebar-user-avatar">
            {user.name ? user.name.charAt(0).toUpperCase() : "?"}
          </div>
          <button
            type="button"
            className="sidebar-logout"
            onClick={() => setShowLogoutConfirm(true)}
            title={collapsed ? "Log out" : undefined}
          >
            <LogOut size={16} className="sidebar-link-icon" />
            <span className="sidebar-link-text">Log out</span>
          </button>
        </div>
      )}

      <ConfirmModal
        open={showLogoutConfirm}
        title="Log Out"
        message="Are you sure you want to log out?"
        confirmLabel="Log Out"
        cancelLabel="Cancel"
        variant="danger"
        onConfirm={() => {
          setShowLogoutConfirm(false);
          logout();
        }}
        onCancel={() => setShowLogoutConfirm(false)}
      />
    </aside>
  );
}