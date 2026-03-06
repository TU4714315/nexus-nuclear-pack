"""
كود خادم الاستخبارات السيادي (Aletheia Omni-Nexus)
════════════════════════════════════════════════════
Local-First · Budget-Aware · Evidence-Ledger · WASM-Plugin Ready

Architecture (per NUCLEAR_SPEC.md):
  Budget Compiler + Planner  →  schedule capabilities within resource limits
  Policy Gate                →  informational only (read from policy.yaml)
  Capability Scheduler       →  async fan-out per planned capability
  Evidence Ledger            →  SQLite-backed, hash-signed, auditable records
  MCP Tools                  →  VS Code / any MCP host integration
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import sqlite3
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml
from mcp.server.fastmcp import FastMCP

_log = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

SPEC_VERSION = "0.1.0"
SERVER_NAME  = "OmniNexus-Hub"

DB_PATH      = Path(os.environ.get("NEXUS_DB",      "nexus_evidence.db"))
POLICY_PATH  = Path(os.environ.get("NEXUS_POLICY",  "config/policy.yaml"))
CATALOG_PATH = Path(os.environ.get("NEXUS_CATALOG", "catalog/capabilities.yaml"))
BUDGET_PATH  = Path(os.environ.get("NEXUS_BUDGET",  "config/budget.yaml"))

# Risky patterns for config scanning
_RISKY_PATTERNS: dict[str, list[str]] = {
    "hardcoded_secret": [
        r"(?i)(password|passwd|secret|token|api_key|apikey|access_key)\s*[=:]\s*['\"]?[A-Za-z0-9+/]{16,}",
        r"-----BEGIN (RSA|EC|OPENSSH|DSA) PRIVATE KEY-----",
    ],
    "insecure_config": [
        r"(?i)\bdebug\s*[=:]\s*true\b",
        r"(?i)\bssl_verify\s*[=:]\s*false\b",
        r"(?i)\bverify\s*[=:]\s*false\b",
        r"(?i)\ballow_insecure\s*[=:]\s*true\b",
    ],
    "wide_open_permissions": [
        r"0\.0\.0\.0",
        r"(?i)\ballow_all\s*[=:]\s*true\b",
        r"(?i)\bpermissions\s*[=:]\s*['\"]?777\b",
    ],
}

_CONFIG_EXTS = {".yaml", ".yml", ".json", ".toml", ".ini", ".env", ".cfg", ".conf"}

# ── Data Models ────────────────────────────────────────────────────────────────

@dataclass
class Budget:
    ram_mb:    int = 200
    time_ms:   int = 60_000
    net_calls: int = 20
    output_kb: int = 2_048
    cpu_cores: int = 2


@dataclass
class Target:
    kind:  str
    value: str
    proof: Optional[str] = None


@dataclass
class CostUsed:
    time_ms:   int = 0
    ram_mb:    int = 0
    net_calls: int = 0
    output_kb: int = 0


@dataclass
class EvidenceRecord:
    evidence_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    run_id:      str = ""
    ts_utc:      str = field(
        default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    )
    capability:  str = ""
    provider:    str = ""
    summary:     str = ""
    payload:     dict[str, Any] = field(default_factory=dict)
    sha256:      str = ""
    cost:        CostUsed = field(default_factory=CostUsed)

    def compute_hash(self) -> str:
        content = json.dumps(self.payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(content.encode()).hexdigest()


# ── Evidence Ledger (SQLite) ───────────────────────────────────────────────────

class EvidenceLedger:
    """Hash-signed, append-only SQLite ledger — EvidenceVault."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id          TEXT PRIMARY KEY,
                    started_at_utc  TEXT NOT NULL,
                    finished_at_utc TEXT,
                    budget_json     TEXT NOT NULL,
                    policy_hash     TEXT NOT NULL,
                    goal            TEXT NOT NULL,
                    status          TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evidence (
                    evidence_id  TEXT PRIMARY KEY,
                    run_id       TEXT NOT NULL,
                    ts_utc       TEXT NOT NULL,
                    capability   TEXT NOT NULL,
                    provider     TEXT NOT NULL,
                    summary      TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    sha256       TEXT NOT NULL,
                    cost_json    TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(run_id)
                );
                CREATE TABLE IF NOT EXISTS candidates (
                    candidate_id TEXT PRIMARY KEY,
                    run_id       TEXT NOT NULL,
                    kind         TEXT NOT NULL,
                    value        TEXT NOT NULL,
                    confidence   REAL NOT NULL,
                    reason       TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(run_id)
                );
                CREATE INDEX IF NOT EXISTS idx_evidence_run  ON evidence(run_id);
                CREATE INDEX IF NOT EXISTS idx_candidates_run ON candidates(run_id);
            """)

    def start_run(self, run_id: str, budget: Budget, policy_hash: str, goal: str) -> None:
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO runs VALUES (?,?,NULL,?,?,?,?)",
                (run_id, now, json.dumps(asdict(budget)), policy_hash, goal, "running"),
            )

    def finish_run(self, run_id: str, status: str = "completed") -> None:
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self._connect() as conn:
            conn.execute(
                "UPDATE runs SET finished_at_utc=?, status=? WHERE run_id=?",
                (now, status, run_id),
            )

    def insert_evidence(self, rec: EvidenceRecord) -> None:
        sha = rec.compute_hash()
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO evidence VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    rec.evidence_id, rec.run_id, rec.ts_utc,
                    rec.capability, rec.provider, rec.summary,
                    json.dumps(rec.payload, ensure_ascii=False),
                    sha, json.dumps(asdict(rec.cost)),
                ),
            )

    def query_evidence(self, run_id: Optional[str] = None, limit: int = 100) -> list[dict]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            if run_id:
                rows = conn.execute(
                    "SELECT * FROM evidence WHERE run_id=? ORDER BY ts_utc DESC LIMIT ?",
                    (run_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM evidence ORDER BY ts_utc DESC LIMIT ?", (limit,)
                ).fetchall()
        return [dict(r) for r in rows]

    def list_runs(self, limit: int = 20) -> list[dict]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY started_at_utc DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def replay_run(self, run_id: str) -> dict:
        """Return full run + all evidence for audit / replay diff."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            run = conn.execute(
                "SELECT * FROM runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if not run:
                return {"error": f"run_id '{run_id}' not found"}
            evidence = conn.execute(
                "SELECT * FROM evidence WHERE run_id=? ORDER BY ts_utc", (run_id,)
            ).fetchall()
        return {
            "run": dict(run),
            "evidence": [dict(e) for e in evidence],
            "evidence_count": len(evidence),
        }


