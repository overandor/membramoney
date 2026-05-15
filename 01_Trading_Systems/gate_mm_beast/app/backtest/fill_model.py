class FillModel:
    def should_fill(self, probability: float, rnd: float) -> bool:
        return rnd <= probability
