def parse_query(query: str):
    q = query.lower()
    if "open" in q and "close" in q:
        return {"type": "open_gt_prev_close", "days": 5}
    elif "volume" in q and "increas" in q:
        return {"type": "volume_increasing", "window": 3}
    return {"type": "unknown"}
