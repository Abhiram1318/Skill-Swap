pip install -r requirements.txt
python app.py

from flask import Flask, render_template, request, jsonify, session
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.secret_key = "skillswap-india-change-this-secret-key"

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
        "reviews": row["reviews"]
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
# START SERVER
# =========================================================

if __name__ == "__main__":
    init_db()

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
