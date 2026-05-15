class ExecutionModel:
    def maker_fill_probability(self, spread_ticks: float, vol_score: float) -> float:
        return max(0.1, min(0.9, 0.25 + 0.05 * spread_ticks + 0.15 * vol_score))
