def sharpe_like(pnls: list[float]) -> float:
    import math
    import numpy as np
    if not pnls:
        return -99.0
    return float(np.mean(pnls) / (np.std(pnls) + 1e-9) * math.sqrt(max(len(pnls), 1)))
