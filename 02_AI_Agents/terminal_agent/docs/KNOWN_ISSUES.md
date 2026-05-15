# Known Issues and Limitations

## Current Limitations

### Exchange Scope
- **Single Exchange**: Only supports Gate.io futures
- **Settlement Currency**: USDT only (no BTC/USDC support)
- **Market Type**: Perpetual futures only (no spot or delivery futures)

### Symbol Constraints
- **Maximum Symbols**: Limited to 5 concurrent symbols (configurable)
- **Symbol Selection**: Automated selection may miss viable pairs in volatile markets
- **Contract Specifications**: Assumes standard Gate.io contract specifications
- **Quanto Multipliers**: Fixed quanto multiplier handling (may not support all contract types)

### Execution Limitations
- **Order Types**: Limited to limit orders (no market, stop, or conditional orders)
- **Execution Modes**: Three predefined modes (no custom execution strategies)
- **Partial Fills**: While supported, may not optimize for partial fill scenarios
- **Order Size**: Fixed notional sizing (no dynamic size adjustment)

### Risk Management
- **Static Limits**: Risk thresholds are static (no dynamic adjustment)
- **Correlation**: No correlation-based risk management
- **Portfolio Risk**: No portfolio-level risk optimization
- **Liquidity Risk**: Limited liquidity risk assessment

### Performance Constraints
- **Single Threaded**: Asyncio event loop (no multi-process scaling)
- **Database**: SQLite (not suitable for high-frequency trading)
- **Network**: Single network connection (no connection pooling)
- **Memory**: In-memory order book cache (no disk-based persistence)

### Monitoring Gaps
- **Latency Monitoring**: No detailed latency metrics
- **Slippage Tracking**: Limited slippage measurement
- **Fill Quality**: No fill quality analytics
- **Strategy Performance**: No backtesting or strategy optimization

## Known Issues

### Paper Mode
- **API Dependency**: Requires API connectivity for symbol selection (has fallback)
- **Private WebSocket**: Skipped in paper mode (expected behavior)
- **No Real Fills**: Simulated fills may not match live execution
- **Stale Book Threshold**: Extended to 60s in paper mode (may miss rapid movements)

### Database
- **Schema Migration**: Manual intervention required for major schema changes
- **No Migration Tool**: No automated database migration system
- **SQLite Limits**: Not suitable for very high-volume trading
- **Concurrent Access**: Limited concurrent write support

### WebSocket
- **Reconnection**: Exponential backoff may be too aggressive for some networks
- **Private WS**: Requires valid API credentials (fails in paper mode)
- **Message Ordering**: No guaranteed message ordering across channels
- **Compression**: No message compression (higher bandwidth usage)

### REST API
- **Rate Limits**: Fixed rate limits (no adaptive rate limiting)
- **Timeouts**: Fixed 15-second timeout (may be too short for some operations)
- **Error Handling**: Generic error handling (may not handle all edge cases)
- **Retry Logic**: Limited retry logic for transient failures

### Dashboard
- **No Authentication**: Dashboard has no access control
- **Single User**: Not designed for multi-user access
- **No Historical Data**: Limited historical data retention
- **Refresh Rate**: Fixed 3-second refresh rate

### Configuration
- **Hard-coded Values**: Some values are hard-coded (not fully configurable)
- **No Config File**: Configuration embedded in code (no external config file)
- **Environment Variables**: Limited environment variable support
- **Hot Reload**: No configuration hot-reload capability

## Compatibility Issues

### Python Version
- **3.13 Compatibility**: Requires signal handling fix (included in v2.0)
- **3.12+ Required**: Not tested on Python < 3.12
- **Type Hints**: Limited type hint coverage
- **Async/Await**: Requires asyncio support

### Operating System
- **Linux**: Primary development and testing platform
- **macOS**: Tested and compatible (signal handling fix included)
- **Windows**: Limited testing (may have signal handling issues)

### Dependencies
- **aiohttp**: Version compatibility may require updates
- **websockets**: Specific version requirements
- **SQLite**: Version-dependent features

## Security Considerations

### API Credentials
- **Environment Variables**: Credentials stored in environment variables
- **No Encryption**: Credentials not encrypted at rest
- **No Rotation**: No automatic credential rotation
- **Logging**: Credentials may appear in debug logs (redaction recommended)

### Network Security
- **TLS**: Uses TLS for API connections
- **Certificate Verification**: Basic certificate verification
- **No Proxy Support**: No proxy configuration support
- **No VPN Integration**: No VPN integration

