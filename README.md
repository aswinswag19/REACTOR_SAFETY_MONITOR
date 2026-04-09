# ☢ AR-Assisted Nuclear Reactor Safety Monitoring using IoT Digital Twin

A complete, production-ready college project that simulates an industrial nuclear reactor safety system using Arduino sensors, a Python Flask backend with JWT authentication, a real-time web dashboard, and an Augmented Reality overlay.

---

## 📁 Project Structure

```
nuclear-reactor-safety/
│
├── arduino/
│   └── reactor_monitor.ino          ← Upload to Arduino Uno R4
│
├── backend/
│   ├── app.py                       ← Flask API server (with auth)
│   ├── requirements.txt             ← Python dependencies
│   ├── schema.sql                   ← Supabase DB schema (includes users table)
│   └── .env                         ← Config (edit before running)
│
├── frontend/
│   └── index.html                   ← Dashboard with login/signup
│
├── ar/
│   └── ar_overlay.html              ← WebAR module (AR.js + A-Frame)
│
└── README.md                        ← This file
```

---

## 🧰 Hardware Components

| Component | Purpose | Connection |
|-----------|---------|------------|
| Arduino Uno R4 | Microcontroller | USB to PC |
| DHT22 Sensor | Temperature & Humidity → Core Heat | Pin 2 |
| MQ-2 Gas Sensor | Coolant Leak Simulation | Pin A0 |
| HC-SR04 Ultrasonic | Coolant Level Simulation | Trig: 9, Echo: 10 |
| I2C LCD 16×2 | Local Display | SDA/SCL (A4/A5) |
| Buzzer | Alert Sound | Pin 6 |
| Green LED | SAFE indicator | Pin 3 + 220Ω |
| Yellow LED | WARNING indicator | Pin 5 + 220Ω |
| Red LED | CRITICAL indicator | Pin 4 + 220Ω |

> **Note:** The UV sensor has been removed from this version. The dashboard monitors Temperature, Humidity, Gas/Coolant Leak, and Coolant Level.

---

## 🔌 Circuit Wiring Guide

### DHT22 Temperature Sensor
```
DHT22 Pin 1 (VCC)  → Arduino 5V
DHT22 Pin 2 (DATA) → Arduino Pin 2  [+ 10kΩ pull-up to 5V]
DHT22 Pin 4 (GND)  → Arduino GND
```

### MQ-2 Gas Sensor
```
MQ-2 VCC  → Arduino 5V
MQ-2 GND  → Arduino GND
MQ-2 AOUT → Arduino A0
MQ-2 DOUT → (Not used)
Note: Allow 2-minute warmup before readings stabilise
```

### HC-SR04 Ultrasonic Sensor
```
HC-SR04 VCC  → Arduino 5V
HC-SR04 GND  → Arduino GND
HC-SR04 TRIG → Arduino Pin 9
HC-SR04 ECHO → Arduino Pin 10
Note: Place 10–100 cm above a water container to simulate coolant level
```

### I2C LCD 16×2
```
LCD VCC → Arduino 5V
LCD GND → Arduino GND
LCD SDA → Arduino A4 (SDA)
LCD SCL → Arduino A5 (SCL)
LCD I2C address: 0x27 (common) — change in code if needed
```

### LEDs & Buzzer
```
Green LED  → Arduino Pin 3 → 220Ω → GND   (SAFE)
Yellow LED → Arduino Pin 5 → 220Ω → GND   (WARNING)
Red LED    → Arduino Pin 4 → 220Ω → GND   (CRITICAL)
Buzzer (+) → Arduino Pin 6
Buzzer (-) → Arduino GND
```

---

## 🚀 Setup & Running

### 1. Backend (Flask API)

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Edit .env — set DEMO_MODE=true for testing without Arduino
# Set JWT_SECRET to a long random string in production

# Run
python app.py
```

The API will be available at `http://localhost:5000`.

### 2. Frontend

Open `frontend/index.html` directly in your browser — **no build step needed**.

You must create an account or log in before the dashboard loads sensor data.

### 3. Supabase (optional — for persistent storage)

