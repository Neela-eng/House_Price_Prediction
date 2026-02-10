from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from werkzeug.security import generate_password_hash,  check_password_hash
import pandas as pd
import joblib
from data_encoder import FurnishingEncoder, FrequencyEncoder
import os
from datetime import datetime
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split

app = Flask(__name__)
app.secret_key = "your_secret_key_here"

# Load ML model
model = joblib.load("house_price_model.pkl")


# ---------- DATABASE CONNECTION ----------
def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="house_app_database"
    )

def get_model_time():
    if os.path.exists("house_price_model.pkl"):
        mtime = os.path.getmtime("house_price_model.pkl")
        return datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
    return "Never"


# ---------- HOMEPAGE ----------
@app.route("/")
def homepage():
    return render_template("homepage.html")


# ---------- SIGNUP ----------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        # Get form data
        usertype = request.form.get("usertype")
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        confirmpassword = request.form.get("confirmpassword")

        # Basic validation
        if not all([usertype, username, email, password, confirmpassword]):
            return render_template("signup.html", error="All fields are required")

        if password != confirmpassword:
            return render_template("signup.html", error="Passwords do not match")

        try:
            # Hash password (recommended even if column is small)
            hashed_password = generate_password_hash(password)

            conn = get_connection()
            cursor = conn.cursor()

            sql = """
                INSERT INTO userdata (Username, Usertype, Email, Password)
                VALUES (%s, %s, %s, %s)
            """
            values = (username, usertype, email, hashed_password)

            cursor.execute(sql, values)
            conn.commit()   # 🔥 THIS SAVES DATA

            cursor.close()
            conn.close()

            return redirect(url_for("signin"))

        except Exception as e:
            print("DB ERROR:", e)
            return render_template("signup.html", error="Database error occurred")

    return render_template("signup.html")


# ---------- SIGNIN (placeholder so redirect works) ----------
@app.route("/signin", methods=["GET", "POST"])
def signin():
    if request.method == "POST":
        # Get form data
        usertype = request.form.get("usertype")
        username = request.form.get("username")
        password = request.form.get("password")

        # Validation
        if not usertype or not username or not password:
            return render_template("signin.html", error="All fields are required")

        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)

            # Fetch user by username + role
            query = """
                SELECT * FROM userdata
                WHERE Username = %s AND Usertype = %s
            """
            cursor.execute(query, (username, usertype))
            user = cursor.fetchone()

            cursor.close()
            conn.close()

            # Check hashed password
            if user and check_password_hash(user["Password"], password):
                session["user_id"] = user["user_id"]
                session["username"] = user["Username"]
                session["usertype"] = user["Usertype"].lower()

                return redirect(url_for("dashboard"))

            return render_template("signin.html", error="Invalid username or password")

        except Exception as e:
            print("SIGNIN ERROR:", e)
            return render_template("signin.html", error="Database error occurred")

    return render_template("signin.html")

# ---------- forgor password ----------
@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        # Validation
        if not email or not new_password or not confirm_password:
            return render_template(
                "forgot_password.html",
                message="All fields are required",
                status="error"
            )

        if new_password != confirm_password:
            return render_template(
                "forgot_password.html",
                message="Passwords do not match",
                status="error"
            )

        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)

            # Check if email exists
            cursor.execute(
                "SELECT * FROM userdata WHERE Email = %s",
                (email,)
            )
            user = cursor.fetchone()

            if not user:
                cursor.close()
                conn.close()
                return render_template(
                    "forgot_password.html",
                    message="Email not found",
                    status="error"
                )

            # Hash new password
            hashed_password = generate_password_hash(new_password)

            # Update password
            cursor.execute(
                "UPDATE userdata SET Password = %s WHERE Email = %s",
                (hashed_password, email)
            )
            conn.commit()

            cursor.close()
            conn.close()

            return render_template(
                "forgot_password.html",
                message="Password reset successful. You can now sign in.",
                status="success"
            )

        except Exception as e:
            print("FORGOT PASSWORD ERROR:", e)
            return render_template(
                "forgot_password.html",
                message="Something went wrong. Try again later.",
                status="error"
            )

    return render_template("forgot_password.html")


# ---------------- DASHBOARD ROUTE ----------------
@app.route("/dashboard")
def dashboard():
    if "username" not in session or "usertype" not in session:
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
    if session.get("usertype") == "admin":
        last_retrained = get_model_time()
        return render_template("admindashboard.html", username=session["username"], last_retrained=last_retrained)
    return redirect(url_for("signin"))

@app.route("/agent_dashboard")
def agent_dashboard():
    if session.get("usertype") == "agent":
        return render_template("agentdashboard.html", username=session["username"])
    return redirect(url_for("signin"))

