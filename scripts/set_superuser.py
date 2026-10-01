#!/usr/bin/env python3
"""Set palavaladineshkumarreddy17@gmail.com as superuser via psql on the remote VM."""
import subprocess, sys

zone  = "us-central1-a"
vm    = "dograh-db-vm"
email = "palavaladineshkumarreddy17@gmail.com"

sql_update = f"UPDATE users SET is_superuser = true WHERE email = '{email}';"
sql_check  = f"SELECT id, email, is_superuser FROM users WHERE email = '{email}';"

for label, sql in [("UPDATE", sql_update), ("CHECK", sql_check)]:
    cmd = [
        "gcloud.cmd", "compute", "ssh", vm,
        "--zone", zone,
        "--command",
        f"sudo docker exec dograh-db-postgres-1 psql -U postgres -d postgres -c \"{sql}\""
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    print(f"--- {label} ---")
    print("STDOUT:", res.stdout)
    print("STDERR:", res.stderr)
    if res.returncode != 0:
        print("FAILED")
        sys.exit(1)
