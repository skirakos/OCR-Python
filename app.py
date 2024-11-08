import cv2
import pytesseract
import sqlite3
from flask import Flask, request, render_template, redirect, url_for
import os
import re

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
import re  # Import regex module for better number parsing

# Step 1: Preprocess OCR Output to Correct Common Mistakes
def preprocess_text(text):
    # Define a dictionary of common OCR misreadings to correct
    corrections = {
        "piease": "please",  # Correcting "piease" to "please"
        "loand": "loan",     # Example: correcting "loand" to "loan" (if relevant)
        # Add more common OCR mistakes here
    }
    
    # Apply each correction to the text
    for wrong, correct in corrections.items():
        text = text.replace(wrong, correct)
    
    return text

# Step 2: Parse Text with Corrected OCR and Keyword Matching
def parse_text(text):
    text = preprocess_text(text)  # Correct OCR mistakes
    
    lines = text.split('\n')
    category = "Uncategorized"  # Default category if no match
    amount = None
    
    # Define categories with keywords
    categories = {
        "food": ["burger", "salad", "pie", "drink", "diner", "restaurant"],
        "clothes": ["shirt", "pants", "jeans", "jacket", "coat", "clothing"],
        "loan": ["loan", "mortgage", "installment", "credit"],
        # Add more categories and keywords as needed
    }

    for line in lines:
        line = line.strip().lower()  # Normalize line for matching
        print("Processing line:", line)  # Debugging: Print each line
        
        # Step 3: Match Categories Using Word Boundaries to Prevent Partial Matches
        for cat, keywords in categories.items():
            for keyword in keywords:
                # Use word boundaries to ensure whole word matching (e.g., 'pie' should not match 'piease')
                if re.search(r'\b' + re.escape(keyword) + r'\b', line):
                    category = cat
                    print(f"Matched keyword: '{keyword}' in line: '{line}'")  # Debugging: Show matched keyword
                    break  # Stop once a category match is found
            if category != "Uncategorized":  # If category is set, break out of the outer loop
                break

        # Step 4: Parse Amount (looking for numbers in lines with total or dollar signs)
        if "total" in line:
            match = re.search(r'[\d.,]+', line)  # Find numbers (amount) in the line
            if match:
                try:
                    amount = float(match.group().replace(',', ''))  # Convert to float, removing commas
                except ValueError:
                    continue

        # Fallback to find any dollar amounts if "total" line didn't work
        if amount is None and "$" in line:
            try:
                match = re.search(r'\$[\d.,]+', line)
                if match:
                    amount = float(match.group().replace('$', '').replace(',', ''))  # Parse dollar amount
            except ValueError:
                continue

    # Final debug print
    print(f"Parsed category: {category}, Parsed amount: {amount}")
    return category, amount

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