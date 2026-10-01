import asyncio
from api.db import db_client

async def check():
    run = await db_client.get_workflow_run_by_id(57199)
    if run:
        print("FOUND RUN 57199:")
        print("gathered_context:", run.gathered_context)
    else:
        print("RUN 57199 NOT FOUND")

if __name__ == "__main__":
    asyncio.run(check())
