from calendar import monthrange

from nonebot.log import logger

from .auth_ep import receive_greyed_users

from datetime import datetime, timedelta

from.mongo_source import meals_data, whitelist_data, cards_data


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
        year=year, month=month, day=today-1, hour=0, minute=0, second=0))
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
        # 是强制删除的情况
        result = meals_data.find_one({'id': id})
        if result:
            await receive_greyed_users([result['giver']])
            meals_data.delete_one({'_id': result['_id']})
            logger.info(f'外卖{id}被强制删除')
    return result


async def update_autoep_status(id, status):
    id = str(id)
    result = meals_data.update_one(
        {'giver': id}, {"$set": {'is_auto_good_ep': status}})
    return result


async def db_clean_fake_meals(force=False):
    timer_for_hidden = datetime.timestamp(datetime.now() - timedelta(hours=2)) if not force else 4102444799
    timer_for_autoep = datetime.timestamp(datetime.now() - timedelta(hours=3)) if not force else 4102444799
    result_hidden = meals_data.find({
        "$and": [
            {
                "status": "已隐藏"
            },
            {
                "order_time": {"$lt": timer_for_hidden}
            }
        ]
    })
    greyed_users = list()
    for result in result_hidden:
        greyed_users.append(result['giver'])
        logger.info(f'外卖{result["id"]}因被隐藏+超时被删除')
        meals_data.delete_one({'_id': result['_id']})
        
        
    result_autoep = meals_data.find({
        "$and": [
            {
                "is_auto_good_ep": True
            },
            {
                "order_time": {"$lt": timer_for_autoep}
            }
        ]
    })
    for result in result_autoep:
        greyed_users.append(result['giver'])
        logger.info(f'外卖{result["id"]}因被自动标记失效+超时被删除')
        meals_data.delete_one({'_id': result['_id']})

    if greyed_users:
        await receive_greyed_users(greyed_users)
