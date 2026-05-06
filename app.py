from flask import Flask, render_template, redirect, url_for, request, flash, session, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os, uuid

app = Flask(__name__)

# ─── Secret Key ───────────────────────────────────────────
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'quran-platform-secret-key-2024-change-in-production')

# ─── Database ─────────────────────────────────────────────
# محلياً: يستخدم SQLite تلقائياً
# على Railway/Render: يستخدم PostgreSQL تلقائياً عبر متغير DATABASE_URL
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///quran_platform.db')
# Railway يرسل postgres:// لكن SQLAlchemy يحتاج postgresql://
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}

# ─── Uploads ──────────────────────────────────────────────
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB

ALLOWED_VIDEO = {'mp4', 'webm', 'mkv', 'avi', 'mov'}
ALLOWED_IMG = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
ALLOWED_FILE = {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'txt', 'zip'}

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ─── Models ───────────────────────────────────────────────
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='student')  # 'sheikh' or 'student'
    avatar = db.Column(db.String(200), default='')
    bio = db.Column(db.Text, default='')
    phone = db.Column(db.String(30), default='')
    whatsapp = db.Column(db.String(50), default='')
    telegram = db.Column(db.String(100), default='')
    hero_photo = db.Column(db.String(200), default='')
    country = db.Column(db.String(60), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active_account = db.Column(db.Boolean, default=True)
    # حقول الدفع للشيخ
    bank_account = db.Column(db.String(200), default='')        # رقم الحساب البنكي
    bank_name = db.Column(db.String(100), default='')           # اسم البنك
    wallet_vodafone = db.Column(db.String(50), default='')      # فودافون كاش
    wallet_instapay = db.Column(db.String(100), default='')     # إنستاباي
    wallet_stcpay = db.Column(db.String(50), default='')        # STC Pay
    wallet_other = db.Column(db.String(200), default='')        # محفظة أخرى / IBAN
    payment_notes = db.Column(db.Text, default='')              # تعليمات الدفع
    enrollments = db.relationship('Enrollment', backref='student', lazy=True)
    progress = db.relationship('Progress', backref='student', lazy=True)

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    thumbnail = db.Column(db.String(200), default='')
    level = db.Column(db.String(30), default='مبتدئ')
    category = db.Column(db.String(60), default='تجويد')
    price = db.Column(db.Float, default=0.0)
    is_free = db.Column(db.Boolean, default=False)
    is_published = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sheikh_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sheikh = db.relationship('User', backref='courses')
    lessons = db.relationship('Lesson', backref='course', lazy=True, cascade='all, delete-orphan')
    enrollments = db.relationship('Enrollment', backref='course', lazy=True, cascade='all, delete-orphan')

class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    video_path = db.Column(db.String(300), default='')
    video_url = db.Column(db.String(500), default='')  # YouTube/external URL
    thumbnail = db.Column(db.String(200), default='')  # صورة الدرس
    duration = db.Column(db.String(20), default='')
    order_num = db.Column(db.Integer, default=0)
    is_free_preview = db.Column(db.Boolean, default=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    materials = db.relationship('Material', backref='lesson', lazy=True, cascade='all, delete-orphan')
    progress = db.relationship('Progress', backref='lesson', lazy=True, cascade='all, delete-orphan')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Material(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    file_path = db.Column(db.String(300), nullable=False)
    file_type = db.Column(db.String(20), default='pdf')
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)

class Enrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_approved = db.Column(db.Boolean, default=True)  # free=auto, paid=manual

class Progress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    watched_at = db.Column(db.DateTime, default=datetime.utcnow)

class LiveSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    meeting_link = db.Column(db.String(500), default='')
    scheduled_at = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, default=60)
    is_active = db.Column(db.Boolean, default=True)
    sheikh_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sheikh = db.relationship('User', backref='live_sessions')
    max_students = db.Column(db.Integer, default=50)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(200), default='')   # صورة الإعلان
    sheikh_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sheikh = db.relationship('User', backref='announcements')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ─── Helpers ──────────────────────────────────────────────
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename, allowed):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed

def save_file(file, subfolder):
    ext = file.filename.rsplit('.', 1)[1].lower()
    fname = f"{uuid.uuid4().hex}.{ext}"
    path = os.path.join(app.config['UPLOAD_FOLDER'], subfolder, fname)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    file.save(path)
    return f"uploads/{subfolder}/{fname}"

def get_enrollment(course_id):
    if not current_user.is_authenticated:
        return None
    return Enrollment.query.filter_by(student_id=current_user.id, course_id=course_id).first()

