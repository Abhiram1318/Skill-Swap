from flask import Flask, render_template, request, jsonify, session
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime, timedelta
import secrets
import smtplib
from email.message import EmailMessage

app = Flask(__name__)

app.secret_key = os.environ.get("SKILLSWAP_SECRET_KEY", "dev-only-change-this-secret-key")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SKILLSWAP_SECURE_COOKIE", "0") == "1"

DATABASE = os.environ.get("SKILLSWAP_DATABASE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "skillswap.db"))


# =========================================================
# DATABASE
# =========================================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


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

    # Extended platform tables (kept separate so older databases upgrade safely).
    cur.execute("""CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        kind TEXT NOT NULL, title TEXT NOT NULL, body TEXT, link TEXT,
        is_read INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, host_id INTEGER NOT NULL, guest_id INTEGER NOT NULL,
        title TEXT NOT NULL, starts_at TEXT NOT NULL, duration_minutes INTEGER DEFAULT 60,
        status TEXT DEFAULT 'scheduled', notes TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(host_id) REFERENCES users(id), FOREIGN KEY(guest_id) REFERENCES users(id)
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS listings (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, title TEXT NOT NULL,
        description TEXT, category TEXT, skill TEXT, mode TEXT DEFAULT 'online',
        status TEXT DEFAULT 'active', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT, reporter_id INTEGER NOT NULL, reported_id INTEGER NOT NULL,
        reason TEXT NOT NULL, details TEXT, status TEXT DEFAULT 'open', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(reporter_id) REFERENCES users(id), FOREIGN KEY(reported_id) REFERENCES users(id)
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS blocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT, blocker_id INTEGER NOT NULL, blocked_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(blocker_id, blocked_id),
        FOREIGN KEY(blocker_id) REFERENCES users(id), FOREIGN KEY(blocked_id) REFERENCES users(id)
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS badges (
        id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL, description TEXT NOT NULL, icon TEXT NOT NULL, xp INTEGER DEFAULT 0
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS user_badges (
        user_id INTEGER NOT NULL, badge_id INTEGER NOT NULL, earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id,badge_id),
        FOREIGN KEY(user_id) REFERENCES users(id), FOREIGN KEY(badge_id) REFERENCES badges(id)
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS password_resets (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, token_hash TEXT UNIQUE NOT NULL, expires_at TEXT NOT NULL, used INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS favorites (
        user_id INTEGER NOT NULL, listing_id INTEGER NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id,listing_id),
        FOREIGN KEY(user_id) REFERENCES users(id), FOREIGN KEY(listing_id) REFERENCES listings(id)
    )""")

    # Safe migrations for databases created by earlier SkillSwap versions.
    for col, definition in [("headline", "TEXT DEFAULT ''"), ("interests", "TEXT DEFAULT ''"), ("verified", "INTEGER DEFAULT 0"), ("is_admin", "INTEGER DEFAULT 0")]:
        try:
            cur.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")
        except sqlite3.OperationalError:
            pass

    badge_seed=[
        ("first_swap","First Swap","Sent your first skill-swap request.","🤝",25),
        ("connector","Community Connector","Made your first connection.","🔗",50),
        ("first_session","Session Starter","Completed your first learning session.","📚",75),
        ("mentor","Community Mentor","Received your first review.","🏆",100),
        ("five_sessions","Learning Streak","Completed five sessions.","🔥",150)
    ]
    for b in badge_seed:
        cur.execute("INSERT OR IGNORE INTO badges(code,name,description,icon,xp) VALUES(?,?,?,?,?)",b)

    admin_email=os.environ.get("SKILLSWAP_ADMIN_EMAIL","").strip().lower()
    if admin_email:
        cur.execute("UPDATE users SET is_admin=1 WHERE lower(email)=?", (admin_email,))
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
        "interests": split_values(row["interests"]) if "interests" in row.keys() else [],
        "verified": bool(row["verified"]) if "verified" in row.keys() else False,
        "category": ("Technology" if any(k in " ".join(split_values(row["teach"]) + split_values(row["want"])).lower() for k in ["python","coding","javascript","ai","machine learning","robotics","sql","web"]) else "Languages" if any(k in " ".join(split_values(row["teach"]) + split_values(row["want"])).lower() for k in ["telugu","hindi","tamil","english","bengali","malayalam","kannada"]) else "Academics")
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

@app.route("/reset-password")
def reset_password_page():
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
    q = request.args.get("q", "").strip().lower()
    city = request.args.get("city", "").strip().lower()
    skill = request.args.get("skill", "").strip().lower()
    min_match = max(0, min(100, int(request.args.get("min_match", 0) or 0)))

    conn = get_db()
    rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    blocked = set()
    if user:
        blocked = {r[0] for r in conn.execute("SELECT blocked_id FROM blocks WHERE blocker_id = ?", (user["id"],)).fetchall()}
    conn.close()

    result = []

    for row in rows:
        person = user_to_dict(row)

        if user and (person["id"] == user["id"] or person["id"] in blocked):
            continue

        searchable = " ".join([person["name"], person["location"], person.get("headline", ""), *person["languages"], *person["teach"], *person["want"], *person.get("interests", [])]).lower()
        if q and q not in searchable:
            continue
        if city and city not in person["location"].lower():
            continue
        if skill and not any(skill_matches(skill, x) for x in person["teach"] + person["want"]):
            continue

        match = calculate_match(user, person)
        if match["score"] < min_match:
            continue

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

    notify(conn, int(receiver_id), "request", "New skill-swap request", f"{user['name']} wants to exchange skills with you.", "#requestsSection")

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
        notify(conn, row["sender_id"], "request", "Request accepted 🎉", "You are now connected and can start chatting.", "#requestsSection")

    elif action == "reject":
        conn.execute("""
            UPDATE requests
            SET status = 'rejected'
            WHERE id = ?
        """, (request_id,))
        notify(conn, row["sender_id"], "request", "Request declined", "Your skill-swap request was declined.", "#requestsSection")

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

    notify(conn, person_id, "review", "You received a new review ⭐", f"{user['name']} left you a {rating}-star review.", "#proDashboard")
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Review submitted!"
    })


