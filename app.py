from flask import Flask, render_template, request, jsonify, session
import sqlite3
import os
import time
import shutil
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.secret_key = os.environ.get("SKILLSWAP_SECRET_KEY", "skillswap-india-change-this-secret-key")
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

DATABASE = os.environ.get("SKILLSWAP_DATABASE", "skillswap.db")
RATE_BUCKET = {}


# =========================================================
# DATABASE
# =========================================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def rate_limit(key, limit=60, window=60):
    now = time.time()
    bucket = RATE_BUCKET.setdefault(key, [])
    bucket[:] = [t for t in bucket if now - t < window]
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True

def add_audit(action, user_id=None, metadata=""):
    try:
        conn = get_db()
        conn.execute("INSERT INTO audit_logs(user_id,action,metadata) VALUES (?,?,?)", (user_id, action, metadata[:1000]))
        conn.commit(); conn.close()
    except Exception:
        pass

def require_user():
    u = current_user()
    if not u:
        return None, (jsonify({"success":False,"message":"Sign in required"}), 401)
    return u, None

def require_admin():
    u = current_user()
    if not u or not u.get("is_admin"):
        return None, (jsonify({"success":False,"message":"Admin access required"}), 403)
    return u, None

@app.before_request
def security_and_rate_limit():
    if request.path.startswith('/api/') and request.method in ('POST','PUT','PATCH','DELETE'):
        ip = request.headers.get('X-Forwarded-For', request.remote_addr or 'unknown').split(',')[0].strip()
        if not rate_limit(ip, 120, 60):
            return jsonify({"success":False,"message":"Too many requests. Please try again shortly."}), 429

