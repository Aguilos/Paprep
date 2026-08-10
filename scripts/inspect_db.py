import sqlite3, os
p='paprep.db'
if not os.path.exists(p):
    print('DB not found:', p)
else:
    conn=sqlite3.connect(p)
    cur=conn.cursor()
    try:
        cur.execute("PRAGMA table_info('clinic_messages')")
        rows=cur.fetchall()
        print('columns:', rows)
    except Exception as e:
        print('error:', e)
    conn.close()