# =========================================================
# PROFILE / NOTIFICATIONS / SCHEDULING / MARKETPLACE / TRUST
# =========================================================

def require_user():
    user = current_user()
    if not user:
        return None, (jsonify({"success": False, "message": "Please sign in."}), 401)
    return user, None

def notify(conn, user_id, kind, title, body="", link=""):
    conn.execute("INSERT INTO notifications(user_id,kind,title,body,link) VALUES (?,?,?,?,?)", (user_id, kind, title, body, link))

@app.route("/api/profile/update", methods=["POST"])
def update_profile():
    user, err = require_user()
    if err: return err
    data = request.get_json() or {}
    name = str(data.get("name", "")).strip()
    if not name: return jsonify({"success": False, "message": "Name is required."}), 400
    def csv(v, default=""):
        if isinstance(v, list): return ",".join(str(x).strip() for x in v if str(x).strip())
        return str(v or default).strip()
    conn = get_db()
    conn.execute("""UPDATE users SET name=?, user_type=?, location=?, languages=?, bio=?, teach=?, want=?, availability=?, avatar=?, headline=?, interests=? WHERE id=?""", (
        name, str(data.get("type", "Student")).strip(), str(data.get("location", "Online")).strip(), csv(data.get("languages")),
        str(data.get("bio", "")).strip(), csv(data.get("teach")), csv(data.get("want")), csv(data.get("availability")),
        str(data.get("avatar", "🧑🏻")).strip() or "🧑🏻", str(data.get("headline", "")).strip(), csv(data.get("interests")), user["id"]))
    conn.commit()
    row = conn.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
    conn.close()
    return jsonify({"success": True, "user": user_to_dict(row)})

@app.route("/api/profile/<int:person_id>")
def public_profile(person_id):
    conn=get_db(); row=conn.execute("SELECT * FROM users WHERE id=?", (person_id,)).fetchone(); conn.close()
    if not row: return jsonify({"success": False, "message": "Profile not found."}),404
    return jsonify({"success": True, "user": user_to_dict(row)})