@app.after_request
def security_headers(response):
    response.headers.setdefault('X-Content-Type-Options','nosniff')
    response.headers.setdefault('X-Frame-Options','SAMEORIGIN')
    response.headers.setdefault('Referrer-Policy','strict-origin-when-cross-origin')
    response.headers.setdefault('Permissions-Policy','geolocation=(), microphone=(), camera=()')
    return response

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            user_type TEXT,
            location TEXT,
            languages TEXT,
            bio TEXT,
            teach TEXT,
            want TEXT,
            availability TEXT,
            avatar TEXT DEFAULT '🧑🏻',
            rating REAL DEFAULT 0,
            reviews INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            skill_wanted TEXT,
            skill_offered TEXT,
            message TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            accepted_at TIMESTAMP,
            FOREIGN KEY(sender_id) REFERENCES users(id),
            FOREIGN KEY(receiver_id) REFERENCES users(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(sender_id) REFERENCES users(id),
            FOREIGN KEY(receiver_id) REFERENCES users(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reviewer_id INTEGER NOT NULL,
            reviewed_id INTEGER NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(reviewer_id) REFERENCES users(id),
            FOREIGN KEY(reviewed_id) REFERENCES users(id)
        )
    """)

    cur.execute("CREATE TABLE IF NOT EXISTS audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action TEXT NOT NULL, metadata TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    cur.execute("CREATE TABLE IF NOT EXISTS subscriptions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER UNIQUE, plan TEXT DEFAULT 'free', status TEXT DEFAULT 'active', started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, expires_at TIMESTAMP, FOREIGN KEY(user_id) REFERENCES users(id))")
    cur.execute("CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY AUTOINCREMENT, reporter_id INTEGER, reported_id INTEGER, reason TEXT, details TEXT, status TEXT DEFAULT 'open', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, resolved_at TIMESTAMP)")
    cur.execute("CREATE TABLE IF NOT EXISTS feature_flags (key TEXT PRIMARY KEY, enabled INTEGER DEFAULT 1)")
    for col, typ, default in [("headline","TEXT","''"),("verified","INTEGER","0"),("is_admin","INTEGER","0"),("plan","TEXT","'free'")]:
        try: cur.execute(f"ALTER TABLE users ADD COLUMN {col} {typ} DEFAULT {default}")
        except sqlite3.OperationalError: pass
    cur.execute("CREATE INDEX IF NOT EXISTS idx_users_created ON users(created_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_requests_receiver_status ON requests(receiver_id,status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_pair ON messages(sender_id,receiver_id,created_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status)")
    conn.commit()

    # Add demo users only if database is empty
    count = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    if count == 0:
        demo_people = [
            (
                "Ananya Reddy",
                "ananya@skillswap.demo",
                "Teen Student",
                "Hyderabad, Telangana",
                "Telugu,Hindi,English",
                "School student who loves languages, technology and helping other students.",
                "Telugu,Hindi",
                "Python,AI",
                "After school,Weekends",
                "👩🏽",
                4.9,
                32
            ),
            (
                "Aarav Sharma",
                "aarav@skillswap.demo",
                "School Student",
                "Bengaluru, Karnataka",
                "Hindi,English,Kannada",
                "Young coding enthusiast building small robotics projects.",
                "Python,Robotics",
                "Guitar,Public Speaking",
                "Weekday evenings,Weekends",
                "👨🏽",
                4.8,
                27
            ),
            (
                "Meera Krishnan",
                "meera@skillswap.demo",
                "Teen Student",
                "Chennai, Tamil Nadu",
                "Tamil,English",
                "Learns classical Indian arts and enjoys creative projects.",
                "Bharatanatyam,Carnatic Music",
                "Graphic Design,Photography",
                "Weekends",
                "👩🏽",
                5,
                41
            ),
            (
                "Rohan Patel",
                "rohan@skillswap.demo",
                "College Student",
                "Pune, Maharashtra",
                "Hindi,Marathi,English",
                "Technology learner who enjoys explaining difficult ideas simply.",
                "Python,AI,Machine Learning",
                "Web Design,Video Editing",
                "Weekday evenings,Flexible",
                "👨🏽",
                5,
                46
            ),
            (
                "Saanvi Gupta",
                "saanvi@skillswap.demo",
                "Teen Student",
                "Delhi, India",
                "Hindi,English",
                "Student who enjoys maths, study techniques and music.",
                "Mathematics,Study Planning",
                "Spanish,Guitar",
                "After school,Weekends",
                "👩🏼",
                4.9,
                29
            ),
            (
                "Vikram Rao",
                "vikram@skillswap.demo",
                "Teen Student",
                "Vijayawada, Andhra Pradesh",
                "Telugu,English",
                "Cricket and chess fan who wants to explore technology.",
                "Cricket,Chess",
                "Python,Photography",
                "Weekends,Flexible",
                "👨🏽",
                4.8,
                21
            ),
            (
                "Ishita Singh",
                "ishita@skillswap.demo",
                "Teen Student",
                "Jaipur, Rajasthan",
                "Hindi,English",
                "Creative student interested in Indian art and digital design.",
                "Rangoli,Mehendi,Drawing",
                "Coding,Photography",
                "Weekends",
                "👩🏽",
                4.9,
                36
            ),
            (
                "Aditya Nair",
                "aditya@skillswap.demo",
                "College Student",
                "Kochi, Kerala",
                "Malayalam,Hindi,English",
                "Science student who loves practical experiments.",
                "Physics,Science Projects",
                "Video Editing,Guitar",
                "Weekday evenings,Flexible",
                "👨🏽",
                4.7,
                18
            ),
            (
                "Kavya Das",
                "kavya@skillswap.demo",
                "Teen Student",
                "Kolkata, West Bengal",
                "Bengali,Hindi,English",
                "Language lover and young writer.",
                "Bengali,Creative Writing",
                "Python,Public Speaking",
                "Weekends",
                "👩🏽",
                4.8,
                25
            ),
            (
                "Dev Malhotra",
                "dev@skillswap.demo",
                "Teen Student",
                "Mumbai, Maharashtra",
                "Hindi,English",
                "Music and video creator who loves learning new skills.",
                "Guitar,Video Editing",
                "Tabla,Cricket",
                "Weekday evenings,Weekends",
                "👨🏻",
                4.8,
                30
            ),
            (
                "Priya Sharma",
                "priya@skillswap.demo",
                "College Student",
                "Hyderabad, Telangana",
                "Telugu,Hindi,English",
                "Home cook who enjoys sharing Indian recipes.",
                "Indian Cooking,Biryani",
                "Baking,Photography",
                "Weekends,Flexible",
                "👩🏾",
                5,
                52
            ),
            (
                "Arjun Mehta",
                "arjun@skillswap.demo",
                "Teen Student",
                "Ahmedabad, Gujarat",
                "Hindi,Gujarati,English",
                "Sports enthusiast who wants to learn technology and music.",
                "Cricket,Football",
                "Coding,Guitar",
                "Weekends",
                "👨🏽",
                4.8,
                27
            )
        ]

        for person in demo_people:
            cur.execute("""
                INSERT INTO users
                (
                    name,email,password,user_type,location,
                    languages,bio,teach,want,availability,
                    avatar,rating,reviews
                )
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                person[0],
                person[1],
                generate_password_hash("demo123"),
                person[2],
                person[3],
                person[4],
                person[5],
                person[6],
                person[7],
                person[8],
                person[9],
                person[10],
                person[11]
            ))

    conn.execute("UPDATE users SET is_admin=1, plan='pro' WHERE email='admin@skillswap.demo'")
    if not conn.execute("SELECT id FROM users WHERE email='admin@skillswap.demo'").fetchone():
        conn.execute("INSERT INTO users(name,email,password,user_type,location,languages,bio,teach,want,availability,avatar,rating,reviews,is_admin,plan) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("SkillSwap Admin","admin@skillswap.demo",generate_password_hash("admin123"),"Admin","India","English,Hindi","Platform administrator.","Community Support","Platform Insights","Flexible","🛡️",5,0,1,"pro"))
    conn.execute("INSERT OR IGNORE INTO feature_flags(key,enabled) VALUES ('pro_enabled',1),('campus_enabled',1),('verification_enabled',1),('maintenance_mode',0)")
    conn.commit()
    conn.close()


# =========================================================
# HELPERS
# =========================================================

def split_values(value):
    if not value:
        return []

    return [
        item.strip()
        for item in value.split(",")
        if item.strip()
    ]


def user_to_dict(row):
    if not row:
        return None

    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "type": row["user_type"],
        "location": row["location"],
        "languages": split_values(row["languages"]),
        "bio": row["bio"],
        "teach": split_values(row["teach"]),
        "want": split_values(row["want"]),
        "availability": split_values(row["availability"]),
        "avatar": row["avatar"],
        "rating": row["rating"],
        "reviews": row["reviews"],
        "headline": row["headline"] if "headline" in row.keys() else "",
        "verified": row["verified"] if "verified" in row.keys() else 0,
        "is_admin": row["is_admin"] if "is_admin" in row.keys() else 0,
        "plan": row["plan"] if "plan" in row.keys() else "free"
    }


def current_user():
    user_id = session.get("user_id")

    if not user_id:
        return None

    conn = get_db()
    row = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    conn.close()

    return user_to_dict(row)


def normalize(value):
    if not value:
        return ""

    return "".join(
        char.lower()
        for char in str(value)
        if char.isalnum() or char in " +#"
    ).strip()


def skill_matches(a, b):
    x = normalize(a)
    y = normalize(b)

    if not x or not y:
        return False

    if x == y:
        return True

    aliases = [
        ["javascript", "js"],
        ["python", "py"],
        ["ai", "artificial intelligence", "machine learning", "ml"],
        ["math", "maths", "mathematics"],
        ["drawing", "art"]
    ]

    for group in aliases:
        if x in group and y in group:
            return True

    return x in y or y in x


def overlap(list_a, list_b):
    count = 0

    for a in list_a:
        for b in list_b:
            if skill_matches(a, b):
                count += 1

    return count


