from pymongo import MongoClient
from nonebot import get_driver

from .utils import shanghai_tz

from bson.codec_options import CodecOptions

codec_opt = CodecOptions(tz_aware=True, tzinfo=shanghai_tz)

global_config = get_driver().config

mongo_host = global_config.mongo_host
mongo_user = global_config.mongo_user
mongo_pass = global_config.mongo_pass

client = MongoClient(f'mongodb://{mongo_user}:{mongo_pass}@{mongo_host}:27017/')

me_data = client.me_data

greylist_data = me_data.greylist.with_options(codec_options=codec_opt)
meals_data = me_data.meals.with_options(codec_options=codec_opt)
whitelist_data = me_data.whitelist.with_options(codec_options=codec_opt)
cards_data = me_data.cards.with_options(codec_options=codec_opt)