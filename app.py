from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
import os

app = Flask(__name__)

# Change this in production
app.secret_key = "skillswap-india-secret-key-change-this"

DATABASE = "skillswap.db"


# =========================================================
# DATABASE
# =========================================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()

    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        type TEXT DEFAULT 'Student',
        location TEXT DEFAULT 'Online',
        languages TEXT DEFAULT '',
        bio TEXT DEFAULT '',
        avatar TEXT DEFAULT '🧑🏻',
        rating REAL DEFAULT 0,
        reviews INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS skills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    );

    CREATE TABLE IF NOT EXISTS user_skills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        skill TEXT NOT NULL,
        skill_type TEXT NOT NULL,

        FOREIGN KEY(user_id)
            REFERENCES users(id)
            ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS availability (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        value TEXT NOT NULL,

        FOREIGN KEY(user_id)
            REFERENCES users(id)
            ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS swap_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        sender_id INTEGER NOT NULL,
        receiver_id INTEGER NOT NULL,

        skill_wanted TEXT NOT NULL,
        skill_offered TEXT NOT NULL,
        message TEXT,

        status TEXT DEFAULT 'pending',

        created_at TEXT NOT NULL,
        accepted_at TEXT,

        FOREIGN KEY(sender_id)
            REFERENCES users(id)
            ON DELETE CASCADE,

        FOREIGN KEY(receiver_id)
            REFERENCES users(id)
            ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        sender_id INTEGER NOT NULL,
        receiver_id INTEGER NOT NULL,

        message TEXT NOT NULL,

        created_at TEXT NOT NULL,

        FOREIGN KEY(sender_id)
            REFERENCES users(id)
            ON DELETE CASCADE,

        FOREIGN KEY(receiver_id)
            REFERENCES users(id)
            ON DELETE CASCADE
    );
    """)

    conn.commit()
    conn.close()


# =========================================================
# HELPERS
# =========================================================

def current_user():
    user_id = session.get("user_id")

    if not user_id:
        return None

    conn = get_db()

    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    conn.close()

    return user


def login_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if not session.get("user_id"):
            return jsonify({
                "success": False,
                "message": "Please sign in first."
            }), 401

        return function(*args, **kwargs)

    return wrapper


def split_values(value):
    if not value:
        return []

    return [
        item.strip()
        for item in value.split(",")
        if item.strip()
    ]


def get_user_skills(user_id, skill_type):

    conn = get_db()

    rows = conn.execute("""
        SELECT skill
        FROM user_skills
        WHERE user_id = ?
        AND skill_type = ?
    """, (user_id, skill_type)).fetchall()

    conn.close()

    return [row["skill"] for row in rows]


def get_user_languages(user):

    if not user["languages"]:
        return []

    return split_values(user["languages"])


def get_user_availability(user_id):

    conn = get_db()

    rows = conn.execute("""
        SELECT value
        FROM availability
        WHERE user_id = ?
    """, (user_id,)).fetchall()

    conn.close()

    return [row["value"] for row in rows]


# =========================================================
# SKILL MATCHING
# =========================================================

ALIASES = {
    "python": ["python", "py"],
    "javascript": ["javascript", "js"],
    "ai": [
        "ai",
        "artificial intelligence",
        "machine learning",
        "ml"
    ],
    "maths": [
        "math",
        "maths",
        "mathematics"
    ],
    "telugu": ["telugu"],
    "guitar": ["guitar"],
    "cricket": ["cricket"]
}


def normalize_skill(skill):

    return (
        skill.lower()
        .replace("-", " ")
        .replace("_", " ")
        .strip()
    )


def skill_matches(a, b):

    x = normalize_skill(a)
    y = normalize_skill(b)

    if not x or not y:
        return False

    if x == y:
        return True

    for group in ALIASES.values():

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
            "score": 80,
            "reasons": [
                "Complementary skills",
                "Active member"
            ]
        }

    user_teach = get_user_skills(user["id"], "teach")
    user_want = get_user_skills(user["id"], "want")

    person_teach = get_user_skills(person["id"], "teach")
    person_want = get_user_skills(person["id"], "want")

    user_languages = get_user_languages(user)
    person_languages = get_user_languages(person)

    user_availability = get_user_availability(user["id"])
    person_availability = get_user_availability(person["id"])

    score = 35
    reasons = []

    learn = overlap(user_want, person_teach)
    teach = overlap(user_teach, person_want)
    language = overlap(user_languages, person_languages)
    available = overlap(
        user_availability,
        person_availability
    )

    if learn:

        score += min(28, learn * 14)

        reasons.append(
            "They teach what you want"
        )

    if teach:

        score += min(22, teach * 11)

        reasons.append(
            "They want what you teach"
        )

    if language:

        score += min(8, language * 4)

        reasons.append(
            "Shared language"
        )

    if available:

        score += min(7, available * 4)

        reasons.append(
            "Matching availability"
        )

    user_city = (user["location"] or "").split(",")[0].lower()
    person_city = (person["location"] or "").split(",")[0].lower()

    if user_city and user_city == person_city:

        score += 8

        reasons.append("Same city")

    if not reasons:

        reasons.append(
            "Good general compatibility"
        )

    return {
        "score": min(99, max(50, round(score))),
        "reasons": reasons[:2]
    }


# =========================================================
# MAIN PAGE
# =========================================================

@app.route("/")
def index():

    return render_template(
        "index.html",
        user=current_user()
    )


# =========================================================
# SIGN UP
# =========================================================

@app.route("/api/signup", methods=["POST"])
def signup():

    data = request.get_json() or {}

    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    user_type = data.get(
        "type",
        "Teen Student"
    )

    location = data.get(
        "location",
        "Online"
    ).strip()

    languages = data.get(
        "languages",
        ""
    ).strip()

    bio = data.get(
        "bio",
        ""
    ).strip()

    teach = data.get(
        "teach",
        ""
    )

    want = data.get(
        "want",
        ""
    )

    availability = data.get(
        "availability",
        []
    )

    if not name or not email or not password:

        return jsonify({
            "success": False,
            "message": "Please fill in your name, email and password."
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
        }), 400

    password_hash = generate_password_hash(password)

    cursor = conn.execute("""
        INSERT INTO users
        (
            name,
            email,
            password,
            type,
            location,
            languages,
            bio,
            avatar,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        name,
        email,
        password_hash,
        user_type,
        location,
        languages,
        bio or "Learning and sharing skills.",
        "🧑🏻",
        datetime.utcnow().isoformat()
    ))

    user_id = cursor.lastrowid

    # Teaching skills
    for skill in split_values(teach):

        conn.execute("""
            INSERT INTO user_skills
            (user_id, skill, skill_type)
            VALUES (?, ?, 'teach')
        """, (user_id, skill))

    # Wanted skills
    for skill in split_values(want):

        conn.execute("""
            INSERT INTO user_skills
            (user_id, skill, skill_type)
            VALUES (?, ?, 'want')
        """, (user_id, skill))

    # Availability
    for item in availability:

        conn.execute("""
            INSERT INTO availability
            (user_id, value)
            VALUES (?, ?)
        """, (user_id, item))

    conn.commit()

    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    conn.close()

    session["user_id"] = user_id

    return jsonify({
        "success": True,
        "message": f"Welcome to SkillSwap India, {name}!",
        "user": dict(user)
    })