@app.route("/api/dashboard")
def dashboard():
    user, err=require_user()
    if err:return err
    conn=get_db(); uid=user["id"]
    counts={
      "sent": conn.execute("SELECT COUNT(*) FROM requests WHERE sender_id=?",(uid,)).fetchone()[0],
      "incoming": conn.execute("SELECT COUNT(*) FROM requests WHERE receiver_id=? AND status='pending'",(uid,)).fetchone()[0],
      "connections": conn.execute("SELECT COUNT(*) FROM requests WHERE status='accepted' AND (sender_id=? OR receiver_id=?)",(uid,uid)).fetchone()[0],
      "messages": conn.execute("SELECT COUNT(*) FROM messages WHERE receiver_id=?",(uid,)).fetchone()[0],
      "sessions": conn.execute("SELECT COUNT(*) FROM sessions WHERE (host_id=? OR guest_id=?) AND status='scheduled'",(uid,uid)).fetchone()[0],
      "unread": conn.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0",(uid,)).fetchone()[0]
    }
    conn.close(); return jsonify({"success":True,"counts":counts})

@app.route("/api/notifications")
def notifications():
    user,err=require_user();
    if err:return err
    conn=get_db(); rows=conn.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 50",(user["id"],)).fetchall(); conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/notifications/read", methods=["POST"])
def notifications_read():
    user,err=require_user();
    if err:return err
    data=request.get_json() or {}; conn=get_db()
    if data.get("id"): conn.execute("UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?",(data["id"],user["id"]))
    else: conn.execute("UPDATE notifications SET is_read=1 WHERE user_id=?",(user["id"],))
    conn.commit(); conn.close(); return jsonify({"success":True})

@app.route("/api/sessions", methods=["GET","POST"])
def sessions_api():
    user,err=require_user();
    if err:return err
    conn=get_db(); uid=user["id"]
    if request.method=="POST":
        d=request.get_json() or {}; guest=int(d.get("guestId",0)); title=str(d.get("title","SkillSwap session")).strip(); starts=str(d.get("startsAt","")).strip(); duration=int(d.get("durationMinutes",60) or 60)
        if not guest or not starts or not title:return jsonify({"success":False,"message":"Title, partner and start time are required."}),400
        ok=conn.execute("SELECT 1 FROM requests WHERE status='accepted' AND ((sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?))",(uid,guest,guest,uid)).fetchone()
        if not ok:return jsonify({"success":False,"message":"You can schedule sessions only with a connection."}),403
        cur=conn.execute("INSERT INTO sessions(host_id,guest_id,title,starts_at,duration_minutes,notes) VALUES(?,?,?,?,?,?)",(uid,guest,title,starts,duration,str(d.get("notes",""))))
        notify(conn,guest,"session","New SkillSwap session",title,"#sessions"); conn.commit(); sid=cur.lastrowid; conn.close(); return jsonify({"success":True,"id":sid})
    rows=conn.execute("SELECT s.*, h.name host_name, g.name guest_name FROM sessions s JOIN users h ON h.id=s.host_id JOIN users g ON g.id=s.guest_id WHERE s.host_id=? OR s.guest_id=? ORDER BY starts_at ASC",(uid,uid)).fetchall(); conn.close(); return jsonify([dict(r) for r in rows])

@app.route("/api/sessions/<int:sid>", methods=["POST"])
def update_session(sid):
    user,err=require_user();
    if err:return err
    action=(request.get_json() or {}).get("action"); conn=get_db(); row=conn.execute("SELECT * FROM sessions WHERE id=? AND (host_id=? OR guest_id=?)",(sid,user["id"],user["id"])).fetchone()
    if not row:conn.close();return jsonify({"success":False,"message":"Session not found."}),404
    if action not in ("cancel","complete"):conn.close();return jsonify({"success":False,"message":"Invalid action."}),400
    conn.execute("UPDATE sessions SET status=? WHERE id=?",("cancelled" if action=="cancel" else "completed",sid)); conn.commit();conn.close();return jsonify({"success":True})