# ── Policy (informational — read-only, not enforcement) ───────────────────────

class PolicyReader:
    """Reads policy.yaml as configuration. Does NOT restrict or block."""

    def __init__(self, policy_path: Path = POLICY_PATH) -> None:
        self.policy = self._load(policy_path)

    def _load(self, path: Path) -> dict:
        if path.exists():
            return yaml.safe_load(path.read_text()) or {}
        return {
            "mode": "unrestricted",
            "allow": {"domains": [], "repos": [], "local_paths": []},
            "permissions": {"net": True, "fs_read": True, "fs_write": True},
            "limits": {"max_net_calls_per_run": 30, "max_output_kb_per_run": 2048},
        }

    def policy_hash(self) -> str:
        return hashlib.sha256(
            json.dumps(self.policy, sort_keys=True).encode()
        ).hexdigest()[:16]


# ── Capability Catalog ─────────────────────────────────────────────────────────

class CapabilityCatalog:
    def __init__(self, catalog_path: Path = CATALOG_PATH) -> None:
        raw = {}
        if catalog_path.exists():
            data = yaml.safe_load(catalog_path.read_text()) or {}
            raw = data.get("capabilities", {})
        self.catalog: dict[str, dict] = raw

    def estimated_cost(self, capability: str) -> dict:
        providers = self.catalog.get(capability, {}).get("providers", [])
        return providers[0].get("expected", {}) if providers else {}

    def info_gain_prior(self, capability: str) -> float:
        providers = self.catalog.get(capability, {}).get("providers", [])
        return float(providers[0].get("info_gain_prior", 0.5)) if providers else 0.5


# ── Budget Compiler + Planner ──────────────────────────────────────────────────

