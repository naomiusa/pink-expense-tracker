import os
import math
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

from flask import (
    Flask, render_template, request, jsonify,
    redirect, url_for, session
)

from werkzeug.security import (
    generate_password_hash, check_password_hash
)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")


def get_db_connection():
    return psycopg2.connect(
        DATABASE_URL,
        sslmode="require"
    )


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id BIGSERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # Add a separate budget for every user.
    cur.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS budget NUMERIC(12, 2) NOT NULL DEFAULT 0
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id BIGSERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            amount NUMERIC(12, 2) NOT NULL,
            date TEXT,
            user_id BIGINT NOT NULL REFERENCES users(id)
                ON DELETE CASCADE
        )
    """)

    conn.commit()
    cur.close()
    conn.close()


init_db()


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            return "Please fill in all fields."

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()

        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO users (username, password)
                VALUES (%s, %s)
                """,
                (username, hashed_password)
            )
            conn.commit()

        except psycopg2.IntegrityError:
            conn.rollback()
            return "Username already exists."

        finally:
            conn.close()

        return redirect(url_for("login"))

    return render_template("auth.html", action="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            "SELECT * FROM users WHERE username = %s",
            (username,)
        )

        user = cur.fetchone()

        cur.close()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("home"))

        return "Invalid username or password."

    return render_template("auth.html", action="login")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/budget", methods=["GET", "POST"])
def budget():
    if "user_id" not in session:
        return jsonify({"error": "Please log in"}), 401

    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        amount = data.get("budget")

        try:
            amount = float(amount)
            if not math.isfinite(amount) or amount <= 0:
                raise ValueError
        except (ValueError, TypeError):
            cur.close()
            conn.close()
            return jsonify({"error": "Enter a valid budget"}), 400

        cur.execute(
            """
            UPDATE users
            SET budget = %s
            WHERE id = %s
            """,
            (amount, session["user_id"])
        )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "message": "Budget saved successfully!",
            "budget": amount
        })

    cur.execute(
        "SELECT budget FROM users WHERE id = %s",
        (session["user_id"],)
    )

    result = cur.fetchone()
    cur.close()
    conn.close()

    return jsonify({
        "budget": float(result[0]) if result else 0
    })


@app.route("/add_expense", methods=["POST"])
def add_expense():
    if "user_id" not in session:
        return jsonify({"error": "Please log in"}), 401

    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "Invalid request"}), 400

    name = data.get("name")
    amount = data.get("amount")
    date = data.get("date")

    if not name or amount is None or not date:
        return jsonify({"error": "Please fill in all fields"}), 400

    try:
        amount = float(amount)
        if not math.isfinite(amount) or amount <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "Enter a valid amount"}), 400

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO expenses (name, amount, date, user_id)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        (name.strip(), amount, date, session["user_id"])
    )

    expense_id = cur.fetchone()[0]

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({
        "message": "Expense saved successfully!",
        "id": expense_id
    })


@app.route("/expenses", methods=["GET"])
def get_expenses():
    if "user_id" not in session:
        return jsonify({"error": "Please log in"}), 401

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        """
        SELECT * FROM expenses
        WHERE user_id = %s
        ORDER BY id DESC
        """,
        (session["user_id"],)
    )

    rows = cur.fetchall()
    expenses = [dict(row) for row in rows]

    cur.close()
    conn.close()

    return jsonify(expenses)


@app.route("/delete_expense/<int:expense_id>", methods=["DELETE"])
def delete_expense(expense_id):
    if "user_id" not in session:
        return jsonify({"error": "Please log in"}), 401

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        DELETE FROM expenses
        WHERE id = %s AND user_id = %s
        """,
        (expense_id, session["user_id"])
    )

    deleted = cur.rowcount

    conn.commit()
    cur.close()
    conn.close()

    if deleted == 0:
        return jsonify({"error": "Expense not found"}), 404

    return jsonify({
        "message": "Expense deleted successfully!"
    })


@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template("index.html")


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        debug=True,
        use_reloader=False
    )