@app.route("/api/listings", methods=["GET","POST"])
def listings_api():
    user=current_user(); conn=get_db()
    if request.method=="POST":
        if not user:conn.close();return jsonify({"success":False,"message":"Please sign in."}),401
        d=request.get_json() or {}; title=str(d.get("title","")).strip();
        if not title:conn.close();return jsonify({"success":False,"message":"Title is required."}),400
        cur=conn.execute("INSERT INTO listings(user_id,title,description,category,skill,mode) VALUES(?,?,?,?,?,?)",(user["id"],title,str(d.get("description","")),str(d.get("category","General")),str(d.get("skill","")),str(d.get("mode","online"))))
        conn.commit(); lid=cur.lastrowid;conn.close();return jsonify({"success":True,"id":lid})
    rows=conn.execute("SELECT l.*,u.name,u.avatar FROM listings l JOIN users u ON u.id=l.user_id WHERE l.status='active' ORDER BY l.id DESC LIMIT 100").fetchall();conn.close();return jsonify([dict(r) for r in rows])

@app.route("/api/journey")
def journey():
    user,err=require_user();
    if err:return err
    conn=get_db();uid=user["id"]
    sent=conn.execute("SELECT COUNT(*) FROM requests WHERE sender_id=?",(uid,)).fetchone()[0]
    connections=conn.execute("SELECT COUNT(*) FROM requests WHERE status='accepted' AND (sender_id=? OR receiver_id=?)",(uid,uid)).fetchone()[0]
    messages=conn.execute("SELECT COUNT(*) FROM messages WHERE sender_id=?",(uid,)).fetchone()[0]
    reviews=conn.execute("SELECT COUNT(*) FROM reviews WHERE reviewer_id=?",(uid,)).fetchone()[0]
    sessions=conn.execute("SELECT COUNT(*) FROM sessions WHERE host_id=? OR guest_id=?",(uid,uid)).fetchone()[0]
    conn.close()
    milestones=[("Profile created",True),("First swap request",sent>0),("First connection",connections>0),("First chat",messages>0),("First session",sessions>0),("First review",reviews>0)]
    return jsonify({"success":True,"milestones":[{"title":a,"done":b} for a,b in milestones]})

@app.route("/api/block/<int:person_id>", methods=["POST","DELETE"])
def block_user(person_id):
    user,err=require_user();
    if err:return err
    conn=get_db()
    if person_id==user["id"]:conn.close();return jsonify({"success":False,"message":"You cannot block yourself."}),400
    if request.method=="POST":conn.execute("INSERT OR IGNORE INTO blocks(blocker_id,blocked_id) VALUES(?,?)",(user["id"],person_id))
    else:conn.execute("DELETE FROM blocks WHERE blocker_id=? AND blocked_id=?",(user["id"],person_id))
    conn.commit();conn.close();return jsonify({"success":True})

@app.route("/api/report/<int:person_id>", methods=["POST"])
def report_user(person_id):
    user,err=require_user();
    if err:return err
    d=request.get_json() or {};reason=str(d.get("reason","Other")).strip();details=str(d.get("details",""))[:1000]
    conn=get_db();conn.execute("INSERT INTO reports(reporter_id,reported_id,reason,details) VALUES(?,?,?,?)",(user["id"],person_id,reason,details));conn.commit();conn.close();return jsonify({"success":True,"message":"Report submitted."})

# =========================================================
# SKILLSWAP 2.0 — RECOMMENDATIONS, GAMIFICATION, SECURITY, ADMIN
# =========================================================

LOGIN_ATTEMPTS = {}

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user, err = require_user()
        if err: return err
        if not user.get("isAdmin"):
            return jsonify({"success": False, "message": "Admin access required."}), 403
        return fn(*args, **kwargs)
    return wrapper

def award_badge(conn, user_id, code):
    badge = conn.execute("SELECT * FROM badges WHERE code=?", (code,)).fetchone()
    if not badge: return False
    cur = conn.execute("INSERT OR IGNORE INTO user_badges(user_id,badge_id) VALUES(?,?)", (user_id, badge["id"]))
    return cur.rowcount > 0