1. Create a free project at [supabase.com](https://supabase.com)
2. Go to **SQL Editor** and run the contents of `backend/schema.sql`
3. Copy your **Project URL** and **anon key** from Project Settings → API
4. Paste them into `backend/.env`

---

## 🔐 Authentication Flow

All sensor API endpoints require a valid JWT Bearer token.

1. User signs up → `POST /api/auth/signup` → receives token
2. User logs in  → `POST /api/auth/login`  → receives token
3. Frontend stores token in `sessionStorage` and sends it as `Authorization: Bearer <token>` on every API call
4. Token expires after 24 hours (configurable via `JWT_EXPIRY_HOURS` in `.env`)

When Supabase is configured, users are stored in the `users` table. Without Supabase, users are kept in memory (lost on server restart — use Supabase for production).

---

## 📡 API Reference

### Public endpoints (no auth required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Server health check |
| POST | `/api/auth/signup` | Register new user |
| POST | `/api/auth/login` | Login and receive token |

### Protected endpoints (require `Authorization: Bearer <token>`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/auth/me` | Get current user info |
| GET | `/api/latest` | Latest sensor snapshot |
| GET | `/api/history?n=50` | Last N readings |
| GET | `/api/status` | Reactor status summary |
| GET | `/api/alerts?n=20` | Recent alert log |
| GET | `/api/predict` | AI anomaly prediction |
| GET | `/api/ar` | Lightweight AR endpoint |
| POST | `/api/inject` | Inject manual sensor data |

---

## 🧪 cURL Examples — Testing with Fake Data

### 1. Sign up a new user
```bash
curl -X POST http://localhost:5000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "operator@reactor.gov", "password": "reactor123", "name": "Dr. Jane Doe"}'
```
Response:
```json
{
  "message": "Account created",
  "token": "eyJ0eXAiOiJKV1Q...",
  "user": {"email": "operator@reactor.gov", "name": "Dr. Jane Doe"}
}
```

### 2. Login
```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "operator@reactor.gov", "password": "reactor123"}'
```

> **Save the token** from the response — use it as `TOKEN` below.

### 3. Get current sensor reading (protected)
```bash
curl http://localhost:5000/api/latest \
  -H "Authorization: Bearer TOKEN"
```

### 4. Inject a SAFE reading
```bash
curl -X POST http://localhost:5000/api/inject \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TOKEN" \
  -d '{
    "temperature": 32.5,
    "humidity": 45.2,
    "gas_raw": 150,
    "gas_detected": false,
    "coolant_level": 85.0,
    "distance_cm": 25.0
  }'
```

### 5. Inject a WARNING reading
```bash
curl -X POST http://localhost:5000/api/inject \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TOKEN" \
  -d '{
    "temperature": 54.0,
    "humidity": 51.3,
    "gas_raw": 450,
    "gas_detected": true,
    "coolant_level": 62.0,
    "distance_cm": 31.2
  }'
```

### 6. Inject a CRITICAL reading
```bash
curl -X POST http://localhost:5000/api/inject \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TOKEN" \
  -d '{
    "temperature": 76.0,
    "humidity": 58.1,
    "gas_raw": 820,
    "gas_detected": true,
    "coolant_level": 8.0,
    "distance_cm": 65.0
  }'
```

### 7. Get recent alerts
```bash
curl "http://localhost:5000/api/alerts?n=10" \
  -H "Authorization: Bearer TOKEN"
```

### 8. Get AI prediction
```bash
curl http://localhost:5000/api/predict \
  -H "Authorization: Bearer TOKEN"
```

### 9. Check server health (no auth needed)
```bash
curl http://localhost:5000/api/health
```

---

## 🧠 Safety Thresholds

| Sensor | Warning | Critical |
|--------|---------|----------|
| Temperature | ≥ 50°C | ≥ 70°C |
| Gas (Coolant Leak) | Detected | Detected + Temp ≥ 50°C |
| Coolant Level | < 30% | < 10% |

Overall status = highest severity among all active sensors.

---

## 🤖 AI Anomaly Detection

- Uses **Isolation Forest** (scikit-learn) for unsupervised anomaly detection
- Collects the first 30 readings as training data (normal baseline)
- Automatically retrains every 30 new readings
- Feature vector: `[temperature, gas_raw, coolant_level]`
- Anomaly score < 0 indicates unusual patterns

---

## 📊 Supabase Schema Summary

Run `backend/schema.sql` in the Supabase SQL Editor. It creates:

- `readings` — every sensor snapshot with timestamp and status
- `alerts` — WARNING/CRITICAL events with reasons
- `users` — registered users with hashed passwords

---

## 🎓 Technology Stack

| Layer | Technology |
|-------|-----------|
| Microcontroller | Arduino Uno R4 |
| Backend | Python 3.11 + Flask |
| Authentication | JWT (PyJWT) + bcrypt |
| Database | Supabase (PostgreSQL) |
| AI/ML | scikit-learn (Isolation Forest) |
| Frontend | Vanilla HTML/CSS/JS + Chart.js |
| AR Overlay | AR.js + A-Frame |
