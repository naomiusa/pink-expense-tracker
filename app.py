import sqlite3
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

expenses = []
def init_db():
    conn = sqlite3.connect("expenses.db")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            amount REAL NOT NULL,
            date TEXT
        )
    """)

    conn.commit()
    conn.close()


init_db()

@app.route("/add_expense", methods=["POST"])
def add_expense():
    data = request.get_json()

    name = data.get("name")
    amount = data.get("amount")
    date = data.get("date")

    conn = sqlite3.connect("expenses.db")

    cursor = conn.execute(
        "INSERT INTO expenses (name, amount, date) VALUES (?, ?, ?)",
        (name, amount, date)
    )

    conn.commit()

    expense_id = cursor.lastrowid
    conn.close()

    return jsonify({
        "message": "Expense saved successfully!",
        "id": expense_id,
        "name": name,
        "amount": amount,
        "date": date
    })


@app.route("/expenses", methods=["GET"])
def get_expenses():
    conn = sqlite3.connect("expenses.db")
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        "SELECT * FROM expenses"
    ).fetchall()

    expenses = [dict(row) for row in rows]

    conn.close()

    return jsonify(expenses)

@app.route("/delete_expense/<int:expense_id>", methods=["DELETE"])
def delete_expense(expense_id):
    conn = sqlite3.connect("expenses.db")

    conn.execute(
        "DELETE FROM expenses WHERE id = ?",
        (expense_id,)
    )

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Expense deleted successfully!"
    })


@app.route("/")
def home():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, use_reloader=False)