@app.route("/customer_dashboard")
def customer_dashboard():
    if session.get("usertype") != "customer":
        return redirect(url_for("signin"))

    username = session["username"]

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Count total users
    cursor.execute("SELECT COUNT(*) AS total_users FROM userdata")
    user_count = cursor.fetchone()["total_users"]

    # Count total predictions
    cursor.execute("SELECT COUNT(*) AS total_predictions FROM house_data")
    prediction_count = cursor.fetchone()["total_predictions"]

    # Count total feedbacks
    cursor.execute("SELECT COUNT(*) AS total_feedbacks FROM feedback_data")
    feedback_count = cursor.fetchone()["total_feedbacks"]

    cursor.close()
    conn.close()

    return render_template(
        "customerdashboard.html",
        username=username,
        user_count=user_count,
        prediction_count=prediction_count,
        feedback_count=feedback_count
    )
# ---------------- PREDICTION ----------------
@app.route("/prediction", methods=["GET", "POST"])
def prediction():
    if "username" not in session:
        return redirect(url_for("signin"))

    prediction_text = None

    if request.method == "POST":
        location = request.form["location"]
        p_type = request.form["type"]
        area = float(request.form["area"])
        bhk = int(request.form["bhk"])
        bath = int(request.form["bath"])
        balcony = int(request.form["balcony"])
        parking = int(request.form["parking"])
        furnishing = request.form["furnishing"]
        age = int(request.form["age"])

        df = pd.DataFrame({
            "location": [location],
            "property_type": [p_type],
            "area": [area],
            "bhk": [bhk],
            "bath": [bath],
            "balcony": [balcony],
            "parking": [parking],
            "furnishing": [furnishing],
            "age": [age]
        })

        predicted_price = model.predict(df)[0]
        prediction_text = f"{round(predicted_price, 2)}"

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO house_data
            (location, property_type, area, bhk, bath, balcony, parking, furnishing, age, price)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (location, p_type, area, bhk, bath, balcony, parking, furnishing, age, predicted_price))
        conn.commit()
        cur.close()
        conn.close()

    return render_template("predictionform.html", prediction_text=prediction_text)

# ---------------- FEEDBACK PAGE (GET) ----------------
@app.route("/feedback", methods=["GET"])
def feedback_page():
    if "username" not in session:
        return redirect(url_for("signin"))
    return render_template("feedbackform.html")

# ---------------- FEEDBACK ----------------
@app.route("/feedback", methods=["POST"])
def submit_feedback():
    if "user_id" not in session:
        return redirect(url_for("signin"))

    rating = request.form["rating"]
    feedback_text = request.form["feedback"]

    user_id = session["user_id"]
    username = session["username"]

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO feedback_data (user_id, username, rating, feedback)
        VALUES (%s, %s, %s, %s)
    """, (user_id, username, rating, feedback_text))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for("dashboard"))

# ---------------- SHOW ALL FEEDBACK (DISPLAY PAGE) ----------------
@app.route("/view_feedback")
def view_feedback():
    if "username" not in session:
        return redirect(url_for("signin"))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT username, rating, feedback, created_at 
        FROM feedback_data 
        ORDER BY created_at DESC
    """
    cursor.execute(query)
    feedbacks = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("feedback_data.html", feedbacks=feedbacks)
# ---------------- PREDICTION HISTORY ----------------
@app.route("/history")
def history():
    if "username" not in session:
        return redirect(url_for("signin"))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM house_data ")
    predictions = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("predicted_data.html", predictions=predictions)
    
# ---------------- ANALYTICS PAGE ----------------
@app.route("/analytics")
def analytics_page():
    if "usertype" not in session or session["usertype"] not in ["agent", "admin"]:
        return redirect(url_for("signin"))
    return render_template("charts.html")

@app.route("/chart-data")
def chart_data_api():
    if "usertype" not in session:
        return {"error": "Unauthorized"}, 403

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    data = {}

    # 1. Area vs Price (Scatter)
    cursor.execute("SELECT area, price FROM house_data LIMIT 100")
    data["area_price"] = cursor.fetchall()

    # 2. Age vs Price (Scatter)
    cursor.execute("SELECT age, price FROM house_data LIMIT 100")
    data["age_price"] = cursor.fetchall()

    # Helper for bar charts (averages)
    def get_avg_data(column):
        cursor.execute(f"SELECT {column} as label, AVG(price) as avg_price FROM house_data GROUP BY {column}")
        return cursor.fetchall()

    data["bhk"] = get_avg_data("bhk")
    data["bath"] = get_avg_data("bath")
    data["balcony"] = get_avg_data("balcony")
    data["parking"] = get_avg_data("parking")
    data["furnishing"] = get_avg_data("furnishing")
    data["property_type"] = get_avg_data("property_type")
    data["location"] = get_avg_data("location")

    cursor.close()
    conn.close()

    return data

