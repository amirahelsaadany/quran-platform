from flask import Flask, render_template, redirect, url_for, request, flash, session, send_from_directory, jsonify, abort
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os, uuid, json

import firebase_admin
from firebase_admin import credentials, firestore

import cloudinary
import cloudinary.uploader
import cloudinary.api

app = Flask(__name__)

# ─── Secret Key ───────────────────────────────────────────
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'quran-platform-secret-key-2024-change-in-production')

# ─── Firebase / Firestore ──────────────────────────────────
# ثلاث طرق لتوفير بيانات اعتماد Firebase (بالأولوية):
# 1) متغير بيئة FIREBASE_CREDENTIALS_JSON يحتوي محتوى ملف service-account كـ JSON كامل (مستخدم في Railway/Render)
# 2) متغير بيئة FIREBASE_CREDENTIALS_PATH يشير إلى مسار ملف service account على القرص
# 3) ملف firebase-credentials.json في مجلد المشروع (للتشغيل المحلي)
def _init_firebase():
    if firebase_admin._apps:
        return firestore.client()

    cred = None
    raw_json = os.environ.get('FIREBASE_CREDENTIALS_JSON')
    cred_path = os.environ.get('FIREBASE_CREDENTIALS_PATH')
    local_default = os.path.join(os.path.dirname(__file__), 'firebase-credentials.json')

    if raw_json:
        cred = credentials.Certificate(json.loads(raw_json))
    elif cred_path and os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
    elif os.path.exists(local_default):
        cred = credentials.Certificate(local_default)
    else:
        cred = credentials.ApplicationDefault()

    firebase_admin.initialize_app(cred)
    return firestore.client()

fdb = _init_firebase()

# ─── Cloudinary Configuration ─────────────────────────────
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME', ''),
    api_key=os.environ.get('CLOUDINARY_API_KEY', ''),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET', ''),
    secure=True
)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ─── Uploads (تبقى محلية على القرص كما كانت) ──────────────
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB

ALLOWED_VIDEO = {'mp4', 'webm', 'mkv', 'avi', 'mov'}
ALLOWED_IMG = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
ALLOWED_FILE = {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'txt', 'zip'}


# ─── Firestore ID counters (للحفاظ على أرقام تسلسلية تشبه SQL) ───
def next_id(collection_name):
    """يولّد رقماً تسلسلياً (مثل auto-increment في SQL) محفوظاً في counters/{collection}"""
    counter_ref = fdb.collection('counters').document(collection_name)

    @firestore.transactional
    def _txn(transaction):
        snap = counter_ref.get(transaction=transaction)
        current = (snap.get('value') if snap.exists else 0) or 0
        current += 1
        transaction.set(counter_ref, {'value': current})
        return current

    return _txn(fdb.transaction())


def _bump_counter_if_needed(collection_name, doc_id):
    """يُستخدم عند إدخال مستند بمعرّف محدد مسبقاً (كما في سكربت الترحيل) للحفاظ على تناسق العداد"""
    try:
        n = int(doc_id)
    except (TypeError, ValueError):
        return
    counter_ref = fdb.collection('counters').document(collection_name)
    snap = counter_ref.get()
    current = (snap.get('value') if snap.exists else 0) or 0
    if n > current:
        counter_ref.set({'value': n})


# ─── طبقة نموذج بسيطة فوق Firestore (تُبقي شكل الكود قريباً من SQLAlchemy) ───
class FirestoreModel:
    collection_name = None
    defaults = {}

    def __init__(self, id=None, **data):
        self.id = id
        merged = dict(self.defaults)
        merged.update(data)
        for k, v in merged.items():
            setattr(self, k, v)

    @classmethod
    def _col(cls):
        return fdb.collection(cls.collection_name)

    @classmethod
    def get(cls, id):
        if id is None:
            return None
        doc = cls._col().document(str(id)).get()
        if not doc.exists:
            return None
        return cls(id=doc.id, **doc.to_dict())

    @classmethod
    def get_or_404(cls, id):
        obj = cls.get(id)
        if obj is None:
            abort(404)
        return obj

    @classmethod
    def all(cls):
        return [cls(id=d.id, **d.to_dict()) for d in cls._col().stream()]

    @classmethod
    def filter_by(cls, **kwargs):
        q = cls._col()
        for k, v in kwargs.items():
            q = q.where(k, '==', v)
        return [cls(id=d.id, **d.to_dict()) for d in q.stream()]

    @classmethod
    def first_by(cls, **kwargs):
        results = cls.filter_by(**kwargs)
        return results[0] if results else None

    @classmethod
    def count_by(cls, **kwargs):
        return len(cls.filter_by(**kwargs)) if kwargs else len(cls.all())

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if k != 'id'}

    def save(self):
        data = self.to_dict()
        if self.id is None:
            new_id = str(next_id(self.collection_name))
            self._col().document(new_id).set(data)
            self.id = new_id
        else:
            self._col().document(str(self.id)).set(data, merge=False)
        return self

    def delete(self):
        if self.id is not None:
            self._col().document(str(self.id)).delete()


