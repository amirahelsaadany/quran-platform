# 🕌 منصة نور القرآن — دليل التشغيل والنشر (نسخة Firebase)

## نظرة عامة على المنصة
منصة متكاملة لتعليم القرآن الكريم تشمل:
- **الصفحة الرئيسية**: واجهة تسويقية احترافية
- **لوحة الشيخ**: رفع المحاضرات، إدارة الكورسات، الجلسات المباشرة، الإعلانات، متابعة الطلاب
- **لوحة الطالب**: متابعة الكورسات، مشاهدة الفيديوهات، تتبع التقدم
- **قاعدة البيانات**: **Firebase Firestore** (سحابية، بدون إعداد سيرفر قاعدة بيانات)
- **PWA**: يمكن تثبيت المنصة كتطبيق على الجوال/الكمبيوتر/الآيباد من المتصفح مباشرة

> 🔄 كانت المنصة تعمل سابقاً بـ SQLite/PostgreSQL عبر SQLAlchemy، وتم تحويلها بالكامل
> إلى Firebase Firestore دون أي تغيير في التصميم أو الروابط أو تجربة الاستخدام.
> راجع `FIREBASE_SETUP.md` لتفاصيل الربط والترحيل.

---

## 🚀 تشغيل المشروع محلياً (على جهازك)

### المتطلبات
- Python 3.10 أو أحدث
- pip
- مشروع Firebase مع Firestore مفعّل + ملف بيانات اعتماد (service account)

### خطوات التشغيل
```bash
# 1. فك ضغط المجلد وادخل إليه
cd quran-platform

# 2. تثبيت المكتبات
pip install -r requirements.txt

# 3. ضع ملف بيانات اعتماد Firebase باسم firebase-credentials.json في جذر المشروع
#    (راجع FIREBASE_SETUP.md لكيفية الحصول عليه)

# 4. (مرة واحدة فقط) إذا كان لديك بيانات قديمة في quran_platform.db، رحّلها:
python migrate_to_firestore.py

# 5. تشغيل المشروع
python app.py
```

### افتح المتصفح على:
```
http://localhost:5000
```

### بيانات الدخول التجريبية
| الدور   | البريد            | كلمة المرور |
|---------|-------------------|-------------|
| شيخ     | sheikh@quran.com  | sheikh123   |
| طالب    | سجّل حساب جديد    | —           |

---

## 🌐 النشر على الإنترنت

راجع `DEPLOY.md` للتفاصيل الكاملة خطوة بخطوة. ملخص سريع:

### Railway (الأسهل — مجاني)
1. ارفع المشروع على GitHub
2. Railway → New Project → Deploy from GitHub repo
3. أضف متغيرات البيئة:
   - `SECRET_KEY`
   - `FIREBASE_CREDENTIALS_JSON` (محتوى ملف service account كاملاً)
4. Deploy

### VPS (Hostinger / DigitalOcean)
```bash
git clone https://github.com/USERNAME/quran-platform.git
cd quran-platform
pip install -r requirements.txt

export FIREBASE_CREDENTIALS_PATH=/path/to/firebase-credentials.json
export SECRET_KEY=your-secret-key

gunicorn app:app --bind 0.0.0.0:8000 --workers 2 --daemon
```

Nginx (اختياري للدومين):
```nginx
server {
    listen 80;
    server_name yourdomain.com;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    client_max_body_size 500M;
}
```

---

## 📁 هيكل المشروع

```
quran-platform/
├── app.py                    ← الخادم الرئيسي (Flask + Firebase Firestore)
├── migrate_to_firestore.py   ← سكربت ترحيل بيانات SQLite القديمة إلى Firestore
├── requirements.txt          ← المكتبات المطلوبة
├── firebase-credentials.json ← ملف اعتماد Firebase (لا يُرفع على GitHub)
├── Procfile                  ← للنشر على Railway/Heroku
├── FIREBASE_SETUP.md         ← دليل ربط Firebase بالتفصيل
├── DEPLOY.md                 ← دليل النشر على Railway
├── templates/
│   ├── base.html             ← القالب الأساسي المشترك (+ PWA manifest/service worker)
│   ├── auth/
│   │   ├── login.html
│   │   └── register.html
│   ├── public/
│   │   ├── index.html
│   │   ├── courses.html
│   │   └── course_detail.html
│   ├── sheikh/
│   │   ├── dashboard.html
│   │   ├── courses.html
│   │   ├── course_form.html
│   │   ├── course_edit.html
│   │   ├── live.html
│   │   ├── announcements.html
│   │   ├── students.html
│   │   └── profile.html
│   └── student/
│       ├── dashboard.html
│       ├── learn.html
│       └── profile.html
└── static/
    ├── manifest.json          ← ملف PWA (تثبيت المنصة كتطبيق)
    ├── sw.js                  ← Service Worker بسيط
    ├── icons/                 ← أيقونات PWA
    └── uploads/
        ├── videos/
        ├── thumbnails/
        ├── materials/
        └── avatars/
```

---

## ⚙️ المتغيرات البيئية المهمة

```env
SECRET_KEY=your-very-secret-key-here-change-this

# طريقة 1 (مفضّلة للنشر السحابي): محتوى ملف service account كاملاً كـ JSON
FIREBASE_CREDENTIALS_JSON={"type": "service_account", ...}

# طريقة 2 (مفيدة على VPS): مسار الملف على القرص
FIREBASE_CREDENTIALS_PATH=/path/to/firebase-credentials.json
```

---

## 🔧 إضافة شيخ جديد

```python
from app import app, User

with app.app_context():
    user = User.first_by(email='example@email.com')
    user.role = 'sheikh'
    user.save()
    print("تم التحويل بنجاح")
```

---

## 🎯 المزايا الجاهزة

✅ تسجيل دخول وإنشاء حساب
✅ رفع فيديوهات (محلياً)
✅ دعم روابط YouTube/خارجية
✅ رفع مرفقات PDF
✅ نظام التقدم والإكمال
✅ قبول/رفض تسجيل الطلاب
✅ جدولة الجلسات المباشرة
✅ نشر الإعلانات
✅ لوحة إحصائيات
✅ تصفية الكورسات
✅ قاعدة بيانات سحابية بالكامل عبر Firebase Firestore
✅ قابلة للتثبيت كتطبيق على أي جهاز (PWA)

---

**تطوير: منصة نور القرآن © 1446 هـ**