def get_progress_pct(course_id, student_id):
    lessons = Lesson.query.filter_by(course_id=course_id).all()
    if not lessons:
        return 0
    done = Progress.query.filter(
        Progress.student_id == student_id,
        Progress.lesson_id.in_([l.id for l in lessons]),
        Progress.completed == True
    ).count()
    return round((done / len(lessons)) * 100)

app.jinja_env.globals['get_enrollment'] = get_enrollment
app.jinja_env.globals['get_progress_pct'] = get_progress_pct

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
    """إرجاع (اسم العملة، الرمز المختصر) حسب البلد"""
    if country and country in CURRENCY_MAP:
        return CURRENCY_MAP[country][2]   # الرمز المختصر
    return '$'   # افتراضي

app.jinja_env.globals['get_currency'] = get_currency
app.jinja_env.globals['CURRENCY_MAP'] = CURRENCY_MAP

# ─── Auth Routes ──────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
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
        if User.query.filter_by(email=email).first():
            flash('هذا البريد الإلكتروني مسجل مسبقاً', 'error')
            return render_template('auth/register.html')
        user = User(name=name, email=email,
                    password=generate_password_hash(password),
                    country=country, role='student')
        db.session.add(user)
        db.session.commit()
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
    courses = Course.query.filter_by(is_published=True).order_by(Course.created_at.desc()).limit(6).all()
    live_sessions = LiveSession.query.filter_by(is_active=True).order_by(LiveSession.scheduled_at).limit(3).all()
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).limit(3).all()
    sheikh = User.query.filter_by(role='sheikh').first()
    stats = {
        'students': User.query.filter_by(role='student').count(),
        'courses': Course.query.filter_by(is_published=True).count(),
        'lessons': Lesson.query.count()
    }
    return render_template('public/index.html', courses=courses, live_sessions=live_sessions,
                           announcements=announcements, stats=stats, sheikh=sheikh, hero_photo=sheikh.hero_photo if sheikh else '')

@app.route('/courses')
def courses_list():
    category = request.args.get('category', '')
    level = request.args.get('level', '')
    q = Course.query.filter_by(is_published=True)
    if category:
        q = q.filter_by(category=category)
    if level:
        q = q.filter_by(level=level)
    courses = q.order_by(Course.created_at.desc()).all()
    return render_template('public/courses.html', courses=courses, category=category, level=level)

@app.route('/course/<int:course_id>')
def course_detail(course_id):
    course = Course.query.get_or_404(course_id)
    if not course.is_published and (not current_user.is_authenticated or current_user.role != 'sheikh'):
        return redirect(url_for('courses_list'))
    lessons = Lesson.query.filter_by(course_id=course_id).order_by(Lesson.order_num).all()
    enrollment = get_enrollment(course_id)
    return render_template('public/course_detail.html', course=course, lessons=lessons, enrollment=enrollment)

@app.route('/enroll/<int:course_id>', methods=['POST'])
@login_required
def enroll(course_id):
    course = Course.query.get_or_404(course_id)
    existing = Enrollment.query.filter_by(student_id=current_user.id, course_id=course_id).first()
    if existing:
        flash('أنت مسجل في هذا الكورس مسبقاً', 'info')
        return redirect(url_for('course_detail', course_id=course_id))
    enrollment = Enrollment(student_id=current_user.id, course_id=course_id,
                            is_approved=course.is_free or course.price == 0)
    db.session.add(enrollment)
    db.session.commit()
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
    course = Course.query.get_or_404(course_id)
    enrollment = Enrollment.query.filter_by(student_id=current_user.id, course_id=course_id).first()
    if not enrollment or not enrollment.is_approved:
        flash('يجب التسجيل في الكورس أولاً', 'error')
        return redirect(url_for('course_detail', course_id=course_id))
    lessons = Lesson.query.filter_by(course_id=course_id).order_by(Lesson.order_num).all()
    if not lessons:
        flash('لا توجد دروس بعد', 'info')
        return redirect(url_for('course_detail', course_id=course_id))
    current_lesson = Lesson.query.get(lesson_id) if lesson_id else lessons[0]
    progress_ids = [p.lesson_id for p in Progress.query.filter_by(
        student_id=current_user.id, completed=True).all()]
    return render_template('student/learn.html', course=course, lessons=lessons,
                           current_lesson=current_lesson, progress_ids=progress_ids)

@app.route('/mark_complete/<int:lesson_id>', methods=['POST'])
@login_required
def mark_complete(lesson_id):
    existing = Progress.query.filter_by(student_id=current_user.id, lesson_id=lesson_id).first()
    if not existing:
        p = Progress(student_id=current_user.id, lesson_id=lesson_id, completed=True)
        db.session.add(p)
        db.session.commit()
    return jsonify({'success': True})

