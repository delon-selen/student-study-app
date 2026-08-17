from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3

app = Flask(__name__)

app.secret_key = "local-study-app-key"

DATABASE = "study.db"


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def create_database():
    connection = get_db()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            subject TEXT NOT NULL,
            score INTEGER NOT NULL,
            total INTEGER NOT NULL
        )
    """)

    # Make sure older databases have user_id
    columns = connection.execute(
        "PRAGMA table_info(results)"
    ).fetchall()

    column_names = [column["name"] for column in columns]

    if "user_id" not in column_names:
        connection.execute(
            "ALTER TABLE results ADD COLUMN user_id INTEGER"
        )

    # Study notes
    connection.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    connection.commit()
    connection.close()
    
 


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"].strip()
        password = request.form["password"]

        if not username or not password:
            return render_template(
                "register.html",
                error="Please enter a username and password."
            )

        connection = get_db()

        existing_user = connection.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        if existing_user:
            connection.close()

            return render_template(
                "register.html",
                error="That username already exists."
            )

        connection.execute(
            """
            INSERT INTO users (username, password)
            VALUES (?, ?)
            """,
            (username, password)
        )

        connection.commit()
        connection.close()

        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        connection = get_db()

        user = connection.execute(
            """
            SELECT * FROM users
            WHERE username = ? AND password = ?
            """,
            (username, password)
        ).fetchone()

        connection.close()

        if user:
            session["user_id"] = user["id"]
            session["username"] = user["username"]

            return redirect(url_for("home"))

        return render_template(
            "login.html",
            error="Invalid username or password."
        )

    return render_template("login.html")


@app.route("/")
def home():

    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template(
        "index.html",
        username=session["username"]
    )


@app.route("/save-result", methods=["POST"])
def save_result():

    if "user_id" not in session:
        return jsonify({
            "success": False,
            "message": "You must be logged in."
        }), 401

    data = request.get_json()

    subject = data["subject"]
    score = data["score"]
    total = data["total"]

    connection = get_db()

    connection.execute(
        """
        INSERT INTO results
        (user_id, subject, score, total)
        VALUES (?, ?, ?, ?)
        """,
        (
            session["user_id"],
            subject,
            score,
            total
        )
    )

    connection.commit()
    connection.close()

    return jsonify({
        "success": True,
        "message": "Result saved successfully"
    })
@app.route("/save-notes", methods=["POST"])
def save_notes():

    if "user_id" not in session:
        return jsonify({
            "success": False,
            "message": "You must be logged in."
        }), 401

    data = request.get_json()
    content = data.get("content", "").strip()

    if not content:
        return jsonify({
            "success": False,
            "message": "Please write something first."
        }), 400

    connection = get_db()

    connection.execute(
        """
        INSERT INTO notes (user_id, content)
        VALUES (?, ?)
        """,
        (session["user_id"], content)
    )

    connection.commit()
    connection.close()

    return jsonify({
        "success": True,
        "message": "Notes saved successfully."
    })


@app.route("/get-notes")
def get_notes():

    if "user_id" not in session:
        return jsonify({
            "success": False,
            "message": "You must be logged in."
        }), 401

    connection = get_db()

    notes = connection.execute(
        """
        SELECT content, created_at
        FROM notes
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    connection.close()

    return jsonify([
        {
            "content": note["content"],
            "created_at": note["created_at"]
        }
        for note in notes
    ])

@app.route("/delete-note/<int:note_id>", methods=["DELETE"])
def delete_note(note_id):

    if "user_id" not in session:
        return jsonify({
            "success": False,
            "message": "You must be logged in."
        }), 401

    connection = get_db()

    connection.execute(
        """
        DELETE FROM notes
        WHERE id = ? AND user_id = ?
        """,
        (note_id, session["user_id"])
    )

    connection.commit()
    connection.close()

    return jsonify({
        "success": True,
        "message": "Note deleted successfully."
    })

@app.route("/progress")
def progress():

    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db()

    results = connection.execute(
        """
        SELECT subject, score, total
        FROM results
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    stats = connection.execute(
        """
        SELECT
            COUNT(*) AS quizzes,
            COALESCE(SUM(score), 0) AS total_score,
            COALESCE(SUM(total), 0) AS total_questions
        FROM results
        WHERE user_id = ?
        """,
        (session["user_id"],)
    ).fetchone()

    connection.close()

    if stats["total_questions"] > 0:
        average = round(
            (stats["total_score"] / stats["total_questions"]) * 100
        )
    else:
        average = 0

    return render_template(
        "progress.html",
        results=results,
        quizzes=stats["quizzes"],
        average=average
    )


@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


create_database()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
    