def refresh_badges(conn, user_id):
    checks = []
    if conn.execute("SELECT 1 FROM requests WHERE sender_id=? LIMIT 1", (user_id,)).fetchone(): checks.append("first_swap")
    if conn.execute("SELECT 1 FROM requests WHERE status='accepted' AND (sender_id=? OR receiver_id=?) LIMIT 1", (user_id,user_id)).fetchone(): checks.append("connector")
    if conn.execute("SELECT 1 FROM sessions WHERE status='completed' AND (host_id=? OR guest_id=?) LIMIT 1", (user_id,user_id)).fetchone(): checks.append("first_session")
    if conn.execute("SELECT 1 FROM reviews WHERE reviewed_id=? LIMIT 1", (user_id,)).fetchone(): checks.append("mentor")
    if conn.execute("SELECT COUNT(*) FROM sessions WHERE status='completed' AND (host_id=? OR guest_id=?)", (user_id,user_id)).fetchone()[0] >= 5: checks.append("five_sessions")
    for code in checks: award_badge(conn,user_id,code)

@app.route("/api/recommendations")
def recommendations():
    user, err = require_user()
    if err: return err
    conn=get_db(); rows=conn.execute("SELECT * FROM users WHERE id!=? AND id NOT IN (SELECT blocked_id FROM blocks WHERE blocker_id=?) AND id NOT IN (SELECT blocker_id FROM blocks WHERE blocked_id=?)",(user["id"],user["id"],user["id"])).fetchall()
    people=[]
    for r in rows:
        person=user_to_dict(r); m=calculate_match(user,person); person["match"]=m["score"]; person["reasons"]=m["reasons"]; people.append(person)
    conn.close(); people.sort(key=lambda x:x["match"], reverse=True)
    return jsonify({"success":True,"recommendations":people[:12]})