class User(UserMixin, FirestoreModel):
    collection_name = 'users'
    defaults = dict(
        name='', email='', password='', role='student', avatar='', bio='',
        phone='', whatsapp='', telegram='', hero_photo='', country='',
        created_at=None, is_active_account=True,
        bank_account='', bank_name='', wallet_vodafone='', wallet_instapay='',
        wallet_stcpay='', wallet_other='', payment_notes='', teacher_id=None
    )


class Course(FirestoreModel):
    collection_name = 'courses'
    defaults = dict(
        title='', description='', thumbnail='', level='مبتدئ', category='تجويد',
        price=0.0, is_free=False, is_published=False, created_at=None, sheikh_id=None,
        created_by=None
    )

    @property
    def sheikh(self):
        return User.get(self.sheikh_id)

    @property
    def author(self):
        return User.get(self.created_by) if self.created_by else None

    @property
    def lessons(self):
        items = Lesson.filter_by(course_id=self.id)
        items.sort(key=lambda l: (l.order_num or 0))
        return items

    @property
    def enrollments(self):
        return Enrollment.filter_by(course_id=self.id)


class Teacher(FirestoreModel):
    collection_name = 'teachers'
    defaults = dict(
        name='', specialty='', bio='', image='', phone='', email='',
        sheikh_id=None, can_upload_lessons=False, created_at=None, user_id=None
    )

    @property
    def user(self):
        return User.get(self.user_id) if self.user_id else None


class Lesson(FirestoreModel):
    collection_name = 'lessons'
    defaults = dict(
        title='', description='', video_path='', video_url='', thumbnail='',
        duration='', order_num=0, is_free_preview=False, course_id=None,
        created_at=None, is_live=False, live_link=''
    )

    @property
    def materials(self):
        return Material.filter_by(lesson_id=self.id)


class Material(FirestoreModel):
    collection_name = 'materials'
    defaults = dict(title='', file_path='', file_type='pdf', lesson_id=None)


class Enrollment(FirestoreModel):
    collection_name = 'enrollments'
    defaults = dict(student_id=None, course_id=None, enrolled_at=None, is_approved=True)

    @property
    def student(self):
        return User.get(self.student_id)

    @property
    def course(self):
        return Course.get(self.course_id)


class Progress(FirestoreModel):
    collection_name = 'progress'
    defaults = dict(student_id=None, lesson_id=None, completed=False, watched_at=None)


class LiveSession(FirestoreModel):
    collection_name = 'live_sessions'
    defaults = dict(
        title='', description='', meeting_link='', scheduled_at=None,
        duration_minutes=60, is_active=True, sheikh_id=None,
        max_students=50, created_at=None
    )

    @property
    def sheikh(self):
        return User.get(self.sheikh_id)


class Announcement(FirestoreModel):
    collection_name = 'announcements'
    defaults = dict(title='', content='', image='', sheikh_id=None, created_at=None)

    @property
    def sheikh(self):
        return User.get(self.sheikh_id)


# ─── Helpers ──────────────────────────────────────────────
@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)


def allowed_file(filename, allowed):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


def save_file(file, subfolder):
    """يرفع الملف إلى Cloudinary ويرجع الرابط المباشر"""
    ext = file.filename.rsplit('.', 1)[1].lower()
    fname = f"{uuid.uuid4().hex}.{ext}"

    # Determine resource_type
    if ext in ALLOWED_VIDEO:
        resource_type = 'video'
    elif ext in ALLOWED_IMG:
        resource_type = 'image'
    else:
        resource_type = 'raw'

    file.seek(0)
    result = cloudinary.uploader.upload(
        file,
        public_id=f"quran_platform/{subfolder}/{fname}",
        resource_type=resource_type,
        folder=f"quran_platform/{subfolder}",
        overwrite=True
    )
    return result.get('secure_url', '')
def get_enrollment(course_id):
    if not current_user.is_authenticated:
        return None
    return Enrollment.first_by(student_id=current_user.id, course_id=str(course_id))


def get_progress_pct(course_id, student_id):
    lessons = Lesson.filter_by(course_id=str(course_id))
    if not lessons:
        return 0
    lesson_ids = {l.id for l in lessons}
    done = 0
    for p in Progress.filter_by(student_id=str(student_id), completed=True):
        if p.lesson_id in lesson_ids:
            done += 1
    return round((done / len(lessons)) * 100)


app.jinja_env.globals['get_enrollment'] = get_enrollment
app.jinja_env.globals['get_progress_pct'] = get_progress_pct


def get_teacher_profile(user):
    """يرجع بطاقة المعلم (Teacher) المرتبطة بحساب دخول المعلم الحالي، أو None"""
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    if user.role != 'teacher' or not user.teacher_id:
        return None
    return Teacher.get(user.teacher_id)


def can_manage_course_lessons(user, course):
    """يتحقق هل المستخدم الحالي (شيخ صاحب الكورس أو معلم مصرّح له) يقدر يدير دروس هذا الكورس"""
    if not course:
        return False
    if str(course.sheikh_id) == str(user.id):
        return True
    teacher = get_teacher_profile(user)
    if teacher and teacher.can_upload_lessons and str(teacher.sheikh_id) == str(course.sheikh_id):
        return True
    return False

