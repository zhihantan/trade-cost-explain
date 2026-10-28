"""Fast unit checks (no network): fixtures tie to the planted targets, chips parse, CSRF/auth fail closed."""
import os

os.environ.setdefault("APP_ENV", "prod")
os.environ.setdefault("PGUSER", "test")

from fastapi.testclient import TestClient  # noqa: E402

from backend import fixtures, template  # noqa: E402
from backend.main import app  # noqa: E402

TARGETS = {  # docs/CONTRACTS.md §2, US$
    "APAC": dict(P0=5_000_000, P1=6_200_000, VOLUME=900_000, MIX=190_000, RATE=100_000, FAILS=150_000,
                 TIMING=-50_000, FX=-100_000, UNEXPLAINED=10_000, FIXED=0),
    "ED_EXCH_CLR": dict(P0=2_170_000, P1=2_680_000, VOLUME=390_000, MIX=90_000, RATE=60_000, TIMING=-20_000,
                        FX=-10_000),
}


def test_fixture_bridge_ties_to_planted_targets():
    reg = fixtures.figure_registry()
    for scope, metrics in TARGETS.items():
        for metric, value in metrics.items():
            assert abs(reg[f"MOM_2026-09|{scope}|{metric}"]["value"] - value) < 0.5, (scope, metric)
    assert abs(reg["MOM_2026-09|APAC|GOOD_PCT"]["value"] - 0.75) < 1e-9
    assert abs(reg["MOM_2026-09|APAC|CONTROLLABLE"]["value"] - 340_000) < 0.5


def test_every_comparison_row_identity_holds():
    for r in fixtures.bridge_rows():
        effects = sum(r[f"{e}_usd"] for e in fixtures.EFFECTS)
        assert abs(r["p1_actual_usd"] - r["p0_actual_usd"] - effects) < 1e-6


def test_template_cites_only_registry_figures():
    comp = fixtures.comparisons()[0]
    reg = fixtures.figure_registry()
    from backend.gold import _figure_from_row

    figs = {k: _figure_from_row(v, "fixtures") for k, v in reg.items() if v.get("comparison_id") == comp["comparison_id"]}
    text = template.draft(comp, "APAC", "APAC Global Markets", figs)
    keys = template.chip_keys(text)
    assert keys and all(k in reg for k in keys)


def test_auth_and_csrf_fail_closed():
    c = TestClient(app)
    assert c.get("/api/health").status_code == 200
    assert c.get("/api/me").status_code == 401
    assert c.get("/api/flux?period=MOM_2026-09").status_code == 401
    assert c.post("/api/commentary", json={}).status_code == 403  # missing CSRF header
    h = {"X-Requested-With": "cost-explain-app", "Origin": "https://evil.example.com", "Host": "app.example.com"}
    assert c.post("/api/commentary", json={}, headers=h).status_code == 403  # cross-origin


def test_entitlement_precheck_requires_full_slice_visibility(monkeypatch):
    """A desk head who can see only HKED may draft HKED / ED_EXCH_CLR but not APAC (the agent may read all desks)."""
    from backend import db_sql, gold
    from backend.auth import User

    monkeypatch.setattr(gold, "_mode", lambda: "live")

    def fake_query(user, statement, params=None):
        assert "ce_desk_scope" in statement
        return [{"desk_code": d, "ok": d == "HKED"} for d in params.values()]

    monkeypatch.setattr(db_sql, "query_as_user", fake_query)
    u = User(email="desk.head@example.com", token="t")
    assert gold.slice_access_check(u, "MOM_2026-09", "ED_EXCH_CLR") == (True, [])
    assert gold.slice_access_check(u, "MOM_2026-09", "DESK:HKED") == (True, [])
    ok, hidden = gold.slice_access_check(u, "MOM_2026-09", "APAC")
    assert not ok and "AUCE" in hidden and "HKED" not in hidden
    ok, hidden = gold.slice_access_check(u, "MOM_2026-09", "BUS:CEQ")
    assert not ok and set(hidden) == {"AUCE", "CNSC", "HKCE", "INEQ", "KTEQ"}


def test_template_keeps_invoice_findings_at_division_level():
    from backend.gold import _figure_from_row

    comp = fixtures.comparisons()[0]
    reg = fixtures.figure_registry()
    figs = {k: _figure_from_row(v, "fixtures") for k, v in reg.items()
            if v.get("comparison_id") == comp["comparison_id"] or k.startswith("INV|2026-08|")}
    assert "INV|2026-08|B03|VARIANCE" in template.draft(comp, "APAC", "APAC Global Markets", figs)
    assert "INV|" not in template.draft(comp, "ED_EXCH_CLR", "Equity Derivatives — exchange & clearing", figs)