def calculate_match(user, person):
    if not user:
        return {
            "score": 85,
            "reasons": [
                "Complementary skills",
                "Active member"
            ]
        }

    score = 35
    reasons = []

    learn = overlap(user["want"], person["teach"])
    teach = overlap(user["teach"], person["want"])
    language = overlap(user["languages"], person["languages"])
    availability = overlap(
        user["availability"],
        person["availability"]
    )

    if learn:
        score += min(28, learn * 14)
        reasons.append("They teach what you want")

    if teach:
        score += min(22, teach * 11)
        reasons.append("They want what you teach")

    if language:
        score += min(8, language * 4)
        reasons.append("Shared language")

    if availability:
        score += min(7, availability * 4)
        reasons.append("Matching availability")

    city_a = user["location"].split(",")[0].strip().lower()
    city_b = person["location"].split(",")[0].strip().lower()

    if city_a and city_b and city_a == city_b:
        score += 8
        reasons.append("Same city")

    if user["type"] and person["type"]:
        if "Student" in user["type"] and "Student" in person["type"]:
            score += 4

    if not reasons:
        reasons.append("Good general compatibility")

    return {
        "score": min(99, max(50, round(score))),
        "reasons": reasons[:2]
    }


# =========================================================
# PAGE
# =========================================================

@app.route("/")
def index():
    return render_template("index.html")


# =========================================================
# AUTH
# =========================================================

@app.route("/api/signup", methods=["POST"])
def signup():
    data = request.get_json() or {}

    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "").strip()

    if not name or not email or not password:
        return jsonify({
            "success": False,
            "message": "Please fill in your name, email and password."
        }), 400

    if len(password) < 6:
        return jsonify({
            "success": False,
            "message": "Password must be at least 6 characters."
        }), 400

    conn = get_db()

    existing = conn.execute(
        "SELECT id FROM users WHERE email = ?",
        (email,)
    ).fetchone()

    if existing:
        conn.close()

        return jsonify({
            "success": False,
            "message": "An account with this email already exists."
        }), 409

    languages = data.get("languages", [])
    teach = data.get("teach", [])
    want = data.get("want", [])
    availability = data.get("availability", [])

    if isinstance(languages, list):
        languages = ",".join(languages)

    if isinstance(teach, list):
        teach = ",".join(teach)

    if isinstance(want, list):
        want = ",".join(want)

    if isinstance(availability, list):
        availability = ",".join(availability)

    cur = conn.execute("""
        INSERT INTO users
        (
            name,email,password,user_type,location,
            languages,bio,teach,want,availability,avatar
        )
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (
        name,
        email,
        generate_password_hash(password),
        data.get("type", "Young Learner"),
        data.get("location", "Online"),
        languages or "English",
        data.get("bio", "Learning and sharing skills."),
        teach or "Knowledge Sharing",
        want or "Something New",
        availability or "Flexible",
        "🧑🏻"
    ))

    conn.commit()

    user_id = cur.lastrowid

    row = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    conn.close()

    session["user_id"] = user_id
    add_audit("signup", user_id, email)

    return jsonify({
        "success": True,
        "user": user_to_dict(row)
    })


@app.route("/api/signin", methods=["POST"])
def signin():
    data = request.get_json() or {}

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    conn = get_db()

    row = conn.execute(
        "SELECT * FROM users WHERE email = ?",
        (email,)
    ).fetchone()

    conn.close()

    if not row:
        return jsonify({
            "success": False,
            "message": "Account not found."
        }), 404

    if not check_password_hash(row["password"], password):
        return jsonify({
            "success": False,
            "message": "Incorrect email or password."
        }), 401

    session["user_id"] = row["id"]
    add_audit("signin", row["id"], email)

    return jsonify({
        "success": True,
        "user": user_to_dict(row)
    })


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()

    return jsonify({
        "success": True
    })


@app.route("/api/me")
def me():
    user = current_user()

    return jsonify({
        "logged_in": bool(user),
        "user": user
    })


# =========================================================
# PEOPLE / MATCHING
# =========================================================

@app.route("/api/people")
def people():
    user = current_user()

    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM users ORDER BY created_at DESC"
    ).fetchall()
    conn.close()

    result = []

    for row in rows:
        person = user_to_dict(row)

        if user and person["id"] == user["id"]:
            continue

        match = calculate_match(user, person)

        person["match"] = match["score"]
        person["reasons"] = match["reasons"]

        result.append(person)

    result.sort(
        key=lambda person: person["match"],
        reverse=True
    )

    return jsonify(result)


# =========================================================
# REQUESTS
# =========================================================

@app.route("/api/requests", methods=["GET"])
def get_requests_api():
    user = current_user()

    if not user:
        return jsonify([])

    conn = get_db()

    rows = conn.execute("""
        SELECT
            r.*,
            u.name AS receiver_name,
            u.avatar AS receiver_avatar
        FROM requests r
        JOIN users u ON u.id = r.receiver_id
        WHERE r.sender_id = ?
        ORDER BY r.id DESC
    """, (user["id"],)).fetchall()

    conn.close()

    result = []

    for row in rows:
        result.append({
            "id": row["id"],
            "receiverId": row["receiver_id"],
            "receiverName": row["receiver_name"],
            "receiverAvatar": row["receiver_avatar"],
            "skillWanted": row["skill_wanted"],
            "skillOffered": row["skill_offered"],
            "message": row["message"],
            "status": row["status"],
            "createdAt": row["created_at"]
        })

    return jsonify(result)


@app.route("/api/requests", methods=["POST"])
def create_request():
    user = current_user()

    if not user:
        return jsonify({
            "success": False,
            "message": "Please sign in first."
        }), 401

    data = request.get_json() or {}

    receiver_id = data.get("receiverId")
    wanted = data.get("wanted", "").strip()
    offered = data.get("offered", "").strip()
    message = data.get(
        "message",
        "I'd love to exchange skills with you!"
    ).strip()

    if not receiver_id or not wanted or not offered:
        return jsonify({
            "success": False,
            "message": "Please enter both skills."
        }), 400

    if int(receiver_id) == int(user["id"]):
        return jsonify({
            "success": False,
            "message": "You cannot send a request to yourself."
        }), 400

    conn = get_db()

    existing = conn.execute("""
        SELECT id
        FROM requests
        WHERE
        (sender_id = ? AND receiver_id = ?)
        OR
        (sender_id = ? AND receiver_id = ?)
    """, (
        user["id"],
        receiver_id,
        receiver_id,
        user["id"]
    )).fetchone()

    if existing:
        conn.close()

        return jsonify({
            "success": False,
            "message": "You already have a request with this member."
        }), 409

    conn.execute("""
        INSERT INTO requests
        (
            sender_id,
            receiver_id,
            skill_wanted,
            skill_offered,
            message
        )
        VALUES (?,?,?,?,?)
    """, (
        user["id"],
        receiver_id,
        wanted,
        offered,
        message
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Skill-swap request sent!"
    })


@app.route("/api/requests/incoming")
def incoming_requests():
    user = current_user()

    if not user:
        return jsonify([])

    conn = get_db()

    rows = conn.execute("""
        SELECT
            r.*,
            u.name AS sender_name,
            u.avatar AS sender_avatar
        FROM requests r
        JOIN users u ON u.id = r.sender_id
        WHERE r.receiver_id = ?
        ORDER BY r.id DESC
    """, (user["id"],)).fetchall()

    conn.close()

    return jsonify([
        {
            "id": row["id"],
            "senderId": row["sender_id"],
            "senderName": row["sender_name"],
            "senderAvatar": row["sender_avatar"],
            "skillWanted": row["skill_wanted"],
            "skillOffered": row["skill_offered"],
            "message": row["message"],
            "status": row["status"]
        }
        for row in rows
    ])


@app.route("/api/requests/<int:request_id>", methods=["POST"])
def update_request(request_id):
    user = current_user()

    if not user:
        return jsonify({
            "success": False,
            "message": "Please sign in."
        }), 401

    data = request.get_json() or {}
    action = data.get("action")

    conn = get_db()

    row = conn.execute("""
        SELECT *
        FROM requests
        WHERE id = ? AND receiver_id = ?
    """, (
        request_id,
        user["id"]
    )).fetchone()

    if not row:
        conn.close()

        return jsonify({
            "success": False,
            "message": "Request not found."
        }), 404

    if action == "accept":
        conn.execute("""
            UPDATE requests
            SET status = 'accepted',
                accepted_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (request_id,))

    elif action == "reject":
        conn.execute("""
            UPDATE requests
            SET status = 'rejected'
            WHERE id = ?
        """, (request_id,))

    else:
        conn.close()

        return jsonify({
            "success": False,
            "message": "Invalid action."
        }), 400

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"Request {action}ed."
    })