# خريطة العملات حسب البلد
CURRENCY_MAP = {
    'مصر': ('جنيه', 'EGP', 'ج.م'),
    'المملكة العربية السعودية': ('ريال سعودي', 'SAR', 'ر.س'),
    'الإمارات العربية المتحدة': ('درهم', 'AED', 'د.إ'),
    'الكويت': ('دينار كويتي', 'KWD', 'د.ك'),
    'البحرين': ('دينار بحريني', 'BHD', 'د.ب'),
    'قطر': ('ريال قطري', 'QAR', 'ر.ق'),
    'عُمان': ('ريال عماني', 'OMR', 'ر.ع'),
    'الأردن': ('دينار أردني', 'JOD', 'د.أ'),
    'العراق': ('دينار عراقي', 'IQD', 'د.ع'),
    'سوريا': ('ليرة سورية', 'SYP', 'ل.س'),
    'لبنان': ('ليرة لبنانية', 'LBP', 'ل.ل'),
    'ليبيا': ('دينار ليبي', 'LYD', 'د.ل'),
    'تونس': ('دينار تونسي', 'TND', 'د.ت'),
    'الجزائر': ('دينار جزائري', 'DZD', 'د.ج'),
    'المغرب': ('درهم مغربي', 'MAD', 'د.م'),
    'السودان': ('جنيه سوداني', 'SDG', 'ج.س'),
    'اليمن': ('ريال يمني', 'YER', 'ر.ي'),
    'فلسطين': ('شيكل', 'ILS', '₪'),
    'موريتانيا': ('أوقية', 'MRU', 'أ.م'),
    'الصومال': ('شلن صومالي', 'SOS', 'ش.ص'),
    'جيبوتي': ('فرنك جيبوتي', 'DJF', 'ف.ج'),
    'تركيا': ('ليرة تركية', 'TRY', '₺'),
    'باكستان': ('روبية باكستانية', 'PKR', 'ر.ب'),
    'ماليزيا': ('رينغيت', 'MYR', 'RM'),
    'إندونيسيا': ('روبية', 'IDR', 'Rp'),
    'نيجيريا': ('نيرة', 'NGN', '₦'),
}


def get_currency(country):
    """إرجاع الرمز المختصر للعملة حسب البلد"""
    if country and country in CURRENCY_MAP:
        return CURRENCY_MAP[country][2]
    return 'جنيه'


app.jinja_env.globals['get_currency'] = get_currency
app.jinja_env.globals['CURRENCY_MAP'] = CURRENCY_MAP



def asset_url(path):
    """تعرض رابطاً مباشراً للملف — تدعم روابط Firebase Storage أو المسارات المحلية"""
    if not path:
        return ''
    if path.startswith('http://') or path.startswith('https://'):
        return path
    return url_for('static', filename=path)

app.jinja_env.globals['asset_url'] = asset_url

