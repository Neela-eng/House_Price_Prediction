from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector
import pandas as pd
import joblib
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "your_secret_key_here"

# ---------------- DATABASE CONFIG ----------------
db_config = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "",
    "database": "house_app_database"
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

# ---------------- LOAD ML MODEL ----------------
model = joblib.load("house_price_model.pkl")

# ---------------- HOME ----------------
@app.route("/")
def homepage():
    return render_template("homepage.html")

# ---------------- SIGN UP ----------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        usertype = request.form["usertype"].strip().lower()
        username = request.form["username"].strip()
        email = request.form["email"].strip()
        password = request.form["password"]
        confirm = request.form["confirmpassword"]

        if password != confirm:
            return render_template("signup.html", error="Passwords do not match")

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO userdata (Usertype, Username, Email, Password) VALUES (%s,%s,%s,%s)",
                (usertype, username, email, hashed_password)
            )
            conn.commit()
            return redirect(url_for("signin"))
        except:
            return render_template("signup.html", error="Username or email already exists")
        finally:
            cursor.close()
            conn.close()

    return render_template("signup.html")

@app.route("/signin", methods=["GET", "POST"])
def signin():
    if request.method == "POST":
        usertype = request.form["usertype"].strip().lower()
        username = request.form["username"].strip()
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # ❌ DO NOT check password in SQL
        cursor.execute(
            "SELECT * FROM userdata WHERE Username=%s AND LOWER(Usertype)=%s",
            (username, usertype)
        )
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if not user:
            return render_template("signin.html", error="Invalid credentials")

        stored_hash = user["Password"]

        # ✅ CORRECT password verification
        if check_password_hash(stored_hash, password):
            session["user_id"] = user["id"]
            session["username"] = user["Username"]
            session["usertype"] = user["Usertype"].lower()
            return redirect(url_for("dashboard"))

        return render_template("signin.html", error="Invalid credentials")

    return render_template("signin.html")

# ---------------- DASHBOARD ROUTER ----------------
@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect(url_for("signin"))

    role = session["usertype"]
    if role == "admin":
        return redirect(url_for("admin_dashboard"))
    elif role == "agent":
        return redirect(url_for("agent_dashboard"))
    else:
        return redirect(url_for("customer_dashboard"))

# ---------------- DASHBOARDS ----------------
@app.route("/admin_dashboard")
def admin_dashboard():
    if session.get("usertype") != "admin":
        return redirect(url_for("signin"))
    return render_template("admindashboard.html", username=session["username"])

@app.route("/agent_dashboard")
def agent_dashboard():
    if session.get("usertype") != "agent":
        return redirect(url_for("signin"))
    return render_template("agentdashboard.html", username=session["username"])

@app.route("/customer_dashboard")
def customer_dashboard():
    if session.get("usertype") != "customer":
        return redirect(url_for("signin"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) AS total_users FROM userdata")
    user_count = cursor.fetchone()["total_users"]

    cursor.execute("SELECT COUNT(*) AS total_predictions FROM house_data")
    prediction_count = cursor.fetchone()["total_predictions"]

    cursor.execute("SELECT COUNT(*) AS total_feedbacks FROM feedback_data")
    feedback_count = cursor.fetchone()["total_feedbacks"]

    cursor.close()
    conn.close()

    return render_template(
        "customerdashboard.html",
        username=session["username"],
        user_count=user_count,
        prediction_count=prediction_count,
        feedback_count=feedback_count
    )

# ---------------- PROFILE ----------------
@app.route("/profile")
def profile():
    if "username" not in session:
        return redirect(url_for("signin"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM userdata WHERE Username=%s", (session["username"],))
    user = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template("profile.html", user=user)

# ---------------- CHANGE PASSWORD ----------------
@app.route("/change_password", methods=["POST"])
def change_password():
    if "username" not in session:
        return redirect(url_for("signin"))

    old_password = request.form["old_password"]
    new_password = request.form["new_password"]
    confirm = request.form["confirm_password"]

    if new_password != confirm:
        return render_template("profile.html", error="Passwords do not match")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM userdata WHERE Username=%s", (session["username"],))
    user = cursor.fetchone()

    stored_password = user["Password"]

    valid = (
        check_password_hash(stored_password, old_password)
        if stored_password.startswith("pbkdf2:")
        else stored_password == old_password
    )

    if not valid:
        cursor.close()
        conn.close()
        return render_template("profile.html", user=user, error="Incorrect current password")

    new_hash = generate_password_hash(new_password)

    cursor.execute(
        "UPDATE userdata SET Password=%s WHERE id=%s",
        (new_hash, user["id"])
    )
    conn.commit()

    cursor.close()
    conn.close()

    return render_template("profile.html", user=user, message="Password updated successfully")

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("homepage"))

# ---------------- RUN APP ----------------
if __name__ == "__main__":
    app.run(debug=True)
