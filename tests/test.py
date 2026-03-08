# test.py
import threading
import requests
import time

URL = "http://localhost:8000/webhook/baileys"

payload_user_1 = {
    "messages": [{
        "from": "628111111111@c.us",
        "from_name": "User Satu",
        "text": {"body": "halo barengan 1"}
    }]
}

payload_user_2 = {
    "messages": [{
        "from": "628222222222@c.us",
        "from_name": "User Dua",
        "text": {"body": "halo barengan 2"}
    }]
}

def send(payload, label):
    print(f"➡️ sending {label}")
    r = requests.post(URL, json=payload)
    print(f"⬅️ response {label}:", r.status_code, r.text)

t1 = threading.Thread(target=send, args=(payload_user_1, "USER 1"))
t2 = threading.Thread(target=send, args=(payload_user_2, "USER 2"))

t1.start()
t2.start()

t1.join()
t2.join()

print("✅ test selesai")