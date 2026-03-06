# Nexus Intelligence Runtime (v0.1.0)

**Local-First · Budget-Aware · Evidence-Ledger · Policy-Gated · Defensive Only**

> "أفضل ذكاء لكل 200MB RAM" — لا OSINT هجومي، لا تتبع أفراد، بياناتك فقط.

---

## الملفات

| الملف / المجلد | الوصف |
|---|---|
| `server.py` | **محرك الاستخبارات** — خادم MCP كامل (Budget Planner + Evidence Ledger + Policy Gate) |
| `NUCLEAR_SPEC.md` | المواصفة المعمارية الكاملة |
| `config/policy.yaml` | سياسة الأمان والقائمة البيضاء |
| `config/budget.yaml` | ميزانيات الموارد الافتراضية |
| `catalog/capabilities.yaml` | كتالوج القدرات مع تكاليفها المقدرة |
| `wit/nexus-capability.wit` | عقد WASM Component Model (WIT) |
| `db/schema.sql` | مخطط SQLite لسجل الأدلة |
| `requirements.txt` | متطلبات Python |
| `bootstrap/omni-bootstrap.ps1` | سكربت إعداد workspace (Windows) |

---

## التشغيل السريع

```bash
# 1. تثبيت المتطلبات
pip install -r requirements.txt

# 2. تشغيل خادم MCP
python server.py
```

---

## أدوات MCP المتاحة

| الأداة | الوصف |
|---|---|
| `run_intelligence` | تشغيل محرك الاستخبارات الدفاعي ضمن ميزانية محددة |
| `budget_plan` | معاينة خطة التنفيذ قبل البدء (بدون تنفيذ فعلي) |
| `list_runs` | استعراض آخر التشغيلات من السجل |
| `get_evidence` | استرجاع سجلات الأدلة الموقّعة لتشغيل معين |
| `replay_run` | إعادة استعراض تشغيل كامل للتدقيق والمقارنة |
| `check_policy` | عرض السياسة الأمنية الحالية وبصمتها |
| `list_capabilities` | عرض القدرات المتاحة مع تكاليفها |

---

## المعمارية

```
MCP Client (VS Code / Claude Desktop)
    │
    ▼
┌─────────────────────────────────────┐
│      Nexus Intelligence Runtime     │
│                                     │
│  run_intelligence()                 │
│      │                              │
│      ├─► Policy Gate  (allowlist)   │
│      ├─► Budget Planner (greedy)    │
│      ├─► Capability Scheduler       │
│      │       ├── inventory_repo     │
│      │       └── scan_configs       │
│      └─► Evidence Ledger (SQLite)   │
└─────────────────────────────────────┘
```

## متغيرات البيئة

| المتغير | الافتراضي | الوصف |
|---|---|---|
| `NEXUS_DB` | `nexus_evidence.db` | مسار قاعدة بيانات SQLite |
| `NEXUS_POLICY` | `config/policy.yaml` | مسار ملف السياسة |
| `NEXUS_CATALOG` | `catalog/capabilities.yaml` | مسار كتالوج القدرات |
| `NEXUS_BUDGET` | `config/budget.yaml` | مسار ملف الميزانية |

---

راجع `NUCLEAR_SPEC.md` للمواصفة الكاملة و`SAVE_GUIDE.md` لطريقة الحفظ.
