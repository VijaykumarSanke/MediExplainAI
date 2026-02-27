import requests
import json

url = "http://localhost:8000/analyze"
payload = {
    "tests": [
        {
            "test_name": "Potassium",
            "measured_value": 2.0,
            "unit": "mmol/L",
            "reference_range": "3.5 - 5.1"
        },
        {
            "test_name": "LDL Cholesterol",
            "measured_value": 145.0,
            "unit": "mg/dL",
            "reference_range": "< 130"
        }
    ],
    "historical_tests": [
        {
            "test_name": "LDL Cholesterol",
            "measured_value": 110.0,
            "unit": "mg/dL",
            "reference_range": "< 130"
        }
    ]
}

response = requests.post(url, json=payload)
print(json.dumps(response.json(), indent=2))