### Code Security
- **Input Validation**: Limited input validation
- **SQL Injection**: Uses parameterized queries (mitigated)
- **Code Injection**: No dynamic code execution
- **Dependency Vulnerabilities**: Regular dependency updates required

## Performance Issues

### Latency
- **Order Placement**: ~100ms average (network dependent)
- **State Updates**: ~10ms average
- **Risk Checks**: ~5ms per check
- **Dashboard Updates**: 3-second refresh rate

### Throughput
- **Orders/Second**: Limited by rate limits (8 RPS private, 15 RPS public)
- **Symbols**: Maximum 5 concurrent symbols
- **Orders**: Maximum 8 open orders per symbol
- **Database Writes**: SQLite write limitations

### Memory Usage
- **Order Book Cache**: In-memory storage (scales with symbol count)
- **Database Connection**: Single connection pool
- **WebSocket Buffers**: Message buffering in memory
- **Log Files**: No automatic log rotation

## Data Integrity

### Persistence
- **SQLite**: ACID compliant but not enterprise-grade
- **No Backup**: No automated backup system
- **No Replication**: No database replication
- **Recovery**: Manual recovery process

### Data Consistency
- **Reconciliation**: Startup reconciliation only
- **No Audit Trail**: Limited audit trail
- **Event Logging**: Events logged but not analyzed
- **State Validation**: Limited state validation

## Usability Issues

### Setup
- **Manual Configuration**: Requires manual configuration
- **No Setup Wizard**: No guided setup process
- **Limited Documentation**: Advanced features may lack documentation
- **Error Messages**: Some error messages may be cryptic

### Operation
- **No GUI**: Command-line interface only (dashboard is web-based)
- **Limited Alerts**: No alerting system
- **No Automation**: No automation/scripting interface
- **Manual Intervention**: May require manual intervention in some scenarios

## Regulatory and Compliance

### No Compliance Features
- **No Trade Reporting**: No automated trade reporting
- **No Audit Logs**: Limited audit trail
- **No KYC/AML**: No identity verification integration
- **No Risk Reporting**: No regulatory risk reporting

### Disclaimer
- **Use at Own Risk**: No warranty or guarantee
- **No Financial Advice**: Not financial advice
- **Cryptocurrency Risk**: High volatility and risk
- **Professional Use**: Recommended for professional traders only

## Future Improvements

### High Priority
1. **Config File Support**: External configuration file
2. **Database Migration Tool**: Automated schema migrations
3. **Enhanced Error Handling**: More specific error messages
4. **Performance Monitoring**: Detailed latency and throughput metrics

### Medium Priority
1. **Multi-Exchange Support**: Support for additional exchanges
2. **Advanced Order Types**: Market, stop, conditional orders
3. **Dynamic Sizing**: Adaptive order sizing
4. **Backtesting Framework**: Strategy backtesting

### Low Priority
1. **Multi-User Dashboard**: User authentication and access control
2. **Strategy Optimization**: Automated parameter optimization
3. **Machine Learning**: ML-based decision making
4. **Portfolio Management**: Portfolio-level optimization

## Workarounds

### Paper Mode Limitations
- **Symbol Selection**: Manually specify symbols if API fails
- **Private WS**: Accept that private WS is skipped in paper mode
- **Stale Book**: Adjust staleness threshold as needed

### Database Issues
- **Schema Mismatch**: Delete and recreate database
- **Performance**: Use external database for high-volume trading
- **Backup**: Implement manual backup procedure

### Performance Issues
- **Latency**: Use collocated servers for lower latency
- **Throughput**: Increase rate limits with exchange
- **Memory**: Monitor and restart if memory grows

### Configuration Issues
- **Hard-coded Values**: Modify code directly (not recommended)
- **Environment Variables**: Use .env file for management
- **Hot Reload**: Restart engine for configuration changes

## Reporting Issues

When reporting issues, please include:
- Python version
- Operating system
- Engine version
- Configuration parameters
- Full error traceback
- Steps to reproduce
- Expected vs actual behavior
- Log files (redacted)

## Disclaimer

This software is provided as-is without warranty of any kind. The known issues and limitations documented here are subject to change. Users should thoroughly test the software in paper mode before using it for live trading.

Cryptocurrency trading involves substantial risk of loss. Past performance is not indicative of future results. Use at your own risk.
