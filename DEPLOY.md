# 🚀 دليل النشر على Railway — خطوة بخطوة (نسخة Firebase)

## المتطلبات
- حساب GitHub (مجاني) → https://github.com
- حساب Railway (مجاني) → https://railway.app
- مشروع Firebase مع Firestore مفعّل (راجع FIREBASE_SETUP.md للتفاصيل الكاملة)

---

## الخطوة 1 — رفع المشروع على GitHub

```powershell
git init
git add .
git commit -m "first commit"
```

ثم على GitHub:
1. افتح https://github.com/new
2. اكتب اسم المستودع مثلاً: `quran-platform`
3. اجعله **Private** (خاص) — مهم لأن ملفات الاعتماد لا تُرفع لكنه أفضل احتياطاً
4. اضغط **Create repository**

```powershell
git remote add origin https://github.com/USERNAME/quran-platform.git
git branch -M main
git push -u origin main
```

---

## الخطوة 2 — إنشاء مشروع على Railway

1. افتح https://railway.app
2. سجّل دخول بحساب GitHub
3. اضغط **New Project → Deploy from GitHub repo**
4. اختر مستودع `quran-platform`
5. سيبدأ البناء تلقائياً ✅ (لا حاجة لإضافة خدمة PostgreSQL بعد الآن)

---

## الخطوة 3 — ربط Firebase

1. من Firebase Console → Project settings → Service accounts → **Generate new private key**
2. افتح الملف الذي نزل وانسخ **محتواه بالكامل**
3. في Railway، اضغط على خدمة المنصة → **Variables** → أضف:

| المتغير | القيمة |
|---------|--------|
| `SECRET_KEY` | نص عشوائي طويل مثل: `my-super-secret-key-12345-quran` |
| `FIREBASE_CREDENTIALS_JSON` | الصق محتوى ملف JSON بالكامل هنا |

> لا حاجة لمتغير `DATABASE_URL` بعد الآن.

---

## الخطوة 4 — الحصول على الرابط

1. اضغط على خدمة المنصة → **Settings**
2. تحت **Domains** اضغط **Generate Domain**
3. ستحصل على رابط مثل: `https://quran-platform-production.up.railway.app` 🎉

---

## الخطوة 5 — ترحيل بياناتك القديمة (إن وُجدت)

إذا كان لديك بيانات سابقة في `quran_platform.db`، شغّل الترحيل **مرة واحدة فقط** قبل أو بعد أول نشر:

```bash
python migrate_to_firestore.py
```

راجع تفاصيل الترحيل والنشر السحابي في `FIREBASE_SETUP.md`.

---

## ✅ بيانات الدخول الافتراضية (إن لم تُرحّل بيانات قديمة)

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
Railway سيعيد النشر تلقائياً خلال دقيقة ✅ (بياناتك في Firestore تبقى كما هي، لا تتأثر بإعادة النشر)

---

## ❓ مشاكل شائعة

**المشروع لا يعمل بعد النشر:**
- تحقق من **Logs** في Railway
- تأكد أن `FIREBASE_CREDENTIALS_JSON` تم لصقه بالكامل وبصيغة JSON صحيحة (يبدأ بـ `{` وينتهي بـ `}`)

**الصور لا تظهر بعد إعادة النشر:**
- Railway لا يحفظ الملفات المرفوعة بين عمليات النشر (هذا لم يتغيّر، غير متعلق بـ Firebase)
- الحل: استخدم **Cloudinary** أو **Firebase Storage** لحفظ الصور بشكل دائم

**خطأ 500 متعلق بـ Firebase:**
- افتح Logs في Railway وابحث عن رسالة `firebase_admin` أو `google.auth`
- تأكد أن Firestore مفعّل في مشروعك على Firebase Console (وليس Realtime Database فقط)
