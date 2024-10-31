import cv2
import pytesseract
import json
import re

# Load the image
image_path = 'receipt-template-us-neat-750px.png'  # Replace with your image path
img = cv2.imread(image_path)

# Check if the image was loaded successfully
if img is None:
    print(f"Error: Unable to load image at {image_path}")
    exit()

# Resize the image if it's too large or too small
scale_percent = 150  # Increase the scale if needed (or decrease if it's too large)
width = int(img.shape[1] * scale_percent / 100)
height = int(img.shape[0] * scale_percent / 100)
dim = (width, height)
resized_img = cv2.resize(img, dim, interpolation=cv2.INTER_AREA)

# Preprocess the image
gray = cv2.cvtColor(resized_img, cv2.COLOR_BGR2GRAY)  # Convert image to grayscale

# Apply GaussianBlur to smooth the image
blurred = cv2.GaussianBlur(gray, (5, 5), 0)

# Option 1: Use simple thresholding
_, thresh_img = cv2.threshold(blurred, 150, 255, cv2.THRESH_BINARY_INV)

# Option 2: Use adaptive thresholding for better results
adaptive_thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                        cv2.THRESH_BINARY_INV, 11, 2)

# Display the preprocessed image (optional)
cv2.imshow('Preprocessed Image', adaptive_thresh)  # Change to thresh_img for simple thresholding
cv2.waitKey(0)
cv2.destroyAllWindows()

# Use pytesseract to extract text from the processed image
extracted_text = pytesseract.image_to_string(adaptive_thresh)  # Use lang='eng' if needed

# Check if text is extracted
if not extracted_text.strip():
    print("Warning: No text extracted! Check preprocessing and Tesseract configuration.")
else:
    # Print the extracted text
    print("Extracted Text:")
    print(extracted_text)

    # Convert the extracted text into arrays for further processing

    # Option 1: Split by spaces to get an array of words
    text_array_words = extracted_text.split()

    # Option 2: Split by lines to get an array of lines
    text_array_lines = extracted_text.splitlines()

    # Improved regex for prices
    price_pattern = r'(\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?|€\d{1,3}(?:,\d{3})*(?:\.\d{2})?|£\d{1,3}(?:,\d{3})*(?:\.\d{2})?|\d{1,3}(?:,\d{3})*(?:\.\d{2})? ?(?:USD|EUR|GBP)?)'
    
    # This regex will match prices in formats like:
    # $1,000.00, €500, £50.99, 100.50 USD, 1000, 20 EUR, etc.
    
    prices = re.findall(price_pattern, extracted_text)

    # Construct the JSON output
    json_output = {
        "extracted_text": extracted_text,
        "words": text_array_words,
        "lines": text_array_lines,
        "prices": prices,
        "word_count": len(text_array_words),
        "line_count": len(text_array_lines),
        "price_count": len(prices)
    }

    # Convert the dictionary to a JSON string
    json_data = json.dumps(json_output, indent=4, ensure_ascii=False)

    # Print the JSON output
    print("JSON Output:")
    print(json_data)

    # (Optional) Save the JSON to a file
    with open('extracted_text_with_prices.json', 'w', encoding='utf-8') as json_file:
        json_file.write(json_data)