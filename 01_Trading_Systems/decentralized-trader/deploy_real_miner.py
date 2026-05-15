#!/usr/bin/env python3
"""
DEPLOYMENT SCRIPT - REAL SOLANA MINER
Deploy to Vercel, Netlify, and other platforms
"""

import os
import subprocess
import json
import sys
import time
import webbrowser
from pathlib import Path

class RealSolanaMinerDeployer:
    """Deploy real Solana miner to multiple platforms"""
    
    def __init__(self):
        self.project_dir = Path(__file__).parent
        self.deployment_urls = {}
        
        print("🚀 Real Solana Miner Deployment Manager")
        print("=" * 50)
    
    def check_dependencies(self):
        """Check if deployment tools are installed"""
        dependencies = {
            'vercel': 'Vercel CLI',
            'netlify': 'Netlify CLI',
            'git': 'Git'
        }
        
        missing = []
        for cmd, name in dependencies.items():
            try:
                subprocess.run([cmd, '--version'], capture_output=True, check=True)
                print(f"✅ {name} installed")
            except (subprocess.CalledProcessError, FileNotFoundError):
                missing.append(cmd)
                print(f"❌ {name} not found")
        
        if missing:
            print(f"\n⚠️  Missing dependencies: {', '.join(missing)}")
            print("Install with:")
            print("  npm i -g vercel netlify-cli")
            return False
        
        return True
    
    def prepare_for_deployment(self):
        """Prepare project for deployment"""
        print("\n📦 Preparing project for deployment...")
        
        # Create necessary directories
        (self.project_dir / "api").mkdir(exist_ok=True)
        (self.project_dir / "netlify").mkdir(exist_ok=True)
        
        # Update requirements
        requirements = [
            "flask>=2.3.0",
            "flask-cors>=4.0.0",
            "solana>=0.30.0",
            "solders>=0.18.0",
            "asyncio-mqtt>=0.13.0",
            "psutil>=5.9.0",
            "structlog>=23.1.0",
            "websockets>=11.0.0"
        ]
        
        with open(self.project_dir / "requirements.txt", "w") as f:
            f.write("\n".join(requirements))
        
        print("✅ Project prepared for deployment")
        return True
    
    def deploy_to_vercel(self):
        """Deploy to Vercel"""
        print("\n🌐 Deploying to Vercel...")
        
        try:
            # Initialize Vercel project
            result = subprocess.run(
                ["vercel", "--version"],
                cwd=self.project_dir,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print("❌ Vercel CLI not working")
                return False
            
            # Deploy
            print("📤 Uploading to Vercel...")
            result = subprocess.run(
                ["vercel", "--prod"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                # Extract URL from output
                output = result.stdout
                for line in output.split('\n'):
                    if 'https://' in line and ('vercel.app' in line or 'vercel.com' in line):
                        url = line.strip()
                        self.deployment_urls['vercel'] = url
                        print(f"✅ Deployed to Vercel: {url}")
                        return True
            
            print(f"❌ Vercel deployment failed: {result.stderr}")
            return False
            
        except subprocess.TimeoutExpired:
            print("❌ Vercel deployment timed out")
            return False
        except Exception as e:
            print(f"❌ Vercel deployment error: {e}")
            return False
    
    def deploy_to_netlify(self):
        """Deploy to Netlify"""
        print("\n🌐 Deploying to Netlify...")
        
        try:
            # Initialize Netlify site
            result = subprocess.run(
                ["netlify", "--version"],
                cwd=self.project_dir,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print("❌ Netlify CLI not working")
                return False
            
            # Deploy
            print("📤 Uploading to Netlify...")
            result = subprocess.run(
                ["netlify", "deploy", "--prod", "--dir=."],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                # Extract URL from output
                output = result.stdout
                for line in output.split('\n'):
                    if 'https://' in line and ('netlify.app' in line or 'netlify.com' in line):
                        url = line.strip()
                        self.deployment_urls['netlify'] = url
                        print(f"✅ Deployed to Netlify: {url}")
                        return True
            
            print(f"❌ Netlify deployment failed: {result.stderr}")
            return False
            
        except subprocess.TimeoutExpired:
            print("❌ Netlify deployment timed out")
            return False
        except Exception as e:
            print(f"❌ Netlify deployment error: {e}")
            return False
    
    def deploy_local(self):
        """Deploy locally for testing"""
        print("\n🏠 Starting local deployment...")
        
        try:
            # Start the real miner locally
            import subprocess
            import threading
            
            # Start the miner in background
            process = subprocess.Popen(
                [sys.executable, "real_solana_miner.py"],
                cwd=self.project_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait a bit for startup
            time.sleep(3)
            
            if process.poll() is None:
                local_url = "http://localhost:8090"
                self.deployment_urls['local'] = local_url
                print(f"✅ Local deployment started: {local_url}")
                
                # Open browser
                webbrowser.open(local_url)
                return True
            else:
                stdout, stderr = process.communicate()
                print(f"❌ Local deployment failed:")
                print(f"stdout: {stdout.decode()}")
                print(f"stderr: {stderr.decode()}")
                return False
                
        except Exception as e:
            print(f"❌ Local deployment error: {e}")
            return False
    
    def test_deployments(self):
        """Test all deployments"""
        print("\n🧪 Testing deployments...")
        
        for platform, url in self.deployment_urls.items():
            print(f"Testing {platform}: {url}")
            
            try:
                import requests
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    print(f"✅ {platform} deployment working")
                else:
                    print(f"❌ {platform} deployment error: {response.status_code}")
                    
            except Exception as e:
                print(f"❌ {platform} deployment test failed: {e}")
    
    def generate_deployment_report(self):
        """Generate deployment report"""
        print("\n📊 DEPLOYMENT REPORT")
        print("=" * 50)
        
        if not self.deployment_urls:
            print("❌ No successful deployments")
            return
        
        print("🌐 Deployed URLs:")
        for platform, url in self.deployment_urls.items():
            print(f"  {platform.upper()}: {url}")
        
        print("\n📋 Next Steps:")
        print("1. Test each deployment URL")
        print("2. Create real mining wallets")
        print("3. Start real Solana mining")
        print("4. Monitor lamports generation")
        print("5. Check Solana Explorer for transactions")
        
        # Save report
        report_file = self.project_dir / "deployment_report.json"
        with open(report_file, "w") as f:
            json.dump(self.deployment_urls, f, indent=2)
        
        print(f"\n💾 Report saved to: {report_file}")
    
    def deploy_all(self):
        """Deploy to all platforms"""
        print("🚀 Starting full deployment process...")
        
        # Check dependencies
        if not self.check_dependencies():
            print("⚠️  Install missing dependencies first")
            return
        
        # Prepare project
        if not self.prepare_for_deployment():
            print("❌ Failed to prepare project")
            return
        
        # Deploy to platforms
        deployments = [
            ("Local", self.deploy_local),
            ("Vercel", self.deploy_to_vercel),
            ("Netlify", self.deploy_to_netlify)
        ]
        
        for name, deploy_func in deployments:
            try:
                deploy_func()
            except KeyboardInterrupt:
                print(f"\n⚠️  {name} deployment interrupted")
                break
            except Exception as e:
                print(f"❌ {name} deployment failed: {e}")
        
        # Test deployments
        self.test_deployments()
        
        # Generate report
        self.generate_deployment_report()

def main():
    """Main deployment function"""
    deployer = RealSolanaMinerDeployer()
    
    print("🎯 Real Solana Miner Deployment Options:")
    print("1. Deploy to all platforms")
    print("2. Deploy locally only")
    print("3. Deploy to Vercel only")
    print("4. Deploy to Netlify only")
    print("5. Test existing deployments")
    
    try:
        choice = input("\nSelect option (1-5): ").strip()
        
        if choice == "1":
            deployer.deploy_all()
        elif choice == "2":
            deployer.prepare_for_deployment()
            deployer.deploy_local()
        elif choice == "3":
            deployer.prepare_for_deployment()
            deployer.deploy_to_vercel()
        elif choice == "4":
            deployer.prepare_for_deployment()
            deployer.deploy_to_netlify()
        elif choice == "5":
            deployer.test_deployments()
        else:
            print("❌ Invalid choice")
            
    except KeyboardInterrupt:
        print("\n👋 Deployment cancelled")
    except Exception as e:
        print(f"❌ Deployment error: {e}")

if __name__ == "__main__":
    main()