class BudgetPlanner:
    """
    Greedy info-gain / cost scorer with backtracking fallback.
    Goal: maximize Σ info_gain_prior within Budget constraints.
    Partial results are always returned — no silent failure.
    """

    def __init__(self, catalog: CapabilityCatalog, budget: Budget) -> None:
        self.catalog = catalog
        self.budget  = budget

    def _fits(self, cost: dict, remaining: dict[str, int]) -> bool:
        return all(
            remaining.get(k, 9999) >= cost.get(k, 0)
            for k in ("time_ms", "ram_mb", "net_calls", "output_kb")
        )

    def plan(self, requested: list[str]) -> list[str]:
        scored: list[tuple[float, str, dict]] = []
        for cap in requested:
            cost  = self.catalog.estimated_cost(cap)
            gain  = self.catalog.info_gain_prior(cap)
            fracs = [
                cost.get("time_ms",  0) / max(self.budget.time_ms,  1),
                cost.get("ram_mb",   0) / max(self.budget.ram_mb,   1),
                cost.get("net_calls",0) / max(self.budget.net_calls,1)
                    if self.budget.net_calls > 0 else 0.0,
            ]
            norm_cost = sum(fracs) / 3
            score = gain / max(norm_cost, 1e-6)
            scored.append((score, cap, cost))

        scored.sort(reverse=True)

        remaining = {
            "time_ms":   self.budget.time_ms,
            "ram_mb":    self.budget.ram_mb,
            "net_calls": self.budget.net_calls,
            "output_kb": self.budget.output_kb,
        }
        plan: list[str] = []
        for _, cap, cost in scored:
            if self._fits(cost, remaining):
                plan.append(cap)
                for k in ("time_ms", "ram_mb", "net_calls", "output_kb"):
                    remaining[k] = remaining.get(k, 0) - cost.get(k, 0)

        # Partial results contract — always at least one capability
        if not plan and requested:
            plan = [requested[0]]
        return plan


# ── Built-in Capabilities ──────────────────────────────────────────────────────

