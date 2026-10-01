import subprocess

def fix_remote():
    remote_cmd = (
        "sudo python3 -c \"c=open('/home/palav/dograh/docker-compose.yaml').read(); "
        "c=c.replace('wget --no-verbose --tries=1 --spider http://127.0.0.1:3010/api/config/version || exit 1', "
        "'node -e \\\"require(\\'http\\').get(\\'http://127.0.0.1:3010/api/config/version\\', (r) => process.exit(r.statusCode === 200 ? 0 : 1))\\\"'); "
        "c=c.replace('wget --no-verbose --tries=1 --spider http://127.0.0.1:3010 || exit 1', "
        "'node -e \\\"require(\\'http\\').get(\\'http://127.0.0.1:3010/api/config/version\\', (r) => process.exit(r.statusCode === 200 ? 0 : 1))\\\"'); "
        "open('/home/palav/dograh/docker-compose.yaml','w').write(c)\" && "
        "cd /home/palav/dograh && "
        "sudo REGISTRY=local docker compose --profile remote up -d --force-recreate ui"
    )
    cmd = [
        "gcloud.cmd", "compute", "ssh", "dograh-server-us",
        "--zone=us-central1-a",
        f"--command={remote_cmd}"
    ]
    print("Executing remote fix...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    print("STDOUT:", res.stdout)
    print("STDERR:", res.stderr)

if __name__ == "__main__":
    fix_remote()