# ─── Dashboard ────────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'sheikh':
        return redirect(url_for('sheikh_dashboard'))
    return redirect(url_for('student_dashboard'))

# ─── Student Routes ───────────────────────────────────────
@app.route('/student/dashboard')
@login_required
def student_dashboard():
    enrollments = Enrollment.query.filter_by(student_id=current_user.id, is_approved=True).all()
    live_sessions = LiveSession.query.filter_by(is_active=True).order_by(LiveSession.scheduled_at).all()
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).limit(5).all()
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
        db.session.commit()
        flash('تم حفظ التغييرات', 'success')
    return render_template('student/profile.html')

# ─── Sheikh Routes ────────────────────────────────────────
@app.route('/sheikh/dashboard')
@login_required
def sheikh_dashboard():
    if current_user.role != 'sheikh':
        return redirect(url_for('student_dashboard'))
    courses = Course.query.filter_by(sheikh_id=current_user.id).all()
    total_students = db.session.query(Enrollment).join(Course).filter(
        Course.sheikh_id == current_user.id).count()
    total_lessons = db.session.query(Lesson).join(Course).filter(
        Course.sheikh_id == current_user.id).count()
    live_sessions = LiveSession.query.filter_by(sheikh_id=current_user.id).order_by(
        LiveSession.scheduled_at.desc()).limit(5).all()
    announcements = Announcement.query.filter_by(sheikh_id=current_user.id).order_by(
        Announcement.created_at.desc()).limit(5).all()
    pending = Enrollment.query.join(Course).filter(
        Course.sheikh_id == current_user.id, Enrollment.is_approved == False).count()
    return render_template('sheikh/dashboard.html', courses=courses,
                           total_students=total_students, total_lessons=total_lessons,
                           live_sessions=live_sessions, announcements=announcements, pending=pending)

@app.route('/sheikh/courses')
@login_required
def sheikh_courses():
    if current_user.role != 'sheikh':
        return redirect(url_for('dashboard'))
    courses = Course.query.filter_by(sheikh_id=current_user.id).order_by(Course.created_at.desc()).all()
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
            sheikh_id=current_user.id
        )
        db.session.add(course)
        db.session.commit()
        flash('تم إنشاء الكورس بنجاح', 'success')
        return redirect(url_for('sheikh_course_edit', course_id=course.id))
    return render_template('sheikh/course_form.html', course=None)

@app.route('/sheikh/course/<int:course_id>/edit', methods=['GET', 'POST'])
@login_required
def sheikh_course_edit(course_id):
    course = Course.query.get_or_404(course_id)
    if course.sheikh_id != current_user.id:
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
        db.session.commit()
        flash('تم حفظ التغييرات', 'success')
    lessons = Lesson.query.filter_by(course_id=course_id).order_by(Lesson.order_num).all()
    enrollments = Enrollment.query.filter_by(course_id=course_id).all()
    return render_template('sheikh/course_edit.html', course=course, lessons=lessons, enrollments=enrollments)

@app.route('/sheikh/course/<int:course_id>/lesson/new', methods=['POST'])
@login_required
def new_lesson(course_id):
    course = Course.query.get_or_404(course_id)
    if course.sheikh_id != current_user.id:
        return redirect(url_for('sheikh_dashboard'))
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
    count = Lesson.query.filter_by(course_id=course_id).count()
    lesson = Lesson(
        title=request.form.get('title'),
        description=request.form.get('description', ''),
        video_path=video_path,
        video_url=request.form.get('video_url', ''),
        thumbnail=lesson_thumb,
        duration=request.form.get('duration', ''),
        order_num=count + 1,
        is_free_preview=request.form.get('is_free_preview') == 'on',
        course_id=course_id
    )
    db.session.add(lesson)
    db.session.flush()
    if 'material' in request.files:
        for f in request.files.getlist('material'):
            if f.filename and allowed_file(f.filename, ALLOWED_FILE):
                mat_path = save_file(f, 'materials')
                mat = Material(title=f.filename, file_path=mat_path,
                               file_type=f.filename.rsplit('.', 1)[1].lower(),
                               lesson_id=lesson.id)
                db.session.add(mat)
    db.session.commit()
    flash('تمت إضافة الدرس بنجاح', 'success')
    return redirect(url_for('sheikh_course_edit', course_id=course_id))

@app.route('/sheikh/lesson/<int:lesson_id>/delete', methods=['POST'])
@login_required
def delete_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    course_id = lesson.course_id
    db.session.delete(lesson)
    db.session.commit()
    flash('تم حذف الدرس', 'success')
    return redirect(url_for('sheikh_course_edit', course_id=course_id))

