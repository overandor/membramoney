class SlippageModel:
    def stop_slippage(self, spread: float) -> float:
        return spread * 0.25
