import { useState } from 'react'

interface DeploymentPanelProps {
  walletAddress?: string
}

export default function DeploymentPanel({ walletAddress }: DeploymentPanelProps) {
  const [contractName, setContractName] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [deploymentParams, setDeploymentParams] = useState<any>(null)
  const [error, setError] = useState('')

  const handleGetParams = async () => {
    if (!contractName) {
      setError('Please enter a contract name')
      return
    }

    setIsLoading(true)
    setError('')

    try {
      const response = await fetch(
        `http://localhost:8000/api/deploy/params?contract_name=${contractName}`
      )
      const data = await response.json()

      if (response.ok) {
        setDeploymentParams(data)
      } else {
        setError(data.message || 'Failed to fetch deployment parameters')
      }
    } catch (err) {
      setError('Failed to connect to backend. Is the server running?')
      console.error(err)
    } finally {
      setIsLoading(false)
    }
  }

  const handlePrepareDeployment = async () => {
    if (!deploymentParams) return

    setIsLoading(true)
    setError('')

    try {
      const response = await fetch('http://localhost:8000/api/deploy/prepare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contract_name: contractName,
          constructor_args: deploymentParams.constructor_args || {},
        }),
      })

      const data = await response.json()

      if (response.ok) {
        // TODO: Use MetaMask to sign and broadcast the deployment transaction
        alert('Deployment transaction prepared. MetaMask signing will be implemented.')
      } else {
        setError(data.message || 'Failed to prepare deployment')
      }
    } catch (err) {
      setError('Failed to prepare deployment')
      console.error(err)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-white mb-4">Contract Deployment</h2>
        <p className="text-white/80 mb-6">
          Deploy smart contracts with Python-prepared parameters
        </p>
      </div>

      <div className="space-y-4">
        <div>
          <label className="block text-white/80 text-sm mb-2">Contract Name</label>
          <input
            type="text"
            value={contractName}
            onChange={(e) => setContractName(e.target.value)}
            placeholder="e.g., MyToken, TradingStrategy"
            className="w-full bg-white/10 border border-white/20 rounded-lg px-4 py-2 text-white placeholder-white/40 focus:outline-none focus:border-white/40"
          />
        </div>

        <button
          onClick={handleGetParams}
          disabled={isLoading}
          className="w-full bg-white text-purple-600 px-6 py-3 rounded-lg font-semibold hover:bg-white/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
        >
          {isLoading ? 'Loading...' : 'Get Deployment Parameters'}
        </button>

        {error && (
          <div className="bg-red-500/20 border border-red-500 text-red-200 px-4 py-3 rounded-lg">
            {error}
          </div>
        )}

        {deploymentParams && (
          <div className="bg-white/10 rounded-lg p-4 space-y-4">
            <h3 className="font-semibold text-white">Deployment Parameters</h3>

            <div className="space-y-2">
              <div>
                <span className="text-white/60 text-sm">Bytecode:</span>
                <p className="text-white font-mono text-xs break-all">
                  {deploymentParams.bytecode}
                </p>
              </div>

              {deploymentParams.constructor_args && (
                <div>
                  <span className="text-white/60 text-sm">Constructor Args:</span>
                  <pre className="text-white font-mono text-xs bg-black/20 p-2 rounded">
                    {JSON.stringify(deploymentParams.constructor_args, null, 2)}
                  </pre>
                </div>
              )}

              {deploymentParams.network_config && (
                <div>
                  <span className="text-white/60 text-sm">Network Config:</span>
                  <pre className="text-white font-mono text-xs bg-black/20 p-2 rounded">
                    {JSON.stringify(deploymentParams.network_config, null, 2)}
                  </pre>
                </div>
              )}
            </div>

            <button
              onClick={handlePrepareDeployment}
              disabled={isLoading}
              className="w-full bg-green-500/20 border border-green-500 text-green-200 px-6 py-3 rounded-lg font-semibold hover:bg-green-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              {isLoading ? 'Preparing...' : 'Prepare Deployment'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