# ---------------- NOTES PAGE ----------------
@app.route("/notes")
def notes_page():
    if "usertype" not in session or session["usertype"] not in ["agent", "admin"]:
        return redirect(url_for("signin"))
    return render_template("notes.html")

# ---------------- ANALYTICS PAGE ----------------
@app.route("/update_terms", methods=["GET", "POST"])
def update_terms():
    # Only admin can access
    if session.get("usertype") != "admin":
        return redirect(url_for("signin"))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":
        terms_content = request.form.get("terms")
        username = session.get("username")  # Admin username

        # Get current highest version to increment
        cursor.execute("SELECT version FROM terms_conditions ORDER BY id DESC LIMIT 1")
        last_version_row = cursor.fetchone()
        if last_version_row:
            last_version = last_version_row["version"]  # e.g., "v1.0"
            major, minor = last_version[1:].split(".")
            new_version = f"v{major}.{int(minor)+1}"
        else:
            new_version = "v1.0"

        # Mark all existing versions as inactive
        cursor.execute("UPDATE terms_conditions SET status='inactive'")
        conn.commit()

        # Insert new version as active
        cursor.execute("""
            INSERT INTO terms_conditions (content, version, updated_by, status)
            VALUES (%s, %s, %s, 'active')
        """, (terms_content, new_version, username))
        conn.commit()

        cursor.close()
        conn.close()
        return render_template("add_terms_conditions.html", terms_text=terms_content, success=True)

    # GET request: fetch current active version
    cursor.execute("SELECT content FROM terms_conditions WHERE status='active' LIMIT 1")
    row = cursor.fetchone()
    terms_text = row["content"] if row else ""
    cursor.close()
    conn.close()

    return render_template("add_terms_conditions.html", terms_text=terms_text)

# ---------------- USER TERMS & CONDITIONS ----------------
@app.route("/terms")
def view_terms():
    # Only logged-in users can view
    if "username" not in session:
        return redirect(url_for("signin"))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch the currently active terms
    cursor.execute("""
        SELECT content, version, updated_by, updated_at
        FROM terms_conditions
        WHERE status='active'
        LIMIT 1
    """)
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if row:
        terms_text = row["content"]
        version = row["version"]
        updated_by = row["updated_by"]
        updated_at = row["updated_at"]
    else:
        terms_text = "No terms available."
        version = updated_by = updated_at = None

    return render_template(
        "view_terms_conditions.html",
        terms_text=terms_text,
        version=version,
        updated_by=updated_by,
        updated_at=updated_at
    )

# ---------------- MODEL RETRAINING ----------------
@app.route("/retrain_model", methods=["GET", "POST"])
def retrain_model():
    if session.get("usertype") != "admin":
        return redirect(url_for("signin"))

    if request.method == "POST":
        if 'dataset' not in request.files:
            return "No file part", 400
        
        file = request.files['dataset']
        if file.filename == '':
            return "No selected file", 400
        
        if file and file.filename.endswith('.csv'):
            try:
                # Load the data
                data = pd.read_csv(file)
                
                # Basic validation: ensure required columns exist
                required_cols = ["area", "location", "bhk", "bath", "balcony", "parking", "furnishing", "property_type", "age", "price"]
                if not all(col in data.columns for col in required_cols):
                    return f"Dataset must contain these columns: {', '.join(required_cols)}", 400

                X = data.drop('price', axis=1)
                y = data['price']

                # Define the preprocessing steps
                preprocess = ColumnTransformer(
                    transformers=[
                        ("location_ohe", OneHotEncoder(handle_unknown="ignore"), ["location"]),
                        ("property_freq", FrequencyEncoder("property_type"), ["property_type"]),
                        ("furnishing_lbl", FurnishingEncoder("furnishing"), ["furnishing"])
                    ],
                    remainder='passthrough'
                )

                # Create the pipeline
                new_model_pipeline = Pipeline(steps=[
                    ("prep", preprocess),
                    ("rf", RandomForestRegressor(n_estimators=300, random_state=42))
                ])

                # Split and Train
                X_train, X_test, y_train, y_test = train_test_split(
                    X, y, test_size=0.2, random_state=42
                )
                new_model_pipeline.fit(X_train, y_train)

                # Save the new model
                joblib.dump(new_model_pipeline, "house_price_model.pkl")
                
                # Update the global model variable
                global model
                model = new_model_pipeline

                # Log Success to Retrain History
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO retrain_history (retrained_by, dataset_name, status)
                        VALUES (%s, %s, 'Success')
                    """, (session.get('username'), file.filename))
                    conn.commit()
                    cursor.close()
                    conn.close()
                except Exception as db_e:
                    print("HISTORY LOG ERROR:", db_e)

                flash("Model retrained successfully!", "success")
                return redirect(url_for("admin_dashboard"))
            except Exception as e:
                import traceback
                print("RETRAIN ERROR:", traceback.format_exc())
                
                # Log Failure to Retrain History
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO retrain_history (retrained_by, dataset_name, status)
                        VALUES (%s, %s, 'Failed')
                    """, (session.get('username'), file.filename if 'file' in locals() else 'Unknown'))
                    conn.commit()
                    cursor.close()
                    conn.close()
                except:
                    pass

                flash(f"Error during retraining: {str(e)}", "error")
                return redirect(url_for("admin_dashboard"))

    return render_template("retrainmodel.html")