# =========================================================
# SIGN IN
# =========================================================

@app.route("/api/signin", methods=["POST"])
def signin():

    data = request.get_json() or {}

    email = data.get(
        "email",
        ""
    ).strip().lower()

    password = data.get(
        "password",
        ""
    )

    if not email or not password:

        return jsonify({
            "success": False,
            "message": "Please enter your email and password."
        }), 400

    conn = get_db()

    user = conn.execute("""
        SELECT *
        FROM users
        WHERE email = ?
    """, (email,)).fetchone()

    conn.close()

    if not user:

        return jsonify({
            "success": False,
            "message": "Account not found."
        }), 404

    if not check_password_hash(
        user["password"],
        password
    ):

        return jsonify({
            "success": False,
            "message": "Incorrect email or password."
        }), 401

    session["user_id"] = user["id"]

    return jsonify({
        "success": True,
        "message": f"Welcome back, {user['name']}!",
        "user": dict(user)
    })


# =========================================================
# LOG OUT
# =========================================================

@app.route("/api/logout", methods=["POST"])
def logout():

    session.clear()

    return jsonify({
        "success": True
    })


# =========================================================
# CURRENT USER
# =========================================================

@app.route("/api/me")
def me():

    user = current_user()

    if not user:

        return jsonify({
            "logged_in": False
        })

    return jsonify({
        "logged_in": True,
        "user": dict(user),
        "teach": get_user_skills(
            user["id"],
            "teach"
        ),
        "want": get_user_skills(
            user["id"],
            "want"
        ),
        "availability": get_user_availability(
            user["id"]
        )
    })


