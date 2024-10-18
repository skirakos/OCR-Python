import json
import requests

url="https://ocr.asprise.com/api/v1/receipt"
image = "image.jpg"

res = requests.post(url,
                    data = {
                        'api_key': 'TEST',
                        'recognizer': 'auto',
                        'ref_no': 'oct_python_123'
                    },
                    files = {
                        'file': open(image, 'rb')
                    })

if res.status_code == 200:
    with open("response1.json", "w") as f:
        json.dump(json.loads(res.text), f, indent=4)
else:
    print(f"Error: {res.status_code}")