# =========================================================
# CONNECTIONS
# =========================================================

@app.route("/api/connections")
def connections():
    user = current_user()

    if not user:
        return jsonify([])

    conn = get_db()

    rows = conn.execute("""
        SELECT
            r.*,
            u.id AS person_id,
            u.name AS person_name,
            u.avatar AS person_avatar
        FROM requests r
        JOIN users u
        ON u.id =
            CASE
                WHEN r.sender_id = ? THEN r.receiver_id
                ELSE r.sender_id
            END
        WHERE
            r.status = 'accepted'
            AND
            (r.sender_id = ? OR r.receiver_id = ?)
        ORDER BY r.accepted_at DESC
    """, (
        user["id"],
        user["id"],
        user["id"]
    )).fetchall()

    conn.close()

    return jsonify([
        {
            "id": row["person_id"],
            "name": row["person_name"],
            "avatar": row["person_avatar"]
        }
        for row in rows
    ])


# =========================================================
# CHAT
# =========================================================

@app.route("/api/messages/<int:person_id>")
def get_messages(person_id):
    user = current_user()

    if not user:
        return jsonify({
            "success": False,
            "message": "Please sign in."
        }), 401

    conn = get_db()

    connection = conn.execute("""
        SELECT id
        FROM requests
        WHERE
            status = 'accepted'
            AND
            (
                (sender_id = ? AND receiver_id = ?)
                OR
                (sender_id = ? AND receiver_id = ?)
            )
        LIMIT 1
    """, (
        user["id"],
        person_id,
        person_id,
        user["id"]
    )).fetchone()

    if not connection:
        conn.close()

        return jsonify({
            "success": False,
            "message": "Your request has not been accepted yet."
        }), 403

    rows = conn.execute("""
        SELECT
            m.*,
            u.name AS sender_name
        FROM messages m
        JOIN users u ON u.id = m.sender_id
        WHERE
            (m.sender_id = ? AND m.receiver_id = ?)
            OR
            (m.sender_id = ? AND m.receiver_id = ?)
        ORDER BY m.id ASC
    """, (
        user["id"],
        person_id,
        person_id,
        user["id"]
    )).fetchall()

    conn.close()

    return jsonify([
        {
            "id": row["id"],
            "type": "me" if row["sender_id"] == user["id"] else "them",
            "text": row["message"],
            "sender": row["sender_name"],
            "createdAt": row["created_at"]
        }
        for row in rows
    ])


@app.route("/api/messages/<int:person_id>", methods=["POST"])
def send_message(person_id):
    user = current_user()

    if not user:
        return jsonify({
            "success": False,
            "message": "Please sign in."
        }), 401

    data = request.get_json() or {}
    message = data.get("message", "").strip()

    if not message:
        return jsonify({
            "success": False,
            "message": "Message cannot be empty."
        }), 400

    conn = get_db()

    connection = conn.execute("""
        SELECT id
        FROM requests
        WHERE
            status = 'accepted'
            AND
            (
                (sender_id = ? AND receiver_id = ?)
                OR
                (sender_id = ? AND receiver_id = ?)
            )
        LIMIT 1
    """, (
        user["id"],
        person_id,
        person_id,
        user["id"]
    )).fetchone()

    if not connection:
        conn.close()

        return jsonify({
            "success": False,
            "message": "You are not connected with this member."
        }), 403

    conn.execute("""
        INSERT INTO messages
        (
            sender_id,
            receiver_id,
            message
        )
        VALUES (?,?,?)
    """, (
        user["id"],
        person_id,
        message
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "success": True
    })


