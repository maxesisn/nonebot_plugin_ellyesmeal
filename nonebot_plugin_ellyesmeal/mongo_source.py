from pymongo import MongoClient
from nonebot import get_driver

global_config = get_driver().config

mongo_host = global_config.mongo_host
mongo_user = global_config.mongo_user
mongo_pass = global_config.mongo_pass

client = MongoClient(f'mongodb://{mongo_user}:{mongo_pass}@{mongo_host}:27017/')

me_data = client.me_data
greylist_data = me_data.greylist
meals_data = me_data.meals
whitelist_data = me_data.whitelist
cards_data = me_data.cards