# =========================================================
# DISCOVER USERS
# =========================================================

@app.route("/api/people")
def people():

    user = current_user()

    conn = get_db()

    rows = conn.execute("""
        SELECT *
        FROM users
        ORDER BY created_at DESC
    """).fetchall()

    conn.close()

    results = []

    for person in rows:

        if user and person["id"] == user["id"]:
            continue

        match = calculate_match(
            user,
            person
        )

        results.append({

            "id": person["id"],

            "name": person["name"],

            "avatar": person["avatar"],

            "location": person["location"],

            "type": person["type"],

            "languages": get_user_languages(
                person
            ),

            "teach": get_user_skills(
                person["id"],
                "teach"
            ),

            "want": get_user_skills(
                person["id"],
                "want"
            ),

            "availability": get_user_availability(
                person["id"]
            ),

            "rating": person["rating"],

            "reviews": person["reviews"],

            "bio": person["bio"],

            "match": match["score"],

            "reasons": match["reasons"]
        })

    results.sort(
        key=lambda x: x["match"],
        reverse=True
    )

    return jsonify(results)


# =========================================================
# SEND REQUEST
# =========================================================

@app.route("/api/requests", methods=["POST"])
@login_required
def send_request():

    user = current_user()

    data = request.get_json() or {}

    receiver_id = data.get("receiver_id")

    wanted = data.get(
        "skill_wanted",
        ""
    ).strip()

    offered = data.get(
        "skill_offered",
        ""
    ).strip()

    message = data.get(
        "message",
        ""
    ).strip()

    if not receiver_id or not wanted or not offered:

        return jsonify({
            "success": False,
            "message": "Please provide all required fields."
        }), 400

    if int(receiver_id) == user["id"]:

        return jsonify({
            "success": False,
            "message": "You cannot request a swap with yourself."
        }), 400

    conn = get_db()

    existing = conn.execute("""
        SELECT id
        FROM swap_requests

        WHERE
        (
            sender_id = ?
            AND receiver_id = ?
        )

        OR

        (
            sender_id = ?
            AND receiver_id = ?
        )
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
        }), 400

    conn.execute("""
        INSERT INTO swap_requests
        (
            sender_id,
            receiver_id,
            skill_wanted,
            skill_offered,
            message,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, 'pending', ?)
    """, (
        user["id"],
        receiver_id,
        wanted,
        offered,
        message or "I'd love to exchange skills with you!",
        datetime.utcnow().isoformat()
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Skill-swap request sent!"
    })


# =========================================================
# GET REQUESTS
# =========================================================

@app.route("/api/requests")
@login_required
def requests():

    user = current_user()

    conn = get_db()

    rows = conn.execute("""
        SELECT
            r.*,

            sender.name AS sender_name,
            sender.avatar AS sender_avatar,

            receiver.name AS receiver_name,
            receiver.avatar AS receiver_avatar

        FROM swap_requests r

        JOIN users sender
            ON sender.id = r.sender_id

        JOIN users receiver
            ON receiver.id = r.receiver_id

        WHERE
            r.sender_id = ?
            OR
            r.receiver_id = ?

        ORDER BY r.created_at DESC
    """, (
        user["id"],
        user["id"]
    )).fetchall()

    conn.close()

    return jsonify([
        dict(row)
        for row in rows
    ])


# =========================================================
# ACCEPT / REJECT REQUEST
# =========================================================

@app.route(
    "/api/requests/<int:request_id>",
    methods=["PATCH"]
)
@login_required
def update_request(request_id):

    user = current_user()

    data = request.get_json() or {}

    status = data.get("status")

    if status not in [
        "accepted",
        "rejected"
    ]:

        return jsonify({
            "success": False,
            "message": "Invalid status."
        }), 400

    conn = get_db()

    row = conn.execute("""
        SELECT *
        FROM swap_requests

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

    accepted_at = (
        datetime.utcnow().isoformat()
        if status == "accepted"
        else None
    )

    conn.execute("""
        UPDATE swap_requests

        SET
            status = ?,
            accepted_at = ?

        WHERE id = ?
    """, (
        status,
        accepted_at,
        request_id
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"Request {status}."
    })


# =========================================================
# CONNECTIONS
# =========================================================

@app.route("/api/connections")
@login_required
def connections():

    user = current_user()

    conn = get_db()

    rows = conn.execute("""
        SELECT
            r.*,

            sender.name AS sender_name,
            sender.avatar AS sender_avatar,

            receiver.name AS receiver_name,
            receiver.avatar AS receiver_avatar

        FROM swap_requests r

        JOIN users sender
            ON sender.id = r.sender_id

        JOIN users receiver
            ON receiver.id = r.receiver_id

        WHERE
            r.status = 'accepted'
            AND
            (
                r.sender_id = ?
                OR
                r.receiver_id = ?
            )

        ORDER BY r.accepted_at DESC
    """, (
        user["id"],
        user["id"]
    )).fetchall()

    conn.close()

    result = []

    for row in rows:

        data = dict(row)

        if row["sender_id"] == user["id"]:

            data["person_id"] = row["receiver_id"]
            data["person_name"] = row["receiver_name"]
            data["person_avatar"] = row["receiver_avatar"]

        else:

            data["person_id"] = row["sender_id"]
            data["person_name"] = row["sender_name"]
            data["person_avatar"] = row["sender_avatar"]

        result.append(data)

    return jsonify(result)


# =========================================================
# CHAT
# =========================================================

@app.route(
    "/api/messages/<int:person_id>"
)
@login_required
def get_messages(person_id):

    user = current_user()

    conn = get_db()

    messages = conn.execute("""
        SELECT
            m.*,
            u.name AS sender_name,
            u.avatar AS sender_avatar

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

        ORDER BY m.created_at ASC
    """, (
        user["id"],
        person_id,
        person_id,
        user["id"]
    )).fetchall()

    conn.close()

    return jsonify([
        dict(row)
        for row in messages
    ])


@app.route(
    "/api/messages/<int:person_id>",
    methods=["POST"]
)
@login_required
def send_message(person_id):

    user = current_user()

    data = request.get_json() or {}

    message = data.get(
        "message",
        ""
    ).strip()

    if not message:

        return jsonify({
            "success": False,
            "message": "Message cannot be empty."
        }), 400

    conn = get_db()

    # Make sure they are connected
    connection = conn.execute("""
        SELECT id

        FROM swap_requests

        WHERE status = 'accepted'

        AND
        (
            (
                sender_id = ?
                AND receiver_id = ?
            )

            OR

            (
                sender_id = ?
                AND receiver_id = ?
            )
        )
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
            message,
            created_at
        )
        VALUES (?, ?, ?, ?)
    """, (
        user["id"],
        person_id,
        message,
        datetime.utcnow().isoformat()
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "success": True
    })


# =========================================================
# SEARCH
# =========================================================

@app.route("/api/search")
def search():

    query = request.args.get(
        "q",
        ""
    ).strip().lower()

    user = current_user()

    conn = get_db()

    rows = conn.execute("""
        SELECT *
        FROM users
    """).fetchall()

    conn.close()

    results = []

    for person in rows:

        if user and person["id"] == user["id"]:
            continue

        skills_teach = get_user_skills(
            person["id"],
            "teach"
        )

        skills_want = get_user_skills(
            person["id"],
            "want"
        )

        languages = get_user_languages(
            person
        )

        searchable = " ".join([
            person["name"],
            person["location"],
            person["type"],
            person["bio"],
            person["languages"],
            " ".join(skills_teach),
            " ".join(skills_want),
            " ".join(languages)
        ]).lower()

        if query in searchable:

            match = calculate_match(
                user,
                person
            )

            results.append({
                "id": person["id"],
                "name": person["name"],
                "avatar": person["avatar"],
                "location": person["location"],
                "type": person["type"],
                "teach": skills_teach,
                "want": skills_want,
                "languages": languages,
                "availability": get_user_availability(
                    person["id"]
                ),
                "rating": person["rating"],
                "reviews": person["reviews"],
                "bio": person["bio"],
                "match": match["score"],
                "reasons": match["reasons"]
            })

    results.sort(
        key=lambda x: x["match"],
        reverse=True
    )

    return jsonify(results)


# =========================================================
# RUN SERVER
# =========================================================

if __name__ == "__main__":

    init_db()

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )