class QueueModel:
    def estimate_queue_rank(self, bid_size: float, ask_size: float) -> float:
        total = max(bid_size + ask_size, 1e-9)
        return bid_size / total
