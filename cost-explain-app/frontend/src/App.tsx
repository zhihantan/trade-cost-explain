import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { api, errorText } from "./api/client";
import type { Me } from "./api/types";
import { Notice } from "./components/common";
import { Icon } from "./components/Icon";
import { Avatar } from "./components/layout";
import { useMe } from "./hooks";
import { useTheme } from "./theme";
import { THEMES } from "./themes";

// A popover anchored above its trigger in the sidebar footer; closes on outside click or Escape.
function Popover({ trigger, children }: { trigger: (open: boolean, toggle: () => void) => ReactNode; children: (close: () => void) => ReactNode }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const down = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", down);
    document.addEventListener("keydown", key);
    return () => { document.removeEventListener("mousedown", down); document.removeEventListener("keydown", key); };
  }, [open]);
  return (
    <div className="menu-wrap" ref={ref}>
      {trigger(open, () => setOpen((o) => !o))}
      {open && <div className="menu" role="menu">{children(() => setOpen(false))}</div>}
    </div>
  );
}

function Swatch({ s }: { s: (typeof THEMES)[number]["swatch"] }) {
  return (
    <span className="swatch" aria-hidden="true">
      <span className="s" style={{ background: s.side }} />
      <span className="m" style={{ background: s.bg }}>
        <i style={{ background: s.ink, width: "70%" }} />
        <i style={{ background: s.up, width: "45%" }} />
        <i style={{ background: s.down, width: "30%" }} />
        <i style={{ background: s.accent, width: "18%" }} />
      </span>
    </span>
  );
}

function ThemePicker() {
  const [theme, setTheme] = useTheme();
  const cur = THEMES.find((t) => t.key === theme) ?? THEMES[0];
  return (
    <Popover
      trigger={(open, toggle) => (
        <button className="side-btn" aria-haspopup="menu" aria-expanded={open} onClick={toggle} title="Theme">
          <Icon name="palette" />
          <span className="meta"><b>{cur.name}</b><span>{cur.tag}</span></span>
          <Icon name={open ? "chevronUp" : "chevron"} className="chev" />
        </button>
      )}
    >
      {(close) => (
        <>
          <h3>Theme</h3>
          {THEMES.map((t) => (
            <button key={t.key} role="menuitemradio" aria-checked={t.key === theme} className={`menu-item ${t.key === theme ? "on" : ""}`}
              onClick={() => { setTheme(t.key); close(); }}>
              <Swatch s={t.swatch} />
              <span className="meta"><b>{t.name}</b><span>{t.tag} — {t.description}</span></span>
              {t.key === theme && <Icon name="tick" className="tick" />}
            </button>
          ))}
        </>
      )}
    </Popover>
  );
}

function UserMenu({ me, onReset, resetting }: { me: Me; onReset: () => void; resetting: boolean }) {
  const name = me.display_name ?? me.email;
  return (
    <Popover
      trigger={(open, toggle) => (
        <button className="side-btn" aria-haspopup="menu" aria-expanded={open} onClick={toggle}>
          <Avatar name={name} />
          <span className="meta"><b>{name}</b><span>{me.roles.length ? me.roles.join(" · ") : "viewer"}</span></span>
          <Icon name={open ? "chevronUp" : "chevron"} className="chev" />
        </button>
      )}
    >
      {(close) => (
        <>
          <div className="menu-item" style={{ cursor: "default" }}>
            <Avatar name={name} />
            <span className="meta"><b>{name}</b><span>{me.email}</span></span>
          </div>
          <hr />
          <div className="menu-item" style={{ cursor: "default" }}>
            <Icon name="check" />
            <span className="meta"><b>Roles</b><span>{me.roles.length ? me.roles.join(", ") : "viewer"} · four-eyes approval applies</span></span>
          </div>
          {me.features.demo_reset && me.is_approver && (
            <>
              <hr />
              <button className="menu-item" disabled={resetting}
                onClick={() => { close(); if (window.confirm("Reset the review store to the seeded storyline? This clears all commentary and audit events (demo environment only).")) onReset(); }}>
                <Icon name="reset" />
                <span className="meta"><b>{resetting ? "Resetting…" : "Reset demo"}</b><span>Restore the seeded commentary and approval queue</span></span>
              </button>
            </>
          )}
        </>
      )}
    </Popover>
  );
}

export function AppLayout() {
  const me = useMe();
  const qc = useQueryClient();
  const queue = useQuery({ queryKey: ["approvals"], queryFn: api.approvals, enabled: !!me.data, refetchInterval: 30_000 });
  const reset = useMutation({ mutationFn: api.demoReset, onSuccess: () => qc.invalidateQueries() });
  const unauth = me.error && (me.error as { status?: number }).status === 401;
  const pending = queue.data?.length ?? 0;
  return (
    <div className="shell">
      <aside className="side" aria-label="Application">
        <div className="side-brand">
          <span className="brand-mark" aria-hidden="true" />
          <div><b>Meridian Group</b><span>Trade Cost Explain</span></div>
        </div>
        <div className="side-section">Analysis</div>
        <nav aria-label="Analysis">
          <NavLink to="/" end><Icon name="bridge" /><span className="lbl">Flux overview</span></NavLink>
        </nav>
        <div className="side-section">Close</div>
        <nav aria-label="Close">
          <NavLink to="/commentary"><Icon name="doc" /><span className="lbl">Commentary</span></NavLink>
          <NavLink to="/approvals"><Icon name="check" /><span className="lbl">Approvals</span>{pending > 0 && <span className="count" aria-label={`${pending} awaiting approval`}>{pending}</span>}</NavLink>
          <NavLink to="/audit"><Icon name="clock" /><span className="lbl">Audit trail</span></NavLink>
        </nav>
        <div className="side-foot">
          {me.data && (
            <div className="side-status" title="Figures are read live from Unity Catalog with your identity">
              <span className="live-dot" aria-hidden="true" /><span className="lbl">{me.data.data_mode === "live" ? "Live · Unity Catalog" : `Data: ${me.data.data_mode}`}</span>
            </div>
          )}
          <ThemePicker />
          {me.data && <UserMenu me={me.data} onReset={() => reset.mutate()} resetting={reset.isPending} />}
        </div>
      </aside>
      <main className="main">
        {reset.isError && <div className="page-body" style={{ paddingBottom: 0 }}><Notice kind="err">{errorText(reset.error)}</Notice></div>}
        {unauth ? (
          <div className="page-body"><Notice kind="err">User authorization is required. Open this app from Databricks so your identity is forwarded.</Notice></div>
        ) : (
          <Outlet />
        )}
      </main>
    </div>
  );
}
