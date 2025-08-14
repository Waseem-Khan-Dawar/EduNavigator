import sqlite3

conn = sqlite3.connect("mydatabase.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS merit_data (
    University TEXT,
    Campus TEXT,
    Department TEXT,
    Program TEXT,
    Year INTEGER,
    MinimumMerit REAL,
    MaximumMerit REAL
)
""")
conn.commit()
conn.close()


# test_db.py
from app import merit_list, UNIVERSITIES, DEPARTMENTS, PROGRAMS, CAMPUSES

print("Total records loaded:", len(merit_list))
print("Sample record:", merit_list[0])

print("\nAvailable Universities:", UNIVERSITIES)
print("\nAvailable Departments:", DEPARTMENTS)
print("\nAvailable Programs:", PROGRAMS)
print("\nAvailable Campuses:", CAMPUSES)