# =========================================================
# REVIEWS
# =========================================================

@app.route("/api/reviews/<int:person_id>", methods=["POST"])
def create_review(person_id):
    user = current_user()

    if not user:
        return jsonify({
            "success": False,
            "message": "Please sign in."
        }), 401

    data = request.get_json() or {}

    try:
        rating = int(data.get("rating"))
    except:
        rating = 0

    comment = data.get("comment", "").strip()

    if rating < 1 or rating > 5:
        return jsonify({
            "success": False,
            "message": "Rating must be between 1 and 5."
        }), 400

    conn = get_db()

    connection = conn.execute("""
        SELECT id
        FROM requests
        WHERE
            status = 'accepted'
            AND
            (
                (sender_id = ? AND receiver_id = ?)
                OR
                (sender_id = ? AND receiver_id = ?)
            )
        LIMIT 1
    """, (
        user["id"],
        person_id,
        person_id,
        user["id"]
    )).fetchone()

    if not connection:
        conn.close()

        return jsonify({
            "success": False,
            "message": "You need a connection before reviewing."
        }), 403

    existing = conn.execute("""
        SELECT id
        FROM reviews
        WHERE reviewer_id = ? AND reviewed_id = ?
    """, (
        user["id"],
        person_id
    )).fetchone()

    if existing:
        conn.close()

        return jsonify({
            "success": False,
            "message": "You already reviewed this member."
        }), 409

    conn.execute("""
        INSERT INTO reviews
        (
            reviewer_id,
            reviewed_id,
            rating,
            comment
        )
        VALUES (?,?,?,?)
    """, (
        user["id"],
        person_id,
        rating,
        comment
    ))

    stats = conn.execute("""
        SELECT
            AVG(rating) AS average_rating,
            COUNT(*) AS total_reviews
        FROM reviews
        WHERE reviewed_id = ?
    """, (person_id,)).fetchone()

    conn.execute("""
        UPDATE users
        SET rating = ?,
            reviews = ?
        WHERE id = ?
    """, (
        round(stats["average_rating"], 1),
        stats["total_reviews"],
        person_id
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Review submitted!"
    })



