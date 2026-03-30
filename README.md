# 🗳 SecureVote — Hackathon Project

A blockchain-inspired secure online voting system with OTP verification, fraud detection, and live admin dashboard.

---

## 🚀 Deploy to Render (Free) — Step by Step

### Step 1: Upload to GitHub
1. Create a new repo at https://github.com/new
2. Name it `securevote`
3. Upload ALL files (drag & drop on GitHub or use Git)

### Step 2: Deploy on Render
1. Go to https://render.com → Sign up free
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repo
4. Fill in these settings:
   - **Name**: securevote
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`
5. Under **Environment Variables**, add:
   - `SECRET_KEY` = `any-random-string-here`
6. Click **"Create Web Service"**
7. Wait ~2 minutes → your app is live! 🎉

---

## 🖥 Run Locally

```bash
pip install flask gunicorn
python app.py
```
Open: http://127.0.0.1:5000

---

## 📖 App Flow

```
/ (login) → /send_otp → /verify_otp → /vote → /cast_vote → /success
                                                              ↓
                                                         /admin (dashboard)
```

## 🔑 Demo Credentials
- Voter ID: `VOTER001`
- Aadhaar: `123456789012`
- OTP: shown on screen (simulated)

## 📂 File Structure
```
voting-system/
├── app.py              ← Flask backend
├── requirements.txt    ← Dependencies
├── Procfile            ← Render start command
└── templates/
    ├── base.html       ← Layout + nav
    ├── login.html      ← Step 1: Voter ID + Aadhaar
    ├── otp.html        ← Step 2: OTP verification
    ├── vote.html       ← Step 3: Choose candidate
    ├── success.html    ← Step 4: Confirmation + hash
    └── admin.html      ← Live dashboard + fraud log
```

## ✨ Features
- ✅ OTP verification (simulated)
- ✅ Double-vote prevention
- ✅ Fraud detection & logging
- ✅ Trust score algorithm
- ✅ Blockchain-style vote hash (SHA-256)
- ✅ Live results chart (Chart.js)
- ✅ Auto-refreshing admin dashboard
- ✅ Vote ledger with all hashes

## 🎤 Demo Script for Judges
1. Open login → enter demo credentials → Send OTP
2. Copy OTP shown on screen → Verify
3. Select a candidate → Submit Vote
4. Show success page with blockchain hash
5. Go to /admin → show live chart + trust score
6. Try voting again from same ID → show fraud detection
