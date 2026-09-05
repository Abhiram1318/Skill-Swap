from flask import Flask, render_template, request, jsonify, session
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.secret_key = os.environ.get("SKILLSWAP_SECRET_KEY", "skillswap-india-change-this-secret-key")

DATABASE = "skillswap.db"


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

    # Marketplace skill offers. This table is created automatically so
    # publishing an offer works on existing databases too.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            skill TEXT NOT NULL,
            category TEXT DEFAULT 'Other',
            description TEXT,
            mode TEXT DEFAULT 'online',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            person_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, person_id),
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(person_id) REFERENCES users(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS profile_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            viewer_id INTEGER NOT NULL,
            person_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(viewer_id) REFERENCES users(id),
            FOREIGN KEY(person_id) REFERENCES users(id)
        )
    """)

    # Lightweight migrations for existing SkillSwap databases.
    existing_cols = {r[1] for r in cur.execute("PRAGMA table_info(users)").fetchall()}
    if "headline" not in existing_cols: cur.execute("ALTER TABLE users ADD COLUMN headline TEXT DEFAULT ''")
    if "verified" not in existing_cols: cur.execute("ALTER TABLE users ADD COLUMN verified INTEGER DEFAULT 0")
    if "is_admin" not in existing_cols: cur.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")

    cur.execute("CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,title TEXT NOT NULL,message TEXT,kind TEXT DEFAULT 'info',read INTEGER DEFAULT 0,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    cur.execute("CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY AUTOINCREMENT,creator_id INTEGER NOT NULL,partner_id INTEGER NOT NULL,title TEXT NOT NULL,start_at TEXT NOT NULL,duration INTEGER DEFAULT 60,notes TEXT,status TEXT DEFAULT 'scheduled',created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    cur.execute("CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY AUTOINCREMENT,reporter_id INTEGER NOT NULL,reported_id INTEGER NOT NULL,reason TEXT,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,status TEXT DEFAULT 'open')")
    cur.execute("CREATE TABLE IF NOT EXISTS blocks (id INTEGER PRIMARY KEY AUTOINCREMENT,blocker_id INTEGER NOT NULL,blocked_id INTEGER NOT NULL,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,UNIQUE(blocker_id,blocked_id))")
    cur.execute("CREATE TABLE IF NOT EXISTS badges (id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE NOT NULL,description TEXT NOT NULL,icon TEXT NOT NULL,xp INTEGER DEFAULT 0)")
    cur.execute("CREATE TABLE IF NOT EXISTS user_badges (user_id INTEGER NOT NULL,badge_id INTEGER NOT NULL,earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,UNIQUE(user_id,badge_id))")
    for b in [("First Swap","Make your first accepted connection","🤝",100),("Profile Pro","Complete your profile","✨",150),("Skill Sharer","Publish your first skill offer","🎓",100),("Community Builder","Reach 5 connections","🌟",250),("Helpful","Receive your first review","⭐",150)]:
        cur.execute("INSERT OR IGNORE INTO badges(name,description,icon,xp) VALUES(?,?,?,?)",b)

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
        "verified": bool(row["verified"]) if "verified" in row.keys() else False
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
# MARKETPLACE LISTINGS
# =========================================================

@app.route("/api/listings", methods=["GET"])
def get_listings():
    conn = get_db()
    rows = conn.execute("""
        SELECT
            l.id,
            l.user_id,
            l.title,
            l.skill,
            l.category,
            l.description,
            l.mode,
            l.created_at,
            u.name,
            u.avatar,
            u.location
        FROM listings l
        JOIN users u ON u.id = l.user_id
        ORDER BY l.id DESC
    """).fetchall()
    conn.close()

    return jsonify([
        {
            "id": row["id"],
            "userId": row["user_id"],
            "title": row["title"],
            "skill": row["skill"],
            "category": row["category"],
            "description": row["description"],
            "mode": row["mode"],
            "createdAt": row["created_at"],
            "name": row["name"],
            "avatar": row["avatar"],
            "location": row["location"]
        }
        for row in rows
    ])


@app.route("/api/listings", methods=["POST"])
def create_listing():
    user = current_user()

    if not user:
        return jsonify({
            "success": False,
            "message": "Please sign in first."
        }), 401

    data = request.get_json(silent=True) or {}

    title = str(data.get("title", "")).strip()
    skill = str(data.get("skill", "")).strip()
    category = str(data.get("category", "Other")).strip() or "Other"
    description = str(data.get("description", "")).strip()
    mode = str(data.get("mode", "online")).strip() or "online"

    if not title or not skill or not description:
        return jsonify({
            "success": False,
            "message": "Please enter a title, skill, and description."
        }), 400

    if len(title) > 120 or len(skill) > 80 or len(description) > 1000:
        return jsonify({
            "success": False,
            "message": "Please keep the offer within the allowed length."
        }), 400

    allowed_modes = {"online", "in-person", "both"}
    if mode not in allowed_modes:
        mode = "online"

    conn = get_db()
    cur = conn.execute("""
        INSERT INTO listings
        (user_id, title, skill, category, description, mode)
        VALUES (?,?,?,?,?,?)
    """, (
        user["id"], title, skill, category, description, mode
    ))
    listing_id = cur.lastrowid
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Skill offer published!",
        "id": listing_id
    }), 201


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
# GROWTH / SAVED PROFILES / ANALYTICS
# =========================================================

@app.route("/api/favorites", methods=["GET", "POST", "DELETE"])
def favorites_api():
    user = current_user()
    if not user:
        return jsonify({"success": False, "message": "Please sign in first."}), 401

    conn = get_db()
    if request.method == "GET":
        rows = conn.execute("""
            SELECT u.* FROM favorites f JOIN users u ON u.id=f.person_id
            WHERE f.user_id=? ORDER BY f.created_at DESC
        """, (user["id"],)).fetchall()
        conn.close()
        return jsonify([user_to_dict(r) for r in rows])

    data = request.get_json(silent=True) or {}
    person_id = int(data.get("person_id") or data.get("personId") or 0)
    if not person_id or person_id == user["id"]:
        conn.close(); return jsonify({"success": False, "message": "Choose a valid profile."}), 400

    exists = conn.execute("SELECT id FROM users WHERE id=?", (person_id,)).fetchone()
    if not exists:
        conn.close(); return jsonify({"success": False, "message": "Profile not found."}), 404

    if request.method == "POST":
        conn.execute("INSERT OR IGNORE INTO favorites(user_id,person_id) VALUES(?,?)", (user["id"], person_id))
        conn.commit(); conn.close()
        return jsonify({"success": True, "saved": True})

    conn.execute("DELETE FROM favorites WHERE user_id=? AND person_id=?", (user["id"], person_id))
    conn.commit(); conn.close()
    return jsonify({"success": True, "saved": False})


@app.route("/api/profile-view/<int:person_id>", methods=["POST"])
def profile_view(person_id):
    user = current_user()
    if not user or user["id"] == person_id:
        return jsonify({"success": True})
    conn = get_db()
    conn.execute("INSERT INTO profile_views(viewer_id,person_id) VALUES(?,?)", (user["id"], person_id))
    conn.commit(); conn.close()
    return jsonify({"success": True})


@app.route("/api/analytics")
def analytics_api():
    user = current_user()
    if not user:
        return jsonify({"logged_in": False})
    conn = get_db(); uid=user["id"]
    connections = conn.execute("SELECT COUNT(*) FROM requests WHERE (sender_id=? OR receiver_id=?) AND status='accepted'", (uid,uid)).fetchone()[0]
    sent_requests = conn.execute("SELECT COUNT(*) FROM requests WHERE sender_id=?", (uid,)).fetchone()[0]
    sessions = conn.execute("SELECT COUNT(*) FROM sessions WHERE creator_id=? OR partner_id=?", (uid,uid)).fetchone()[0]
    taught = conn.execute("SELECT COUNT(*) FROM listings WHERE user_id=?", (uid,)).fetchone()[0]
    messages = conn.execute("SELECT COUNT(*) FROM messages WHERE sender_id=?", (uid,)).fetchone()[0]
    reviews = conn.execute("SELECT COUNT(*) FROM reviews WHERE reviewed_id=?", (uid,)).fetchone()[0]
    views = conn.execute("SELECT COUNT(*) FROM profile_views WHERE person_id=?", (uid,)).fetchone()[0]
    from datetime import date, timedelta
    weekly=[]
    for i in range(6,-1,-1):
        d=(date.today()-timedelta(days=i)).isoformat()
        actions=0
        for table,where,args in [
            ("requests","(sender_id=? OR receiver_id=?) AND date(created_at)=?",(uid,uid,d)),
            ("messages","(sender_id=? OR receiver_id=?) AND date(created_at)=?",(uid,uid,d)),
            ("sessions","(creator_id=? OR partner_id=?) AND date(created_at)=?",(uid,uid,d)),
            ("listings","user_id=? AND date(created_at)=?",(uid,d)),
            ("reviews","reviewed_id=? AND date(created_at)=?",(uid,d))]:
            actions += conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}",args).fetchone()[0]
        weekly.append({"day": d and date.fromisoformat(d).strftime('%a'), "actions": actions})
    conn.close()
    return jsonify({"logged_in":True,"analytics":{"connections":connections,"requests_sent":sent_requests,"sessions":sessions,"offers":taught,"messages_sent":messages,"reviews":reviews,"profile_views":views,"weekly":weekly}})


# =========================================================
# DASHBOARD / NOTIFICATIONS / SESSIONS / TRUST / GAMIFICATION
# =========================================================

@app.route("/api/profile/update", methods=["POST"])
def update_profile():
    user=current_user()
    if not user: return jsonify({"success":False,"message":"Please sign in first."}),401
    data=request.get_json(silent=True) or {}
    def csv(v):
        if isinstance(v,list): return ",".join(str(x).strip() for x in v if str(x).strip())
        return str(v or "").strip()
    fields={"name":str(data.get("name",user["name"])).strip(),"user_type":str(data.get("type",data.get("user_type",user["type"]))).strip(),"location":str(data.get("location",user["location"])).strip(),"languages":csv(data.get("languages",user["languages"])),"bio":str(data.get("bio",user["bio"])).strip(),"teach":csv(data.get("teach",user["teach"])),"want":csv(data.get("want",user["want"])),"availability":csv(data.get("availability",user["availability"])),"avatar":str(data.get("avatar",user["avatar"])).strip() or "🧑🏻","headline":str(data.get("headline",user.get("headline",''))).strip()}
    if not fields["name"] or not fields["location"]: return jsonify({"success":False,"message":"Name and location are required."}),400
    conn=get_db(); conn.execute("UPDATE users SET name=?,user_type=?,location=?,languages=?,bio=?,teach=?,want=?,availability=?,avatar=?,headline=? WHERE id=?",(*fields.values(),user["id"])); conn.commit(); row=conn.execute("SELECT * FROM users WHERE id=?",(user["id"],)).fetchone(); conn.close()
    return jsonify({"success":True,"user":user_to_dict(row)})

@app.route("/api/dashboard")
def dashboard_api():
    user=current_user()
    if not user: return jsonify({"logged_in":False})
    uid=user["id"]; conn=get_db()
    counts={
      "connections":conn.execute("SELECT COUNT(*) FROM requests WHERE (sender_id=? OR receiver_id=?) AND status='accepted'",(uid,uid)).fetchone()[0],
      "pending_requests":conn.execute("SELECT COUNT(*) FROM requests WHERE receiver_id=? AND status='pending'",(uid,)).fetchone()[0],
      "sessions":conn.execute("SELECT COUNT(*) FROM sessions WHERE creator_id=? OR partner_id=?",(uid,uid)).fetchone()[0],
      "unread_notifications":conn.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND read=0",(uid,)).fetchone()[0],
      "unread_messages":conn.execute("SELECT COUNT(*) FROM messages WHERE receiver_id=?",(uid,)).fetchone()[0],
      "profile_views":conn.execute("SELECT COUNT(*) FROM profile_views WHERE person_id=?",(uid,)).fetchone()[0]
    }
    conn.close(); return jsonify({"logged_in":True,"dashboard":counts})

@app.route("/api/notifications")
def notifications_api():
    user=current_user()
    if not user: return jsonify([]),401
    conn=get_db(); rows=conn.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 30",(user["id"],)).fetchall(); conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/notifications/read", methods=["POST"])
def notifications_read():
    user=current_user()
    if not user: return jsonify({"success":False}),401
    conn=get_db(); conn.execute("UPDATE notifications SET read=1 WHERE user_id=?",(user["id"],)); conn.commit(); conn.close(); return jsonify({"success":True})

@app.route("/api/sessions", methods=["GET","POST"])
def sessions_api():
    user=current_user()
    if not user: return jsonify({"success":False,"message":"Please sign in first."}),401
    uid=user["id"]; conn=get_db()
    if request.method=="GET":
        rows=conn.execute("SELECT s.*,u.name partner_name FROM sessions s JOIN users u ON u.id=CASE WHEN s.creator_id=? THEN s.partner_id ELSE s.creator_id END WHERE s.creator_id=? OR s.partner_id=? ORDER BY s.start_at",(uid,uid,uid)).fetchall(); conn.close(); return jsonify([dict(r) for r in rows])
    d=request.get_json(silent=True) or {}; partner=int(d.get("partner_id") or d.get("partnerId") or 0); title=str(d.get("title","")).strip(); start=str(d.get("start_at") or d.get("start") or "").strip(); duration=int(d.get("duration",60) or 60); notes=str(d.get("notes","")).strip()
    if not partner or not title or not start: conn.close(); return jsonify({"success":False,"message":"Partner, title and date/time are required."}),400
    conn.execute("INSERT INTO sessions(creator_id,partner_id,title,start_at,duration,notes) VALUES(?,?,?,?,?,?)",(uid,partner,title,start,max(15,min(duration,240)),notes)); conn.execute("INSERT INTO notifications(user_id,title,message,kind) VALUES(?,?,?,?)",(partner,"New learning session",f"{user['name']} scheduled {title}.","session")); conn.commit(); conn.close(); return jsonify({"success":True})

@app.route("/api/sessions/<int:sid>", methods=["POST"])
def update_session(sid):
    user=current_user()
    if not user: return jsonify({"success":False}),401
    d=request.get_json(silent=True) or {}; status=str(d.get("status","scheduled"))
    conn=get_db(); row=conn.execute("SELECT * FROM sessions WHERE id=? AND (creator_id=? OR partner_id=?)",(sid,user["id"],user["id"])).fetchone()
    if not row: conn.close(); return jsonify({"success":False,"message":"Session not found."}),404
    conn.execute("UPDATE sessions SET status=? WHERE id=?",(status,sid)); conn.commit(); conn.close(); return jsonify({"success":True})

@app.route("/api/journey")
def journey_api():
    user=current_user()
    if not user: return jsonify([]),401
    uid=user["id"]; conn=get_db(); items=[]
    for label,query in [("Profile created","SELECT created_at FROM users WHERE id=?"),("Connections made","SELECT MAX(created_at) FROM requests WHERE (sender_id=? OR receiver_id=?) AND status='accepted'"),("Latest skill offer","SELECT MAX(created_at) FROM listings WHERE user_id=?"),("Latest review","SELECT MAX(created_at) FROM reviews WHERE reviewed_id=?")]:
        params=(uid,uid) if 'sender_id' in query else (uid,)
        val=conn.execute(query,params).fetchone()[0]; items.append({"title":label,"date":val})
    conn.close(); return jsonify(items)

@app.route("/api/recommendations")
def recommendations_api():
    user=current_user()
    if not user: return jsonify([]),401
    conn=get_db(); rows=conn.execute("SELECT * FROM users WHERE id != ?",(user["id"],)).fetchall(); conn.close(); out=[]
    for r in rows:
        p=user_to_dict(r); m=calculate_match(user,p); p["match"]=m["score"]; p["reasons"]=m["reasons"]; out.append(p)
    out.sort(key=lambda x:x["match"],reverse=True); return jsonify({"recommendations":out[:8]})

@app.route("/api/gamification")
def gamification_api():
    user=current_user()
    if not user: return jsonify({"gamification":{"xp":0,"level":1,"streak":0}})
    uid=user["id"]; conn=get_db()
    xp=0
    xp += 150 if user["name"] and user["location"] and user["bio"] else 0
    xp += conn.execute("SELECT COUNT(*) FROM requests WHERE (sender_id=? OR receiver_id=?) AND status='accepted'",(uid,uid)).fetchone()[0]*100
    xp += conn.execute("SELECT COUNT(*) FROM listings WHERE user_id=?",(uid,)).fetchone()[0]*100
    xp += conn.execute("SELECT COUNT(*) FROM reviews WHERE reviewed_id=?",(uid,)).fetchone()[0]*75
    level=max(1,xp//500+1)
    from datetime import date, timedelta
    active_dates=set()
    for table,field in [("requests","sender_id"),("requests","receiver_id"),("messages","sender_id"),("messages","receiver_id"),("listings","user_id"),("reviews","reviewed_id")]:
        rows=conn.execute(f"SELECT DISTINCT date(created_at) d FROM {table} WHERE {field}=?",(uid,)).fetchall()
        active_dates.update(r["d"] for r in rows if r["d"])
    streak=0; day=date.today()
    while day.isoformat() in active_dates:
        streak+=1; day-=timedelta(days=1)
    conn.close(); return jsonify({"gamification":{"xp":xp,"level":level,"streak":streak,"next_level_xp":level*500}})

@app.route("/api/block/<int:person_id>", methods=["POST","DELETE"])
def block_api(person_id):
    user=current_user()
    if not user: return jsonify({"success":False}),401
    conn=get_db()
    if request.method=="POST": conn.execute("INSERT OR IGNORE INTO blocks(blocker_id,blocked_id) VALUES(?,?)",(user["id"],person_id))
    else: conn.execute("DELETE FROM blocks WHERE blocker_id=? AND blocked_id=?",(user["id"],person_id))
    conn.commit(); conn.close(); return jsonify({"success":True})

@app.route("/api/report/<int:person_id>", methods=["POST"])
def report_api(person_id):
    user=current_user()
    if not user: return jsonify({"success":False}),401
    reason=str((request.get_json(silent=True) or {}).get("reason","Community safety concern"))[:500]
    conn=get_db(); conn.execute("INSERT INTO reports(reporter_id,reported_id,reason) VALUES(?,?,?)",(user["id"],person_id,reason)); conn.commit(); conn.close(); return jsonify({"success":True,"message":"Report submitted. Thank you for helping keep SkillSwap safe."})

# =========================================================
# START SERVER
# =========================================================

if __name__ == "__main__":
    init_db()

    # Open the local Flask site in Chrome automatically when possible.
    # Set SKILLSWAP_AUTO_OPEN=0 to disable this behavior.
    if os.environ.get("SKILLSWAP_AUTO_OPEN", "1") != "0":
        import threading, webbrowser
        def open_browser():
            try:
                webbrowser.get("windows-default").open("http://127.0.0.1:5000")
            except Exception:
                webbrowser.open("http://127.0.0.1:5000")
        threading.Timer(1.0, open_browser).start()

    app.run(host="127.0.0.1", port=5000, debug=True)