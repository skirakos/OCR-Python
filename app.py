import cv2
import pytesseract
import sqlite3
from flask import Flask, request, render_template, redirect, url_for
import os

app = Flask(__name__)

# Define the database path using an absolute path for consistency
DB_PATH = os.path.join(os.path.dirname(__file__), 'receipts.db')

# Create database table if it doesn't exist
def create_tables():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS receipts (
                        id INTEGER PRIMARY KEY,
                        purchase_description TEXT,
                        amount REAL,
                        date_uploaded TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

create_tables()

# Process uploaded image to extract text
def process_image(image_path):
    # Load image and convert to grayscale
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Apply thresholding for better OCR results
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
    
    # Use Tesseract to extract text
    text = pytesseract.image_to_string(thresh)
    print("Extracted text:", text)  # Debug: print the extracted text
    return text

# Parse text to find description and amount
def parse_text(text):
    lines = text.split('\n')
    description = ""
    amount = None
    
    for line in lines:
        line = line.strip()  # Trim whitespace for cleaner processing
        print("Processing line:", line)  # Debug: print each line being processed
        
        # Capture the first valid line containing 'total' or 'amount' as a description
        if "total" in line.lower() and not description:
            description = line
        
        # Look for lines that contain amounts with a dollar sign
        if "$" in line:
            try:
                # Extract the amount by stripping unwanted characters
                amount = float(line.replace('$', '').strip())
            except ValueError:
                continue
    
    # Default description if nothing matched
    if not description and amount:
        description = "Total Amount"
    
    print(f"Parsed description: {description}, Parsed amount: {amount}")  # Debug: print parsed values
    return description, amount

# Insert data into SQLite
def insert_data(description, amount):
    if not description or amount is None:
        print("Invalid data: Skipping insertion")  # Debug: print if data is invalid
        return
    print(f"Inserting data: {description}, {amount}")  # Debug: print data before insertion
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO receipts (purchase_description, amount) VALUES (?, ?)", (description, amount))
    conn.commit()
    conn.close()

# Upload and process the image
@app.route('/upload', methods=['POST'])
def upload_image():
    file = request.files['receipt']
    file_path = "image.png"
    file.save(file_path)

    print("File saved successfully")  # Debug: confirm file save
    text = process_image(file_path)
    description, amount = parse_text(text)

    if description and amount:
        print("Data ready for insertion:", description, amount)  # Debug: confirm data is ready for insertion
        insert_data(description, amount)
    else:
        print("Failed to parse valid description or amount")  # Debug: print if parsing fails
    
    return redirect(url_for('display_receipts'))

# Display stored receipts
@app.route('/')
def display_receipts():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM receipts")
    receipts = cursor.fetchall()
    conn.close()
    print("Receipts to render:", receipts)  # Debug: print receipts fetched from DB
    return render_template('receipts.html', receipts=receipts)

# Run the app
if __name__ == "__main__":
    app.run(debug=True)