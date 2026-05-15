import requests
import json

BASE = "http://localhost:8001/v1"

def post(path, data):
    r = requests.post(f"{BASE}{path}", json=data)
    if r.status_code >= 400:
        print(f"ERROR {path}: {r.status_code} {r.text}")
    return r.json()

def get(path):
    r = requests.get(f"{BASE}{path}")
    return r.json()

def seed():
    print("Seeding Membra Ads...")

    # Owners
    owners = []
    for name, city, neighborhood in [
        ("Sarah Johnson", "New York", "SoHo"),
        ("Mike Torres", "New York", "Williamsburg"),
        ("Lisa Chen", "New York", "Chelsea"),
        ("David Park", "New York", "East Village"),
        ("Emma Wilson", "New York", "Greenpoint"),
    ]:
        o = post("/owners", {
            "email": f"{name.lower().replace(' ', '.')}@membra.demo",
            "name": name,
            "phone": "+1-555-0100",
            "city": city,
            "neighborhood": neighborhood,
        })
        owners.append(o)
    print(f"Created {len(owners)} owners")

    # Advertisers
    advertisers = []
    for name, company in [
        ("Joe Rossi", "Joe's Pizza"),
        ("Amy Liu", "FitHub Gym"),
        ("Carlos Mendez", "Barber King"),
    ]:
        a = post("/advertisers", {
            "email": f"{name.lower().replace(' ', '.')}@{company.lower().replace(' ', '')}.com",
            "name": name,
            "company": company,
        })
        advertisers.append(a)
    print(f"Created {len(advertisers)} advertisers")

    # Assets
    assets = []
    asset_data = [
        {"owner_id": owners[0]["owner_id"], "asset_type": "window", "title": "SoHo Storefront Window", "description": "High foot traffic corner window. 6ft x 4ft visible area. Facing Broadway.", "address": "123 Broadway, New York, NY", "latitude": 40.7308, "longitude": -73.9975, "city": "New York", "neighborhood": "SoHo", "daily_rate_cents": 2000, "photos": ["https://membra.demo/photos/w1.jpg"]},
        {"owner_id": owners[1]["owner_id"], "asset_type": "vehicle", "title": "Brooklyn Delivery Car", "description": "White Honda Civic. 200+ daily miles across Brooklyn and Manhattan. Rear window visible.", "address": "456 Berry St, Brooklyn, NY", "latitude": 40.7150, "longitude": -73.9590, "city": "New York", "neighborhood": "Williamsburg", "daily_rate_cents": 1500, "photos": ["https://membra.demo/photos/v1.jpg"]},
        {"owner_id": owners[2]["owner_id"], "asset_type": "wearable", "title": "Chelsea Food Courier Jacket", "description": "Delivery rider jacket. Worn 8+ hours daily in Chelsea/Meatpacking area.", "address": "789 9th Ave, New York, NY", "latitude": 40.7480, "longitude": -74.0010, "city": "New York", "neighborhood": "Chelsea", "daily_rate_cents": 1000, "photos": ["https://membra.demo/photos/wr1.jpg"]},
        {"owner_id": owners[3]["owner_id"], "asset_type": "window", "title": "East Village Cafe Window", "description": "Cozy cafe front window. Heavy student foot traffic. 4ft x 3ft area.", "address": "321 E 14th St, New York, NY", "latitude": 40.7330, "longitude": -73.9870, "city": "New York", "neighborhood": "East Village", "daily_rate_cents": 1200, "photos": ["https://membra.demo/photos/w2.jpg"]},
        {"owner_id": owners[4]["owner_id"], "asset_type": "vehicle", "title": "Greenpoint Rideshare Car", "description": "Black Toyota Camry. 150+ daily miles. Clean rear window for decals.", "address": "654 Manhattan Ave, Brooklyn, NY", "latitude": 40.7240, "longitude": -73.9510, "city": "New York", "neighborhood": "Greenpoint", "daily_rate_cents": 1300, "photos": ["https://membra.demo/photos/v2.jpg"]},
    ]
    for a in asset_data:
        asset = post("/ad-assets", a)
        assets.append(asset)
    print(f"Created {len(assets)} assets")

    # Campaign
    campaign = post("/campaigns", {
        "advertiser_id": advertisers[0]["advertiser_id"],
        "title": "Joe's Pizza — SoHo Takeover",
        "description": "7-day local ad blitz. Window, car, and wearable placements.",
        "target_city": "New York",
        "target_neighborhoods": ["SoHo", "Williamsburg", "Chelsea", "East Village", "Greenpoint"],
        "asset_types": ["window", "vehicle", "wearable"],
        "budget_cents": 50000,
        "daily_budget_cents": 7000,
        "start_date": "2026-06-01T00:00:00",
        "end_date": "2026-06-07T23:59:59",
        "destination_url": "https://joespizza.com/special",
        "payout_rules": {"window": 2000, "vehicle": 1500, "wearable": 1000},
    })
    print(f"Created campaign: {campaign['campaign_id']}")

    # Submit creative
    creative = post(f"/campaigns/{campaign['campaign_id']}/submit-creative", {
        "asset_type": "window",
        "mockup_url": "https://membra.demo/mockups/joes-pizza-window.png",
        "print_ready_url": "https://membra.demo/print/joes-pizza-window.pdf",
    })
    print(f"Submitted creative: {creative.get('creative_id')}")

    # Approve creative
    approved = post(f"/campaigns/{campaign['campaign_id']}/approve-creative", {
        "approved": True,
        "reviewer_notes": "Looks great. Proceed to production.",
    })
    print(f"Creative approved: {approved['approved']}")

    # Fund campaign
    funded = post(f"/campaigns/{campaign['campaign_id']}/fund", {
        "stripe_payment_intent_id": "pi_demo_joespizza_001",
    })
    print(f"Campaign funded: {funded['status']}")

    # Accept placements
    for i, asset in enumerate(assets):
        placement = post(f"/campaigns/{campaign['campaign_id']}/accept", {
            "owner_id": asset["owner_id"],
            "asset_id": asset["asset_id"],
            "daily_rate_cents": asset["daily_rate_cents"],
        })
        print(f"  Placement {i+1}: {placement.get('placement_id')}")

    print("\nSeed complete. API ready for testing.")
    print(f"Health: {get('/health')}")

if __name__ == "__main__":
    seed()
