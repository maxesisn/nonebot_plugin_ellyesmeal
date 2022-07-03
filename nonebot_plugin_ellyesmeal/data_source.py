from redis import StrictRedis
from nonebot import get_driver

from datetime import datetime

global_config = get_driver().config
redis_host = global_config.redis_host
redis_pass = global_config.redis_pass

r = StrictRedis(host=redis_host, port=6379, db=5, password=redis_pass)
bep = StrictRedis(host=redis_host, port=6379, db=6, password=redis_pass)

async def get_gm_info(user_id):
    user_id = str(user_id)
    gm_info = r.get(user_id)
    return gm_info

async def set_gm_info(user_id, gm_info):
    user_id = str(user_id)
    r.set(user_id, gm_info)
    r.expire(user_id, 60 * 60 * 24)
    return True

async def set_badeps(user_id, time):
    user_id = str(user_id)
    bep.set(user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    if time is not None:
        bep.expire(user_id, time)
    return True

async def get_badep(user_id):
    user_id = str(user_id)
    time = bep.get(user_id)
    return time