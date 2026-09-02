```python
from flask import Flask, render_template, request, jsonify, session
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# No configuration changes are required.
app.secret_key = os.environ.get(
    "SKILLSWAP_SECRET",
    "skillswap-india-development-secret-change-for-production"
)

DATABASE = "skillswap.db"


# ============================================================
# DATABASE
# ============================================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            user_type TEXT DEFAULT 'Young Learner',
            location TEXT DEFAULT 'Online',
            languages TEXT DEFAULT 'English',
            bio TEXT DEFAULT '',
            teach TEXT DEFAULT '',
            want TEXT DEFAULT '',
            availability TEXT DEFAULT 'Flexible',
            avatar TEXT DEFAULT '🧑🏻',
            rating REAL DEFAULT 0,
            reviews INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            skill_wanted TEXT NOT NULL,
            skill_offered TEXT NOT NULL,
            message TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            accepted_at TIMESTAMP,
            FOREIGN KEY(sender_id) REFERENCES users(id),
            FOREIGN KEY(receiver_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(sender_id) REFERENCES users(id),
            FOREIGN KEY(receiver_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reviewer_id INTEGER NOT NULL,
            reviewed_id INTEGER NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(reviewer_id) REFERENCES users(id),
            FOREIGN KEY(reviewed_id) REFERENCES users(id),
            UNIQUE(reviewer_id, reviewed_id)
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            notification_type TEXT DEFAULT 'info',
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
    """)

    # Demo users
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    if count == 0:
        demo_users = [
            (
                "Ananya Reddy",
                "ananya@skillswap.demo",
                "Teen Student",
                "Hyderabad, Telangana",
                "Telugu,Hindi,English",
                "Languages and technology learner who enjoys helping other students.",
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
                "Young coding enthusiast building robotics projects.",
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
                "Creative learner interested in Indian classical arts.",
                "Bharatanatyam,Carnatic Music",
                "Graphic Design,Photography",
                "Weekends",
                "👩🏽",
                5.0,
                41
            ),
            (
                "Rohan Patel",
                "rohan@skillswap.demo",
                "College Student",
                "Pune, Maharashtra",
                "Hindi,Marathi,English",
                "Technology learner who loves explaining difficult ideas simply.",
                "Python,AI,Machine Learning",
                "Web Design,Video Editing",
                "Weekday evenings,Flexible",
                "👨🏽",
                5.0,
                46
            ),
            (
                "Saanvi Gupta",
                "saanvi@skillswap.demo",
                "Teen Student",
                "Delhi, India",
                "Hindi,English",
                "Maths and study-planning enthusiast.",
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
                "Cricket and chess fan exploring technology.",
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
                "Priya Sharma",
                "priya@skillswap.demo",
                "College Student",
                "Hyderabad, Telangana",
                "Telugu,Hindi,English",
                "Home cook who loves sharing Indian recipes.",
                "Indian Cooking,Biryani",
                "Baking,Photography",
                "Weekends,Flexible",
                "👩🏾",
                5.0,
                52
            )
        ]

        for user in demo_users:
            (
                name,
                email,
                user_type,
                location,
                languages,
                bio,
                teach,
                want,
                availability,
                avatar,
                rating,
                reviews
            ) = user

            conn.execute("""
                INSERT INTO users
                (
                    name,
                    email,
                    password,
                    user_type,
                    location,
                    languages,
                    bio,
                    teach,
                    want,
                    availability,
                    avatar,
                    rating,
                    reviews
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                name,
                email,
                generate_password_hash("demo123"),
                user_type,
                location,
                languages,
                bio,
                teach,
                want,
                availability,
                avatar,
                rating,
                reviews
            ))

    conn.commit()
    conn.close()


# ============================================================
# HELPERS
# ============================================================

def split_values(value):
    if not value:
        return []

    return [
        x.strip()
        for x in str(value).split(",")
        if x.strip()
    ]


def user_dict(row):
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

    return user_dict(row)


def normalize(value):
    return "".join(
        char.lower()
        for char in str(value or "")
        if char.isalnum() or char in " +#"
    ).strip()


def skill_matches(a, b):
    x = normalize(a)
    y = normalize(b)

    if not x or not y:
        return False

    if x == y or x in y or y in x:
        return True

    groups = [
        {"javascript", "js"},
        {"python", "py"},
        {"ai", "artificial intelligence", "machine learning", "ml"},
        {"math", "maths", "mathematics"},
        {"drawing", "art"}
    ]

    for group in groups:
        if x in group and y in group:
            return True

    return False


def overlap(first, second):
    total = 0

    for a in first:
        for b in second:
            if skill_matches(a, b):
                total += 1

    return total


def calculate_match(user, person):
    if not user:
        return 80, ["Good community match"]

    score = 35
    reasons = []

    learn = overlap(
        user["want"],
        person["teach"]
    )

    teach = overlap(
        user["teach"],
        person["want"]
    )

    languages = overlap(
        user["languages"],
        person["languages"]
    )

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

    if languages:
        score += min(8, languages * 4)
        reasons.append("Shared language")

    if availability:
        score += min(7, availability * 4)
        reasons.append("Matching availability")

    user_city = user["location"].split(",")[0].strip().lower()
    person_city = person["location"].split(",")[0].strip().lower()

    if user_city and user_city == person_city:
        score += 8
        reasons.append("Same city")

    return min(99, max(50, round(score))), (
        reasons or ["Good general compatibility"]
    )[:3]


def add_notification(
    conn,
    user_id,
    title,
    message,
    notification_type="info"
):
    conn.execute("""
        INSERT INTO notifications
        (
            user_id,
            title,
            message,
            notification_type
        )
        VALUES (?, ?, ?, ?)
    """, (
        user_id,
        title,
        message,
        notification_type
    ))


def connected(conn, first_id, second_id):
    return conn.execute("""
        SELECT id
        FROM requests
        WHERE status = 'accepted'
        AND (
            (sender_id = ? AND receiver_id = ?)
            OR
            (sender_id = ? AND receiver_id = ?)
        )
        LIMIT 1
    """, (
        first_id,
        second_id,
        second_id,
        first_id
    )).fetchone()


# ============================================================
# FRONTEND
# ============================================================

@app.route("/")
def home():
    return render_template("index.html")


# ============================================================
# AUTH
# ============================================================

@app.post("/api/signup")
def signup():
    data = request.get_json() or {}

    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not name or not email or not password:
        return jsonify({
            "success": False,
            "message": "Please complete all required fields."
        }), 400

    if len(password) < 6:
        return jsonify({
            "success": False,
            "message": "Password must contain at least 6 characters."
        }), 400

    conn = get_db()

    exists = conn.execute(
        "SELECT id FROM users WHERE email = ?",
        (email,)
    ).fetchone()

    if exists:
        conn.close()

        return jsonify({
            "success": False,
            "message": "An account with this email already exists."
        }), 409

    def values(key):
        value = data.get(key, "")

        if isinstance(value, list):
            return ",".join(value)

        return ",".join(split_values(value))

    cursor = conn.execute("""
        INSERT INTO users
        (
            name,
            email,
            password,
            user_type,
            location,
            languages,
            bio,
            teach,
            want,
            availability
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        name,
        email,
        generate_password_hash(password),
        data.get("type", "Young Learner"),
        data.get("location", "Online"),
        values("languages") or "English",
        data.get("bio", ""),
        values("teach") or "Knowledge Sharing",
        values("want") or "Something New",
        values("availability") or "Flexible"
    ))

    user_id = cursor.lastrowid

    add_notification(
        conn,
        user_id,
        "Welcome to SkillSwap India!",
        "Your profile is ready. Start discovering skill partners.",
        "welcome"
    )

    conn.commit()

    row = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    conn.close()

    session["user_id"] = user_id

    return jsonify({
        "success": True,
        "user": user_dict(row)
    })


@app.post("/api/signin")
@app.post("/api/login")
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
        "user": user_dict(row)
    })


@app.post("/api/logout")
def logout():
    session.clear()

    return jsonify({
        "success": True
    })


@app.get("/api/me")
def me():
    user = current_user()

    return jsonify({
        "logged_in": bool(user),
        "user": user
    })


# ============================================================
# PEOPLE + MATCHING
# ============================================================

@app.get("/api/people")
def people():
    user = current_user()

    conn = get_db()

    rows = conn.execute("""
        SELECT *
        FROM users
        ORDER BY rating DESC, reviews DESC, created_at DESC
    """).fetchall()

    conn.close()

    results = []

    for row in rows:
        person = user_dict(row)

        if user and person["id"] == user["id"]:
            continue

        score, reasons = calculate_match(
            user,
            person
        )

        person["match"] = score
        person["reasons"] = reasons

        results.append(person)

    results.sort(
        key=lambda person: (
            person["match"],
            person["rating"],
            person["reviews"]
        ),
        reverse=True
    )

    return jsonify(results)


# ============================================================
# REQUESTS
# ============================================================

@app.get("/api/requests")
def sent_requests():
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
        JOIN users u
            ON u.id = r.receiver_id
        WHERE r.sender_id = ?
        ORDER BY r.id DESC
    """, (
        user["id"],
    )).fetchall()

    conn.close()

    return jsonify([
        {
            "id": row["id"],
            "receiverId": row["receiver_id"],
            "receiverName": row["receiver_name"],
            "receiverAvatar": row["receiver_avatar"],
            "skillWanted": row["skill_wanted"],
            "skillOffered": row["skill_offered"],
            "message": row["message"],
            "status": row["status"]
        }
        for row in rows
    ])


@app.get("/api/requests/incoming")
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
        JOIN users u
            ON u.id = r.sender_id
        WHERE r.receiver_id = ?
        ORDER BY r.id DESC
    """, (
        user["id"],
    )).fetchall()

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


@app.post("/api/requests")
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
        "Hi! I'd love to exchange skills with you."
    ).strip()

    if not receiver_id or not wanted or not offered:
        return jsonify({
            "success": False,
            "message": "Please enter both skills."
        }), 400

    receiver_id = int(receiver_id)

    if receiver_id == user["id"]:
        return jsonify({
            "success": False,
            "message": "You cannot connect with yourself."
        }), 400

    conn = get_db()

    receiver = conn.execute(
        "SELECT id FROM users WHERE id = ?",
        (receiver_id,)
    ).fetchone()

    if not receiver:
        conn.close()

        return jsonify({
            "success": False,
            "message": "Member not found."
        }), 404

    duplicate = conn.execute("""
        SELECT id
        FROM requests
        WHERE
            (sender_id = ? AND receiver_id = ?)
            OR
            (sender_id = ? AND receiver_id = ?)
        LIMIT 1
    """, (
        user["id"],
        receiver_id,
        receiver_id,
        user["id"]
    )).fetchone()

    if duplicate:
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
        VALUES (?, ?, ?, ?, ?)
    """, (
        user["id"],
        receiver_id,
        wanted,
        offered,
        message
    ))

    add_notification(
        conn,
        receiver_id,
        "New skill-swap request",
        f"{user['name']} wants to exchange skills with you.",
        "request"
    )

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Skill-swap request sent!"
    })


@app.post("/api/requests/<int:request_id>")
def update_request(request_id):
    user = current_user()

    if not user:
        return jsonify({
            "success": False,
            "message": "Please sign in."
        }), 401

    data = request.get_json() or {}
    action = data.get("action")

    if action not in ("accept", "reject"):
        return jsonify({
            "success": False,
            "message": "Invalid request action."
        }), 400

    conn = get_db()

    row = conn.execute("""
        SELECT *
        FROM requests
        WHERE id = ?
        AND receiver_id = ?
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

    sender_id = row["sender_id"]

    if action == "accept":

        conn.execute("""
            UPDATE requests
            SET
                status = 'accepted',
                accepted_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            request_id,
        ))

        add_notification(
            conn,
            sender_id,
            "Request accepted 🎉",
            f"{user['name']} accepted your skill-swap request.",
            "success"
        )

        message = "Connection accepted!"

    else:

        conn.execute("""
            UPDATE requests
            SET status = 'rejected'
            WHERE id = ?
        """, (
            request_id,
        ))

        add_notification(
            conn,
            sender_id,
            "Request update",
            f"{user['name']} declined your skill-swap request.",
            "info"
        )

        message = "Request declined."

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": message
    })


# ============================================================
# CONNECTIONS
# ============================================================

@app.get("/api/connections")
def connections():
    user = current_user()

    if not user:
        return jsonify([])

    conn = get_db()

    rows = conn.execute("""
        SELECT
            p.id,
            p.name,
            p.avatar,
            p.location,
            p.rating,
            p.reviews
        FROM requests r
        JOIN users p
            ON p.id =
                CASE
                    WHEN r.sender_id = ?
                    THEN r.receiver_id
                    ELSE r.sender_id
                END
        WHERE r.status = 'accepted'
        AND (
            r.sender_id = ?
            OR r.receiver_id = ?
        )
        ORDER BY r.accepted_at DESC
    """, (
        user["id"],
        user["id"],
        user["id"]
    )).fetchall()

    conn.close()

    return jsonify([
        {
            "id": row["id"],
            "name": row["name"],
            "avatar": row["avatar"],
            "location": row["location"],
            "rating": row["rating"],
            "reviews": row["reviews"]
        }
        for row in rows
    ])


# ============================================================
# CHAT
# ============================================================

@app.get("/api/messages/<int:person_id>")
def get_messages(person_id):
    user = current_user()

    if not user:
        return jsonify({
            "success": False,
            "message": "Please sign in."
        }), 401

    conn = get_db()

    if not connected(
        conn,
        user["id"],
        person_id
    ):
        conn.close()

        return jsonify({
            "success": False,
            "message": "You need an accepted connection before chatting."
        }), 403

    rows = conn.execute("""
        SELECT
            m.*,
            u.name AS sender_name
        FROM messages m
        JOIN users u
            ON u.id = m.sender_id
        WHERE
            (
                m.sender_id = ?
                AND m.receiver_id = ?
            )
            OR
            (
                m.sender_id = ?
                AND m.receiver_id = ?
            )
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
            "type": "me"
                if row["sender_id"] == user["id"]
                else "them",
            "text": row["message"],
            "sender": row["sender_name"],
            "createdAt": row["created_at"]
        }
        for row in rows
    ])


@app.post("/api/messages/<int:person_id>")
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

    if len(message) > 2000:
        return jsonify({
            "success": False,
            "message": "Message is too long."
        }), 400

    conn = get_db()

    if not connected(
        conn,
        user["id"],
        person_id
    ):
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
        VALUES (?, ?, ?)
    """, (
        user["id"],
        person_id,
        message
    ))

    add_notification(
        conn,
        person_id,
        "New message 💬",
        f"{user['name']} sent you a message.",
        "message"
    )

    conn.commit()
    conn.close()

    return jsonify({
        "success": True
    })


# ============================================================
# REVIEWS
# ============================================================

@app.post("/api/reviews/<int:person_id>")
def review(person_id):
    user = current_user()

    if not user:
        return jsonify({
            "success": False,
            "message": "Please sign in."
        }), 401

    data = request.get_json() or {}

    try:
        rating = int(data.get("rating", 0))
    except (ValueError, TypeError):
        rating = 0

    comment = data.get(
        "comment",
        ""
    ).strip()

    if rating < 1 or rating > 5:
        return jsonify({
            "success": False,
            "message": "Rating must be between 1 and 5."
        }), 400

    conn = get_db()

    if not connected(
        conn,
        user["id"],
        person_id
    ):
        conn.close()

        return jsonify({
            "success": False,
            "message": "You need a connection before leaving a review."
        }), 403

    already = conn.execute("""
        SELECT id
        FROM reviews
        WHERE reviewer_id = ?
        AND reviewed_id = ?
    """, (
        user["id"],
        person_id
    )).fetchone()

    if already:
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
        VALUES (?, ?, ?, ?)
    """, (
        user["id"],
        person_id,
        rating,
        comment
    ))

    stats = conn.execute("""
        SELECT
            AVG(rating) AS average,
            COUNT(*) AS total
        FROM reviews
        WHERE reviewed_id = ?
    """, (
        person_id,
    )).fetchone()

    conn.execute("""
        UPDATE users
        SET
            rating = ?,
            reviews = ?
        WHERE id = ?
    """, (
        round(stats["average"], 1),
        stats["total"],
        person_id
    ))

    add_notification(
        conn,
        person_id,
        "New review ⭐",
        f"{user['name']} left you a {rating}-star review.",
        "review"
    )

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Review submitted!"
    })


# ============================================================
# NOTIFICATIONS
# ============================================================

@app.get("/api/notifications")
def notifications():
    user = current_user()

    if not user:
        return jsonify([])

    conn = get_db()

    rows = conn.execute("""
        SELECT *
        FROM notifications
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 30
    """, (
        user["id"],
    )).fetchall()

    conn.close()

    return jsonify([
        {
            "id": row["id"],
            "title": row["title"],
            "message": row["message"],
            "type": row["notification_type"],
            "read": bool(row["is_read"]),
            "createdAt": row["created_at"]
        }
        for row in rows
    ])


@app.post("/api/notifications/read")
def mark_notifications_read():
    user = current_user()

    if not user:
        return jsonify({
            "success": False
        }), 401

    conn = get_db()

    conn.execute("""
        UPDATE notifications
        SET is_read = 1
        WHERE user_id = ?
    """, (
        user["id"],
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "success": True
    })


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":
    init_db()

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
```
