from flask import Flask, request, jsonify
import os, csv, sqlite3, json, re
import google.generativeai as genai

# --- API Config Stuff ---
# This reads my Gemini API key from an environment var.
# NOTE: Don't hardcode keys (unless you like bad surprises).
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_KEY:
    raise RuntimeError("Uh-oh: GEMINI_API_KEY not set. Try: export GEMINI_API_KEY='...'")

# I usually use flash model 'cause it's snappy
genai.configure(api_key=GEMINI_KEY)
llm_model = genai.GenerativeModel("gemini-1.5-flash")

# --- Flask app ---
app = Flask(__name__, static_url_path="", static_folder="static")

# --- DB/CSV paths ---
DB_FILE = "merit_list.db"
CSV_FILE = "merit_list.csv"   # assuming it's sitting there

def init_database():
    """Creates the table if it's missing and loads CSV if empty."""
    conn = sqlite3.connect(DB_FILE)
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

    cur.execute("SELECT COUNT(*) FROM merit_data")
    count = cur.fetchone()[0]
    if count == 0 and os.path.exists(CSV_FILE):
        with open(CSV_FILE, newline="", encoding="utf-8") as fh:
            csv_reader = csv.DictReader(fh)
            for row in csv_reader:
                cur.execute("""
                INSERT INTO merit_data 
                (University, Campus, Department, Program, Year, MinimumMerit, MaximumMerit)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    row["University"].strip(),
                    row["Campus"].strip(),
                    row["Department"].strip(),
                    row["Program"].strip(),
                    int(row["Year"]),
                    float(row["Minimum Merit"]),
                    float(row["Maximum Merit"])
                ))
        conn.commit()
    conn.close()

def grab_merit_data():
    """Just loads all merit data rows into a list of dicts."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM merit_data")
    records = []
    for r in cur.fetchall():
        records.append({
            "University": r["University"].strip(),
            "Campus": r["Campus"].strip(),
            "Department": r["Department"].strip(),
            "Program": r["Program"].strip(),
            "Year": r["Year"],
            "Minimum Merit": r["MinimumMerit"],
            "Maximum Merit": r["MaximumMerit"]
        })
    conn.close()
    return records

# Boot up the DB and data
init_database()
merit_records = grab_merit_data()

# Quick lookups
UNIS = sorted({r["University"] for r in merit_records})
DEPTS = sorted({r["Department"] for r in merit_records})
PROGS = sorted({r["Program"] for r in merit_records})
CAMPS = sorted({r["Campus"] for r in merit_records})

# Map uni -> campuses
UNI_TO_CAMP = {}
for rec in merit_records:
    UNI_TO_CAMP.setdefault(rec["University"], set()).add(rec["Campus"])
for k in UNI_TO_CAMP:
    UNI_TO_CAMP[k] = sorted(UNI_TO_CAMP[k])

# --- Synonym dictionaries ---
dept_aliases = {
    "cs": "Computing", "computer science": "Computing", "computing": "Computing",
    "se": "Computing", "software engineering": "Computing",
    "ee": "Electrical", "electrical": "Electrical", "electrical engineering": "Electrical",
    "me": "Mechanical", "mechanical": "Mechanical", "mechanical engineering": "Mechanical",
}

prog_aliases = {
    "bs": "BS", "b.s": "BS", "bsc": "BS", "b.sc": "BS", "bachelors": "BS",
    "bachelor": "BS", "undergrad": "BS", "ug": "BS",
    "ms": "MS", "m.s": "MS", "msc": "MS", "m.sc": "MS",
    "mphil": "MPhil", "m.phil": "MPhil", "postgrad": "MS", "pg": "MS",
    "phd": "PhD", "ph.d": "PhD", "doctorate": "PhD"
}

def norm_dept(txt):
    return dept_aliases.get(txt.strip().lower(), txt.strip()) if txt else txt

def norm_prog(txt):
    if not txt: return txt
    t = txt.strip().lower().replace("-", "").replace("_", "").replace(" ", "")
    return prog_aliases.get(t, txt.strip())

def campus_like(c1, c2):
    if not c2: return True
    return c2.lower() in c1.lower()

# --- Searching ---
def lookup_rows(uni, camp, dept, prog, yr):
    hits = []
    for rec in merit_records:
        if rec["University"].lower() != (uni or "").lower(): continue
        if not campus_like(rec["Campus"], camp): continue
        if rec["Department"].lower() != (dept or "").lower(): continue
        if rec["Program"].lower() != (prog or "").lower(): continue
        if int(rec["Year"]) != int(yr): continue
        hits.append(rec)
    return hits

