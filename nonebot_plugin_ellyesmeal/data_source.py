from calendar import monthrange
from unittest import result
from pymongo import MongoClient

from nonebot import get_driver
from nonebot.log import logger

from datetime import datetime, timedelta



global_config = get_driver().config

mongo_host = global_config.mongo_host
mongo_user = global_config.mongo_user
mongo_pass = global_config.mongo_pass

client = MongoClient(f'mongodb://{mongo_user}:{mongo_pass}@{mongo_host}:27017/')
me_data = client.me_data

meals_data = me_data.meals
whitelist_data = me_data.whitelist
cards_data = me_data.cards


async def get_gm_info(user_id):
    user_id = str(user_id)
    result = cards_data.find_one({'id': user_id})
    card = result['card'] if result else None
    return card


async def set_gm_info(user_id, gm_info):
    user_id = str(user_id)
    result = cards_data.update_one(
        {'id': user_id},
        {'$set': {'card': gm_info}},
        upsert=True
    )
    return result.modified_count


async def set_goodeps(user_id, time):
    user_id = str(user_id)
    whitelist_data.update_one(
        {'id': user_id},
        {'$set': {'set_time': time}},
        upsert=True
    )


async def get_goodep(user_id):
    user_id = str(user_id)
    result = whitelist_data.find_one({'id': user_id})
    return True if result else False

async def check_id_exist(id):
    id = meals_data.find_one({'id': id})
    return True if id else False


async def insert_meal(meal):
    meals_data.insert_one(meal)
    return True


async def get_decent_meals():
    year = datetime.now().year
    month = datetime.now().month
    today = datetime.now().day
    if today == 1:
        month = month - 1
        if month == 0:
            month = 12
            year = year - 1
        today = monthrange(year, month)[1] + 1
    decent_time = datetime.timestamp(datetime.now().replace(
        year=year, month=month, day=today-1, hour=23, minute=59, second=0))
    result = meals_data.find(
        {
            "$or":
            [
                {
                    "est_arrival_time": {"$gt": decent_time}
                },
                {
                    "status": "在吃"
                }
            ]
        }
    )
    return result


async def get_exact_meal(id):
    id = str(id)
    meal = meals_data.find_one({'id': id})
    return meal


async def update_exact_meal(id, k, v):
    id = str(id)
    result = meals_data.update_one({'id': id}, {"$set": {k: v}})
    return result


async def del_exact_meal(id, k=None, v=None):
    id = str(id)
    if k is not None:
        result = meals_data.delete_one({'id': id, k: v})
    else:
        result = meals_data.delete_one({'id': id})
    return result


async def update_autoep_status(id, status):
    id = str(id)
    result = meals_data.update_one(
        {'giver': id}, {"$set": {'is_auto_good_ep': status}})
    return result


async def db_clean_fake_meals():
    timer_for_hidden = datetime.timestamp(datetime.now() - timedelta(hours=2))
    timer_for_autoep = datetime.timestamp(datetime.now() - timedelta(hours=3))
    result_hidden = meals_data.delete_many({
        "$and": [
            {
                "status": "已隐藏"
            },
            {
                "order_time": {"$lt": timer_for_hidden}
            }
        ]
    })
    if result_hidden.deleted_count > 0:
        logger.info(f'已隐藏的外卖被删除了{result_hidden.deleted_count}个')
    result_autoep = meals_data.delete_many({
        "$and": [
            {
                "is_auto_good_ep": True
            },
            {
                "order_time": {"$lt": timer_for_autoep}
            }
        ]
    })
    if result_autoep.deleted_count > 0:
        logger.info(f'带有自动标记的外卖被删除了{result_autoep.deleted_count}个')
    return True
