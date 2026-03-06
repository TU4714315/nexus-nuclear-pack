# NEXUS-RUNTIME (v0.1) — ملف المواصفة “شبه نووي”
**Local‑First / Budget‑Aware / WASM‑Plugin Intelligence Runtime — VS Code Native**

## 0) الملخص التنفيذي
أنت لا تبني “أداة OSINT”.
أنت تبني **Runtime** محلي يحقق:
- تشغيل تلقائي داخل VS Code
- استهلاك موارد منخفض جدًا
- أداء ثابت وقابل للقياس
- قابليّة إعادة التشغيل (Replay) والتدقيق (Audit)
- Plugins آمنة وخفيفة عبر WebAssembly Component Model + WIT
- تخزين Evidence محلي بملف واحد (SQLite) + تحليلات داخل العملية (DuckDB in‑process)
- تخطيط “Budget‑Aware” (العقل يعمل تحت سقف موارد)

**الهوية التنافسية**:
> “أفضل ذكاء لكل 200MB RAM” بدل “أكثر أدوات”.

---

## 1) تعريف المنتج
### 1.1 ماذا نبني؟
**Binary واحد** اسمه `nexus` يعمل محليًا.
و**VS Code Extension** خفيف (UI فقط).

النظام يعمل هكذا:
- تفتح Workspace → `nexus` يبدأ تلقائيًا (Auto-start)
- المستخدم يضغط “Run” → runtime ينفّذ خطة ضمن ميزانية موارد
- يكتب Evidence في SQLite
- يبني Views وتحليلات بـ DuckDB عند الطلب (on-demand)

### 1.2 ما الذي لا نبنيه (Non‑Goals)
- لا تتبع أفراد/أرقام/حسابات أشخاص ولا OSINT هجومي.
- لا scraping واسع ولا crawling بلا تفويض.
- المنصة تستهدف: **Asset / Project / Repo / Infra owned-by-you** وبياناتك/سجلاتك.

---

## 2) قيودك (Constraints) — تُعامل كـ “قانون”
### 2.1 ميزانيات الموارد (Budget)
كل تشغيل له Budget صريح:
- RAM_MB
- CPU_CORES
- TIME_MS
- NET_CALLS
- OUTPUT_KB

### 2.2 KPI (مقاييس نجاح “تسويقية/هندسية”)
- **Cold start → أول نتيجة** (ثواني)
- **Intel per MB RAM**
- **Evidence records / minute**
- **Replay equivalence rate** (نفس المدخلات = نفس النتائج)
- **Budget adherence rate** (% التزام بالميزانية)

---

## 3) الابتكار الحقيقي (Design Differentiator)
### 3.1 Budget‑Aware Planning (موضع الابتكار)
المنافسون يبنون “Workflow ثابت” أو “Agents”.
أنت تبني:
> **Goal + Budget → Plan**

### 3.2 WASM Component Plugins
Plugins آمنة، محمولة، footprint صغير.
WIT يعرّف العقد (contract).

### 3.3 Embedded Ledger + On‑Demand Analytics
SQLite للـ ledger + DuckDB للتحليلات in‑process.

---

## 4) المعمارية (Architecture)
### 4.1 نظرة عالية المستوى
VS Code Extension (UI)
- Run / Replay / Diff
- Budget dashboard (live)
- Evidence browser

nexus (single binary)
- Budget Compiler + Planner
- Capability Scheduler
- WASM Host (Wasmtime)
- Policy Gate (Authorization + Allowlist)
- Evidence Ledger (SQLite)
- Analytics Views (DuckDB, optional)

---

## 5) نموذج البيانات (Core Data Model)
- Run
- Target
- Capability
- Provider
- EvidenceRecord
- Candidate

EvidenceRecord يجب أن يحتوي دائمًا:
- source
- timestamp
- hash
- capability + provider
- cost_used
- payload (JSON)
- references

---

## 6) Budget Compiler + Planner (قلب الابتكار)
- Cost Model لكل capability/provider
- هدف: maximize info_gain ضمن قيود الميزانية
- تنفيذ v0.1: greedy + backtracking بسيط + anytime improvement
- Partial results دائمًا (لا يوجد “فشل صامت”)

---

## 7) WASM Plugin Contract (WIT)
راجع الملف: `wit/nexus-capability.wit`

---

## 8) Policy Gate
راجع الملف: `config/policy.yaml`

---

## 9) Evidence Ledger (SQLite) + Analytics (DuckDB)
راجع الملف: `db/schema.sql`

---

## 10) VS Code Extension
الـ Extension UI فقط. التشغيل الحقيقي داخل binary `nexus`.

---

## 11) One‑File Bootstrap
راجع الملف: `bootstrap/omni-bootstrap.ps1`

---

## 12) Roadmap مختصر
v0.1:
- runtime skeleton + sqlite ledger
- wasm host + limiter
- 2–3 capabilities دفاعية (repo inventory / config scan / sbom parse)
- VS Code basic panel

v0.2:
- planner smarter
- plugin registry offline
- replay/diff stable

---

**نهاية الملف**