# ---------------- RETRAIN HISTORY ----------------
@app.route("/retrain_history")
def view_retrain_history():
    if session.get("usertype") != "admin":
        return redirect(url_for("signin"))

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM retrain_history ORDER BY retrained_at DESC")
        history = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template("retrain_history.html", history=history)
    except Exception as e:
        print("VIEW HISTORY ERROR:", e)
        flash("Database error occurred while fetching history", "error")
        return redirect(url_for("admin_dashboard"))

# ---------------- USER LIST (ADMIN ONLY - NO ADMINS SHOWN) ----------------
@app.route("/users")
def view_users():
    # Only admin can access
    if session.get("usertype") != "admin":
        return redirect(url_for("signin"))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT user_id, Usertype, Username, Email
        FROM userdata
        WHERE LOWER(Usertype) != 'admin'
    """)

    users = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("users.html", users=users)

# ---------------- PROFILE PAGE ----------------
@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "username" not in session:
        return redirect(url_for("signin"))  # redirect if not logged in

    username = session["username"]

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch user details
    cursor.execute("SELECT * FROM userdata WHERE Username = %s", (username,))
    user = cursor.fetchone()

    if not user:
        cursor.close()
        conn.close()
        return redirect(url_for("signin"))

    message = None
    error = None

    # Handle password change
    if request.method == "POST":
        old_password = request.form.get("old_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        # Check if old password matches
        if not check_password_hash(user["Password"], old_password):
            error = "Current password is incorrect."
        elif new_password != confirm_password:
            error = "New password and confirm password do not match."
        else:
            # Update password in DB
            hashed_password = generate_password_hash(new_password)
            cursor.execute("UPDATE userdata SET Password = %s WHERE Username = %s",
                           (hashed_password, username))
            conn.commit()
            message = "Password updated successfully."

    cursor.close()
    conn.close()

    return render_template("profile.html", user=user, message=message, error=error)


# ---------------- HELP & SUPPORT ----------------
@app.route("/help")
def help_page():
    if "username" not in session:
        return redirect(url_for("signin"))
    return render_template("help.html")

@app.route("/submit_help", methods=["POST"])
def submit_help():
    if "username" not in session:
        return redirect(url_for("signin"))
    
    subject = request.form.get("subject")
    message = request.form.get("message")
    username = session.get("username")
    usertype = session.get("usertype")
    
    if not subject or not message:
        flash("Please fill in all fields", "error")
        return redirect(url_for("help_page"))
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        
        cursor.execute("""
            INSERT INTO help_requests (username, usertype, subject, message)
            VALUES (%s, %s, %s, %s)
        """, (username, usertype, subject, message))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash("Your request has been submitted successfully!", "success")
        return redirect(url_for("help_page"))
    except Exception as e:
        print("HELP SUBMISSION ERROR:", e)
        flash("Error submitting request. Please try again later.", "error")
        return redirect(url_for("help_page"))

@app.route("/view_help")
def view_help_requests():
    if session.get("usertype") != "admin":
        return redirect(url_for("signin"))
    
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        
        cursor.execute("SELECT * FROM help_requests ORDER BY created_at DESC")
        requests = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template("view_help.html", help_requests=requests)
    except Exception as e:
        print("VIEW HELP ERROR:", e)
        flash("Error fetching help requests", "error")
        return redirect(url_for("admin_dashboard"))

@app.route("/resolve_help/<int:request_id>")
def resolve_help(request_id):
    if session.get("usertype") != "admin":
        return redirect(url_for("signin"))
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE help_requests SET status='Resolved' WHERE id=%s", (request_id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Request marked as resolved", "success")
    except Exception as e:
        print("RESOLVE HELP ERROR:", e)
        flash("Error resolving request", "error")
        
    return redirect(url_for("view_help_requests"))

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("homepage"))

# ---------- RUN ----------
if __name__ == "__main__":
    app.run(debug=True)
