# -*- coding: utf-8 -*-
"""
سكربت ترحيل البيانات من قاعدة SQLite القديمة (quran_platform.db) إلى Firestore.

الاستخدام:
    python migrate_to_firestore.py

قبل التشغيل:
  1) تأكد من وجود ملف quran_platform.db في نفس مجلد هذا السكربت
     (أو مرّر المسار كوسيط: python migrate_to_firestore.py /path/to/quran_platform.db)
  2) تأكد من ضبط بيانات اعتماد Firebase بنفس الطريقة المستخدمة في app.py
     (FIREBASE_CREDENTIALS_JSON أو FIREBASE_CREDENTIALS_PATH أو ملف firebase-credentials.json محلياً)
  3) هذا السكربت يُنصح بتشغيله مرة واحدة فقط. تشغيله مرة ثانية سيقوم
     بتحديث المستندات بنفس المعرفات (id) دون تكرارها، لكن الأفضل تجنّب التكرار.
"""
import os
import sys
import sqlite3
import json
from datetime import datetime

import firebase_admin
from firebase_admin import credentials, firestore


# ─── الاتصال بـ Firebase (نفس منطق app.py) ─────────────────
def init_firebase():
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


# ─── تحويل القيم من صيغة SQLite إلى صيغة بايثون مناسبة لـ Firestore ───
BOOL_COLUMNS = {
    'is_active_account', 'is_free', 'is_published', 'can_upload_lessons',
    'is_free_preview', 'is_live', 'is_approved', 'completed', 'is_active',
}
DATETIME_COLUMNS = {
    'created_at', 'enrolled_at', 'watched_at', 'scheduled_at',
}


def convert_row(row_dict):
    out = {}
    for k, v in row_dict.items():
        if k == 'id':
            continue
        if k in BOOL_COLUMNS and v is not None:
            out[k] = bool(v)
        elif k in DATETIME_COLUMNS and v:
            try:
                out[k] = datetime.strptime(v, '%Y-%m-%d %H:%M:%S.%f')
            except (ValueError, TypeError):
                try:
                    out[k] = datetime.strptime(v, '%Y-%m-%d %H:%M:%S')
                except (ValueError, TypeError):
                    out[k] = v
        else:
            out[k] = v if v is not None else ''
    return out


# خريطة: اسم جدول SQLite -> اسم مجموعة Firestore (نفس الأسماء المستخدمة في app.py)
TABLE_TO_COLLECTION = {
    'user': 'users',
    'course': 'courses',
    'teacher': 'teachers',
    'lesson': 'lessons',
    'material': 'materials',
    'enrollment': 'enrollments',
    'progress': 'progress',
    'live_session': 'live_sessions',
    'announcement': 'announcements',
}

# ترتيب الترحيل مهم قليلاً للقراءة الواضحة في اللوج فقط (Firestore لا يفرض قيود مفاتيح خارجية)
MIGRATION_ORDER = ['user', 'course', 'teacher', 'lesson', 'material',
                   'enrollment', 'progress', 'live_session', 'announcement']


def main():
    db_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(__file__), 'quran_platform.db')
    if not os.path.exists(db_path):
        alt = os.path.join(os.path.dirname(__file__), 'instance', 'quran_platform.db')
        if os.path.exists(alt):
            db_path = alt
        else:
            print(f'❌ لم يتم العثور على قاعدة البيانات: {db_path}')
            sys.exit(1)

    print(f'📂 قاعدة البيانات المصدر: {db_path}')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    fdb = init_firebase()
    print('🔥 تم الاتصال بـ Firestore بنجاح')

    max_ids = {}

    for table in MIGRATION_ORDER:
        collection = TABLE_TO_COLLECTION[table]
        try:
            cur = conn.execute(f'SELECT * FROM {table}')
        except sqlite3.OperationalError:
            print(f'⚠️  الجدول {table} غير موجود في قاعدة البيانات، تم تجاوزه')
            continue
        rows = cur.fetchall()
        count = 0
        max_id = 0
        for row in rows:
            row_dict = dict(row)
            doc_id = str(row_dict['id'])
            data = convert_row(row_dict)
            fdb.collection(collection).document(doc_id).set(data)
            count += 1
            try:
                max_id = max(max_id, int(row_dict['id']))
            except (TypeError, ValueError):
                pass
        max_ids[collection] = max_id
        print(f'✅ {table} → {collection}: تم ترحيل {count} سجل')

    # ضبط العدادات (counters) لكل مجموعة حتى تستمر أرقام الـ ID التسلسلية بشكل صحيح
    for collection, max_id in max_ids.items():
        fdb.collection('counters').document(collection).set({'value': max_id})
    print('\n🔢 تم ضبط عدادات الترقيم (counters) لكل المجموعات')

    conn.close()
    print('\n🎉 انتهى الترحيل بنجاح! يمكنك الآن حذف/أرشفة ملف quran_platform.db وتشغيل المنصة على Firestore.')


if __name__ == '__main__':
    main()
