"""
============================================================
 AR Nuclear Reactor Safety Monitor — Flask Backend v2.0
============================================================
 Features:
   - User Auth (signup / login with JWT tokens)
   - Serial port reader (thread)
   - Supabase (PostgreSQL) storage
   - REST endpoints for frontend/AR
   - Basic AI anomaly prediction (scikit-learn)
   - Alert logging system
   - CORS enabled

 Install:
   pip install flask flask-cors pyserial supabase scikit-learn numpy python-dotenv PyJWT bcrypt

 Run:
   python app.py
============================================================
"""

import os, json, time, threading, math, random
import numpy as np
from datetime import datetime, timezone, timedelta
from collections import deque
from functools import wraps
from flask import Flask, jsonify, request, abort
from flask_cors import CORS
from dotenv import load_dotenv

try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    print("⚠  supabase-py not installed – local-only mode")

try:
    from sklearn.ensemble import IsolationForest
    SK_AVAILABLE = True
except ImportError:
    SK_AVAILABLE = False

try:
    import jwt, bcrypt
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False
    print("⚠  PyJWT/bcrypt missing. Install: pip install PyJWT bcrypt")

load_dotenv()

app = Flask(__name__)
CORS(app)

SUPABASE_URL      = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY      = os.getenv("SUPABASE_ANON_KEY", "")
SERIAL_PORT       = os.getenv("SERIAL_PORT", "COM3")
BAUD_RATE         = int(os.getenv("BAUD_RATE", "9600"))
DEMO_MODE         = os.getenv("DEMO_MODE", "true").lower() == "true"
JWT_SECRET        = os.getenv("JWT_SECRET", "reactor-super-secret-key-change-in-production")
JWT_EXPIRY_HOURS  = int(os.getenv("JWT_EXPIRY_HOURS", "24"))

latest_reading = {}
history_buffer = deque(maxlen=100)
alerts_log     = deque(maxlen=200)
ai_model       = None
training_data  = []
MODEL_TRAINED  = False
_users_db      = {}
supabase       = None
_demo_tick     = 0

# ─── SUPABASE ────────────────────────────────────────────
def init_supabase():
    global supabase
    if SUPABASE_AVAILABLE and SUPABASE_URL and SUPABASE_KEY:
        try:
            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            print("✅ Supabase connected")
        except Exception as e:
            print(f"⚠  Supabase init failed: {e}")

# ═════════════════════════════════════════════════════════
#  AUTH
# ═════════════════════════════════════════════════════════

def hash_password(pw):
    if AUTH_AVAILABLE:
        return bcrypt.hashpw(pw.encode(), bcrypt.gensalt())
    return pw.encode()

def check_password(pw, hashed):
    if AUTH_AVAILABLE:
        return bcrypt.checkpw(pw.encode(), hashed)
    return pw.encode() == hashed

def generate_token(email):
    if AUTH_AVAILABLE:
        payload = {
            "sub": email,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
        }
        return jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    return f"dummy-token-{email}"

def verify_token(token):
    if AUTH_AVAILABLE:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            return payload.get("sub")
        except Exception:
            return None
    if token.startswith("dummy-token-"):
        return token.replace("dummy-token-", "")
    return None

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        email = verify_token(auth.split(" ", 1)[1])
        if not email:
            return jsonify({"error": "Invalid or expired token"}), 401
        request.current_user = email
        return f(*args, **kwargs)
    return decorated

def find_user(email):
    if supabase:
        try:
            res = supabase.table("users").select("*").eq("email", email).limit(1).execute()
            if res.data:
                u = res.data[0]
                return {**u, "password_hash": u["password_hash"].encode()}
        except Exception:
            pass
    return _users_db.get(email)

def create_user(email, name, pw_hash):
    if supabase:
        try:
            supabase.table("users").insert({
                "email": email, "name": name,
                "password_hash": pw_hash.decode(),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }).execute()
            return
        except Exception as e:
            print(f"Supabase user insert error: {e}")
    _users_db[email] = {"email": email, "name": name, "password_hash": pw_hash}

# ─── AUTH ENDPOINTS ──────────────────────────────────────