# ─── Auth Routes ──────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.first_by(email=email)
        if user and check_password_hash(user.password, password):
            login_user(user, remember=True)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        flash('البريد الإلكتروني أو كلمة المرور غير صحيحة', 'error')
    return render_template('auth/login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        country = request.form.get('country', '')
        if User.first_by(email=email):
            flash('هذا البريد الإلكتروني مسجل مسبقاً', 'error')
            return render_template('auth/register.html')
        user = User(
            name=name, email=email,
            password=generate_password_hash(password),
            country=country, role='student',
            created_at=datetime.utcnow()
        )
        user.save()
        login_user(user)
        flash('مرحباً بك! تم إنشاء حسابك بنجاح', 'success')
        return redirect(url_for('dashboard'))
    return render_template('auth/register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


# ─── Public Routes ────────────────────────────────────────
@app.route('/')
def index():
    published = Course.filter_by(is_published=True)
    published.sort(key=lambda c: c.created_at or datetime.min, reverse=True)
    courses = published[:6]

    active_sessions = LiveSession.filter_by(is_active=True)
    active_sessions.sort(key=lambda s: s.scheduled_at or datetime.min)
    live_sessions = active_sessions[:3]

    all_anns = Announcement.all()
    all_anns.sort(key=lambda a: a.created_at or datetime.min, reverse=True)
    announcements = all_anns[:3]

    sheikh = User.first_by(role='sheikh')
    teachers = Teacher.all()

    stats = {
        'students': User.count_by(role='student'),
        'courses': Course.count_by(is_published=True),
        'lessons': len(Lesson.all())
    }

    return render_template(
        'public/index.html',
        courses=courses,
        live_sessions=live_sessions,
        announcements=announcements,
        stats=stats,
        sheikh=sheikh,
        teachers=teachers,
        hero_photo=sheikh.hero_photo if sheikh else ''
    )


@app.route('/courses')
def courses_list():
    category = request.args.get('category', '')
    level = request.args.get('level', '')
    courses = Course.filter_by(is_published=True)
    if category:
        courses = [c for c in courses if c.category == category]
    if level:
        courses = [c for c in courses if c.level == level]
    courses.sort(key=lambda c: c.created_at or datetime.min, reverse=True)
    return render_template('public/courses.html', courses=courses, category=category, level=level)


@app.route('/course/<int:course_id>')
def course_detail(course_id):
    course = Course.get(course_id) or abort(404)
    if not course.is_published and (not current_user.is_authenticated or current_user.role != 'sheikh'):
        return redirect(url_for('courses_list'))
    lessons = course.lessons
    enrollment = get_enrollment(course_id)
    return render_template('public/course_detail.html', course=course, lessons=lessons, enrollment=enrollment)


@app.route('/enroll/<int:course_id>', methods=['POST'])
@login_required
def enroll(course_id):
    course = Course.get(course_id) or abort(404)
    existing = Enrollment.first_by(student_id=current_user.id, course_id=str(course_id))
    if existing:
        flash('أنت مسجل في هذا الكورس مسبقاً', 'info')
        return redirect(url_for('course_detail', course_id=course_id))
    enrollment = Enrollment(
        student_id=current_user.id, course_id=str(course_id),
        enrolled_at=datetime.utcnow(),
        is_approved=course.is_free or course.price == 0
    )
    enrollment.save()
    if course.is_free or course.price == 0:
        flash('تم التسجيل بنجاح!', 'success')
        return redirect(url_for('learn', course_id=course_id))
    else:
        flash('تم إرسال طلب التسجيل، سيتم المراجعة قريباً', 'info')
        return redirect(url_for('course_detail', course_id=course_id))


@app.route('/learn/<int:course_id>')
@app.route('/learn/<int:course_id>/lesson/<int:lesson_id>')
@login_required
def learn(course_id, lesson_id=None):
    course = Course.get(course_id) or abort(404)
    enrollment = Enrollment.first_by(student_id=current_user.id, course_id=str(course_id))
    if str(current_user.id) != str(course.sheikh_id):
        if not enrollment or not enrollment.is_approved:
            flash('يجب التسجيل في الكورس أولاً', 'error')
            return redirect(url_for('course_detail', course_id=course.id))
    lessons = course.lessons
    if not lessons:
        flash('لا توجد دروس بعد', 'info')
        return redirect(url_for('course_detail', course_id=course_id))
    current_lesson = Lesson.get(lesson_id) if lesson_id else lessons[0]
    progress_ids = [p.lesson_id for p in Progress.filter_by(student_id=current_user.id, completed=True)]
    return render_template('student/learn.html', course=course, lessons=lessons,
                           current_lesson=current_lesson, progress_ids=progress_ids)


@app.route('/mark_complete/<int:lesson_id>', methods=['POST'])
@login_required
def mark_complete(lesson_id):
    existing = Progress.first_by(student_id=current_user.id, lesson_id=str(lesson_id))
    if not existing:
        p = Progress(student_id=current_user.id, lesson_id=str(lesson_id),
                     completed=True, watched_at=datetime.utcnow())
        p.save()
    return jsonify({'success': True})


# ─── Dashboard ────────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'sheikh':
        return redirect(url_for('sheikh_dashboard'))
    if current_user.role == 'teacher':
        return redirect(url_for('teacher_dashboard'))
    return redirect(url_for('student_dashboard'))


# ─── Student Routes ───────────────────────────────────────
@app.route('/student/dashboard')
@login_required
def student_dashboard():
    enrollments = Enrollment.filter_by(student_id=current_user.id, is_approved=True)
    active_sessions = LiveSession.filter_by(is_active=True)
    active_sessions.sort(key=lambda s: s.scheduled_at or datetime.min)
    live_sessions = active_sessions
    all_anns = Announcement.all()
    all_anns.sort(key=lambda a: a.created_at or datetime.min, reverse=True)
    announcements = all_anns[:5]
    my_courses = []
    for e in enrollments:
        pct = get_progress_pct(e.course_id, current_user.id)
        my_courses.append({'course': e.course, 'progress': pct})
    return render_template('student/dashboard.html', my_courses=my_courses,
                           live_sessions=live_sessions, announcements=announcements)


@app.route('/student/profile', methods=['GET', 'POST'])
@login_required
def student_profile():
    if request.method == 'POST':
        current_user.name = request.form.get('name', current_user.name)
        current_user.phone = request.form.get('phone', current_user.phone)
        current_user.country = request.form.get('country', current_user.country)
        current_user.bio = request.form.get('bio', current_user.bio)
        if 'avatar' in request.files and request.files['avatar'].filename:
            f = request.files['avatar']
            if allowed_file(f.filename, ALLOWED_IMG):
                current_user.avatar = save_file(f, 'avatars')
        new_pw = request.form.get('new_password', '')
        if new_pw:
            current_user.password = generate_password_hash(new_pw)
        current_user.save()
        flash('تم حفظ التغييرات', 'success')
    return render_template('student/profile.html')


# ─── Sheikh Routes ────────────────────────────────────────
@app.route('/sheikh/dashboard')
@login_required
def sheikh_dashboard():
    if current_user.role != 'sheikh':
        return redirect(url_for('student_dashboard'))
    courses = Course.filter_by(sheikh_id=current_user.id)
    course_ids = [c.id for c in courses]

    total_students = 0
    total_lessons = 0
    pending = 0
    for cid in course_ids:
        c_enrollments = Enrollment.filter_by(course_id=cid)
        total_students += len(c_enrollments)
        pending += len([e for e in c_enrollments if not e.is_approved])
        total_lessons += len(Lesson.filter_by(course_id=cid))

    live_sessions = LiveSession.filter_by(sheikh_id=current_user.id)
    live_sessions.sort(key=lambda s: s.scheduled_at or datetime.min, reverse=True)
    live_sessions = live_sessions[:5]

    announcements = Announcement.filter_by(sheikh_id=current_user.id)
    announcements.sort(key=lambda a: a.created_at or datetime.min, reverse=True)
    announcements = announcements[:5]

    return render_template('sheikh/dashboard.html', courses=courses,
                           total_students=total_students, total_lessons=total_lessons,
                           live_sessions=live_sessions, announcements=announcements, pending=pending)


@app.route('/sheikh/courses')
@login_required
def sheikh_courses():
    if current_user.role != 'sheikh':
        return redirect(url_for('dashboard'))
    courses = Course.filter_by(sheikh_id=current_user.id)
    courses.sort(key=lambda c: c.created_at or datetime.min, reverse=True)
    return render_template('sheikh/courses.html', courses=courses)


@app.route('/sheikh/course/new', methods=['GET', 'POST'])
@login_required
def new_course():
    if current_user.role != 'sheikh':
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        thumb_path = ''
        if 'thumbnail' in request.files and request.files['thumbnail'].filename:
            f = request.files['thumbnail']
            if allowed_file(f.filename, ALLOWED_IMG):
                thumb_path = save_file(f, 'thumbnails')
        course = Course(
            title=request.form.get('title'),
            description=request.form.get('description', ''),
            level=request.form.get('level', 'مبتدئ'),
            category=request.form.get('category', 'تجويد'),
            price=float(request.form.get('price', 0)),
            is_free=request.form.get('is_free') == 'on',
            is_published=request.form.get('is_published') == 'on',
            thumbnail=thumb_path,
            sheikh_id=current_user.id,
            created_by=current_user.id,
            created_at=datetime.utcnow()
        )
        course.save()
        flash('تم إنشاء الكورس بنجاح', 'success')
        return redirect(url_for('sheikh_course_edit', course_id=course.id))
    return render_template('sheikh/course_form.html', course=None)


@app.route('/sheikh/course/<int:course_id>/edit', methods=['GET', 'POST'])
@login_required
def sheikh_course_edit(course_id):
    course = Course.get(course_id) or abort(404)
    if str(course.sheikh_id) != str(current_user.id):
        return redirect(url_for('sheikh_dashboard'))
    if request.method == 'POST':
        course.title = request.form.get('title', course.title)
        course.description = request.form.get('description', course.description)
        course.level = request.form.get('level', course.level)
        course.category = request.form.get('category', course.category)
        course.price = float(request.form.get('price', course.price))
        course.is_free = request.form.get('is_free') == 'on'
        course.is_published = request.form.get('is_published') == 'on'
        if 'thumbnail' in request.files and request.files['thumbnail'].filename:
            f = request.files['thumbnail']
            if allowed_file(f.filename, ALLOWED_IMG):
                course.thumbnail = save_file(f, 'thumbnails')
        course.save()
        flash('تم حفظ التغييرات', 'success')
    lessons = course.lessons
    enrollments = Enrollment.filter_by(course_id=course_id)
    return render_template('sheikh/course_edit.html', course=course, lessons=lessons, enrollments=enrollments)


@app.route('/sheikh/course/<int:course_id>/lesson/new', methods=['POST'])
@login_required
def new_lesson(course_id):
    course = Course.get(course_id) or abort(404)
    if not can_manage_course_lessons(current_user, course):
        flash('ليست لديك صلاحية رفع دروس لهذا الكورس', 'error')
        return redirect(url_for('dashboard'))
    video_path = ''
    if 'video' in request.files and request.files['video'].filename:
        f = request.files['video']
        if allowed_file(f.filename, ALLOWED_VIDEO):
            video_path = save_file(f, 'videos')
    lesson_thumb = ''
    if 'lesson_thumbnail' in request.files and request.files['lesson_thumbnail'].filename:
        f = request.files['lesson_thumbnail']
        if allowed_file(f.filename, ALLOWED_IMG):
            lesson_thumb = save_file(f, 'thumbnails')
    count = len(Lesson.filter_by(course_id=course_id))
    lesson_type = request.form.get('lesson_type')
    lesson = Lesson(
        title=request.form.get('title'),
        description=request.form.get('description', ''),
        video_path=video_path,
        video_url=request.form.get('video_url', ''),
        thumbnail=lesson_thumb,
        duration=request.form.get('duration', ''),
        order_num=count + 1,
        is_free_preview=request.form.get('is_free_preview') == 'on',
        course_id=str(course_id),
        is_live=(lesson_type == 'live'),
        live_link=request.form.get('video_url', ''),
        created_at=datetime.utcnow()
    )
    lesson.save()
    if 'material' in request.files:
        for f in request.files.getlist('material'):
            if f.filename and allowed_file(f.filename, ALLOWED_FILE):
                mat_path = save_file(f, 'materials')
                mat = Material(title=f.filename, file_path=mat_path,
                               file_type=f.filename.rsplit('.', 1)[1].lower(),
                               lesson_id=lesson.id)
                mat.save()
    flash('تمت إضافة الدرس بنجاح', 'success')
    if current_user.role == 'teacher':
        return redirect(url_for('teacher_course_lessons', course_id=course_id))
    return redirect(url_for('sheikh_course_edit', course_id=course_id))


@app.route('/sheikh/lesson/<int:lesson_id>/delete', methods=['POST'])
@login_required
def delete_lesson(lesson_id):
    lesson = Lesson.get(lesson_id) or abort(404)
    course = Course.get(lesson.course_id)
    if not can_manage_course_lessons(current_user, course):
        flash('ليست لديك صلاحية حذف دروس هذا الكورس', 'error')
        return redirect(url_for('dashboard'))
    course_id = lesson.course_id
    for mat in lesson.materials:
        mat.delete()
    for p in Progress.filter_by(lesson_id=lesson_id):
        p.delete()
    lesson.delete()
    flash('تم حذف الدرس', 'success')
    if current_user.role == 'teacher':
        return redirect(url_for('teacher_course_lessons', course_id=course_id))
    return redirect(url_for('sheikh_course_edit', course_id=course_id))


@app.route('/sheikh/course/<int:course_id>/delete', methods=['POST'])
@login_required
def delete_course(course_id):
    course = Course.get(course_id) or abort(404)
    if str(course.sheikh_id) != str(current_user.id):
        return redirect(url_for('sheikh_dashboard'))
    for lesson in course.lessons:
        for mat in lesson.materials:
            mat.delete()
        lesson.delete()
    for e in course.enrollments:
        e.delete()
    course.delete()
    flash('تم حذف الكورس', 'success')
    return redirect(url_for('sheikh_courses'))


@app.route('/sheikh/live', methods=['GET', 'POST'])
@login_required
def sheikh_live():
    if current_user.role != 'sheikh':
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'create':
            dt_str = request.form.get('scheduled_at')
            dt = datetime.strptime(dt_str, '%Y-%m-%dT%H:%M')
            ls = LiveSession(
                title=request.form.get('title'),
                description=request.form.get('description', ''),
                meeting_link=request.form.get('meeting_link', ''),
                scheduled_at=dt,
                duration_minutes=int(request.form.get('duration_minutes', 60)),
                max_students=int(request.form.get('max_students', 50)),
                sheikh_id=current_user.id,
                created_at=datetime.utcnow()
            )
            ls.save()
            flash('تم إنشاء الجلسة المباشرة', 'success')
        elif action == 'delete':
            ls_id = request.form.get('session_id')
            ls = LiveSession.get(ls_id)
            if ls and str(ls.sheikh_id) == str(current_user.id):
                ls.delete()
                flash('تم حذف الجلسة', 'success')
        elif action == 'toggle':
            ls_id = request.form.get('session_id')
            ls = LiveSession.get(ls_id)
            if ls and str(ls.sheikh_id) == str(current_user.id):
                ls.is_active = not ls.is_active
                ls.save()
    sessions = LiveSession.filter_by(sheikh_id=current_user.id)
    sessions.sort(key=lambda s: s.scheduled_at or datetime.min, reverse=True)
    return render_template('sheikh/live.html', sessions=sessions)


@app.route('/sheikh/announcements', methods=['GET', 'POST'])
@login_required
def sheikh_announcements():
    if current_user.role != 'sheikh':
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'create':
            ann_image = ''
            if 'ann_image' in request.files and request.files['ann_image'].filename:
                f = request.files['ann_image']
                if allowed_file(f.filename, ALLOWED_IMG):
                    ann_image = save_file(f, 'announcements')
            ann = Announcement(
                title=request.form.get('title'),
                content=request.form.get('content'),
                image=ann_image,
                sheikh_id=current_user.id,
                created_at=datetime.utcnow()
            )
            ann.save()
            flash('تم نشر الإعلان', 'success')
        elif action == 'delete':
            ann_id = request.form.get('ann_id')
            ann = Announcement.get(ann_id)
            if ann and str(ann.sheikh_id) == str(current_user.id):
                ann.delete()
                flash('تم حذف الإعلان', 'success')
    announcements = Announcement.filter_by(sheikh_id=current_user.id)
    announcements.sort(key=lambda a: a.created_at or datetime.min, reverse=True)
    return render_template('sheikh/announcements.html', announcements=announcements)


@app.route('/sheikh/students')
@login_required
def sheikh_students():
    if current_user.role != 'sheikh':
        return redirect(url_for('dashboard'))
    courses = Course.filter_by(sheikh_id=current_user.id)
    courses_by_id = {c.id: c for c in courses}
    enrollments = []
    for cid in courses_by_id:
        for e in Enrollment.filter_by(course_id=cid):
            user = User.get(e.student_id)
            course = courses_by_id.get(e.course_id)
            if user and course:
                enrollments.append((e, user, course))
    enrollments.sort(key=lambda row: row[0].enrolled_at or datetime.min, reverse=True)
    return render_template('sheikh/students.html', enrollments=enrollments)


@app.route('/sheikh/enrollment/<int:enroll_id>/approve', methods=['POST'])
@login_required
def approve_enrollment(enroll_id):
    e = Enrollment.get(enroll_id) or abort(404)
    e.is_approved = True
    e.save()
    flash('تم قبول الطالب', 'success')
    return redirect(url_for('sheikh_students'))


@app.route('/sheikh/profile', methods=['GET', 'POST'])
@login_required
def sheikh_profile():
    if current_user.role != 'sheikh':
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        current_user.name = request.form.get('name', current_user.name)
        current_user.phone = request.form.get('phone', current_user.phone)
        current_user.whatsapp = request.form.get('whatsapp', current_user.whatsapp)
        current_user.telegram = request.form.get('telegram', current_user.telegram)
        current_user.bio = request.form.get('bio', current_user.bio)
        # حقول الدفع
        current_user.bank_account = request.form.get('bank_account', current_user.bank_account)
        current_user.bank_name = request.form.get('bank_name', current_user.bank_name)
        current_user.wallet_vodafone = request.form.get('wallet_vodafone', current_user.wallet_vodafone)
        current_user.wallet_instapay = request.form.get('wallet_instapay', current_user.wallet_instapay)
        current_user.wallet_stcpay = request.form.get('wallet_stcpay', current_user.wallet_stcpay)
        current_user.wallet_other = request.form.get('wallet_other', current_user.wallet_other)
        current_user.payment_notes = request.form.get('payment_notes', current_user.payment_notes)
        # Profile picture (small avatar)
        if 'avatar' in request.files and request.files['avatar'].filename:
            f = request.files['avatar']
            if allowed_file(f.filename, ALLOWED_IMG):
                current_user.avatar = save_file(f, 'avatars')
        # Hero photo (large image shown on homepage)
        if 'hero_photo' in request.files and request.files['hero_photo'].filename:
            f = request.files['hero_photo']
            if allowed_file(f.filename, ALLOWED_IMG):
                current_user.hero_photo = save_file(f, 'avatars')
        new_pw = request.form.get('new_password', '')
        if new_pw:
            current_user.password = generate_password_hash(new_pw)
        current_user.save()
        flash('تم حفظ الملف الشخصي بنجاح ✅', 'success')
    return render_template('sheikh/profile.html')


# ─── Contact Page ─────────────────────────────────────────
@app.route('/contact')
def contact():
    sheikh = User.first_by(role='sheikh')
    return render_template('public/contact.html', sheikh=sheikh)


# ─── Teachers ─────────────────────────────────────────────
@app.route('/add-teacher', methods=['GET', 'POST'])
@login_required
def add_teacher():
    if current_user.role != 'sheikh':
        abort(403)
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        can_upload = request.form.get('can_upload_lessons') == 'on'

        if not email or not password:
            flash('البريد الإلكتروني وكلمة المرور مطلوبان لإنشاء حساب دخول للمعلم', 'error')
            return render_template('add_teacher.html')
        if User.first_by(email=email):
            flash('هذا البريد الإلكتروني مستخدم مسبقاً لحساب آخر', 'error')
            return render_template('add_teacher.html')

        image_file = request.files.get('image')
        image_path = ''
        if image_file and image_file.filename:
            if allowed_file(image_file.filename, ALLOWED_IMG):
                image_path = save_file(image_file, 'avatars')

        teacher = Teacher(
            name=request.form.get('name'),
            specialty=request.form.get('specialty', ''),
            bio=request.form.get('bio', ''),
            phone=request.form.get('phone', ''),
            email=email,
            image=image_path,
            sheikh_id=current_user.id,
            can_upload_lessons=can_upload,
            created_at=datetime.utcnow()
        )
        teacher.save()

        teacher_user = User(
            name=request.form.get('name'),
            email=email,
            password=generate_password_hash(password),
            role='teacher',
            teacher_id=teacher.id,
            created_at=datetime.utcnow()
        )
        teacher_user.save()
        teacher.user_id = teacher_user.id
        teacher.save()

        flash(f'تم إضافة المعلم بنجاح ✅ — يمكنه الآن الدخول بالبريد {email} وكلمة المرور التي حددتها', 'success')
        return redirect(url_for('teachers'))
    return render_template('add_teacher.html')


@app.route('/teacher/<int:teacher_id>/delete', methods=['POST'])
@login_required
def delete_teacher(teacher_id):
    if current_user.role != 'sheikh':
        abort(403)
    teacher = Teacher.get(teacher_id) or abort(404)
    if str(teacher.sheikh_id) != str(current_user.id):
        abort(403)
    if teacher.user_id:
        linked_user = User.get(teacher.user_id)
        if linked_user:
            linked_user.delete()
    teacher.delete()
    flash('تم حذف المعلم وحسابه بنجاح', 'success')
    return redirect(url_for('teachers'))


@app.route('/teacher/<int:teacher_id>/toggle-permissions', methods=['POST'])
@login_required
def toggle_teacher_permissions(teacher_id):
    if current_user.role != 'sheikh':
        abort(403)
    teacher = Teacher.get(teacher_id) or abort(404)
    if str(teacher.sheikh_id) != str(current_user.id):
        abort(403)
    teacher.can_upload_lessons = not teacher.can_upload_lessons
    teacher.save()
    status = 'مفعلة' if teacher.can_upload_lessons else 'معطلة'
    flash(f'تم تحديث صلاحيات المعلم - الرفع: {status}', 'success')
    return redirect(url_for('teachers'))


@app.route('/teachers')
def teachers():
    if current_user.is_authenticated and current_user.role == 'sheikh':
        teacher_list = Teacher.filter_by(sheikh_id=current_user.id)
        return render_template('teachers.html', teachers=teacher_list, is_sheikh=True)
    else:
        teacher_list = Teacher.all()
        return render_template('teachers.html', teachers=teacher_list, is_sheikh=False)


# ─── لوحة تحكم المعلم (حساب دخول مستقل بصلاحية رفع الدروس فقط) ───
@app.route('/teacher/dashboard')
@login_required
def teacher_dashboard():
    if current_user.role != 'teacher':
        return redirect(url_for('dashboard'))
    teacher = get_teacher_profile(current_user)
    if not teacher:
        abort(404)
    courses = Course.filter_by(sheikh_id=teacher.sheikh_id) if teacher.can_upload_lessons else []
    courses.sort(key=lambda c: c.created_at or datetime.min, reverse=True)
    return render_template('teacher/dashboard.html', teacher=teacher, courses=courses)


@app.route('/teacher/course/<int:course_id>/lessons')
@login_required
def teacher_course_lessons(course_id):
    if current_user.role != 'teacher':
        return redirect(url_for('dashboard'))
    course = Course.get(course_id) or abort(404)
    if not can_manage_course_lessons(current_user, course):
        flash('ليست لديك صلاحية إدارة دروس هذا الكورس', 'error')
        return redirect(url_for('teacher_dashboard'))
    lessons = course.lessons
    return render_template('teacher/course_lessons.html', course=course, lessons=lessons)


@app.route('/teacher/course/new', methods=['GET', 'POST'])
@login_required
def teacher_new_course():
    if current_user.role != 'teacher':
        return redirect(url_for('dashboard'))
    teacher = get_teacher_profile(current_user)
    if not teacher or not teacher.can_upload_lessons:
        flash('ليست لديك صلاحية إنشاء كورسات بعد. تواصلي مع الشيخ لتفعيلها.', 'error')
        return redirect(url_for('teacher_dashboard'))
    if request.method == 'POST':
        thumb_path = ''
        if 'thumbnail' in request.files and request.files['thumbnail'].filename:
            f = request.files['thumbnail']
            if allowed_file(f.filename, ALLOWED_IMG):
                thumb_path = save_file(f, 'thumbnails')
        course = Course(
            title=request.form.get('title'),
            description=request.form.get('description', ''),
            level=request.form.get('level', 'مبتدئ'),
            category=request.form.get('category', 'تجويد'),
            price=float(request.form.get('price', 0)),
            is_free=request.form.get('is_free') == 'on',
            is_published=request.form.get('is_published') == 'on',
            thumbnail=thumb_path,
            sheikh_id=teacher.sheikh_id,
            created_by=current_user.id,
            created_at=datetime.utcnow()
        )
        course.save()
        flash('تم إنشاء الكورس بنجاح ✅ يمكنك الآن إضافة الدروس إليه', 'success')
        return redirect(url_for('teacher_course_lessons', course_id=course.id))
    return render_template('teacher/course_form.html')


# ─── تهيئة أولية (تعمل فقط إذا كانت قاعدة Firestore فارغة) ───
def init_db():
    for _sub in ['thumbnails', 'videos', 'avatars', 'materials', 'announcements']:
        os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], _sub), exist_ok=True)

    if User.first_by(email='sheikh@quran.com'):
        return

    sheikh = User(
        name='الشيخ نظمي السعدني',
        email='sheikh@quran.com',
        password=generate_password_hash('sheikh123'),
        role='sheikh',
        bio='مقرئ متخصص برواية حفص عن عاصم، حاصل على إجازة بالسند المتصل',
        country='المملكة العربية السعودية',
        created_at=datetime.utcnow()
    )
    sheikh.save()
    course = Course(
        title='مبادئ التجويد للمبتدئين',
        description='كورس شامل لتعلم أحكام التجويد من الصفر مع تطبيق عملي',
        level='مبتدئ', category='تجويد',
        price=0, is_free=True, is_published=True,
        sheikh_id=sheikh.id,
        created_at=datetime.utcnow()
    )
    course.save()
    for i, t in enumerate(['مقدمة في التجويد', 'أحكام النون الساكنة', 'المدود وأنواعها'], 1):
        lesson = Lesson(title=t, order_num=i,
                        video_url='https://www.youtube.com/embed/dQw4w9WgXcQ',
                        duration='45 دقيقة', course_id=course.id,
                        is_free_preview=(i == 1), created_at=datetime.utcnow())
        lesson.save()
    print("✅ Firestore initialized with demo data")
    print("👤 Sheikh login: sheikh@quran.com / sheikh123")


init_db()


if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG', 'true').lower() == 'true',
            host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
