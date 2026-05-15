import { createConnect } from '@metamask/connect-evm';
import { InjectedConnector } from '@metamask/connect-evm/injected';
import { config } from 'wagmi';
import { mainnet, sepolia } from 'wagmi/chains';

// Configure wagmi with MetaMask Connect
export const metamaskConnect = createConnect({
  chains: [mainnet, sepolia],
  connectors: [
    new InjectedConnector({
      options: {
        name: 'MetaMask',
        shimDisconnect: true,
      },
    }),
  ],
  projectId: 'metamask-python-bridge', // Replace with your project ID
});

// Wagmi configuration
export const wagmiConfig = config({
  chains: [mainnet, sepolia],
  connectors: metamaskConnect.connectors,
  ssr: true,
});

export type { Connect } from '@metamask/connect-evm';
