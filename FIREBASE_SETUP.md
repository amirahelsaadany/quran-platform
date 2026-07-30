# 🔥 دليل ربط المنصة بـ Firebase (Firestore)

تم تحويل قاعدة بيانات منصة "نور القرآن" بالكامل من SQLite/PostgreSQL إلى **Firebase Firestore**.
كل الشيفرة والتصميم بقيا كما هما — التغيير الوحيد هو مكان تخزين البيانات.

---

## 1) إنشاء مشروع Firebase

1. افتح https://console.firebase.google.com
2. اضغط **Add project** (إضافة مشروع) واختر اسماً مثل `quran-platform`
3. لا حاجة لتفعيل Google Analytics (اختياري)

---

## 2) تفعيل Firestore

1. من القائمة الجانبية: **Build → Firestore Database**
2. اضغط **Create database**
3. اختر **Production mode** (سنضبط الصلاحيات لاحقاً إن احتجت قواعد أمان مخصصة)
4. اختر أقرب منطقة جغرافية (مثلاً `eur3` أو `europe-west`)

> ملاحظة: التطبيق يتواصل مع Firestore عبر **Firebase Admin SDK** من السيرفر (Python)،
> وليس من المتصفح مباشرة، فلا حاجة لضبط قواعد أمان (Security Rules) معقّدة — الوصول محمي بمفتاح الخدمة (service account).

---

## 3) الحصول على ملف بيانات اعتماد الخدمة (Service Account)

1. من إعدادات المشروع (⚙️ Project settings) → تبويب **Service accounts**
2. اضغط **Generate new private key**
3. سيتم تحميل ملف JSON — **احتفظ به بأمان ولا ترفعه على GitHub أبداً**

---

## 4) تشغيل المنصة محلياً

1. ضع الملف الذي حمّلته في مجلد المشروع باسم:
   ```
   firebase-credentials.json
   ```
   (هذا الاسم مضاف تلقائياً إلى `.gitignore` كي لا يُرفع بالخطأ)

2. ثبّت المكتبات:
   ```bash
   pip install -r requirements.txt
   ```

3. **رحّل بياناتك القديمة من SQLite إلى Firestore** (مرة واحدة فقط):
   ```bash
   python migrate_to_firestore.py
   ```
   سيقوم السكربت بترحيل كل المستخدمين والكورسات والدروس والإعلانات... إلخ،
   مع الحفاظ على نفس الأرقام التعريفية (IDs) والعلاقات بينها.

4. شغّل المنصة:
   ```bash
   python app.py
   ```

---

## 5) النشر على Railway / Render

نفس الملف JSON يُستخدم في البيئة السحابية، لكن بدلاً من رفعه كملف، نضعه كمتغير بيئة:

1. افتح ملف `firebase-credentials.json` وانسخ **كل محتواه** (JSON كامل)
2. في لوحة Railway → **Variables** → أضف متغيراً جديداً:

   | المتغير | القيمة |
   |---------|--------|
   | `FIREBASE_CREDENTIALS_JSON` | (الصق محتوى ملف JSON كاملاً هنا) |
   | `SECRET_KEY` | نص عشوائي طويل |

3. لا حاجة لأي متغير `DATABASE_URL` بعد الآن، ولا لخدمة PostgreSQL — يمكنك حذفها من مشروع Railway إن كانت موجودة.
4. ثم اضغط **Deploy** كالمعتاد.

> بالإضافة إلى `FIREBASE_CREDENTIALS_JSON`، يدعم التطبيق أيضاً:
> - `FIREBASE_CREDENTIALS_PATH`: مسار ملف على القرص (مفيد على VPS)
> - أو الاعتماد التلقائي على `GOOGLE_APPLICATION_CREDENTIALS` إن كنت تستخدم بيئة Google Cloud

---

## 6) تشغيل الترحيل على نفس بيئة Railway (اختياري)

إن كان ملف `quran_platform.db` القديم موجوداً فقط على السيرفر البعيد، ارفعه ضمن المشروع مؤقتاً،
ثم من "Railway CLI" أو من تبويب Shell:
```bash
python migrate_to_firestore.py
```
بعد نجاح الترحيل، يمكنك حذف ملف `quran_platform.db` نهائياً من المستودع.

---

## ✅ ملخص التغييرات

| قبل | بعد |
|-----|-----|
| SQLite / PostgreSQL (SQLAlchemy) | Firebase Firestore (firebase-admin) |
| `DATABASE_URL` | `FIREBASE_CREDENTIALS_JSON` |
| `quran_platform.db` | مجموعات Firestore: `users, courses, teachers, lessons, materials, enrollments, progress, live_sessions, announcements` |
| ملفات الصور/الفيديو | لا تغيير — تبقى محفوظة محلياً في `static/uploads/` كما كانت |

التصميم، القوالب (HTML)، الروابط (routes)، وكل تجربة الاستخدام **لم تتغير أبداً** — فقط طبقة قاعدة البيانات في الخلفية.
