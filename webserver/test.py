import requests

# Endpoint URL
url = "http://localhost:5000/api/v1/streamservers/"

# Headers including the content type and authorization token
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer YOUR_ACCESS_TOKEN"  # Replace YOUR_ACCESS_TOKEN with your actual token
}

# Data payload as a dictionary
data = {
    "hostname": "newserver",
    "workspace": "d6516e3e-9600-4826-9121-5c18e2829a46"
}

# Make the POST request
response = requests.post(url, json=data, headers=headers)

# response = requests.delete(url + "266fd7be-2b88-454d-9385-a213307e5aed", headers=headers)

# Check response status and print the result
if response.status_code == 201:
    print("Success:", response.json())
else:
    print("Failed to make request:", response.status_code, response.text)
