// Page scaffolding shared by every screen: sticky page header, card, tabs, avatar, empty state.
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Icon } from "./Icon";

export function PageHeader({ crumbs, title, badge, sub, actions }: {
  crumbs?: { label: string; to?: string }[]; title: ReactNode; badge?: ReactNode; sub?: ReactNode; actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div style={{ minWidth: 0 }}>
        {crumbs && crumbs.length > 0 && (
          <nav className="crumbs" aria-label="Breadcrumb">
            {crumbs.map((c, i) => (
              <span key={i} className="crumbs">
                {i > 0 && <span aria-hidden="true">/</span>}
                {c.to ? <Link to={c.to}>{c.label}</Link> : <span>{c.label}</span>}
              </span>
            ))}
          </nav>
        )}
        <div className="title-row"><h1>{title}</h1>{badge}</div>
        {sub && <div className="sub">{sub}</div>}
      </div>
      {actions && <div className="ph-actions">{actions}</div>}
    </header>
  );
}

export function Card({ title, sub, actions, children, className = "", foot }: {
  title?: ReactNode; sub?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; foot?: ReactNode;
}) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <div className="card-head">
          <div className="card-title">{title && <h2>{title}</h2>}{sub && <span className="card-sub">{sub}</span>}</div>
          {actions}
        </div>
      )}
      <div className="card-body">{children}</div>
      {foot && <div className="card-foot">{foot}</div>}
    </section>
  );
}

export function Tabs<K extends string>({ tabs, value, onChange }: {
  tabs: { key: K; label: string; count?: number; icon?: string }[]; value: K; onChange: (k: K) => void;
}) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((t) => (
        <button key={t.key} role="tab" aria-selected={value === t.key} className={value === t.key ? "on" : ""} onClick={() => onChange(t.key)}>
          {t.icon && <Icon name={t.icon} size={14} />}{t.label}{t.count !== undefined && <span className="n">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function initials(name: string | null | undefined): string {
  const base = (name ?? "").split("@")[0].replace(/[._-]+/g, " ").trim();
  const parts = base.split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "?") + (parts[1]?.[0] ?? "")).toUpperCase();
}

export function Avatar({ name, small = false }: { name: string | null | undefined; small?: boolean }) {
  return <span className={`avatar ${small ? "sm" : ""}`} aria-hidden="true">{initials(name)}</span>;
}

export function Person({ email }: { email: string | null | undefined }) {
  return <span className="who"><Avatar name={email} small />{email ?? "—"}</span>;
}

export function EmptyState({ icon = "inbox", title, children }: { icon?: string; title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <Icon name={icon} />
      <b>{title}</b>
      {children && <div>{children}</div>}
    </div>
  );
}
