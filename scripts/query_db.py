import base64
import subprocess

py_code = """
import httpx
import asyncio

async def test_patch():
    async with httpx.AsyncClient(verify=False) as client:
        # test patch endpoint
        resp = await client.patch('http://127.0.0.1:8000/api/v1/workflow/0/runs/57198/intent', json={'intent': 'Not Interested'})
        print("PATCH RESP STATUS:", resp.status_code)
        print("PATCH RESP BODY:", resp.text)

asyncio.run(test_patch())
"""

b = base64.b64encode(py_code.encode()).decode()

cmd = f"sudo docker exec dograh-api-1 bash -c \"echo {b} | base64 -d > /tmp/test_patch.py && python /tmp/test_patch.py\""
b_cmd = base64.b64encode(cmd.encode()).decode()

out = subprocess.check_output(
    f'gcloud compute ssh dograh-server-us --zone=us-central1-a --command="echo {b_cmd} | base64 -d | bash"',
    shell=True
).decode()

print(out)
