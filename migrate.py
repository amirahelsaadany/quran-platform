import sqlite3
conn = sqlite3.connect('instance/quran_platform.db')
for col in ['whatsapp', 'telegram', 'hero_photo']:
    try:
        conn.execute(f'ALTER TABLE user ADD COLUMN {col} VARCHAR(200) DEFAULT ""')
        print(f'✅ تمت إضافة: {col}')
    except Exception as e:
        print(f'⚠️  {col}: {e}')
conn.commit()
conn.close()
print('✅ انتهى!')