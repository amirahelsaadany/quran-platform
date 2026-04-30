# 🚀 دليل النشر على Railway — خطوة بخطوة

## المتطلبات
- حساب GitHub (مجاني) → https://github.com
- حساب Railway (مجاني) → https://railway.app

---

## الخطوة 1 — رفع المشروع على GitHub

### افتح PowerShell في مجلد المشروع وشغّل:

```powershell
git init
git add .
git commit -m "first commit"
```

### أنشئ مستودعاً جديداً على GitHub:
1. افتح https://github.com/new
2. اكتب اسم المستودع مثلاً: `quran-platform`
3. اجعله **Private** (خاص)
4. اضغط **Create repository**

### ارفع الكود:
```powershell
git remote add origin https://github.com/USERNAME/quran-platform.git
git branch -M main
git push -u origin main
```
> استبدل USERNAME باسم مستخدمك على GitHub

---

## الخطوة 2 — إنشاء مشروع على Railway

1. افتح https://railway.app
2. سجّل دخول بحساب GitHub
3. اضغط **New Project**
4. اختر **Deploy from GitHub repo**
5. اختر مستودع `quran-platform`
6. سيبدأ البناء تلقائياً ✅

---

## الخطوة 3 — إضافة قاعدة بيانات PostgreSQL

1. في لوحة Railway، اضغط **+ New**
2. اختر **Database → Add PostgreSQL**
3. انتظر دقيقة حتى تنشأ قاعدة البيانات ✅

---

## الخطوة 4 — ربط المتغيرات

1. اضغط على خدمة المنصة (ليس قاعدة البيانات)
2. اذهب لـ **Variables**
3. اضغط **+ New Variable** وأضف:

| المتغير | القيمة |
|---------|--------|
| `SECRET_KEY` | أي نص عشوائي طويل مثل: `my-super-secret-key-12345-quran` |
| `DATABASE_URL` | انسخها من قاعدة البيانات تلقائياً (انظر أدناه) |

### كيف تنسخ DATABASE_URL:
1. اضغط على خدمة PostgreSQL
2. اضغط **Connect**
3. انسخ قيمة **DATABASE_URL**
4. الصقها في متغيرات خدمة المنصة

---

## الخطوة 5 — الحصول على الرابط

1. اضغط على خدمة المنصة
2. اضغط **Settings**
3. تحت **Domains** اضغط **Generate Domain**
4. ستحصل على رابط مثل: `https://quran-platform-production.up.railway.app` 🎉

---

## ✅ بيانات الدخول بعد النشر

| الدور | البريد | كلمة المرور |
|-------|--------|-------------|
| 👳 شيخ | sheikh@quran.com | sheikh123 |
| 👤 طالب | أنشئ حساباً جديداً | — |

> **مهم:** غيّر كلمة مرور الشيخ من لوحة التحكم بعد أول دخول!

---

## 🔄 كيف ترفع تحديثات لاحقة

```powershell
git add .
git commit -m "وصف التغيير"
git push
```
Railway سيعيد النشر تلقائياً خلال دقيقة ✅

---

## ❓ مشاكل شائعة

**المشروع لا يعمل بعد النشر:**
- تحقق من **Logs** في Railway
- تأكد أن DATABASE_URL مضبوطة صح

**الصور لا تظهر بعد إعادة النشر:**
- Railway لا يحفظ الملفات المرفوعة بين عمليات النشر
- الحل: استخدم **Cloudinary** لحفظ الصور (مجاني) — راجع README

**خطأ 500:**
- افتح Logs في Railway وابحث عن السطر الأحمر
