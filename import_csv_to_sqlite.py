import sqlite3
import pandas as pd

# Load CSV
df = pd.read_csv("merit_list.csv")

# Connect to SQLite (this will create merit.db if it doesn't exist)
conn = sqlite3.connect("merit.db")

# Store into table
df.to_sql("merit_list", conn, if_exists="replace", index=False)

conn.close()
print("✅ Data stored in SQLite!")
