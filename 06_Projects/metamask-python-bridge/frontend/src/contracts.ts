import { parseAbi, encodeFunctionData } from 'viem';

// Contract ABIs
export const DEPLOYMENT_HELPER_ABI = parseAbi([
  'function getDeploymentParams(address token) external view returns (bytes bytecode, bytes constructorArgs)',
  'function estimateGas(address token) external view returns (uint256)',
]);

export const TRADING_CONTRACT_ABI = parseAbi([
  'function executeTrade(address token, uint256 amount, bytes calldata data) external returns (bool)',
  'function getStrategyParams() external view returns (uint256 minProfit, uint256 maxSlippage)',
]);

export interface DeploymentParams {
  bytecode: `0x${string}`;
  constructorArgs: `0x${string}`;
  estimatedGas: bigint;
}

export interface TradeIntent {
  targetContract: `0x${string}`;
  method: string;
  params: unknown[];
  rationale: string;
  estimatedGas: bigint;
}

export function encodeDeploymentParams(params: DeploymentParams): `0x${string}` {
  return encodeFunctionData({
    abi: DEPLOYMENT_HELPER_ABI,
    functionName: 'getDeploymentParams',
    args: [params.bytecode, params.constructorArgs],
  });
}

export function encodeTradeIntent(intent: TradeIntent): `0x${string}` {
  return encodeFunctionData({
    abi: TRADING_CONTRACT_ABI,
    functionName: 'executeTrade',
    args: intent.params,
  });
}