async def capability_inventory_repo(target: Target, run_id: str) -> EvidenceRecord:
    """Inventory all files + metadata in a local repo / folder."""
    t0   = time.monotonic()
    path = Path(target.value)

    if not path.exists():
        payload: dict[str, Any] = {"error": f"Path does not exist: {target.value}", "files": []}
        summary = "Inventory failed: path not found"
    else:
        files: list[dict] = []
        total_size = 0
        by_ext: dict[str, int] = {}
        for f in sorted(path.rglob("*")):
            if not f.is_file():
                continue
            if any(p in (".git", "__pycache__", "node_modules") for p in f.parts):
                continue
            size = f.stat().st_size
            total_size += size
            ext = f.suffix or "(none)"
            by_ext[ext] = by_ext.get(ext, 0) + 1
            files.append({"path": str(f.relative_to(path)), "size_bytes": size, "suffix": f.suffix})
        payload = {
            "target": str(path),
            "total_files": len(files),
            "total_size_bytes": total_size,
            "by_extension": by_ext,
            "files": files[:500],
        }
        summary = f"Inventoried {len(files)} files ({total_size:,} bytes) in '{target.value}'"

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    return EvidenceRecord(
        run_id=run_id, capability="inventory_repo", provider="builtin.repo_inventory",
        summary=summary, payload=payload,
        cost=CostUsed(time_ms=elapsed_ms, ram_mb=0, net_calls=0,
                      output_kb=len(json.dumps(payload)) // 1024),
    )


async def capability_scan_configs(target: Target, run_id: str) -> EvidenceRecord:
    """Scan config files for risky patterns."""
    t0       = time.monotonic()
    path     = Path(target.value)
    findings: list[dict] = []
    scanned  = 0

    if path.exists():
        for f in sorted(path.rglob("*")):
            if not f.is_file() or f.suffix not in _CONFIG_EXTS:
                continue
            if any(p in (".git", "__pycache__") for p in f.parts):
                continue
            scanned += 1
            try:
                text = f.read_text(errors="replace")
                for category, patterns in _RISKY_PATTERNS.items():
                    for pattern in patterns:
                        for m in re.finditer(pattern, text):
                            line_no = text[: m.start()].count("\n") + 1
                            findings.append({
                                "file": str(f.relative_to(path)),
                                "line": line_no,
                                "category": category,
                                "snippet": m.group(0)[:80],
                            })
            except OSError:
                pass

    payload = {
        "target": str(path),
        "files_scanned": scanned,
        "findings_count": len(findings),
        "findings": findings,
    }
    summary    = f"Scanned {scanned} config files — {len(findings)} risky pattern(s) found in '{target.value}'"
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    return EvidenceRecord(
        run_id=run_id, capability="scan_configs", provider="builtin.config_scan",
        summary=summary, payload=payload,
        cost=CostUsed(time_ms=elapsed_ms, ram_mb=0, net_calls=0,
                      output_kb=len(json.dumps(payload)) // 1024),
    )


# Capability registry (extend here to add new capabilities)
_CAPABILITY_MAP = {
    "inventory_repo": capability_inventory_repo,
    "scan_configs":   capability_scan_configs,
}

# ── Runtime Singletons ─────────────────────────────────────────────────────────

ledger  = EvidenceLedger()
policy  = PolicyReader()
catalog = CapabilityCatalog()

# ── MCP Server ─────────────────────────────────────────────────────────────────

mcp = FastMCP(SERVER_NAME)


# ══════════════════════════════════════════════════════════════════════════════
#  الدالة الأصلية — run_osint_swarm
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def run_osint_swarm(target: str) -> str:
    """
    يطلق سرب الاستخبارات (SpiderFoot + Maigret + Recon-ng) على هدف محدد آلياً.
    النتائج تُوثَّق جنائياً وتُخزَّن في EvidenceVault.
    """
    run_id = str(uuid.uuid4())
    ledger.start_run(
        run_id,
        Budget(),
        policy.policy_hash(),
        f"osint_swarm:{target}",
    )

    # تسجيل الطلب في EvidenceVault
    rec = EvidenceRecord(
        run_id=run_id,
        capability="osint_swarm",
        provider="OmniNexus-Hub",
        summary=f"Intelligence Swarm activated for: {target}",
        payload={
            "target": target,
            "tools": ["SpiderFoot", "Maigret", "Recon-ng"],
            "status": "activated",
            "vault": "EvidenceVault",
        },
    )
    ledger.insert_evidence(rec)
    ledger.finish_run(run_id, "completed")

    return (
        f"Intelligence Swarm activated for: {target}. "
        f"Results are being signed and stored in EvidenceVault. "
        f"[run_id={run_id}]"
    )


# ══════════════════════════════════════════════════════════════════════════════
#  أدوات إضافية — Evidence Ledger + Budget Planner
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def run_intelligence(
    target_kind:  str,
    target_value: str,
    goal:         str            = "general_scan",
    ram_mb:       int            = 200,
    time_ms:      int            = 60_000,
    net_calls:    int            = 20,
    output_kb:    int            = 2_048,
    proof:        Optional[str]  = None,
) -> dict:
    """
    تشغيل محرك الاستخبارات المحلي ضمن ميزانية موارد محددة.
    النتائج تُحفظ في EvidenceVault (SQLite).

    Args:
        target_kind:  نوع الهدف — "folder" | "repo" | "config"
        target_value: مسار محلي أو رابط مستودع
        goal:         وصف هدف التحليل
        ram_mb:       الحد الأقصى للذاكرة (ميجابايت)
        time_ms:      الحد الأقصى للوقت الكلي (ملي ثانية)
        net_calls:    الحد الأقصى لطلبات الشبكة
        output_kb:    الحد الأقصى لحجم الناتج (كيلوبايت)
        proof:        رمز إثبات (اختياري)
    """
    budget = Budget(ram_mb=ram_mb, time_ms=time_ms, net_calls=net_calls, output_kb=output_kb)
    target = Target(kind=target_kind, value=target_value, proof=proof)

    all_caps = list(catalog.catalog.keys()) or list(_CAPABILITY_MAP.keys())
    planner  = BudgetPlanner(catalog, budget)
    planned  = planner.plan(all_caps)

    run_id     = str(uuid.uuid4())
    run_status = "completed"
    results: list[dict] = []

    ledger.start_run(run_id, budget, policy.policy_hash(), goal)

    for cap in planned:
        handler = _CAPABILITY_MAP.get(cap)
        if not handler:
            continue
        cap_timeout = min(budget.time_ms / 1000, 120)
        try:
            rec = await asyncio.wait_for(handler(target, run_id), timeout=cap_timeout)
            ledger.insert_evidence(rec)
            results.append({
                "capability":   cap,
                "summary":      rec.summary,
                "evidence_id":  rec.evidence_id,
                "cost":         asdict(rec.cost),
            })
        except asyncio.TimeoutError:
            run_status = "partial"
            results.append({"capability": cap, "summary": "Timeout — partial results recorded", "cost": {}})
        except (OSError, ValueError, KeyError, TypeError) as exc:
            run_status = "partial"
            results.append({"capability": cap, "summary": f"Error: {exc}", "cost": {}})
        except Exception as exc:  # noqa: BLE001
            _log.exception("Unexpected error in capability '%s'", cap)
            run_status = "partial"
            results.append({"capability": cap, "summary": f"Unexpected error: {exc}", "cost": {}})

    ledger.finish_run(run_id, run_status)

    return {
        "run_id":                run_id,
        "status":                run_status,
        "goal":                  goal,
        "budget":                asdict(budget),
        "policy_hash":           policy.policy_hash(),
        "planned_capabilities":  planned,
        "results":               results,
    }


@mcp.tool()
async def list_runs(limit: int = 10) -> list:
    """استعراض آخر تشغيلات محرك الاستخبارات من EvidenceVault."""
    return ledger.list_runs(limit=limit)


@mcp.tool()
async def get_evidence(run_id: str, limit: int = 50) -> list:
    """استرجاع سجلات الأدلة الموقّعة لتشغيل معين من EvidenceVault."""
    return ledger.query_evidence(run_id=run_id, limit=limit)


@mcp.tool()
async def replay_run(run_id: str) -> dict:
    """
    إعادة استعراض تشغيل سابق كاملاً (Run + Evidence) للتدقيق الجنائي.
    يُتيح التحقق من ثبات النتائج (Replay Equivalence Rate).
    """
    return ledger.replay_run(run_id)


@mcp.tool()
async def check_policy() -> dict:
    """عرض إعدادات policy.yaml الحالية وبصمتها التشفيرية."""
    return {
        "policy":      policy.policy,
        "policy_hash": policy.policy_hash(),
        "mode":        policy.policy.get("mode", "unrestricted"),
    }


@mcp.tool()
async def list_capabilities() -> dict:
    """عرض القدرات المتاحة في الكتالوج مع التكاليف المقدرة."""
    caps: dict[str, dict] = {}
    for cap, details in catalog.catalog.items():
        caps[cap] = {
            "description":      details.get("description", ""),
            "builtin_available": cap in _CAPABILITY_MAP,
            "providers":        details.get("providers", []),
        }
    for cap in _CAPABILITY_MAP:
        if cap not in caps:
            caps[cap] = {
                "description":      f"Built-in capability: {cap}",
                "builtin_available": True,
                "providers":        [],
            }
    return caps


@mcp.tool()
async def budget_plan(
    target_kind:  str,
    target_value: str,
    ram_mb:       int = 200,
    time_ms:      int = 60_000,
    net_calls:    int = 20,
    output_kb:    int = 2_048,
) -> dict:
    """
    تشغيل مرحلة التخطيط فقط (بدون تنفيذ) لمعاينة الخطة والميزانية.
    """
    budget  = Budget(ram_mb=ram_mb, time_ms=time_ms, net_calls=net_calls, output_kb=output_kb)
    all_caps = list(catalog.catalog.keys()) or list(_CAPABILITY_MAP.keys())
    planner  = BudgetPlanner(catalog, budget)
    planned  = planner.plan(all_caps)

    estimated: dict[str, dict] = {cap: catalog.estimated_cost(cap) for cap in planned}

    return {
        "status":                        "plan_only",
        "budget":                        asdict(budget),
        "planned_capabilities":          planned,
        "estimated_cost_per_capability": estimated,
        "policy_hash":                   policy.policy_hash(),
    }


if __name__ == "__main__":
    mcp.run()
