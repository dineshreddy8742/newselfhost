import asyncio
from api.db import db_client

async def test_update():
    run_id = 57199
    run = await db_client.get_workflow_run_by_id(run_id)
    print("BEFORE GATHERED_CONTEXT:", run.gathered_context if run else "NOT FOUND")
    
    await db_client.update_workflow_run(run_id, gathered_context={"user_intent": "Not Interested"})
    
    run_after = await db_client.get_workflow_run_by_id(run_id)
    print("AFTER GATHERED_CONTEXT:", run_after.gathered_context if run_after else "NOT FOUND")

if __name__ == "__main__":
    asyncio.run(test_update())