# Basic dumb extractor (regex + contains)
def cheap_extract(msg):
    msg_l = msg.lower()
    uni_found, dept_found, prog_found, camp_found = None, None, None, None

    for u in UNIS:
        if u.lower() in msg_l:
            uni_found = u
            break

    for k, v in dept_aliases.items():
        if k in msg_l:
            dept_found = v
            break
    if not dept_found:
        for d in DEPTS:
            if d.lower() in msg_l:
                dept_found = d
                break

    for k, v in prog_aliases.items():
        if k in msg_l:
            prog_found = v
            break

    if uni_found and uni_found in UNI_TO_CAMP:
        for c in UNI_TO_CAMP[uni_found]:
            if c.lower() in msg_l:
                camp_found = c
                break
    if not camp_found:
        for c in CAMPS:
            if c.lower() in msg_l:
                camp_found = c
                break

    year_match = re.search(r"\b(20\d{2}|19\d{2})\b", msg_l)
    year_found = int(year_match.group(1)) if year_match else 2024
    if not prog_found:
        prog_found = "BS"

    return uni_found, camp_found, dept_found, prog_found, year_found

@app.route("/chat", methods=["POST"])
def chat():
    user_msg = request.json["message"]

    # Try to use LLM extraction first
    prompt = f"""
    From the question, pull:
    - university (one of: {UNIS})
    - campus (string; "" if none)
    - department (canonical to: {DEPTS})
    - program (canonical to: {PROGS}, default "BS")
    - year (int, default 2024)

    Return ONLY JSON.
    User said:
    \"\"\"{user_msg}\"\"\"
    """

    try:
        res = llm_model.generate_content(prompt)
        text_out = (res.text or "").strip()
        json_match = re.search(r"\{.*\}", text_out, re.DOTALL)
        info = json.loads(json_match.group()) if json_match else None
    except Exception:
        info = None

    if not info:
        uni, camp, dept, prog, yr = cheap_extract(user_msg)
    else:
        uni = info.get("university")
        camp = info.get("campus", "")
        dept = info.get("department")
        prog = info.get("program", "BS")
        yr = info.get("year", 2024)

    dept = norm_dept(dept) if dept else None
    prog = norm_prog(prog) if prog else None

    # quick 'list departments' intent
    if re.search(r"\b(fields?|departments?|programs?)\b", user_msg.lower()):
        if uni:
            deps_here = sorted({
                r["Department"] for r in merit_records
                if r["University"].lower() == uni.lower()
                and (not camp or r["Campus"].lower() == camp.lower())
                and (not prog or r["Program"].lower() == prog.lower())
            })
            if deps_here:
                return jsonify({"reply": f"Departments at {uni}{' ('+camp+')' if camp else ''}{' for '+prog if prog else ''}: {', '.join(deps_here)}"})
            else:
                return jsonify({"reply": f"Couldn't find departments for {uni} with given filters."})
        else:
            return jsonify({"reply": f"Need a university name. Example: 'What BS fields are in {UNIS[0]}?'"})

    # Fill in missing bits with cheap_extract again
    if not uni or not dept or not prog:
        f_uni, f_camp, f_dep, f_prog, f_yr = cheap_extract(user_msg)
        uni = uni or f_uni
        camp = camp or f_camp
        dept = dept or f_dep
        prog = prog or f_prog
        yr = yr or f_yr

    if not uni and not dept:
        return jsonify({"reply": "Please tell me the university and department."})
    if not uni:
        return jsonify({"reply": f"Missing university. Try one of: {', '.join(UNIS)}"})
    if not dept:
        return jsonify({"reply": f"Missing department. Try one of: {', '.join(DEPTS)}"})
    if not prog:
        return jsonify({"reply": f"Missing program. Try one of: {', '.join(PROGS)}"})

    rows = lookup_rows(uni, camp, dept, prog, yr)

    if not rows:
        years_avail = sorted({r["Year"] for r in merit_records if r["University"].lower()==uni.lower() and r["Department"].lower()==dept.lower() and r["Program"].lower()==prog.lower()})
        if years_avail:
            return jsonify({"reply": f"No data for {yr}. Available years: {', '.join(map(str, years_avail))}."})
        progs_avail = sorted({r["Program"] for r in merit_records if r["University"].lower()==uni.lower() and r["Department"].lower()==dept.lower()})
        if progs_avail:
            return jsonify({"reply": f"No {prog} program here. Available: {', '.join(progs_avail)}."})
        if uni in UNI_TO_CAMP:
            deps_avail = sorted({r["Department"] for r in merit_records if r["University"].lower()==uni.lower()})
            return jsonify({"reply": f"No match found. {uni} campuses: {', '.join(UNI_TO_CAMP[uni])}. Departments: {', '.join(deps_avail)}"})
        return jsonify({"reply": "Sorry, nothing matched."})

    if len(rows) > 1 and not camp:
        lines = [f"- {r['Campus']}: min {r['Minimum Merit']}% / max {r['Maximum Merit']}%" for r in rows]
        return jsonify({"reply": f"Multiple campuses found:\n" + "\n".join(lines)})

    first_hit = rows[0]
    camp_txt = f" ({first_hit['Campus']})" if first_hit["Campus"] else ""
    return jsonify({"reply": f"The merit for {first_hit['Program']} {first_hit['Department']} at {first_hit['University']}{camp_txt} in {first_hit['Year']} is: min {first_hit['Minimum Merit']}% / max {first_hit['Maximum Merit']}%."})

@app.route("/")
def home():
    return app.send_static_file("index.html")

@app.route("/health")
def health():
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(debug=True)