@app.route("/api/gamification")
def gamification():
    user,err=require_user()
    if err:return err
    conn=get_db(); refresh_badges(conn,user["id"])
    row=conn.execute("SELECT COUNT(*) FROM user_badges WHERE user_id=?",(user["id"],)).fetchone()[0]
    xp=conn.execute("SELECT COALESCE(SUM(b.xp),0) FROM user_badges ub JOIN badges b ON b.id=ub.badge_id WHERE ub.user_id=?",(user["id"],)).fetchone()[0]
    completed=conn.execute("SELECT COUNT(*) FROM sessions WHERE status='completed' AND (host_id=? OR guest_id=?)",(user["id"],user["id"])).fetchone()[0]
    level=1+(xp//100); next_xp=((xp//100)+1)*100
    badges=conn.execute("SELECT b.*,ub.earned_at FROM user_badges ub JOIN badges b ON b.id=ub.badge_id WHERE ub.user_id=? ORDER BY ub.earned_at DESC",(user["id"],)).fetchall()
    conn.commit();conn.close()
    return jsonify({"success":True,"xp":xp,"level":level,"nextXp":next_xp,"badges": [dict(b) for b in badges],"completedSessions":completed})

@app.route("/api/change-password", methods=["POST"])
def change_password():
    user,err=require_user()
    if err:return err
    d=request.get_json() or {}; old=str(d.get("currentPassword","")); new=str(d.get("newPassword",""))
    if len(new)<8:return jsonify({"success":False,"message":"New password must be at least 8 characters."}),400
    conn=get_db(); row=conn.execute("SELECT password FROM users WHERE id=?",(user["id"],)).fetchone()
    if not row or not check_password_hash(row["password"],old):conn.close();return jsonify({"success":False,"message":"Current password is incorrect."}),400
    conn.execute("UPDATE users SET password=? WHERE id=?",(generate_password_hash(new),user["id"]));conn.commit();conn.close();return jsonify({"success":True})

@app.route("/api/password-reset/request", methods=["POST"])
def password_reset_request():
    d=request.get_json() or {}; email=str(d.get("email","")).strip().lower()
    conn=get_db(); row=conn.execute("SELECT id,email FROM users WHERE lower(email)=?",(email,)).fetchone()
    # Always return the same public message to avoid account enumeration.
    response={"success":True,"message":"If an account exists, a password reset link has been generated."}
    if not row: conn.close(); return jsonify(response)
    token=secrets.token_urlsafe(32); import hashlib; th=hashlib.sha256(token.encode()).hexdigest(); expires=(datetime.utcnow()+timedelta(minutes=30)).isoformat()
    conn.execute("UPDATE password_resets SET used=1 WHERE user_id=? AND used=0",(row["id"],)); conn.execute("INSERT INTO password_resets(user_id,token_hash,expires_at) VALUES(?,?,?)",(row["id"],th,expires)); conn.commit();conn.close()
    # Optional SMTP delivery. In local development expose a one-time dev link in the JSON only when explicitly enabled.
    if os.environ.get("SKILLSWAP_DEV_RESET_LINK","0")=="1": response["resetLink"]="/reset-password?token="+token
    smtp_host=os.environ.get("SKILLSWAP_SMTP_HOST")
    if smtp_host:
        try:
            msg=EmailMessage(); msg["Subject"]="SkillSwap India password reset"; msg["From"]=os.environ.get("SKILLSWAP_SMTP_FROM",""); msg["To"]=row["email"]; msg.set_content("Your SkillSwap password reset token is valid for 30 minutes: "+token)
            with smtplib.SMTP(smtp_host,int(os.environ.get("SKILLSWAP_SMTP_PORT","587")),timeout=10) as server:
                server.starttls(); server.login(os.environ.get("SKILLSWAP_SMTP_USER",""),os.environ.get("SKILLSWAP_SMTP_PASSWORD","")); server.send_message(msg)
        except Exception:
            app.logger.exception("Password reset email failed")
    return jsonify(response)

@app.route("/api/password-reset/confirm", methods=["POST"])
def password_reset_confirm():
    d=request.get_json() or {}; token=str(d.get("token","")); new=str(d.get("newPassword",""))
    if len(new)<8 or not token:return jsonify({"success":False,"message":"Valid token and an 8+ character password are required."}),400
    import hashlib; th=hashlib.sha256(token.encode()).hexdigest(); conn=get_db(); row=conn.execute("SELECT * FROM password_resets WHERE token_hash=? AND used=0",(th,)).fetchone()
    if not row or datetime.fromisoformat(row["expires_at"]) < datetime.utcnow():conn.close();return jsonify({"success":False,"message":"This reset link is invalid or expired."}),400
    conn.execute("UPDATE users SET password=? WHERE id=?",(generate_password_hash(new),row["user_id"]));conn.execute("UPDATE password_resets SET used=1 WHERE id=?",(row["id"],));conn.commit();conn.close();return jsonify({"success":True})

@app.route("/api/admin/overview")
@admin_required
def admin_overview():
    conn=get_db(); counts={
        "users":conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],"activeUsers":conn.execute("SELECT COUNT(*) FROM users WHERE created_at>=datetime('now','-30 day')").fetchone()[0],
        "requests":conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0],"connections":conn.execute("SELECT COUNT(*) FROM requests WHERE status='accepted'").fetchone()[0],
        "sessions":conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0],"reports":conn.execute("SELECT COUNT(*) FROM reports WHERE status='open'").fetchone()[0],"listings":conn.execute("SELECT COUNT(*) FROM listings WHERE status='active'").fetchone()[0]
    }; reports=conn.execute("SELECT r.*,u1.name reporter,u2.name reported FROM reports r JOIN users u1 ON u1.id=r.reporter_id JOIN users u2 ON u2.id=r.reported_id WHERE r.status='open' ORDER BY r.id DESC LIMIT 30").fetchall();conn.close();return jsonify({"success":True,"counts":counts,"reports":[dict(r) for r in reports]})

@app.route("/api/admin/users")
@admin_required
def admin_users():
    conn=get_db(); rows=conn.execute("SELECT id,name,email,user_type,location,verified,is_admin,created_at,rating,reviews FROM users ORDER BY id DESC LIMIT 200").fetchall();conn.close();return jsonify({"success":True,"users":[dict(r) for r in rows]})

@app.route("/api/admin/report/<int:rid>", methods=["POST"])
@admin_required
def admin_report(rid):
    action=(request.get_json() or {}).get("action","resolve"); status="resolved" if action=="resolve" else "dismissed" if action=="dismiss" else "open"
    conn=get_db(); conn.execute("UPDATE reports SET status=? WHERE id=?",(status,rid));conn.commit();conn.close();return jsonify({"success":True})

# =========================================================
# START SERVER
# =========================================================

init_db()

if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )