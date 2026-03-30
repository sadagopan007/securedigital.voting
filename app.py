from flask import Flask, render_template, request, session, redirect, url_for, jsonify
import random
import hashlib
import time
import os
import csv
import requests as req

app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY", "securevote-fixed-key-2024-xk9z")
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"]   = False

# ── SUPABASE CONNECTION (using REST API directly — no SDK needed) ──────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://lssucascactoghfnapgn.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imxzc3VjYXNjYWN0b2doZm5hcGduIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ4ODQwMzIsImV4cCI6MjA5MDQ2MDAzMn0.3lAnNj_30ohWNOfeAxXWYz-QIHH1eEzO0Vp6Ft2pOro")

HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
}

BASE = f"{SUPABASE_URL}/rest/v1"

def sb_select(table, filters=None):
    params = {"select": "*"}
    if filters:
        params.update(filters)
    try:
        r = req.get(f"{BASE}/{table}", headers=HEADERS, params=params, timeout=10)
        if r.ok:
            return r.json()
        print(f"❌ sb_select({table}) HTTP {r.status_code}: {r.text}")
        return []
    except Exception as e:
        print(f"❌ sb_select({table}) error: {e}")
        return []

def sb_insert(table, data):
    try:
        r = req.post(f"{BASE}/{table}", headers={**HEADERS, "Prefer": "return=minimal"},
                     json=data, timeout=10)
        if not r.ok:
            print(f"❌ sb_insert({table}) HTTP {r.status_code}: {r.text}")
        return r.ok
    except Exception as e:
        print(f"❌ sb_insert({table}) error: {e}")
        return False

def sb_delete(table, filters):
    try:
        r = req.delete(f"{BASE}/{table}", headers={**HEADERS, "Prefer": "return=minimal"},
                       params=filters, timeout=10)
        if not r.ok:
            print(f"❌ sb_delete({table}) HTTP {r.status_code}: {r.text}")
        return r.ok
    except Exception as e:
        print(f"❌ sb_delete({table}) error: {e}")
        return False

print("✅ Supabase REST client ready!")

# ── LOAD VOTER DATABASE FROM CSV ──────────────────────────────────────
def load_voters():
    voters = {}
    try:
        with open("voters.csv", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                voters[row["voter_id"].strip().upper()] = row["aadhaar"].strip()
        print(f"✅ Loaded {len(voters)} voters from voters.csv")
    except FileNotFoundError:
        print("❌ voters.csv not found!")
    return voters

VOTER_DATABASE = load_voters()

otp_storage    = {}
login_attempts = {}
trust_score    = [100]
voting_ended   = [False]

CANDIDATES = [
    {"id": "A", "name": "Arun Kumar",   "party": "Progressive Alliance", "symbol": "🌟"},
    {"id": "B", "name": "Bhavna Mehta", "party": "United Front",         "symbol": "🔥"},
    {"id": "C", "name": "Chetan Rao",   "party": "People's Party",       "symbol": "🌿"},
]

# ── SUPABASE HELPERS ──────────────────────────────────────────────────
def db_get_votes():
    rows = sb_select("votes")
    return {r["voter_id"]: {"candidate": r["candidate"],
                             "timestamp": r["timestamp"],
                             "hash":      r["hash"]} for r in rows}

def db_voter_voted(voter_id):
    rows = sb_select("votes", {"voter_id": f"eq.{voter_id}", "select": "voter_id"})
    return len(rows) > 0

def db_cast_vote(voter_id, candidate, timestamp, vote_hash):
    return sb_insert("votes", {
        "voter_id":  voter_id,
        "candidate": candidate,
        "timestamp": timestamp,
        "hash":      vote_hash
    })

def db_log_fraud(fraud_type, voter_id):
    sb_insert("fraud_log", {
        "type":     fraud_type,
        "voter_id": voter_id,
        "time":     time.time()
    })

def db_get_fraud_log():
    return sb_select("fraud_log", {"order": "time.desc", "limit": "10"})

def db_reset():
    sb_delete("votes",     {"voter_id": "neq.NONE"})
    sb_delete("fraud_log", {"id": "gt.0"})
    print("✅ Supabase data cleared!")

# ── HELPERS ───────────────────────────────────────────────────────────
def generate_vote_hash(voter_id, candidate, timestamp):
    data = f"{voter_id}{candidate}{timestamp}"
    return hashlib.sha256(data.encode()).hexdigest()[:16].upper()

def reduce_trust(amount=10):
    trust_score[0] = max(0, trust_score[0] - amount)

def get_results():
    votes = db_get_votes()
    counts = {c["id"]: 0 for c in CANDIDATES}
    for v in votes.values():
        counts[v["candidate"]] += 1
    return counts

# ── ROUTES ────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return redirect(url_for("login"))

@app.route("/login")
def login():
    return render_template("login.html", voting_ended=voting_ended[0])

@app.route("/end_voting", methods=["POST"])
def end_voting():
    voting_ended[0] = True
    return redirect(url_for("admin"))

@app.route("/send_otp", methods=["POST"])
def send_otp():
    if voting_ended[0]:
        return render_template("login.html", voting_ended=True,
            error="⚠ Voting has ended. No more votes accepted.")

    voter_id = request.form.get("voter_id", "").strip().upper()
    aadhaar  = request.form.get("aadhaar", "").strip()

    if not voter_id or not aadhaar:
        return render_template("login.html", voting_ended=False, error="Please fill all fields.")

    if len(aadhaar) != 12 or not aadhaar.isdigit():
        return render_template("login.html", voting_ended=False, error="Aadhaar must be 12 digits.")

    if voter_id not in VOTER_DATABASE:
        db_log_fraud("unregistered_voter", voter_id)
        reduce_trust(10)
        return render_template("login.html", voting_ended=False,
            error="⚠ Voter ID not found in database. This attempt has been flagged.", alert=True)

    if VOTER_DATABASE[voter_id] != aadhaar:
        db_log_fraud("aadhaar_mismatch", voter_id)
        reduce_trust(10)
        return render_template("login.html", voting_ended=False,
            error="⚠ Aadhaar does not match records. This attempt has been flagged.", alert=True)

    if db_voter_voted(voter_id):
        db_log_fraud("double_vote_attempt", voter_id)
        reduce_trust(10)
        return render_template("login.html", voting_ended=False,
            error="⚠ This Voter ID has already voted. Attempt flagged.", alert=True)

    attempts = login_attempts.get(voter_id, 0)
    if attempts >= 5:
        db_log_fraud("brute_force", voter_id)
        reduce_trust(15)
        return render_template("login.html", voting_ended=False,
            error="⚠ Too many attempts. Contact election office.", alert=True)

    otp = random.randint(100000, 999999)
    otp_storage[voter_id] = {
        "otp":        otp,
        "aadhaar":    aadhaar,
        "expires_at": time.time() + 300
    }
    login_attempts[voter_id] = attempts + 1

    print(f"\n{'='*40}\n  OTP for {voter_id}: {otp}\n{'='*40}\n")
    return render_template("otp.html", voter_id=voter_id, otp_demo=otp)

@app.route("/verify_otp", methods=["POST"])
def verify_otp():
    voter_id    = request.form.get("voter_id", "").strip().upper()
    entered_otp = request.form.get("otp", "").strip()

    record = otp_storage.get(voter_id)
    if not record:
        return render_template("login.html", voting_ended=voting_ended[0],
                               error="Session expired. Please login again.")

    if time.time() > record["expires_at"]:
        del otp_storage[voter_id]
        return render_template("login.html", voting_ended=voting_ended[0],
                               error="OTP expired. Please login again.")

    if str(record["otp"]) != entered_otp:
        db_log_fraud("wrong_otp", voter_id)
        reduce_trust(5)
        return render_template("otp.html", voter_id=voter_id,
                               error="Wrong OTP. Try again.", otp_demo=record["otp"])

    session.clear()
    session["voter_id"]      = voter_id
    session["authenticated"] = True
    session.modified         = True
    return redirect(url_for("vote"))

@app.route("/vote")
def vote():
    voter_id = session.get("voter_id")
    auth     = session.get("authenticated")

    if not voter_id or not auth:
        return redirect(url_for("login"))

    if db_voter_voted(voter_id):
        return redirect(url_for("success"))

    return render_template("vote.html", voter_id=voter_id, candidates=CANDIDATES)

@app.route("/cast_vote", methods=["POST"])
def cast_vote():
    voter_id = session.get("voter_id")
    auth     = session.get("authenticated")

    if not voter_id or not auth:
        return redirect(url_for("login"))

    candidate = request.form.get("candidate")

    if db_voter_voted(voter_id):
        db_log_fraud("double_vote", voter_id)
        reduce_trust(10)
        return render_template("vote.html", voter_id=voter_id, candidates=CANDIDATES,
                               error="Fraud detected! You already voted.")

    if candidate not in [c["id"] for c in CANDIDATES]:
        return render_template("vote.html", voter_id=voter_id, candidates=CANDIDATES,
                               error="Invalid candidate selected.")

    timestamp = time.time()
    vote_hash = generate_vote_hash(voter_id, candidate, timestamp)
    success   = db_cast_vote(voter_id, candidate, timestamp, vote_hash)

    if not success:
        return render_template("vote.html", voter_id=voter_id, candidates=CANDIDATES,
                               error="Database error. Please try again.")

    session["vote_hash"]     = vote_hash
    session["voted_for"]     = candidate
    session["authenticated"] = False
    session.modified         = True
    return redirect(url_for("success"))

@app.route("/success")
def success():
    candidate_id = session.get("voted_for")
    vote_hash    = session.get("vote_hash", "N/A")

    if not candidate_id:
        return redirect(url_for("login"))

    candidate = next((c for c in CANDIDATES if c["id"] == candidate_id), None)
    return render_template("success.html", vote_hash=vote_hash, candidate=candidate)

@app.route("/admin")
def admin():
    votes       = db_get_votes()
    fraud_log   = db_get_fraud_log()
    results     = get_results()
    total_votes = len(votes)
    results_with_names = [
        {**c, "votes": results[c["id"]],
         "pct": round(results[c["id"]] / total_votes * 100) if total_votes else 0}
        for c in CANDIDATES
    ]
    return render_template("admin.html",
                           candidates=results_with_names,
                           total_votes=total_votes,
                           trust_score=trust_score[0],
                           fraud_log=fraud_log,
                           votes=votes,
                           voting_ended=voting_ended[0])

@app.route("/api/results")
def api_results():
    return jsonify({
        "results":      get_results(),
        "total":        len(db_get_votes()),
        "trust_score":  trust_score[0],
        "fraud_events": len(db_get_fraud_log()),
        "voting_ended": voting_ended[0]
    })

@app.route("/reset")
def reset():
    global login_attempts, otp_storage
    db_reset()
    otp_storage    = {}
    login_attempts = {}
    trust_score[0] = 100
    voting_ended[0] = False
    session.clear()
    print("✅ All data reset successfully!")
    return redirect(url_for("admin"))

@app.route("/database")
def database():
    return jsonify(VOTER_DATABASE)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
