# Live Kamino Jupiter Flash Arb

This repo can build, simulate, sign, and send a Kamino flash-loan Jupiter arbitrage transaction.

## Flow

```text
scan Jupiter USDC -> target -> USDC
estimate flash-loan fee and priority fee
build Kamino flash borrow
insert Jupiter swap instructions
build Kamino flash repay
sign transaction
simulate signed transaction
manual approval
send live mainnet transaction
confirm
write proof JSON
```

## Setup

```bash
npm install
cp .env.example .env
# edit .env
npm run once
```

## Live send

Only after simulation works:

```bash
# in .env:
LIVE_SEND_ENABLED=true
WALLET_KEYPAIR_PATH=/absolute/path/to/throwaway-wallet.json

npm run send
```

You must type:

```
EXECUTE
```

## Warning

This can lose transaction fees. It does not include an on-chain profit assertion program.
