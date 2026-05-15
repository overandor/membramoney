#!/usr/bin/env node

const { Connection, PublicKey } = require("@solana/web3.js");
const { getAssociatedTokenAddressSync } = require("@solana/spl-token");
const {
  KaminoMarket,
  getFlashLoanInstructions,
  PROGRAM_ID,
} = require("@kamino-finance/klend-sdk");

function readStdin() {
  return new Promise((resolve, reject) => {
    let data = "";
    process.stdin.setEncoding("utf8");

    process.stdin.on("data", (chunk) => {
      data += chunk;
    });

    process.stdin.on("end", () => {
      try {
        resolve(JSON.parse(data));
      } catch (err) {
        reject(new Error(`Invalid JSON stdin: ${err.message}`));
      }
    });

    process.stdin.on("error", reject);
  });
}

function serializeInstruction(ix) {
  return {
    programId: ix.programId.toBase58(),
    accounts: ix.keys.map((key) => ({
      pubkey: key.pubkey.toBase58(),
      isSigner: key.isSigner,
      isWritable: key.isWritable,
    })),
    data: Buffer.from(ix.data).toString("base64"),
  };
}

function getReserveAddress(reserve) {
  if (reserve?.address) return reserve.address;
  if (reserve?.publicKey) return reserve.publicKey;
  if (typeof reserve?.getAddress === "function") return reserve.getAddress();
  return null;
}

async function main() {
  const input = await readStdin();

  const rpcUrl =
    process.env.SOLANA_RPC_URL || "https://api.mainnet-beta.solana.com";

  const connection = new Connection(rpcUrl, "confirmed");

  const userPublicKey = new PublicKey(input.userPublicKey);
  const marketAddress = new PublicKey(input.market);
  const reserveAddress = new PublicKey(input.reserveAddress);
  const usdcMint = new PublicKey(
    input.reserveMint || "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
  );

  const amountAtoms = BigInt(input.amountAtoms);
  const borrowIxIndex = Number(input.borrowIxIndex ?? 0);

  if (borrowIxIndex !== 0) {
    throw new Error("This bridge expects borrowIxIndex=0.");
  }

  const market = await KaminoMarket.load(connection, marketAddress);
  await market.loadReserves();

  const lendingMarketAuthority = await market.getLendingMarketAuthority();
  const userUsdcAta = getAssociatedTokenAddressSync(usdcMint, userPublicKey);

  const reserve =
    market.reserves?.find((candidate) => {
      const addr = getReserveAddress(candidate);
      return addr?.equals(reserveAddress);
    }) || reserveAddress;

  const { flashBorrowIx, flashRepayIx } = getFlashLoanInstructions({
    borrowIxIndex,
    userTransferAuthority: userPublicKey,
    lendingMarketAuthority,
    lendingMarketAddress: market.getAddress(),
    reserve,
    amountLamports: amountAtoms,
    destinationAta: userUsdcAta,
    referrerAccount: null,
    referrerTokenState: null,
    programId: PROGRAM_ID,
  });

  process.stdout.write(
    JSON.stringify({
      flashBorrowInstruction: serializeInstruction(flashBorrowIx),
      flashRepayInstruction: serializeInstruction(flashRepayIx),
    })
  );
}

main().catch((err) => {
  process.stderr.write(`${err.stack || err.message}\n`);
  process.exit(1);
});
