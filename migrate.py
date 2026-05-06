import sqlite3
conn = sqlite3.connect('instance/quran_platform.db')

# أعمدة جدول المستخدمين
user_cols = [
    ('whatsapp', 'VARCHAR(50) DEFAULT ""'),
    ('telegram', 'VARCHAR(100) DEFAULT ""'),
    ('hero_photo', 'VARCHAR(200) DEFAULT ""'),
    ('bank_account', 'VARCHAR(200) DEFAULT ""'),
    ('bank_name', 'VARCHAR(100) DEFAULT ""'),
    ('wallet_vodafone', 'VARCHAR(50) DEFAULT ""'),
    ('wallet_instapay', 'VARCHAR(100) DEFAULT ""'),
    ('wallet_stcpay', 'VARCHAR(50) DEFAULT ""'),
    ('wallet_other', 'VARCHAR(200) DEFAULT ""'),
    ('payment_notes', 'TEXT DEFAULT ""'),
]
for col, dtype in user_cols:
    try:
        conn.execute(f'ALTER TABLE user ADD COLUMN {col} {dtype}')
        print(f'✅ user.{col} أضيف')
    except Exception as e:
        print(f'⚠️  user.{col}: {e}')

# أعمدة جدول الإعلانات
try:
    conn.execute('ALTER TABLE announcement ADD COLUMN image VARCHAR(200) DEFAULT ""')
    print('✅ announcement.image أضيف')
except Exception as e:
    print(f'⚠️  announcement.image: {e}')

# عمود صورة الدرس
try:
    conn.execute('ALTER TABLE lesson ADD COLUMN thumbnail VARCHAR(200) DEFAULT ""')
    print('✅ lesson.thumbnail أضيف')
except Exception as e:
    print(f'⚠️  lesson.thumbnail: {e}')

conn.commit()
conn.close()
print('✅ انتهت عملية التحديث!')
