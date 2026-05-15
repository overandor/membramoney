from datetime import datetime, timezone, timedelta
from typing import Optional
from src.db.database import get_connection
from src.models.enums import (
    VisitStatus, PaymentStatus, CoverageStatus,
    AdCampaignStatus, AdPlacementStatus, AdPayoutStatus
)


def _parse_iso(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def dashboard_summary() -> dict:
    conn = get_connection()

    # Identity
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    hosts = conn.execute("SELECT COUNT(*) FROM users WHERE user_type = 'host'").fetchone()[0]
    guests = conn.execute("SELECT COUNT(*) FROM users WHERE user_type = 'guest'").fetchone()[0]
    verified_users = conn.execute("SELECT COUNT(*) FROM users WHERE identity_level != 'unverified'").fetchone()[0]

    # Assets
    total_assets = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
    active_assets = conn.execute("SELECT COUNT(*) FROM assets WHERE active = 1").fetchone()[0]
    insurable_assets = conn.execute("SELECT COUNT(*) FROM assets WHERE insurable = 1").fetchone()[0]

    # Visits / Reservations
    total_visits = conn.execute("SELECT COUNT(*) FROM visits").fetchone()[0]
    visit_status_counts = {}
    for row in conn.execute("SELECT status, COUNT(*) FROM visits GROUP BY status").fetchall():
        visit_status_counts[row[0]] = row[1]

    # Payments
    total_payments = conn.execute("SELECT COUNT(*) FROM payments").fetchone()[0]
    authorized_payments = conn.execute("SELECT COUNT(*) FROM payments WHERE status = 'authorized'").fetchone()[0]
    captured_payments = conn.execute("SELECT COUNT(*) FROM payments WHERE status = 'captured'").fetchone()[0]
    refunded_payments = conn.execute("SELECT COUNT(*) FROM payments WHERE status = 'refunded'").fetchone()[0]
    revenue_cents = conn.execute("SELECT COALESCE(SUM(total_captured_cents), 0) FROM payments").fetchone()[0]
    platform_fees_cents = conn.execute("SELECT COALESCE(SUM(platform_fee_cents), 0) FROM payments").fetchone()[0]

    # Insurance
    total_coverages = conn.execute("SELECT COUNT(*) FROM coverages").fetchone()[0]
    active_coverages = conn.execute("SELECT COUNT(*) FROM coverages WHERE status = 'active'").fetchone()[0]
    total_premiums_cents = conn.execute("SELECT COALESCE(SUM(premium_cents), 0) FROM coverages").fetchone()[0]

    # Incidents & Claims
    total_incidents = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
    open_incidents = conn.execute("SELECT COUNT(*) FROM incidents WHERE status = 'open'").fetchone()[0]
    total_claims = conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
    total_claims_cents = conn.execute("SELECT COALESCE(SUM(damage_cents), 0) FROM claims").fetchone()[0]

    # Ads
    total_campaigns = conn.execute("SELECT COUNT(*) FROM ad_campaigns").fetchone()[0]
    active_campaigns = conn.execute("SELECT COUNT(*) FROM ad_campaigns WHERE status = 'active'").fetchone()[0]
    total_ad_budget_cents = conn.execute("SELECT COALESCE(SUM(budget_cents), 0) FROM ad_campaigns").fetchone()[0]
    total_placements = conn.execute("SELECT COUNT(*) FROM ad_placements").fetchone()[0]
    total_payouts_cents = conn.execute("SELECT COALESCE(SUM(amount_cents), 0) FROM ad_payouts WHERE status = 'released'").fetchone()[0]

    # QR Scans
    total_qr_scans = conn.execute("SELECT COUNT(*) FROM ad_scan_events").fetchone()[0]

    # Wear
    total_wearers = conn.execute("SELECT COUNT(*) FROM wearers").fetchone()[0]
    active_wearers = conn.execute("SELECT COUNT(*) FROM wearers WHERE is_active = 1").fetchone()[0]
    total_wearables = conn.execute("SELECT COUNT(*) FROM wearable_assets").fetchone()[0]

    conn.close()

    return {
        "identity": {
            "total_users": total_users,
            "hosts": hosts,
            "guests": guests,
            "verified_users": verified_users,
            "verification_rate": round(verified_users / total_users, 4) if total_users else 0,
        },
        "assets": {
            "total_assets": total_assets,
            "active_assets": active_assets,
            "insurable_assets": insurable_assets,
        },
        "visits": {
            "total_visits": total_visits,
            "status_breakdown": visit_status_counts,
        },
        "payments": {
            "total_payments": total_payments,
            "authorized": authorized_payments,
            "captured": captured_payments,
            "refunded": refunded_payments,
            "revenue_cents": revenue_cents,
            "revenue_usd": round(revenue_cents / 100, 2),
            "platform_fees_cents": platform_fees_cents,
            "platform_fees_usd": round(platform_fees_cents / 100, 2),
        },
        "insurance": {
            "total_coverages": total_coverages,
            "active_coverages": active_coverages,
            "total_premiums_cents": total_premiums_cents,
            "total_premiums_usd": round(total_premiums_cents / 100, 2),
        },
        "incidents": {
            "total_incidents": total_incidents,
            "open_incidents": open_incidents,
            "total_claims": total_claims,
            "total_claims_usd": round(total_claims_cents / 100, 2),
        },
        "ads": {
            "total_campaigns": total_campaigns,
            "active_campaigns": active_campaigns,
            "total_budget_usd": round(total_ad_budget_cents / 100, 2),
            "total_placements": total_placements,
            "total_payouts_usd": round(total_payouts_cents / 100, 2),
            "total_qr_scans": total_qr_scans,
        },
        "wear": {
            "total_wearers": total_wearers,
            "active_wearers": active_wearers,
            "total_wearables": total_wearables,
        },
    }


def time_series_metrics(days: int = 30) -> list[dict]:
    conn = get_connection()
    start = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    rows = conn.execute(
        """
        SELECT DATE(created_at) as day,
               COUNT(*) as visits,
               SUM(guest_count) as guests
        FROM visits
        WHERE created_at >= ?
        GROUP BY DATE(created_at)
        ORDER BY day
        """,
        (start,),
    ).fetchall()

    payment_rows = conn.execute(
        """
        SELECT DATE(created_at) as day,
               COALESCE(SUM(total_authorized_cents), 0) as authorized_cents,
               COUNT(*) as payment_count
        FROM payments
        WHERE created_at >= ?
        GROUP BY DATE(created_at)
        ORDER BY day
        """,
        (start,),
    ).fetchall()

    incident_rows = conn.execute(
        """
        SELECT DATE(created_at) as day,
               COUNT(*) as incidents
        FROM incidents
        WHERE created_at >= ?
        GROUP BY DATE(created_at)
        ORDER BY day
        """,
        (start,),
    ).fetchall()

    conn.close()

    data = {}
    for r in rows:
        data[r[0]] = {"day": r[0], "visits": r[1], "guests": r[2], "authorized_cents": 0, "payment_count": 0, "incidents": 0}
    for r in payment_rows:
        if r[0] not in data:
            data[r[0]] = {"day": r[0], "visits": 0, "guests": 0, "authorized_cents": r[1], "payment_count": r[2], "incidents": 0}
        else:
            data[r[0]]["authorized_cents"] = r[1]
            data[r[0]]["payment_count"] = r[2]
    for r in incident_rows:
        if r[0] not in data:
            data[r[0]] = {"day": r[0], "visits": 0, "guests": 0, "authorized_cents": 0, "payment_count": 0, "incidents": r[1]}
        else:
            data[r[0]]["incidents"] = r[1]

    return list(data.values())


def top_assets_by_revenue(limit: int = 10) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT a.asset_id, a.title, a.category,
               COUNT(v.visit_id) as visit_count,
               COALESCE(SUM(p.total_captured_cents), 0) as revenue_cents
        FROM assets a
        LEFT JOIN visits v ON a.asset_id = v.asset_id
        LEFT JOIN payments p ON v.visit_id = p.visit_id AND p.status = 'captured'
        GROUP BY a.asset_id
        ORDER BY revenue_cents DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    return [
        {
            "asset_id": r[0],
            "title": r[1],
            "category": r[2],
            "visit_count": r[3],
            "revenue_usd": round(r[4] / 100, 2),
        }
        for r in rows
    ]


def top_hosts_by_revenue(limit: int = 10) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT u.user_id, u.name, u.email,
               COUNT(DISTINCT a.asset_id) as asset_count,
               COUNT(v.visit_id) as visit_count,
               COALESCE(SUM(p.total_captured_cents), 0) as revenue_cents
        FROM users u
        LEFT JOIN assets a ON u.user_id = a.host_id
        LEFT JOIN visits v ON a.asset_id = v.asset_id
        LEFT JOIN payments p ON v.visit_id = p.visit_id AND p.status = 'captured'
        WHERE u.user_type = 'host'
        GROUP BY u.user_id
        ORDER BY revenue_cents DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    return [
        {
            "user_id": r[0],
            "name": r[1],
            "email": r[2],
            "asset_count": r[3],
            "visit_count": r[4],
            "revenue_usd": round(r[5] / 100, 2),
        }
        for r in rows
    ]
