import "dotenv/config";
import Decimal from "decimal.js";
import { address, createSolanaRpc, createSolanaRpcSubscriptions, pipe, createTransactionMessage, setTransactionMessageFeePayerSigner, setTransactionMessageLifetimeUsingBlockhash, appendTransactionMessageInstructions, signTransactionMessageWithSigners, sendAndConfirmTransactionFactory, getSignatureFromTransaction, none, getProgramDerivedAddress, getAddressEncoder } from "@solana/kit";
import { KaminoMarket, PROGRAM_ID as KAMINO_PROGRAM_ID, getFlashLoanInstructions } from "@kamino-finance/klend-sdk";
import { parseKeypairFile } from "@kamino-finance/klend-sdk/dist/utils/signer.js";
