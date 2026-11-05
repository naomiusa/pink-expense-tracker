import sqlite3
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
app = Flask(__name__)
app.secret_key = "change-this-to-a-random-secret-key"

expenses = []
def init_db():
    conn = sqlite3.connect("expenses.db")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            amount REAL NOT NULL,
            date TEXT
        )
    """)

    columns = [
        row[1] for row in conn.execute(
            "PRAGMA table_info(expenses)"
        ).fetchall()
    ]

    if "user_id" not in columns:
        conn.execute(
            "ALTER TABLE expenses ADD COLUMN user_id INTEGER"
        )

    conn.commit()
    conn.close()

init_db()
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            return "Please fill in all fields."

        hashed_password = generate_password_hash(password)

        conn = sqlite3.connect("expenses.db")

        try:
            conn.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, hashed_password)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return "Username already exists."

        conn.close()
        return redirect(url_for("login"))

    return render_template("auth.html", action="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn = sqlite3.connect("expenses.db")
        conn.row_factory = sqlite3.Row

        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            return redirect(url_for("home"))

        return "Invalid username or password."

    return render_template("auth.html", action="login")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/add_expense", methods=["POST"])
def add_expense():
    if "user_id" not in session:
        return jsonify({"error": "Please log in"}), 401

    data = request.get_json()

    name = data.get("name")
    amount = data.get("amount")
    date = data.get("date")

    conn = sqlite3.connect("expenses.db")

    cursor = conn.execute(
        """INSERT INTO expenses
        (name, amount, date, user_id)
        VALUES (?, ?, ?, ?)""",
        (name, amount, date, session["user_id"])
    )

    conn.commit()
    expense_id = cursor.lastrowid
    conn.close()

    return jsonify({
        "message": "Expense saved successfully!",
        "id": expense_id
    })
@app.route("/expenses", methods=["GET"])
def get_expenses():
    if "user_id" not in session:
        return jsonify({"error": "Please log in"}), 401

    conn = sqlite3.connect("expenses.db")
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        "SELECT * FROM expenses WHERE user_id = ?",
        (session["user_id"],)
    ).fetchall()

    expenses = [dict(row) for row in rows]

    conn.close()

    return jsonify(expenses)
@app.route("/delete_expense/<int:expense_id>", methods=["DELETE"])
def delete_expense(expense_id):
    if "user_id" not in session:
        return jsonify({"error": "Please log in"}), 401

    conn = sqlite3.connect("expenses.db")

    conn.execute(
        "DELETE FROM expenses WHERE id = ? AND user_id = ?",
        (expense_id, session["user_id"])
    )

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Expense deleted successfully!"
    })


@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template("index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, use_reloader=False)
