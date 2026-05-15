# Membra Ads API

Certified campaign kit system. Membra controls campaign IDs, QR/NFC tracking, proof verification, and payouts. Vendors handle printing and shipping.

## Architecture

Membra is the master API. Frontend, mobile apps, advertiser dashboard, and owner dashboard call Membra, not Printful, Printify, Stripe, or NFC vendors directly.

## Vendor Integrations

- **App/Database/Storage**: Supabase (Postgres + Auth + Storage)
- **Payments/Payouts**: Stripe Connect
- **Clothing (shirts, hoodies, hats, bags)**: Printful, Printify, Gelato
- **Stickers/Decals/Magnets**: Sticker Mule (manual MVP) → Printify API for automation
- **NFC/QR Tags**: GoToTags (batch CSV workflow) → API when available
- **QR Tracking**: Membra internal redirect links (`/t/{qr_id}`)

## Core Rules

1. No approved creative → no kit generated
2. No Membra QR/NFC ID → no certified placement
3. No shipped kit → no activation
4. No proof photo + GPS + time match → no payout
5. No Membra tracking URL → no analytics

## API Endpoints

### Owners
- `POST /v1/owners` — onboard owner
- `GET /v1/owners/{owner_id}` — get owner

### Advertisers
- `POST /v1/advertisers` — onboard advertiser
- `GET /v1/advertisers/{advertiser_id}` — get advertiser

### Ad Assets
- `POST /v1/ad-assets` — list an asset (window, vehicle, wearable)
- `GET /v1/ad-assets` — browse assets
- `GET /v1/ad-assets/{asset_id}` — asset details
- `PATCH /v1/ad-assets/{asset_id}` — update asset
- `POST /v1/ad-assets/{asset_id}/verify` — verify asset
- `POST /v1/windows`, `/v1/vehicles`, `/v1/wearables` — create subtypes

### Campaigns
- `POST /v1/campaigns` — create campaign
- `GET /v1/campaigns` — list campaigns
- `GET /v1/campaigns/{campaign_id}` — campaign details
- `POST /v1/campaigns/{campaign_id}/submit-creative` — submit creative
- `POST /v1/campaigns/{campaign_id}/approve-creative` — approve/reject creative
- `POST /v1/campaigns/{campaign_id}/fund` — fund campaign
- `POST /v1/campaigns/{campaign_id}/launch` — launch campaign
- `GET /v1/campaigns/available` — available campaigns for owners
- `POST /v1/campaigns/{campaign_id}/accept` — owner accepts campaign
- `POST /v1/campaigns/{campaign_id}/decline` — owner declines campaign

### Media Kits
- `POST /v1/media-kits` — create kit
- `GET /v1/media-kits/{kit_id}` — kit details
- `POST /v1/media-kits/{kit_id}/generate-qr` — generate QR tag
- `POST /v1/media-kits/{kit_id}/assign-nfc` — assign NFC tag
- `POST /v1/media-kits/{kit_id}/order` — order from vendor
- `POST /v1/media-kits/{kit_id}/confirm-receipt` — owner confirms receipt

### Proof
- `POST /v1/proof/photo` — submit photo proof
- `POST /v1/proof/location` — submit GPS proof
- `POST /v1/proof/qr-scan` — track QR scan
- `POST /v1/proof/nfc-tap` — track NFC tap
- `POST /v1/proof/review` — review proof (release payout eligibility)
- `GET /v1/proof-reports/{campaign_id}` — proof report

### Payments & Payouts
- `POST /v1/payments/authorize` — authorize advertiser payment
- `POST /v1/payments/capture` — capture payment
- `POST /v1/payouts/release` — release owner payout
- `POST /v1/payouts/create-transfer` — create payout record
- `GET /v1/payouts/{payout_id}` — get payout

### Analytics
- `GET /v1/analytics/campaign/{campaign_id}` — campaign analytics
- `GET /v1/analytics/owner/{owner_id}` — owner earnings analytics

### Webhooks
- `POST /v1/webhooks/stripe` — Stripe events
- `POST /v1/webhooks/printful` — Printful order events
- `POST /v1/webhooks/printify` — Printify order events
- `POST /v1/webhooks/gelato` — Gelato order events
- `POST /v1/webhooks/nfc-vendor` — NFC batch events

### Public QR Redirect
- `GET /t/{qr_id}` — track scan and redirect to advertiser

## Database Tables

- `owners` — asset owners
- `advertisers` — campaign advertisers
- `ad_assets` — windows, vehicles, wearables
- `window_assets`, `vehicle_assets`, `wearable_assets` — subtypes
- `campaigns` — ad campaigns
- `campaign_creatives` — submitted/approved creative
- `accepted_placements` — owner-campaign pairings
- `media_kits` — physical kits (decal, shirt, magnet, NFC)
- `qr_tags` — unique QR codes per kit
- `nfc_tags` — unique NFC tags per kit
- `proof_events` — owner-submitted proof
- `scan_events` — QR scans and NFC taps
- `payments` — advertiser payments
- `payouts` — owner payouts
- `claims` — disputes
- `audit_events` — audit log

## Quick Start

```bash
# Local dev
cp .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --reload

# With Docker
docker-compose up --build
```

## 30-Day Launch Plan

See `30_DAY_PLAN.md` for the day-by-day manual-to-automated campaign playbook.
