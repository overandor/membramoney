import requests

BASE = "http://localhost:8000/v1"

def seed():
    # Create hosts
    h1 = requests.post(f"{BASE}/hosts", json={
        "email": "cafe@membra.demo", "name": "Bean & Byte Cafe", "phone": "+1-555-0101", "user_type": "host"
    }).json()
    h2 = requests.post(f"{BASE}/hosts", json={
        "email": "hotel@membra.demo", "name": "Metro Stay Hotel", "phone": "+1-555-0102", "user_type": "host"
    }).json()
    h3 = requests.post(f"{BASE}/hosts", json={
        "email": "garage@membra.demo", "name": "Downtown Parking LLC", "phone": "+1-555-0103", "user_type": "host"
    }).json()
    h4 = requests.post(f"{BASE}/hosts", json={
        "email": "gym@membra.demo", "name": "FitHub Gym", "phone": "+1-555-0104", "user_type": "host"
    }).json()
    h5 = requests.post(f"{BASE}/hosts", json={
        "email": "cowork@membra.demo", "name": "LaunchDesk Coworking", "phone": "+1-555-0105", "user_type": "host"
    }).json()

    hosts = [h1, h2, h3, h4, h5]

    # Create guest
    g1 = requests.post(f"{BASE}/guests", json={
        "email": "alex@membra.demo", "name": "Alex Chen", "phone": "+1-555-0201", "user_type": "guest"
    }).json()

    # Create assets (NYC area)
    assets = [
        {"host_id": h1["user_id"], "title": "Clean Restroom Access", "description": "Private, single-occupancy restroom. Cleaned hourly. Soap, towels, hand dryer provided.", "category": "restroom", "address": "123 Mercer St, New York, NY", "latitude": 40.7308, "longitude": -73.9975, "price_cents": 500, "deposit_cents": 0, "rules": "15 min max. No smoking.", "hours_open": "7am-10pm", "max_guests": 1, "insurable": True},
        {"host_id": h1["user_id"], "title": "Printer & WiFi Station", "description": "High-speed laser printer, scanning, and fast WiFi. Perfect for quick work tasks.", "category": "printer", "address": "123 Mercer St, New York, NY", "latitude": 40.7305, "longitude": -73.9970, "price_cents": 300, "deposit_cents": 0, "rules": "30 min session. Paper included for first 10 pages.", "hours_open": "8am-8pm", "max_guests": 1, "insurable": True},
        {"host_id": h2["user_id"], "title": "Luggage Drop-off", "description": "Secure luggage storage behind front desk. Key-locked room with CCTV.", "category": "luggage_drop", "address": "456 Broadway, New York, NY", "latitude": 40.7260, "longitude": -73.9940, "price_cents": 800, "deposit_cents": 0, "rules": "Max 4 hours. No perishables. ID required at pickup.", "hours_open": "24h", "max_guests": 1, "insurable": True},
        {"host_id": h2["user_id"], "title": "Guest Shower Access", "description": "Hotel-grade private shower. Towels, shampoo, body wash provided. Fresh daily.", "category": "shower", "address": "456 Broadway, New York, NY", "latitude": 40.7255, "longitude": -73.9945, "price_cents": 1200, "deposit_cents": 0, "rules": "30 min max. Clean up after use.", "hours_open": "6am-11pm", "max_guests": 1, "insurable": True},
        {"host_id": h3["user_id"], "title": "Reserved Parking Spot #4", "description": "Covered, monitored parking spot in downtown garage. Security guard on duty.", "category": "parking", "address": "78 Lafayette St, New York, NY", "latitude": 40.7220, "longitude": -73.9980, "price_cents": 1500, "deposit_cents": 5000, "rules": "Park within lines. No overnight without approval.", "hours_open": "24h", "max_guests": 1, "insurable": True},
        {"host_id": h3["user_id"], "title": "EV Charger Bay A", "description": "Level 2 EV charger. 32A, J1772 connector. Charging cable included.", "category": "ev_charger", "address": "78 Lafayette St, New York, NY", "latitude": 40.7215, "longitude": -73.9985, "price_cents": 2500, "deposit_cents": 0, "rules": "Unplug when done. Report damage immediately.", "hours_open": "24h", "max_guests": 1, "insurable": True},
        {"host_id": h4["user_id"], "title": "Locker Storage - Large", "description": "Gym locker with digital lock. Big enough for a duffel bag + laptop. CCTV monitored.", "category": "storage_locker", "address": "200 Canal St, New York, NY", "latitude": 40.7180, "longitude": -73.9990, "price_cents": 600, "deposit_cents": 0, "rules": "Max 8 hours. No valuables over $500.", "hours_open": "5am-11pm", "max_guests": 1, "insurable": True},
        {"host_id": h4["user_id"], "title": "Laundry Machine - Quick Cycle", "description": "High-efficiency washer/dryer combo. Detergent included. 45 min cycle.", "category": "laundry", "address": "200 Canal St, New York, NY", "latitude": 40.7175, "longitude": -73.9995, "price_cents": 700, "deposit_cents": 0, "rules": "Remove clothes promptly. Report broken machines.", "hours_open": "6am-10pm", "max_guests": 1, "insurable": True},
        {"host_id": h5["user_id"], "title": "Hot Desk - Window View", "description": "Bright desk by window. Power, monitor, ergonomic chair. Coffee bar access.", "category": "coworking_desk", "address": "55 Water St, New York, NY", "latitude": 40.7150, "longitude": -74.0020, "price_cents": 1800, "deposit_cents": 0, "rules": "No calls without headphones. Clean desk at end.", "hours_open": "8am-8pm", "max_guests": 1, "insurable": True},
        {"host_id": h5["user_id"], "title": "Meeting Room - 4 Person", "description": "Soundproof meeting room. TV, whiteboard, video call setup. Coffee included.", "category": "coworking_desk", "address": "55 Water St, New York, NY", "latitude": 40.7145, "longitude": -74.0025, "price_cents": 3500, "deposit_cents": 0, "rules": "Book min 1 hour. Cancel 2h before.", "hours_open": "8am-8pm", "max_guests": 4, "insurable": True},
    ]

    created = []
    for a in assets:
        r = requests.post(f"{BASE}/assets", json=a)
        if r.status_code == 200:
            created.append(r.json())
        else:
            print("Asset error:", r.status_code, r.text)

    print(f"Created {len(created)} assets")
    print(f"Guest: {g1['user_id']}")
    print(f"Hosts: {[h['user_id'] for h in hosts]}")

if __name__ == "__main__":
    seed()
