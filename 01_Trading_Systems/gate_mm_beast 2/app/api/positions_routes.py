def positions_payload(position_repo, symbols: list[str]) -> list[dict]:
    out = []
    for symbol in symbols:
        pos = position_repo.get_open(symbol)
        if pos:
            out.append(pos)
    return out
