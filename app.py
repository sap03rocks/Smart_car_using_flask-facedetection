import os
import cv2
import dlib
import time
import uuid
import random
import numpy as np
import threading
import pyttsx3
import smtplib
import requests
from datetime import datetime
from scipy.spatial import distance
from threading import Thread
from flask import (
    Flask, flash, request, render_template, redirect,
    url_for, session
)
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash


newname=None

unknown_timers = {}
UNKNOWN_TIMEOUT = 3  # Time in seconds before capturing the unknown person's image
last_sent_time = 0  # Prevent multiple alerts being sent too frequently

detection_running = False  # Track if detection is running
detection_thread = None    # Store detection thread

app = Flask(__name__)
app.secret_key = 'hellofriends'
CORS(app)

# Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Flask-Login Setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    surname = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    lastlocation_url = db.Column(db.String(500))  
    location_updated_at = db.Column(db.DateTime, default=datetime.now)

# Admin Model
class Admin(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

#Intruder Model
class Intruder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lastpicture = db.Column(db.String(500))
    time_detected = db.Column(db.DateTime, default=datetime.now)

# Create Database Tables
with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    # Load user first, if not found, try loading admin
    return User.query.get(int(user_id)) or Admin.query.get(int(user_id))

# Home Route
@app.route("/")
def home():
    return redirect(url_for("login"))



@app.route("/register", methods=["GET", "POST"])
def register():
    file_path = ""
    with open(file_path, "r") as file:
        lines = file.readlines()
        urltext = lines[2].split(": ", 1)[1].strip()

    if request.method == "POST":
        name = request.form["name"]
        surname = request.form["surname"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm-password"]
        lastlocation_url=urltext


        if password != confirm_password:
            return "Passwords do not match!"

        otp = str(random.randint(100000, 999999))

        # Store data temporarily in session
        session['temp_user'] = {
        "name": name,
        "surname": surname,
        "email": email,
        "password": generate_password_hash(password),
        "otp": otp,
        "lastlocation_url": lastlocation_url
    }

        # Send OTP via email
        send_otp_email(email, otp)

        return redirect(url_for("verify_otp"))

    return render_template("register.html")

# User Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for("dashboard"))
        else:
            return render_template("incorrectpassword.html")

    return render_template("login.html")

@app.route("/admin_registration", methods=["GET", "POST"])
def admin_registration():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm-password"]

        if password != confirm_password:
            return "Passwords do not match!"

        # Check if username or email already exists
        if Admin.query.filter_by(username=username).first():
            return "Admin username already exists!"

        if Admin.query.filter_by(email=email).first():
            return "Email already in use!"

        otp = str(random.randint(100000, 999999))

        # Store admin info temporarily in session
        session["temp_admin"] = {
            "username": username,
            "email": email,
            "password": generate_password_hash(password),
            "otp": otp
        }

        # Send OTP via email
        send_otp_email(email, otp)

        return redirect(url_for("verify_admin_otp"))

    return render_template("admin_registration.html")

@app.route("/verify_admin_otp", methods=["GET", "POST"])
def verify_admin_otp():
    if request.method == "POST":
        entered_otp = request.form["otp"]
        temp_admin = session.get("temp_admin", {})

        if temp_admin and entered_otp == temp_admin.get("otp"):
            new_admin = Admin(
                username=temp_admin["username"],
                email=temp_admin["email"],
                password_hash=temp_admin["password"]
            )
            db.session.add(new_admin)
            db.session.commit()

            flash("Admin registered successfully!", "success")
            session.pop("temp_admin", None)  # Clear session
            return redirect(url_for("admin_login"))
        else:
            return "Invalid OTP. Please try again."

    return render_template("verify_admin_otp.html")

# Admin Login
@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        admin = Admin.query.filter_by(username=username, email=email).first()

        if admin and check_password_hash(admin.password_hash, password):
            login_user(admin)
            return redirect(url_for("admin_panel"))
        else:
            return render_template("incorrectpassword.html")

    return render_template("admin_login.html")

# User Dashboard
@app.route("/dashboard")
@login_required
def dashboard():
    global detection_running, detection_thread
    
    if not detection_running:
        detection_running = True
        detection_thread = threading.Thread(target=run_detection, daemon=True)
        detection_thread.start()
    return render_template('index.html')

# Admin Panel (Restricted Access)
@app.route("/admin_panel")
@login_required
def admin_panel():
    if not isinstance(current_user, Admin):  # Ensure only admins access it
        return "Access Denied! You are not an admin."

    users = User.query.all()
    return render_template("admin_panel.html", users=users)

# Logout
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return render_template("logout.html")

@app.route("/location", methods=["POST"])
@login_required
def location():
    now = datetime.now()
    date_str = now.strftime("%d-%m-%Y")
    time_str = now.strftime("%H:%M:%S")
    day_str = now.strftime("%A")
    data = request.get_json()
    
    latitude = data.get('latitude')
    longitude = data.get('longitude')

    if not latitude or not longitude:
        return "Invalid location data!"

    urltext = f"https://www.google.com/maps/?q={latitude},{longitude}"
    print(urltext)

    if current_user.is_authenticated and isinstance(current_user, User):
        user = User.query.get(current_user.id)
        if user:
            user.lastlocation_url = urltext
            user.location_updated_at = datetime.now()
            db.session.commit()

    # Save to file (optional debug or log)
    directory = " "
    os.makedirs(directory, exist_ok=True)
    file_path = os.path.join(directory, "")
    with open(file_path, "w") as file:
        file.write(f"Latitude: {latitude}\n")
        file.write(f"Longitude: {longitude}\n")
        file.write(f"URL: {urltext}\n")

    # Telegram notification
    token = ""
    chat_id = ""
    text = f'''
    The panic button was pressed from the car app:
    Date: {date_str}
    Time: {time_str}
    Day: {day_str}

    The location of the car is:
    Latitude: {latitude} and Longitude: {longitude}

    Check the location here: {urltext}
    '''
    requests.post(
        url=f'https://api.telegram.org/bot{token}/sendMessage',
        data={'chat_id': chat_id, 'text': text}
    )

    return "Location sent successfully"

@app.route("/capture", methods=["GET", "POST"])
def handle_capture_request():
    newname = session.get("newname")
    if not newname:
        return "Missing user name for face capture", 400

    cappics = 30
    capture_faces(newname, cappics)
    return redirect(url_for("login"))

def capture_faces(user_name, num_images):
    """Function to capture faces with a live OpenCV window."""
    os.makedirs("known_faces", exist_ok=True)
    
    cap = cv2.VideoCapture(0)  # Open webcam
    captured = 0

    while captured < num_images:
        ret, frame = cap.read()
        if not ret:
            cap.release()
            return {"status": "error", "message": "Failed to access webcam"}

        # Display the webcam feed
        cv2.imshow("Face Capture", frame)
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5, minSize=(50, 50))

        for (x, y, w, h) in faces:
            face_roi = frame[y:y+h, x:x+w]  # Crop face region
            img_name = os.path.join("known_faces", f'{user_name}_{uuid.uuid1()}.jpg')
            cv2.imwrite(img_name, face_roi)
            captured += 1

            if captured >= num_images:
                break

        # Allow user to close window with 'q'
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

 
@app.route("/verify_otp", methods=["GET", "POST"])
def verify_otp():
    if request.method == "POST":
        user_otp = request.form["otp"]
        temp_user = session.get("temp_user", {})

        if temp_user and user_otp == temp_user.get("otp"):
            # Save user to DB
            new_user = User(
                name=temp_user["name"],
                surname=temp_user["surname"],
                email=temp_user["email"],
                password_hash=temp_user["password"],
                lastlocation_url=temp_user["lastlocation_url"]
            )

            db.session.add(new_user)
            db.session.commit()

            session['newname'] = temp_user["name"]

            # Render page with popup trigger instead of redirecting immediately
            return render_template("verify_otp.html", otp_verified=True)

        else:
            flash("Invalid OTP. Please try again.", "danger")

    return render_template("verify_otp.html", otp_verified=False)


def send_otp_email(receiver_email, otp):
    sender_email = ""
    sender_password = ""

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()  # Required for port 587
        server.login(sender_email, sender_password)

        subject = "Your OTP Code"
        body = f"Your OTP is: {otp}"
        message = f"Subject: {subject}\n\n{body}"

        server.sendmail(sender_email, receiver_email, message)
        server.quit()
    except Exception as e:
        print("Email sending failed:", e)

@app.route('/intruders')
@login_required
def view_intruders():
    if not isinstance(current_user, Admin):  # Only allow Admins
        return "Access Denied! You are not authorized to view this page.", 403
    
    intruders = Intruder.query.order_by(Intruder.time_detected.desc()).all()
    return render_template('intruders.html', intruders=intruders)


def clean_intruder_table(session):
    try:
        # Query all intruders and their image paths
        intruders = session.query(Intruder.id, Intruder.lastpicture).all()

        for intruder_id, image_path in intruders:
            # Get the absolute path of the image file
            abs_path = os.path.join("static", *image_path.strip("/").split("/")[1:])
            
            # Check if the image file exists
            if not os.path.exists(abs_path):
                print(f"[Thread Cleanup] Deleting ID {intruder_id} — Missing file: {abs_path}")
                
                # Delete the record from the Intruder table
                intruder_record = session.query(Intruder).filter(Intruder.id == intruder_id).first()
                if intruder_record:
                    session.delete(intruder_record)

        # Commit changes to the database
        session.commit()
    except Exception as e:
        print(f"[Thread Cleanup Error] {e}")
        session.rollback()  # Rollback in case of error
    finally:
        session.close()  # Close the session

# Function to start the cleanup in a background loop with a configurable interval
def background_cleanup_loop(interval=120):
    def clean_loop():
        while True:
            with app.app_context():  # Wrap in app context
                session = db.session  # Use the existing SQLAlchemy session
                clean_intruder_table(session)  # Run the cleanup
            time.sleep(interval)  # Wait before the next cleanup

    # Start the cleanup loop in a background thread
    thread = threading.Thread(target=clean_loop, daemon=True)
    thread.start()

def run_detection():
    global detection_running
    detection_running = True

    with app.app_context():
        # Load location info
        with open("", "r") as file:
            lines = file.readlines()
        latitude = float(lines[0].split(":")[1].strip())
        longitude = float(lines[1].split(":")[1].strip())
        urltext = lines[2].split(": ", 1)[1].strip()

        # Load face detection and recognition
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        recognizer = cv2.face.LBPHFaceRecognizer_create()

        known_faces_folder = "known_faces"
        os.makedirs("static/unknown_faces", exist_ok=True)

        faces, labels, label_map = [], [], {}
        for idx, filename in enumerate(os.listdir(known_faces_folder)):
            if filename.lower().endswith((".jpg", ".jpeg", ".png")):
                path = os.path.join(known_faces_folder, filename)
                image = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                if image is None:
                    continue
                detected = face_cascade.detectMultiScale(image, scaleFactor=1.1, minNeighbors=5)
                if len(detected) == 0:
                    continue
                (x, y, w, h) = detected[0]
                faces.append(image[y:y + h, x:x + w])
                labels.append(idx)
                label_map[idx] = os.path.splitext(filename)[0].split('_')[0]

        if not faces:
            print("No training data found. Check your known_faces folder.")
            return

        recognizer.train(faces, np.array(labels))

        # Setup
        CONFIDENCE_THRESHOLD = 110
        UNKNOWN_TIMEOUT = 3
        last_sent_time = 0
        drowsiness_start_time = None
        alert_sent = False
        unknown_timers = {}

        dlib_detector = dlib.get_frontal_face_detector()
        dlib_predictor = dlib.shape_predictor("shape_predictor_68_face_landmarks.dat")
        engine = pyttsx3.init()

        CLOSED_EYE_THRESHOLD = 0.20
        DROWSINESS_TIMER = 1.0
        token = ""
        chat_id = ""
        def detect_eye(eye):
            A = distance.euclidean(eye[1], eye[5])
            B = distance.euclidean(eye[2], eye[4])
            C = distance.euclidean(eye[0], eye[3])
            return (A + B) / (2.0 * C)

        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 250)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 250)

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces_detected = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
            current_time = time.time()

            for (x, y, w, h) in faces_detected:
                roi_gray = gray[y:y + h, x:x + w]
                label, confidence = recognizer.predict(roi_gray)
                predicted_name = label_map.get(label, "Unknown") if confidence < CONFIDENCE_THRESHOLD else "Unknown"

                if predicted_name == "Unknown":
                    key = (x, y, w, h)
                    if key not in unknown_timers:
                        unknown_timers[key] = current_time
                    elif current_time - unknown_timers[key] >= UNKNOWN_TIMEOUT:
                        if current_time - last_sent_time > 2:
                            last_sent_time = current_time

                            filename = f"unknown_{int(current_time)}.jpg"
                            save_path = os.path.join("static", "unknown_faces", filename)
                            web_path = f"/static/unknown_faces/{filename}"

                            cv2.imwrite(save_path, frame)

                            db.session.add(Intruder(lastpicture=web_path, time_detected=datetime.now()))
                            db.session.commit()

                            now = datetime.now()
                            text = f"""
🚨 Intruder Detected! 🚨
Date: {now.strftime('%d-%m-%Y')}
Time: {now.strftime('%H:%M:%S')}
Day: {now.strftime('%A')}
The location of the car is:
Latitude: {latitude}
Longitude: {longitude}
Check the location here: {urltext}
"""
                            with open(save_path, 'rb') as photo:
                                requests.post(
                                    url=f'https://api.telegram.org/bot{token}/sendPhoto',
                                    data={'chat_id': chat_id, 'caption': text},
                                    files={'photo': photo}
                                )
                else:
                    for key in list(unknown_timers):
                        if x in key and y in key:
                            del unknown_timers[key]

                color = (0, 0, 255) if predicted_name == "Unknown" else (0, 255, 0)
                label_text = "UNKNOWN" if predicted_name == "Unknown" else f"{predicted_name} {confidence:.1f}"
                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                cv2.putText(frame, label_text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

            # Drowsiness detection
            for face in dlib_detector(gray):
                landmarks = dlib_predictor(gray, face)
                leftEye = [(landmarks.part(n).x, landmarks.part(n).y) for n in range(36, 42)]
                rightEye = [(landmarks.part(n).x, landmarks.part(n).y) for n in range(42, 48)]

                ear = (detect_eye(leftEye) + detect_eye(rightEye)) / 2.0

                if ear < CLOSED_EYE_THRESHOLD:
                    if drowsiness_start_time is None:
                        drowsiness_start_time = current_time
                    elif current_time - drowsiness_start_time >= DROWSINESS_TIMER:
                        cv2.putText(frame, "DROWSINESS DETECTED", (30, 60), cv2.FONT_HERSHEY_PLAIN, 1.5, (21, 56, 210), 2)
                        engine.say("Wake up! Please pay attention!")
                        engine.runAndWait()

                        if not alert_sent:
                            drow_text = f"""
DROWSINESS ALERT!!!!
The location of the car is:
Latitude: {latitude}
Longitude: {longitude}
Check the location here: {urltext}
"""
                            requests.post(
                                url=f'https://api.telegram.org/bot{token}/sendMessage',
                                data={'chat_id': chat_id, 'text': drow_text}
                            )
                            alert_sent = True
                else:
                    drowsiness_start_time = None
                    alert_sent = False

            cv2.imshow("Detection", frame)
            if cv2.waitKey(1) & 0xFF == 27:
                break

        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    
    background_cleanup_loop(interval=120)
    
    app.run(debug=True)