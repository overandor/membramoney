#!/usr/bin/env python3
"""
Position Manager for Hedging Project
Manages positions and profit-taking logic
"""

import logging
from typing import List, Dict, Optional
from dataclasses import dataclass
from .api_client import GateIOClient

@dataclass
class PositionInfo:
    symbol: str
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pct: float
    age_seconds: float

class PositionManager:
    """Manages trading positions and profit-taking"""
    
    def __init__(self, client: GateIOClient, profit_threshold: float = 0.002):
        self.client = client
        self.profit_threshold = profit_threshold
        self.logger = logging.getLogger('PositionManager')
    
    def get_positions(self) -> List[PositionInfo]:
        """Get current positions with detailed info"""
        result = self.client.get_positions()
        
        if not result.success:
            self.logger.error(f"Failed to get positions: {result.error}")
            return []
        
        positions = []
        current_time = time.time()
        
        for pos in result.data:
            size = float(pos['size'])
            if size != 0:  # Only non-zero positions
                entry_price = float(pos['entry_price'])
                mark_price = float(pos['mark_price'])
                unrealized_pnl = float(pos['unrealised_pnl'])
                
                # Calculate percentage
                unrealized_pct = (mark_price - entry_price) / entry_price if entry_price > 0 else 0
                
                position = PositionInfo(
                    symbol=pos['contract'],
                    size=size,
                    entry_price=entry_price,
                    current_price=mark_price,
                    unrealized_pnl=unrealized_pnl,
                    unrealized_pct=unrealized_pct,
                    age_seconds=0  # Would need timestamp info
                )
                
                positions.append(position)
        
        return positions
    
    def get_profitable_positions(self) -> List[PositionInfo]:
        """Get positions that exceed profit threshold"""
        positions = self.get_positions()
        profitable = []
        
        for pos in positions:
            if pos.unrealized_pct >= self.profit_threshold:
                profitable.append(pos)
                self.logger.info(f"💰 Profitable position: {pos.symbol} {pos.unrealized_pct:.2%}")
        
        return profitable
    
    def should_sell_position(self, position: PositionInfo) -> bool:
        """Determine if position should be sold for profit"""
        return position.unrealized_pct >= self.profit_threshold
    
    def close_position_for_profit(self, position: PositionInfo, size: float = None) -> bool:
        """Close position for profit"""
        if size is None:
            size = abs(position.size)
        
        # Determine side based on position size
        side = "SELL" if position.size > 0 else "BUY"
        
        result = self.client.place_order(
            symbol=position.symbol,
            side=side,
            size=size,
            price=0,  # Market order
            order_type="market"
        )
        
        if result.success:
            self.logger.info(f"💰 Profit taken: {side} {size:.6f} {position.symbol} (Profit: {position.unrealized_pct:.2%})")
            return True
        else:
            self.logger.error(f"❌ Failed to take profit: {result.error}")
            return False