@app.route('/sheikh/course/<int:course_id>/delete', methods=['POST'])
@login_required
def delete_course(course_id):
    course = Course.query.get_or_404(course_id)
    if course.sheikh_id != current_user.id:
        return redirect(url_for('sheikh_dashboard'))
    db.session.delete(course)
    db.session.commit()
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
                sheikh_id=current_user.id
            )
            db.session.add(ls)
            db.session.commit()
            flash('تم إنشاء الجلسة المباشرة', 'success')
        elif action == 'delete':
            ls_id = int(request.form.get('session_id'))
            ls = LiveSession.query.get(ls_id)
            if ls and ls.sheikh_id == current_user.id:
                db.session.delete(ls)
                db.session.commit()
                flash('تم حذف الجلسة', 'success')
        elif action == 'toggle':
            ls_id = int(request.form.get('session_id'))
            ls = LiveSession.query.get(ls_id)
            if ls and ls.sheikh_id == current_user.id:
                ls.is_active = not ls.is_active
                db.session.commit()
    sessions = LiveSession.query.filter_by(sheikh_id=current_user.id).order_by(
        LiveSession.scheduled_at.desc()).all()
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
                sheikh_id=current_user.id
            )
            db.session.add(ann)
            db.session.commit()
            flash('تم نشر الإعلان', 'success')
        elif action == 'delete':
            ann_id = int(request.form.get('ann_id'))
            ann = Announcement.query.get(ann_id)
            if ann and ann.sheikh_id == current_user.id:
                db.session.delete(ann)
                db.session.commit()
                flash('تم حذف الإعلان', 'success')
    announcements = Announcement.query.filter_by(sheikh_id=current_user.id).order_by(
        Announcement.created_at.desc()).all()
    return render_template('sheikh/announcements.html', announcements=announcements)

@app.route('/sheikh/students')
@login_required
def sheikh_students():
    if current_user.role != 'sheikh':
        return redirect(url_for('dashboard'))
    enrollments = db.session.query(Enrollment, User, Course).join(
        User, Enrollment.student_id == User.id).join(
        Course, Enrollment.course_id == Course.id).filter(
        Course.sheikh_id == current_user.id).order_by(Enrollment.enrolled_at.desc()).all()
    return render_template('sheikh/students.html', enrollments=enrollments)

@app.route('/sheikh/enrollment/<int:enroll_id>/approve', methods=['POST'])
@login_required
def approve_enrollment(enroll_id):
    e = Enrollment.query.get_or_404(enroll_id)
    e.is_approved = True
    db.session.commit()
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
        db.session.commit()
        flash('تم حفظ الملف الشخصي بنجاح ✅', 'success')
    return render_template('sheikh/profile.html')

# ─── Contact Page ─────────────────────────────────────────
@app.route('/contact')
def contact():
    sheikh = User.query.filter_by(role='sheikh').first()
    return render_template('public/contact.html', sheikh=sheikh)

# ─── Init DB & seed ───────────────────────────────────────
def init_db():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(email='sheikh@quran.com').first():
            sheikh = User(
                name='الشيخ عبدالرحمن الحسيني',
                email='sheikh@quran.com',
                password=generate_password_hash('sheikh123'),
                role='sheikh',
                bio='مقرئ متخصص برواية حفص عن عاصم، حاصل على إجازة بالسند المتصل',
                country='المملكة العربية السعودية'
            )
            db.session.add(sheikh)
            db.session.commit()
            course = Course(
                title='مبادئ التجويد للمبتدئين',
                description='كورس شامل لتعلم أحكام التجويد من الصفر مع تطبيق عملي',
                level='مبتدئ', category='تجويد',
                price=0, is_free=True, is_published=True,
                sheikh_id=sheikh.id
            )
            db.session.add(course)
            db.session.flush()
            for i, t in enumerate(['مقدمة في التجويد', 'أحكام النون الساكنة', 'المدود وأنواعها'], 1):
                lesson = Lesson(title=t, order_num=i,
                                video_url='https://www.youtube.com/embed/dQw4w9WgXcQ',
                                duration='45 دقيقة', course_id=course.id,
                                is_free_preview=(i == 1))
                db.session.add(lesson)
            db.session.commit()
            print("✅ Database initialized with demo data")
            print("👤 Sheikh login: sheikh@quran.com / sheikh123")

# ─── تهيئة تلقائية عند أول تشغيل ─────────────────────────
# يعمل سواء كانت SQLite أو PostgreSQL
# إنشاء مجلدات الرفع تلقائياً
for _sub in ['thumbnails', 'videos', 'avatars', 'materials', 'announcements']:
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], _sub), exist_ok=True)

init_db()

if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG', 'true').lower() == 'true',
            host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