@app.route("/api/auth/signup", methods=["POST"])
def auth_signup():
    data     = request.get_json(silent=True) or {}
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    name     = (data.get("name") or "").strip()
    if not email or not password or not name:
        return jsonify({"error": "email, password and name are required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    if find_user(email):
        return jsonify({"error": "Email already registered"}), 409
    create_user(email, name, hash_password(password))
    token = generate_token(email)
    return jsonify({"message": "Account created", "token": token, "user": {"email": email, "name": name}}), 201

@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    data     = request.get_json(silent=True) or {}
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400
    user = find_user(email)
    if not user or not check_password(password, user["password_hash"]):
        return jsonify({"error": "Invalid email or password"}), 401
    token = generate_token(email)
    return jsonify({"message": "Login successful", "token": token, "user": {"email": email, "name": user.get("name", "")}})

@app.route("/api/auth/me", methods=["GET"])
@require_auth
def auth_me():
    user = find_user(request.current_user)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"email": user["email"], "name": user.get("name", "")})

# ─── SAFETY THRESHOLDS ───────────────────────────────────
def compute_status(r):
    temp, gas, coolant = r.get("temperature", 0), r.get("gas_detected", False), r.get("coolant_level", 100)
    if temp >= 70 or (gas and temp >= 50) or coolant < 10:
        return "CRITICAL"
    if temp >= 50 or gas or coolant < 30:
        return "WARNING"
    return "SAFE"

def log_alert(reading):
    status = reading.get("status", "SAFE")
    if status == "SAFE":
        return
    reasons, temp, gas, coolant = [], reading.get("temperature",0), reading.get("gas_detected",False), reading.get("coolant_level",100)
    if temp >= 70:     reasons.append(f"CRITICAL TEMP: {temp}°C")
    elif temp >= 50:   reasons.append(f"High temp: {temp}°C")
    if gas:            reasons.append("Coolant gas leak detected")
    if coolant < 10:   reasons.append(f"Critical coolant: {coolant:.1f}%")
    elif coolant < 30: reasons.append(f"Low coolant: {coolant:.1f}%")
    alert = {"timestamp": datetime.now(timezone.utc).isoformat(), "status": status, "reasons": reasons, "reading": reading}
    alerts_log.appendleft(alert)
    if supabase:
        try:
            supabase.table("alerts").insert({"timestamp": alert["timestamp"], "status": status, "reasons": json.dumps(reasons), "temperature": reading.get("temperature"), "gas_detected": gas, "coolant_level": coolant}).execute()
        except Exception as e:
            print(f"Alert insert error: {e}")

# ─── AI ──────────────────────────────────────────────────
def extract_features(r):
    return [r.get("temperature", 0), r.get("gas_raw", 0), r.get("coolant_level", 100)]

def train_ai_model():
    global ai_model, MODEL_TRAINED
    if not SK_AVAILABLE or len(training_data) < 30: return
    try:
        ai_model = IsolationForest(n_estimators=100, contamination=0.1, random_state=42)
        ai_model.fit(np.array(training_data))
        MODEL_TRAINED = True
        print("✅ AI model trained on", len(training_data), "samples")
    except Exception as e:
        print(f"AI training error: {e}")

def predict_anomaly(r):
    if not MODEL_TRAINED or ai_model is None:
        return {"anomaly": False, "score": 0, "trained": False}
    try:
        feat = np.array([extract_features(r)])
        return {"anomaly": bool(ai_model.predict(feat)[0] == -1), "score": round(float(ai_model.score_samples(feat)[0]), 4), "trained": True}
    except Exception as e:
        return {"anomaly": False, "score": 0, "error": str(e)}

# ─── PROCESS READING ─────────────────────────────────────
def process_reading(data):
    global latest_reading
    data["timestamp"] = datetime.now(timezone.utc).isoformat()
    data["status"]    = compute_status(data)
    training_data.append(extract_features(data))
    if len(training_data) % 30 == 0:
        threading.Thread(target=train_ai_model, daemon=True).start()
    data["ai"]    = predict_anomaly(data)
    latest_reading = data
    history_buffer.appendleft(data)
    log_alert(data)
    if supabase:
        try:
            supabase.table("readings").insert({"timestamp": data["timestamp"], "temperature": data.get("temperature"), "humidity": data.get("humidity"), "gas_raw": data.get("gas_raw"), "gas_detected": data.get("gas_detected"), "coolant_level": data.get("coolant_level"), "distance_cm": data.get("distance_cm"), "status": data.get("status")}).execute()
        except Exception as e:
            print(f"Supabase insert error: {e}")

