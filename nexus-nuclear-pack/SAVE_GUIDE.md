# SAVE_GUIDE — طريقة الحفظ والتشغيل

## 1) أسهل طريقة (موصى بها): تنزيل الباك ثم فك الضغط
1) نزّل ملف الـ ZIP (الرابط الذي أعطيتك إياه)
2) فك الضغط
3) افتح المجلد في VS Code:
   - File → Open Folder
   - أو افتح ملف workspace: `nexus-nuclear.code-workspace`

## 2) طريقة يدوية (بدون ZIP)
إذا تريد تحفظ يدويًا:
1) أنشئ مجلد: `nexus-nuclear-pack`
2) أنشئ نفس هيكل المجلدات الموجود في الشجرة أدناه
3) انسخ محتوى كل ملف (سأعطيك المحتوى داخل الملفات في هذا الباك)

## 3) تشغيل سكربت bootstrap (Windows)
داخل PowerShell داخل المجلد:
```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
.\bootstrap\omni-bootstrap.ps1
```

## 4) على كالي/لينكس
هذا الباك مجرد مواصفة/هيكل، وليس فيه binary جاهز.
بعدها تقدر تبني runtime حسب لغة اختيارك (Rust/Go) وتربطه بالـ VS Code UI.

## شجرة الملفات
```
nexus-nuclear-pack/
  NUCLEAR_SPEC.md
  README.md
  SAVE_GUIDE.md
  config/
    budget.yaml
    policy.yaml
  catalog/
    capabilities.yaml
  wit/
    nexus-capability.wit
  db/
    schema.sql
  bootstrap/
    omni-bootstrap.ps1
  .vscode/
    settings.json
    tasks.json
  nexus-nuclear.code-workspace
```
