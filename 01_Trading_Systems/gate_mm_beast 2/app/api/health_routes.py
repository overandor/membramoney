def health_payload(app_state: dict) -> dict:
    return {"ok": app_state.get("healthy", True), "message": app_state.get("message", "ok")}