# ─── SERIAL / DEMO ───────────────────────────────────────
def serial_reader():
    while True:
        try:
            with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2) as ser:
                print(f"✅ Serial connected: {SERIAL_PORT}")
                while True:
                    line = ser.readline().decode("utf-8", errors="ignore").strip()
                    if line.startswith("{"):
                        try: process_reading(json.loads(line))
                        except json.JSONDecodeError: pass
        except Exception as e:
            print(f"Serial error: {e} — retrying in 5s"); time.sleep(5)

def demo_generator():
    global _demo_tick
    while True:
        _demo_tick += 1
        t = _demo_tick
        base_temp   = 35 + 20 * abs(math.sin(t / 60))
        temperature = round(base_temp + random.gauss(0, 1.5), 1)
        gas_raw     = int(200 + 300 * abs(math.sin(t / 45)) + random.gauss(0, 20))
        coolant     = round(70 - 40 * abs(math.sin(t / 90)) + random.gauss(0, 2), 1)
        process_reading({
            "temperature":   max(20, min(100, temperature)),
            "humidity":      round(45 + random.gauss(0, 3), 1),
            "gas_raw":       max(0, gas_raw),
            "gas_detected":  gas_raw > 400,
            "coolant_level": max(0, min(100, coolant)),
            "distance_cm":   round(20 + random.gauss(0, 2), 1),
        })
        time.sleep(2)

# ═════════════════════════════════════════════════════════
#  PROTECTED SENSOR ENDPOINTS
# ═════════════════════════════════════════════════════════

@app.route("/api/latest", methods=["GET"])
@require_auth
def api_latest():
    if not latest_reading: return jsonify({"error": "No data yet"}), 503
    return jsonify(latest_reading)

@app.route("/api/history", methods=["GET"])
@require_auth
def api_history():
    n = min(int(request.args.get("n", 50)), 100)
    return jsonify(list(history_buffer)[:n])

@app.route("/api/status", methods=["GET"])
@require_auth
def api_status():
    return jsonify({"status": latest_reading.get("status","UNKNOWN"), "temperature": latest_reading.get("temperature"), "coolant": latest_reading.get("coolant_level"), "gas": latest_reading.get("gas_detected"), "timestamp": latest_reading.get("timestamp")})

@app.route("/api/alerts", methods=["GET"])
@require_auth
def api_alerts():
    n = min(int(request.args.get("n", 50)), 200)
    return jsonify(list(alerts_log)[:n])

@app.route("/api/predict", methods=["GET"])
@require_auth
def api_predict():
    if not latest_reading: return jsonify({"error": "No data yet"}), 503
    return jsonify({"prediction": predict_anomaly(latest_reading), "model_trained": MODEL_TRAINED, "samples_collected": len(training_data)})

@app.route("/api/ar", methods=["GET"])
@require_auth
def api_ar():
    if not latest_reading: return jsonify({"error": "No data yet"}), 503
    return jsonify({"temperature": latest_reading.get("temperature",0), "gas_status": "LEAK" if latest_reading.get("gas_detected") else "OK", "coolant": latest_reading.get("coolant_level",0), "status": latest_reading.get("status","UNKNOWN"), "ai_anomaly": latest_reading.get("ai",{}).get("anomaly",False), "timestamp": latest_reading.get("timestamp")})

@app.route("/api/inject", methods=["POST"])
@require_auth
def api_inject():
    data = request.get_json(silent=True)
    if not data: abort(400, "JSON body required")
    process_reading(data)
    return jsonify({"ok": True, "status": latest_reading.get("status")})

@app.route("/api/health", methods=["GET"])
def api_health():
    return jsonify({"server":"online","demo_mode":DEMO_MODE,"ai_trained":MODEL_TRAINED,"samples":len(training_data),"alerts":len(alerts_log),"supabase":supabase is not None,"auth":AUTH_AVAILABLE})

@app.route("/", methods=["GET"])
def index():
    return jsonify({"message": "Reactor Safety API v2.0 — POST /api/auth/login to authenticate"})

if __name__ == "__main__":
    init_supabase()
    if DEMO_MODE:
        print("🔬 DEMO MODE: Generating simulated reactor data")
        threading.Thread(target=demo_generator, daemon=True).start()
    else:
        print(f"🔌 Connecting to Arduino on {SERIAL_PORT}...")
        threading.Thread(target=serial_reader, daemon=True).start()
    print("🚀 Flask API running on http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
