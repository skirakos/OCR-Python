import cv2
import pytesseract
import sqlite3
from flask import Flask, request, render_template, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import os
import re
import pandas as pd
from flask import send_file
import datetime
from reportlab.pdfgen import canvas
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Replace with a strong, unique secret key

# Define the database path
def get_db_path(username):
    # Each user gets their own database file
    return os.path.join(os.path.dirname(__file__), f'{username}_receipts.db')

# Create database tables if they don't exist
def create_tables(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS receipts (
                        id INTEGER PRIMARY KEY,
                        user_id INTEGER,
                        purchase_description TEXT,
                        amount REAL,
                        date_uploaded TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (id))''')
    conn.commit()
    conn.close()

# Process uploaded image to extract text
def process_image(image_path):
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
    text = pytesseract.image_to_string(thresh)
    return text

# Parse text to find description and amount
def preprocess_text(text):
    corrections = {
        "piease": "please",
        "loand": "loan",
    }
    for wrong, correct in corrections.items():
        text = text.replace(wrong, correct)
    return text

def parse_text(text):
    text = preprocess_text(text)
    lines = text.split('\n')
    category = "Uncategorized"
    amount = None
    categories = {
        "food": ["burger", "salad", "pie", "drink", "diner", "restaurant"],
        "clothes": ["shirt", "pants", "jeans", "jacket", "coat", "clothing"],
        "loan": ["loan", "mortgage", "installment", "credit"],
    }

    for line in lines:
        line = line.strip().lower()
        for cat, keywords in categories.items():
            for keyword in keywords:
                if re.search(r'\b' + re.escape(keyword) + r'\b', line):
                    category = cat
                    break
            if category != "Uncategorized":
                break
        if "total" in line:
            match = re.search(r'[\d.,]+', line)
            if match:
                try:
                    amount = float(match.group().replace(',', ''))
                except ValueError:
                    continue
        if amount is None and "$" in line:
            try:
                match = re.search(r'\$[\d.,]+', line)
                if match:
                    amount = float(match.group().replace('$', '').replace(',', ''))
            except ValueError:
                continue

    return category, amount

# Insert data into SQLite
def insert_data(db_path, user_id, description, amount):
    if not description or amount is None:
        return
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO receipts (user_id, purchase_description, amount) VALUES (?, ?, ?)", (user_id, description, amount))
    conn.commit()
    conn.close()

# Routes for sign up and sign in
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password)  # Use default hashing method

        db_path = get_db_path(username)
        create_tables(db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
            conn.commit()
            flash('User registered successfully! You can now log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists. Please choose a different one.', 'danger')
        finally:
            conn.close()

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        db_path = get_db_path(username)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['db_path'] = db_path
            flash('Logged in successfully!', 'success')
            return redirect(url_for('display_receipts'))
        else:
            flash('Invalid username or password.', 'danger')

    return render_template('login.html')

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()  # Clears the session
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))

# Upload and process the image
@app.route('/upload', methods=['POST'])
def upload_image():
    if 'user_id' not in session:
        flash('Please log in to upload receipts.', 'warning')
        return redirect(url_for('login'))

    db_path = session['db_path']
    user_id = session['user_id']
    file = request.files['receipt']
    file_path = "image.png"
    file.save(file_path)

    text = process_image(file_path)
    description, amount = parse_text(text)

    if description and amount:
        insert_data(db_path, user_id, description, amount)

    return redirect(url_for('display_receipts'))

@app.route('/download_receipts', methods=['GET'])
def download_receipts():
    if 'user_id' not in session:
        flash('Please log in to download your receipts.', 'warning')
        return redirect(url_for('login'))

    db_path = session['db_path']
    user_id = session['user_id']
    
    # Fetch receipts from the database
    conn = sqlite3.connect(db_path)
    query = "SELECT purchase_description, amount, date_uploaded FROM receipts WHERE user_id = ?"
    receipts = pd.read_sql_query(query, conn, params=(user_id,))
    conn.close()

    # Convert to Excel file
    file_path = "receipts.xlsx"
    receipts.to_excel(file_path, index=False, engine='openpyxl')  # Save as Excel file

    # Send the file as a download response
    return send_file(file_path, as_attachment=True)

# Display stored receipts
@app.route('/')
def display_receipts():
    if 'user_id' not in session:
        flash('Please log in to view your receipts.', 'warning')
        return redirect(url_for('login'))

    db_path = session['db_path']
    user_id = session['user_id']
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM receipts WHERE user_id = ?", (user_id,))
    receipts = cursor.fetchall()
    conn.close()
    return render_template('receipts.html', receipts=receipts)

@app.route('/generate_invoice', methods=['POST'])
def generate_invoice():
    # Fetch data from form
    client_name = request.form.get("client_name")
    client_address = request.form.get("client_address")
    invoice_date = request.form.get("invoice_date", datetime.date.today().strftime("%Y-%m-%d"))
    due_date = request.form.get("due_date", "")
    invoice_number = request.form.get("invoice_number")
    tax_rate = float(request.form.get("tax_rate", 0))
    subtotal = float(request.form.get("subtotal", 0))
    tax = float(request.form.get("tax", 0))
    grand_total = float(request.form.get("grand_total", 0))
    descriptions = request.form.getlist("description[]")
    quantities = request.form.getlist("quantity[]")
    unit_prices = request.form.getlist("unit_price[]")
    item_totals = request.form.getlist("item_total[]")

    # Create a PDF in memory
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.setTitle(f"Invoice {invoice_number}")

    # Invoice Header
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(100, 750, f"Invoice #{invoice_number}")
    pdf.setFont("Helvetica", 12)
    pdf.drawString(100, 730, f"Client: {client_name}")
    pdf.drawString(100, 710, f"Address: {client_address}")
    pdf.drawString(100, 690, f"Date: {invoice_date}")
    pdf.drawString(100, 670, f"Due Date: {due_date}")

    # Table Header
    y = 640
    pdf.drawString(100, y, "Description")
    pdf.drawString(300, y, "Qty")
    pdf.drawString(350, y, "Unit Price")
    pdf.drawString(450, y, "Total")
    y -= 20

    # Table Items
    for desc, qty, unit, total in zip(descriptions, quantities, unit_prices, item_totals):
        pdf.drawString(100, y, desc)
        pdf.drawString(300, y, qty)
        pdf.drawString(350, y, f"${unit}")
        pdf.drawString(450, y, f"${total}")
        y -= 20

    # Totals
    pdf.drawString(100, y - 20, f"Subtotal: ${subtotal}")
    pdf.drawString(100, y - 40, f"Tax ({tax_rate}%): ${tax}")
    pdf.drawString(100, y - 60, f"Grand Total: ${grand_total}")

    pdf.save()
    buffer.seek(0)

    # Serve the PDF
    return send_file(buffer, as_attachment=True, download_name=f"invoice_{invoice_number}.pdf", mimetype="application/pdf")

@app.route('/invoice_form', methods=['GET'])
def invoice_form():
    # This renders the `generate_invoice.html` form.
    return render_template('generate_invoice.html')

# Run the app
if __name__ == "__main__":
    app.run(debug=True)