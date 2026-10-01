import os
import subprocess

print("1. Extracting archive...")
subprocess.run("tar -xzf /home/palav/deploy_code.tar.gz -C /home/palav/dograh", shell=True, check=True)

print("2. Rebuilding and starting Docker Compose services...")
subprocess.run("cd /home/palav/dograh && sudo REGISTRY=local docker compose --profile remote up -d --build --force-recreate", shell=True, check=True)

print("SUCCESSFULLY COMPLETED REMOTE DEPLOYMENT!")