# =========================================================
# SKILLSWAP 6.0 / COMMUNITY FEATURES
# =========================================================
def init_v6_db():
    conn=get_db(); c=conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS campuses (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER UNIQUE, college TEXT, university TEXT, city TEXT, course TEXT, year TEXT, visibility INTEGER DEFAULT 1, FOREIGN KEY(user_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS skill_verifications (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, skill TEXT, level TEXT DEFAULT 'Intermediate', evidence TEXT, status TEXT DEFAULT 'pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, verified_at TIMESTAMP, FOREIGN KEY(user_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS learning_paths (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, title TEXT, description TEXT, progress INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(user_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS learning_path_steps (id INTEGER PRIMARY KEY AUTOINCREMENT, path_id INTEGER, title TEXT, done INTEGER DEFAULT 0, position INTEGER DEFAULT 0, FOREIGN KEY(path_id) REFERENCES learning_paths(id));
    CREATE TABLE IF NOT EXISTS achievements (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, title TEXT, description TEXT, icon TEXT);
    CREATE TABLE IF NOT EXISTS user_achievements (user_id INTEGER, achievement_id INTEGER, earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(user_id,achievement_id), FOREIGN KEY(user_id) REFERENCES users(id), FOREIGN KEY(achievement_id) REFERENCES achievements(id));
    CREATE TABLE IF NOT EXISTS reputation_events (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, kind TEXT, points INTEGER, note TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(user_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS session_reminders (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER, user_id INTEGER, minutes_before INTEGER DEFAULT 60, sent INTEGER DEFAULT 0);
    """)
    seeds=[('first_swap','First Skill Exchange','Complete your first accepted connection','🤝'),('verified_skill','Verified Skill','Get a skill verified','✅'),('five_sessions','5 Sessions','Complete five learning sessions','🎓'),('ten_connections','10 Connections','Build ten accepted connections','🌐'),('helpful_teacher','Helpful Teacher','Receive a 5-star review','⭐'),('streak_7','7 Day Streak','Stay active for seven days','🔥')]
    for a in seeds:
        c.execute('INSERT OR IGNORE INTO achievements(code,title,description,icon) VALUES (?,?,?,?)',a)
    conn.commit(); conn.close()

def v6_user():
    return current_user()

def award(uid, code):
    conn=get_db(); a=conn.execute('SELECT id FROM achievements WHERE code=?',(code,)).fetchone()
    if a: conn.execute('INSERT OR IGNORE INTO user_achievements(user_id,achievement_id) VALUES (?,?)',(uid,a['id']))
    conn.commit(); conn.close()

def v6_connections_count(uid):
    conn=get_db(); n=conn.execute("SELECT COUNT(*) n FROM requests WHERE status='accepted' AND (sender_id=? OR receiver_id=?)",(uid,uid)).fetchone()['n']; conn.close(); return n

@app.route('/api/campus', methods=['GET','POST'])
def campus_api():
    u=v6_user()
    if not u: return jsonify({'success':False,'message':'Sign in required'}),401
    conn=get_db()
    if request.method=='POST':
        d=request.get_json() or {}
        conn.execute('INSERT INTO campuses(user_id,college,university,city,course,year,visibility) VALUES (?,?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET college=excluded.college,university=excluded.university,city=excluded.city,course=excluded.course,year=excluded.year,visibility=excluded.visibility',(u['id'],d.get('college','').strip(),d.get('university','').strip(),d.get('city','').strip(),d.get('course','').strip(),d.get('year','').strip(),1 if d.get('visibility',True) else 0)); conn.commit()
    r=conn.execute('SELECT * FROM campuses WHERE user_id=?',(u['id'],)).fetchone(); conn.close()
    return jsonify(dict(r) if r else {})

@app.route('/api/campus/members')
def campus_members():
    u=v6_user()
    if not u: return jsonify([])
    conn=get_db(); r=conn.execute("""SELECT u.id,u.name,u.avatar,u.location,u.teach,u.want,u.rating,u.reviews,c.college,c.university,c.course,c.year FROM users u JOIN campuses c ON c.user_id=u.id WHERE c.visibility=1 AND u.id<>? ORDER BY u.name""",(u['id'],)).fetchall(); conn.close(); return jsonify([dict(x) for x in r])

@app.route('/api/verifications', methods=['GET','POST'])
def verifications():
    u=v6_user()
    if not u: return jsonify({'success':False,'message':'Sign in required'}),401
    conn=get_db()
    if request.method=='POST':
        d=request.get_json() or {}; skill=str(d.get('skill','')).strip(); level=str(d.get('level','Intermediate')).strip(); evidence=str(d.get('evidence','')).strip()
        if not skill: conn.close(); return jsonify({'success':False,'message':'Enter a skill.'}),400
        conn.execute('INSERT INTO skill_verifications(user_id,skill,level,evidence) VALUES (?,?,?,?)',(u['id'],skill,level,evidence)); conn.commit()
    rows=conn.execute('SELECT * FROM skill_verifications WHERE user_id=? ORDER BY created_at DESC',(u['id'],)).fetchall(); conn.close(); return jsonify([dict(x) for x in rows])

@app.route('/api/learning-paths', methods=['GET','POST'])
def paths_api():
    u=v6_user()
    if not u: return jsonify({'success':False,'message':'Sign in required'}),401
    conn=get_db()
    if request.method=='POST':
        d=request.get_json() or {}; title=str(d.get('title','')).strip(); desc=str(d.get('description','')).strip(); steps=d.get('steps') or []
        if not title: conn.close(); return jsonify({'success':False,'message':'Path title is required.'}),400
        cur=conn.execute('INSERT INTO learning_paths(user_id,title,description) VALUES (?,?,?)',(u['id'],title,desc)); pid=cur.lastrowid
        for i,step in enumerate(steps): conn.execute('INSERT INTO learning_path_steps(path_id,title,position) VALUES (?,?,?)',(pid,str(step).strip(),i))
        conn.commit()
    rows=conn.execute('SELECT * FROM learning_paths WHERE user_id=? ORDER BY created_at DESC',(u['id'],)).fetchall(); out=[]
    for x in rows:
        steps=conn.execute('SELECT * FROM learning_path_steps WHERE path_id=? ORDER BY position',(x['id'],)).fetchall(); out.append({**dict(x),'steps':[dict(z) for z in steps]})
    conn.close(); return jsonify(out)

@app.route('/api/learning-paths/<int:path_id>/step/<int:step_id>', methods=['POST'])
def path_step(path_id,step_id):
    u=v6_user()
    if not u:return jsonify({'success':False}),401
    conn=get_db(); ok=conn.execute("""UPDATE learning_path_steps SET done=CASE WHEN done=1 THEN 0 ELSE 1 END WHERE id=? AND path_id=? AND path_id IN (SELECT id FROM learning_paths WHERE user_id=?)""",(step_id,path_id,u['id'])).rowcount
    if ok: 
        total=conn.execute('SELECT COUNT(*) n FROM learning_path_steps WHERE path_id=?',(path_id,)).fetchone()['n']; done=conn.execute('SELECT COUNT(*) n FROM learning_path_steps WHERE path_id=? AND done=1',(path_id,)).fetchone()['n']; progress=round(done*100/total) if total else 0; conn.execute('UPDATE learning_paths SET progress=? WHERE id=?',(progress,path_id))
    conn.commit(); conn.close(); return jsonify({'success':bool(ok)})

@app.route('/api/achievements')
def achievements_api():
    u=v6_user()
    if not u:return jsonify([])
    # derive a few automatic achievements
    if v6_connections_count(u['id'])>=1: award(u['id'],'first_swap')
    conn=get_db(); rows=conn.execute("""SELECT a.*,ua.earned_at FROM achievements a LEFT JOIN user_achievements ua ON ua.achievement_id=a.id AND ua.user_id=? ORDER BY ua.earned_at DESC,a.id""",(u['id'],)).fetchall(); conn.close(); return jsonify([dict(x) for x in rows])

@app.route('/api/reputation')
def reputation_api():
    u=v6_user()
    if not u:return jsonify({'score':0,'events':[]})
    conn=get_db(); events=conn.execute('SELECT * FROM reputation_events WHERE user_id=? ORDER BY created_at DESC LIMIT 30',(u['id'],)).fetchall();
    conns=conn.execute("SELECT COUNT(*) n FROM requests WHERE status='accepted' AND (sender_id=? OR receiver_id=?)",(u['id'],u['id'])).fetchone()['n']; sessions=conn.execute("SELECT COUNT(*) n FROM sessions WHERE status='completed' AND (host_id=? OR guest_id=?)",(u['id'],u['id'])).fetchone()['n'] if conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'").fetchone() else 0
    score=min(1000,conns*20+sessions*40+(u.get('reviews') or 0)*15+int((u.get('rating') or 0)*10)); conn.close(); return jsonify({'score':score,'level':'Trusted' if score>=300 else 'Rising','events':[dict(x) for x in events]})

@app.route('/api/sessions', methods=['GET','POST'])
def sessions_api():
    u=v6_user()
    if not u:return jsonify({'success':False,'message':'Sign in required'}),401
    conn=get_db(); conn.execute("""CREATE TABLE IF NOT EXISTS sessions(id INTEGER PRIMARY KEY AUTOINCREMENT,host_id INTEGER,guest_id INTEGER,title TEXT,starts_at TEXT,duration_minutes INTEGER DEFAULT 60,notes TEXT,status TEXT DEFAULT 'scheduled',created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    if request.method=='POST':
        d=request.get_json() or {}; guest=int(d.get('guestId') or 0); title=str(d.get('title','SkillSwap Session')).strip(); start=str(d.get('startsAt','')).strip(); dur=max(15,min(240,int(d.get('durationMinutes') or 60))); notes=str(d.get('notes','')).strip()
        if not guest or not start: conn.close(); return jsonify({'success':False,'message':'Choose a partner and time.'}),400
        conn.execute('INSERT INTO sessions(host_id,guest_id,title,starts_at,duration_minutes,notes) VALUES (?,?,?,?,?,?)',(u['id'],guest,title,start,dur,notes)); conn.commit()
    rows=conn.execute("""SELECT s.*,h.name host_name,g.name guest_name FROM sessions s JOIN users h ON h.id=s.host_id JOIN users g ON g.id=s.guest_id WHERE s.host_id=? OR s.guest_id=? ORDER BY starts_at""",(u['id'],u['id'])).fetchall(); conn.close(); return jsonify([dict(x) for x in rows])

@app.route('/api/sessions/<int:sid>',methods=['POST'])
def session_update(sid):
    u=v6_user();
    if not u:return jsonify({'success':False}),401
    d=request.get_json() or {}; action=d.get('action'); status={'complete':'completed','cancel':'cancelled'}.get(action)
    if not status:return jsonify({'success':False,'message':'Invalid action'}),400
    conn=get_db(); conn.execute("CREATE TABLE IF NOT EXISTS sessions(id INTEGER PRIMARY KEY AUTOINCREMENT,host_id INTEGER,guest_id INTEGER,title TEXT,starts_at TEXT,duration_minutes INTEGER DEFAULT 60,notes TEXT,status TEXT DEFAULT 'scheduled',created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"); ok=conn.execute('UPDATE sessions SET status=? WHERE id=? AND (host_id=? OR guest_id=?)',(status,sid,u['id'],u['id'])).rowcount; conn.commit(); conn.close()
    if ok and status=='completed': award(u['id'],'five_sessions')
    return jsonify({'success':bool(ok)})

@app.route('/api/notifications', methods=['GET'])
def notifications_v6():
    u=v6_user()
    if not u:return jsonify([])
    # Keep the existing notifications route behavior if its table exists.
    conn=get_db(); conn.execute('CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,title TEXT,message TEXT,is_read INTEGER DEFAULT 0,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)'); rows=conn.execute('SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 30',(u['id'],)).fetchall(); conn.close(); return jsonify([dict(x) for x in rows])

@app.route('/api/smart-match')
def smart_match_api():
    u=v6_user()
    if not u:return jsonify([])
    conn=get_db(); people=conn.execute('SELECT * FROM users WHERE id<>?',(u['id'],)).fetchall(); me=user_to_dict(conn.execute('SELECT * FROM users WHERE id=?',(u['id'],)).fetchone()); out=[]
    for r in people:
        p=user_to_dict(r); m=calculate_match(me,p); out.append({**p,'match_score':m['score'],'reasons':m['reasons']})
    conn.close(); return jsonify(sorted(out,key=lambda x:x['match_score'],reverse=True)[:20])


# =========================================================
# SKILLSWAP 9.0 — SCALE, TRUST, ANALYTICS & MONETIZATION
# =========================================================

@app.route('/api/health')
def health():
    conn=get_db(); conn.execute('SELECT 1').fetchone(); conn.close()
    return jsonify({'status':'ok','service':'SkillSwap India','version':'9.0','time':datetime.utcnow().isoformat()+'Z'})

@app.route('/api/account/export')
def account_export():
    u,err=require_user()
    if err:return err
    conn=get_db()
    data={'profile':dict(conn.execute('SELECT * FROM users WHERE id=?',(u['id'],)).fetchone()),
          'requests':[dict(x) for x in conn.execute('SELECT * FROM requests WHERE sender_id=? OR receiver_id=?',(u['id'],u['id']))],
          'messages':[dict(x) for x in conn.execute('SELECT * FROM messages WHERE sender_id=? OR receiver_id=?',(u['id'],u['id']))],
          'reviews':[dict(x) for x in conn.execute('SELECT * FROM reviews WHERE reviewer_id=? OR reviewed_id=?',(u['id'],u['id']))]}
    conn.close(); add_audit('data_export',u['id'],'account')
    return jsonify(data)

@app.route('/api/account/delete',methods=['POST'])
def account_delete():
    u,err=require_user()
    if err:return err
    conn=get_db(); uid=u['id']
    for table,cols in [('messages','sender_id,receiver_id'),('requests','sender_id,receiver_id'),('reviews','reviewer_id,reviewed_id')]:
        a,b=cols.split(','); conn.execute(f'DELETE FROM {table} WHERE {a}=? OR {b}=?',(uid,uid))
    for table,col in [('campuses','user_id'),('skill_verifications','user_id'),('learning_paths','user_id'),('user_achievements','user_id'),('reputation_events','user_id'),('notifications','user_id'),('subscriptions','user_id'),('audit_logs','user_id')]:
        try: conn.execute(f'DELETE FROM {table} WHERE {col}=?',(uid,))
        except sqlite3.OperationalError: pass
    conn.execute('DELETE FROM users WHERE id=?',(uid,)); conn.commit(); conn.close(); session.clear()
    return jsonify({'success':True})

@app.route('/api/billing/plan',methods=['GET','POST'])
def billing_plan():
    u,err=require_user()
    if err:return err
    conn=get_db()
    if request.method=='POST':
        d=request.get_json() or {}; plan=d.get('plan','free')
        if plan not in ('free','pro','campus'): conn.close(); return jsonify({'success':False,'message':'Invalid plan'}),400
        conn.execute('INSERT INTO subscriptions(user_id,plan,status) VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET plan=excluded.plan,status="active"',(u['id'],plan))
        conn.execute('UPDATE users SET plan=? WHERE id=?',(plan,u['id'])); conn.commit(); add_audit('plan_changed',u['id'],plan)
    row=conn.execute('SELECT plan,status,started_at,expires_at FROM subscriptions WHERE user_id=?',(u['id'],)).fetchone(); conn.close()
    return jsonify(dict(row) if row else {'plan':u.get('plan','free'),'status':'active'})

@app.route('/api/admin/overview')
def admin_overview():
    u,err=require_admin()
    if err:return err
    conn=get_db()
    total=conn.execute('SELECT COUNT(*) n FROM users').fetchone()['n']; new7=conn.execute("SELECT COUNT(*) n FROM users WHERE datetime(created_at)>=datetime('now','-7 day')").fetchone()['n']
    req=conn.execute('SELECT COUNT(*) n FROM requests').fetchone()['n']; accepted=conn.execute("SELECT COUNT(*) n FROM requests WHERE status='accepted'").fetchone()['n']
    msgs=conn.execute('SELECT COUNT(*) n FROM messages').fetchone()['n']; reviews=conn.execute('SELECT COUNT(*) n FROM reviews').fetchone()['n']
    reports=conn.execute("SELECT COUNT(*) n FROM reports WHERE status='open'").fetchone()['n']; pro=conn.execute("SELECT COUNT(*) n FROM users WHERE plan!='free'").fetchone()['n']
    top=conn.execute("SELECT teach FROM users WHERE teach IS NOT NULL AND teach!='' LIMIT 500").fetchall(); conn.close()
    skills={}
    for r in top:
        for sk in split_values(r['teach']): skills[sk]=skills.get(sk,0)+1
    return jsonify({'version':'9.0','users':total,'new_users_7d':new7,'requests':req,'accepted_requests':accepted,'messages':msgs,'reviews':reviews,'open_reports':reports,'paid_or_campus_users':pro,'conversion_rate':round(accepted/req*100,1) if req else 0,'top_skills':sorted(skills.items(),key=lambda x:x[1],reverse=True)[:10]})

@app.route('/api/admin/users')
def admin_users():
    u,err=require_admin()
    if err:return err
    q=request.args.get('q','').strip(); limit=min(100,max(1,int(request.args.get('limit',50))))
    conn=get_db()
    if q: rows=conn.execute('SELECT id,name,email,user_type,location,rating,reviews,verified,is_admin,plan,created_at FROM users WHERE name LIKE ? OR email LIKE ? ORDER BY id DESC LIMIT ?',(f'%{q}%',f'%{q}%',limit)).fetchall()
    else: rows=conn.execute('SELECT id,name,email,user_type,location,rating,reviews,verified,is_admin,plan,created_at FROM users ORDER BY id DESC LIMIT ?',(limit,)).fetchall()
    conn.close(); return jsonify([dict(x) for x in rows])

@app.route('/api/admin/reports')
def admin_reports():
    u,err=require_admin()
    if err:return err
    conn=get_db(); conn.execute('CREATE TABLE IF NOT EXISTS reports(id INTEGER PRIMARY KEY AUTOINCREMENT,reporter_id INTEGER,reported_id INTEGER,reason TEXT,details TEXT,status TEXT DEFAULT "open",created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,resolved_at TIMESTAMP)')
    rows=conn.execute('SELECT r.*,a.name reporter_name,b.name reported_name FROM reports r LEFT JOIN users a ON a.id=r.reporter_id LEFT JOIN users b ON b.id=r.reported_id WHERE r.status="open" ORDER BY r.created_at DESC LIMIT 100').fetchall(); conn.close(); return jsonify([dict(x) for x in rows])

@app.route('/api/admin/reports/<int:rid>',methods=['POST'])
def admin_report_update(rid):
    u,err=require_admin()
    if err:return err
    status=(request.get_json() or {}).get('status','resolved')
    if status not in ('open','resolved','dismissed'): return jsonify({'success':False,'message':'Invalid status'}),400
    conn=get_db(); ok=conn.execute('UPDATE reports SET status=?,resolved_at=CURRENT_TIMESTAMP WHERE id=?',(status,rid)).rowcount; conn.commit(); conn.close(); add_audit('report_'+status,u['id'],str(rid)); return jsonify({'success':bool(ok)})

@app.route('/api/admin/audit')
def admin_audit():
    u,err=require_admin()
    if err:return err
    conn=get_db(); rows=conn.execute('SELECT a.*,u.name user_name FROM audit_logs a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.id DESC LIMIT 100').fetchall(); conn.close(); return jsonify([dict(x) for x in rows])

@app.route('/api/admin/flags',methods=['GET','POST'])
def admin_flags():
    u,err=require_admin()
    if err:return err
    conn=get_db()
    if request.method=='POST':
        d=request.get_json() or {}; key=d.get('key',''); enabled=1 if d.get('enabled') else 0
        if key: conn.execute('INSERT INTO feature_flags(key,enabled) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET enabled=excluded.enabled',(key,enabled)); conn.commit()
    rows=conn.execute('SELECT * FROM feature_flags ORDER BY key').fetchall(); conn.close(); return jsonify([dict(x) for x in rows])

@app.route('/api/admin/backup',methods=['POST'])
def admin_backup():
    u,err=require_admin()
    if err:return err
    target=f"skillswap_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    conn=get_db(); conn.execute('PRAGMA wal_checkpoint(FULL)'); conn.close(); shutil.copy2(DATABASE,target); add_audit('database_backup',u['id'],target)
    return jsonify({'success':True,'file':target,'message':'Backup created in the server folder.'})

@app.route('/api/report/<int:person_id>',methods=['POST'])
def create_report_9(person_id):
    u,err=require_user()
    if err:return err
    if person_id==u['id']: return jsonify({'success':False,'message':'You cannot report yourself.'}),400
    d=request.get_json() or {}; reason=str(d.get('reason','Other')).strip()[:120]; details=str(d.get('details','')).strip()[:1000]
    conn=get_db(); exists=conn.execute('SELECT id FROM users WHERE id=?',(person_id,)).fetchone()
    if not exists: conn.close(); return jsonify({'success':False,'message':'User not found.'}),404
    conn.execute('INSERT INTO reports(reporter_id,reported_id,reason,details) VALUES (?,?,?,?)',(u['id'],person_id,reason,details)); conn.commit(); conn.close(); add_audit('report_user',u['id'],str(person_id)); return jsonify({'success':True})

# =========================================================
# START SERVER
# =========================================================

if __name__ == "__main__":
    init_db()
    init_v6_db()

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )