# 🕌 منصة نور القرآن — دليل التشغيل والنشر

## نظرة عامة على المنصة
منصة متكاملة لتعليم القرآن الكريم تشمل:
- **الصفحة الرئيسية**: واجهة تسويقية احترافية
- **لوحة الشيخ**: رفع المحاضرات، إدارة الكورسات، الجلسات المباشرة، الإعلانات، متابعة الطلاب
- **لوحة الطالب**: متابعة الكورسات، مشاهدة الفيديوهات، تتبع التقدم
- **قاعدة البيانات**: SQLite مدمجة لا تحتاج إعداد

---

## 🚀 تشغيل المشروع محلياً (على جهازك)

### المتطلبات
- Python 3.10 أو أحدث
- pip

### خطوات التشغيل
```bash
# 1. فك ضغط المجلد وادخل إليه
cd quran-platform

# 2. تثبيت المكتبات
pip install -r requirements.txt

# 3. تشغيل المشروع
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

### الخيار 1: Railway (الأسهل — مجاني)

1. سجّل في [railway.app](https://railway.app)
2. اضغط **New Project → Deploy from GitHub**
3. ارفع المشروع على GitHub أولاً:
   ```bash
   git init
   git add .
   git commit -m "initial commit"
   git remote add origin https://github.com/USERNAME/quran-platform.git
   git push -u origin main
   ```
4. في Railway: اختر الـ repo → سيتعرف تلقائياً على Python
5. أضف متغير البيئة:
   - `SECRET_KEY` = أي نص عشوائي طويل
6. اضغط **Deploy** — ستحصل على رابط مثل: `https://quran-platform.up.railway.app`

---

### الخيار 2: Render (مجاني)

1. سجّل في [render.com](https://render.com)
2. **New → Web Service → Connect GitHub**
3. الإعدادات:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
4. أضف متغير البيئة `SECRET_KEY`
5. اضغط **Create Web Service**

---

### الخيار 3: VPS (Hostinger / DigitalOcean)

```bash
# على السيرفر
git clone https://github.com/USERNAME/quran-platform.git
cd quran-platform
pip install -r requirements.txt

# تشغيل مع gunicorn
gunicorn app:app --bind 0.0.0.0:8000 --workers 2 --daemon

# إعداد Nginx (اختياري للدومين)
# /etc/nginx/sites-available/quran
server {
    listen 80;
    server_name yourdomain.com;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    client_max_body_size 500M;  # للسماح برفع فيديوهات كبيرة
}
```

---

## 📁 هيكل المشروع

```
quran-platform/
├── app.py                    ← الخادم الرئيسي وقاعدة البيانات
├── requirements.txt          ← المكتبات المطلوبة
├── Procfile                  ← للنشر على Railway/Heroku
├── templates/
│   ├── base.html             ← القالب الأساسي المشترك
│   ├── auth/
│   │   ├── login.html        ← صفحة تسجيل الدخول
│   │   └── register.html     ← صفحة إنشاء حساب
│   ├── public/
│   │   ├── index.html        ← الصفحة الرئيسية
│   │   ├── courses.html      ← قائمة الكورسات
│   │   └── course_detail.html← تفاصيل الكورس
│   ├── sheikh/
│   │   ├── dashboard.html    ← لوحة تحكم الشيخ
│   │   ├── courses.html      ← إدارة الكورسات
│   │   ├── course_form.html  ← إنشاء كورس جديد
│   │   ├── course_edit.html  ← تعديل الكورس + رفع دروس
│   │   ├── live.html         ← الجلسات المباشرة
│   │   ├── announcements.html← الإعلانات
│   │   ├── students.html     ← إدارة الطلاب
│   │   └── profile.html      ← الملف الشخصي
│   └── student/
│       ├── dashboard.html    ← لوحة الطالب
│       ├── learn.html        ← مشاهدة الدروس
│       └── profile.html      ← الملف الشخصي
└── static/
    └── uploads/
        ├── videos/           ← الفيديوهات المرفوعة
        ├── thumbnails/       ← صور الكورسات
        ├── materials/        ← ملفات PDF والمرفقات
        └── avatars/          ← صور المستخدمين
```

---

## ⚙️ المتغيرات البيئية المهمة

```env
SECRET_KEY=your-very-secret-key-here-change-this
DATABASE_URL=sqlite:///quran_platform.db   # يمكن تغييرها لـ PostgreSQL
```

---

## 🔧 إضافة شيخ جديد

للتحويل من طالب إلى شيخ، شغّل هذا الأمر في Python:

```python
from app import app, db, User
with app.app_context():
    user = User.query.filter_by(email='example@email.com').first()
    user.role = 'sheikh'
    db.session.commit()
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

---

**تطوير: منصة نور القرآن © 1446 هـ**
