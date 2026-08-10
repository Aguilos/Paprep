import sqlite3
conn=sqlite3.connect('paprep.db')
cur=conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print('tables=', cur.fetchall())
try:
    cur.execute("PRAGMA table_info('clinic_messages')")
    print('clinic_messages cols=', cur.fetchall())
except Exception as e:
    print('err', e)
conn.close()
