def parse_query(query: str) -> dict:
    q = query.lower()
    if "open higher than last" in q:
        days = 1
        if "five" in q or "5" in q: days = 5
        return {"type": "open_gt_prev_close", "days": days}
    if "volume increasing" in q:
        return {"type": "volume_increasing", "window": 5}
    return {"type": "unknown"}
