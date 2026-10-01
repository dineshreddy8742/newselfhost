import subprocess

def run_fix():
    print("Step 1: Uploading clean deploy_code.tar.gz...")
    scp_cmd = [
        "gcloud.cmd", "compute", "scp",
        "deploy_code.tar.gz",
        "dograh-server-us:/home/palav/deploy_code.tar.gz",
        "--zone=us-central1-a"
    ]
    res1 = subprocess.run(scp_cmd, capture_output=True, text=True)
    print("SCP Output:", res1.stdout, res1.stderr)

    python_remote_script = (
        "import re\n"
        "with open('/home/palav/dograh/docker-compose.yaml', 'r') as f:\n"
        "    content = f.read()\n"
        "if 'PORT: \"3010\"' not in content:\n"
        "    content = content.replace('HOSTNAME: \"0.0.0.0\"', 'HOSTNAME: \"0.0.0.0\"\\n      PORT: \"3010\"')\n"
        "content = re.sub(r'healthcheck:.*?(?=\\s+networks:)', 'healthcheck:\\n      test: [\"CMD\", \"/usr/local/bin/node\", \"-e\", \"require(\\'http\\').get(\\'http://127.0.0.1:3010/api/config/version\\', (r) => process.exit(r.statusCode === 200 ? 0 : 1))\"]\\n      interval: 30s\\n      timeout: 10s\\n      retries: 5\\n      start_period: 15s\\n', content, flags=re.DOTALL)\n"
        "with open('/home/palav/dograh/docker-compose.yaml', 'w') as f:\n"
        "    f.write(content)\n"
    )

    ssh_fix_cmd = [
        "gcloud.cmd", "compute", "ssh", "dograh-server-us",
        "--zone=us-central1-a",
        f"--command=tar -xzf /home/palav/deploy_code.tar.gz -C /home/palav/dograh && python3 -c \"{python_remote_script}\" && cd /home/palav/dograh && sudo REGISTRY=local docker compose --profile remote up -d --build --force-recreate ui api"
    ]
    print("Step 2: Updating docker-compose.yaml and recreating containers...")
    res2 = subprocess.run(ssh_fix_cmd, capture_output=True, text=True)
    print("SSH Output:", res2.stdout, res2.stderr)

if __name__ == "__main__":
    run_fix()
