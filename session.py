import json
from bandit import UCB1Bandit
import redis.asyncio as redis

async def get_bandit(redis_client: redis.Redis, session_id: str) -> UCB1Bandit:
    data = await redis_client.get(f"session:{session_id}")
    if data is None:
        return UCB1Bandit()
    else:
        return UCB1Bandit.from_dict(json.loads(data))

async def save_bandit(redis_client: redis.Redis, session_id: str, bandit: UCB1Bandit):
    data_str = json.dumps(bandit.to_dict())
    await redis_client.set(f"session:{session_id}", data_str, ex=3600)

async def get_event_log(redis_client: redis.Redis, session_id: str) -> list[dict]:
    events = await redis_client.lrange(f"events:{session_id}", 0, -1)
    return [json.loads(e) for e in events]

async def append_event(redis_client: redis.Redis, session_id: str, event: dict):
    event_str = json.dumps(event)
    await redis_client.rpush(f"events:{session_id}", event_str)
    await redis_client.expire(f"events:{session_id}", 3600)
