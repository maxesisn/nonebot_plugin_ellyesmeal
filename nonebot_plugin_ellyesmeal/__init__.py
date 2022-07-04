from typing import Tuple
from nonebot.adapters.onebot.v11 import Message, GroupMessageEvent, MessageSegment, Bot, Event
from nonebot.typing import T_State
from nonebot.params import State, CommandArg, Command
from nonebot.permission import SUPERUSER
from nonebot import get_bot, get_driver
from nonebot import on_command
from nonebot.log import logger

from nonebot import require
require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler

from nonebot_plugin_txt2img import Txt2Img

from .data_source import get_gm_info as db_get_gminfo, set_gm_info as db_set_gminfo
from .data_source import set_goodeps as db_set_goodeps, get_goodep as db_get_goodep

import re
import uuid
from tinydb import TinyDB, Query
from datetime import datetime, timedelta
import time
from calendar import monthrange

global_config = get_driver().config

font_size = 32

blacklist = ["114514", "昏睡", "田所", "查理酱", "[CQ:", "&#91;CQ:"]

config_dir = "/home/maxesisn/botData/misc_data"

db = TinyDB(f'{config_dir}/ellyesmeal.json')

zh_pat = re.compile(r"[\u4e00-\u9fa5]")

ep_pat = re.compile(r"^e.{1,3}q$")


async def ELLYE(bot: Bot, event: Event) -> bool:
    return event.get_user_id() == "491673070"

ellyesmeal = on_command("怡宝今天吃", aliases={"怡宝今天喝", "怡宝明天吃", "怡宝明天喝"})
update_meal_status = on_command("更新外卖状态")
delete_meal = on_command("删除外卖")
force_delete_meal = on_command("强制删除外卖", permission=SUPERUSER | ELLYE)
meal_howto = on_command("投食指南", aliases={"投喂指南"})
mark_good_ep = on_command("标记优质怡批", permission=SUPERUSER)


def to_img_msg(content, title="信息"):
    img = Txt2Img(font_size)
    pic = img.save(title, content)
    return MessageSegment.image(pic)


async def get_goodep_status(id):
    goodep = await db_get_goodep(id)
    return True if goodep is not None else False


@ellyesmeal.handle()
async def _(bot: Bot, event: GroupMessageEvent, command: Tuple[str, ...] = Command(), args: Message = CommandArg(), state: T_State = State()):
    command = command[0]
    day = "今天" if command == "怡宝今天吃" else "明天"
    sub_commands = str(args).split(" ")
    if len(sub_commands) == 1 and sub_commands[0] == "什么":
        meals = await get_ellyes_meal(event.self_id, day)
        await ellyesmeal.finish(to_img_msg(meals, f"怡宝{day}的菜单"))
    elif len(sub_commands) == 2 and sub_commands[0] == "什么" and sub_commands[1] == "-a":
        meals = await get_ellyes_meal(event.self_id, day, show_all=True)
        await ellyesmeal.finish(to_img_msg(meals, f"怡宝{day}的菜单"))
    elif len(sub_commands) == 1 and sub_commands[0] == "什么帮助":
        help = await get_ellyesmeal_help()
        await ellyesmeal.finish(to_img_msg(help, "帮助"))
    elif len(sub_commands) > 1 and sub_commands[1] == "帮助":
        help = await get_ellyesmeal_help()
        await ellyesmeal.finish(to_img_msg(help, "帮助"))
    else:
        ges = await get_goodep_status(event.user_id)
        state["is_auto_good_ep"] = False
        if not ges:
            nickname = await bot.get_group_member_info(group_id=event.group_id, user_id=event.user_id)
            nickname = nickname["card"] or nickname["nickname"] or nickname["user_id"]
            if "怡宝" in nickname or ep_pat.search(nickname):
                logger.info("auto good ep marked")
                state["is_hidden"] = False
                state["is_auto_good_ep"] = True
            else:
                logger.info(
                    f"{event.user_id} is not marked as good ep, marked as hidden.")
                state["is_hidden"] = True
        else:
            state["is_hidden"] = False
        state["day"] = day
        state["meal_string_data"] = sub_commands


@ellyesmeal.got("meal_string_data")
async def _(event: GroupMessageEvent, state: T_State = State()):
    meal_string_data: list[str] = state["meal_string_data"]
    day = state["day"]
    meal_string = "".join(meal_string_data)

    if any(word in meal_string for word in blacklist):
        await ellyesmeal.finish(to_img_msg("怡宴丁真，鉴定为假", "整蛊的"))

    meal_string = meal_string.strip()
    if meal_string == "":
        await ellyesmeal.finish()
    if meal_string.endswith(("?", "？")):
        await ellyesmeal.finish()
    if not zh_pat.search(meal_string):
        await ellyesmeal.finish(to_img_msg("怡宴丁真，鉴定为假", "卑鄙的"))
    if meal_string == "我":
        await ellyesmeal.finish(to_img_msg("怡宴丁真，鉴定为做梦", "虚无缥缈的"))
    if len(meal_string) > 30:
        await ellyesmeal.finish(to_img_msg("怡宴丁真，鉴定为假", "虚伪的"))

    est_arrival_time = meal_string_data[-1]
    est_arrival_time = est_arrival_time.replace("：", ":").replace(":", "")
    is_tomorrow = True if day == "明天" else False
    is_time_recorded = True
    # 判断时间是否为 HHMM 格式
    if est_arrival_time.isdigit():
        est_arrival_time = int(est_arrival_time)
        if est_arrival_time < 100 or est_arrival_time > 2400:
            is_time_recorded = False
        else:
            minute = int(est_arrival_time % 100)
            hour = int(est_arrival_time / 100)
            est_arrival_time = datetime.now().replace(hour=hour, minute=minute)

    # 处理没有指定时间的情况
    else:
        est_arrival_time = datetime.now() + timedelta(hours=1)
        is_time_recorded = False

    # 处理预计送达时间为明天的情况
    if is_tomorrow:
        # 如果时间只为"明天"，则默认为明天12:00
        if not is_time_recorded:
            est_arrival_time = datetime.now() + timedelta(days=1)
            est_arrival_time = est_arrival_time.replace(hour=12, minute=0)
        # 如果还写了时间，则修改为明天的该时间
        else:
            est_arrival_time += timedelta(days=1)

    # 判断是否已过预计送达时间
    if est_arrival_time < datetime.now():
        await ellyesmeal.finish(to_img_msg("怡宴丁真，鉴定为假", "错误的"))

    if is_time_recorded:
        meal_string_data = meal_string_data[:-1]
    meal_string = "+".join(meal_string_data)

    unique_id = str(uuid.uuid4())[:4]

    result = db.search(Query().id == unique_id)
    while len(result) > 0:
        unique_id = str(uuid.uuid4())[:4]

    data = {
        "id": unique_id.upper(),
        "giver": event.get_user_id(),
        "meal_content": meal_string,
        "order_time": datetime.timestamp(datetime.now()),
        "est_arrival_time": est_arrival_time.timestamp(),
        "status": "已下单" if not state["is_hidden"] else "已隐藏",
        "is_auto_good_ep": state["is_auto_good_ep"]
    }
    db.insert(data)
    if state["is_hidden"]:
        await ellyesmeal.finish(to_img_msg(f"投喂成功，但由于您暂未通过优质怡批认证，暂时隐藏。\nID: {unique_id.upper()}"))
    elif state["is_auto_good_ep"]:
        await ellyesmeal.finish(to_img_msg(f"投喂成功，由于您的群名片符合规范，自动认证为优质怡批。\nID: {unique_id.upper()}"))
    else:
        await ellyesmeal.finish(to_img_msg(f"投喂成功！  ID: {unique_id.upper()}"))


async def get_ellyes_meal(id, day, show_all=False):
    bot = get_bot()
    year = datetime.now().year
    month = datetime.now().month
    today = datetime.now().day
    if today == 1:
        month = month - 1
        if month == 0:
            month = 12
            year = year - 1
        today = monthrange(year, month)[1] + 1

    Mealdb = Query()
    meals = db.search((Mealdb.est_arrival_time > datetime.timestamp(
        datetime.now().replace(year=year, month=month, day=today-1, hour=23, minute=0, second=0))) | (Mealdb.status == "在吃"))

    msg = ""
    is_tmr_has_meal = False
    start = time.time()
    for meal in meals:
        if meal["status"] == "已隐藏" and not show_all:
            continue
        if day == "今天":
            if meal['est_arrival_time'] > datetime.timestamp(datetime.now().replace(year=year, month=month, day=today, hour=23, minute=0, second=0)):
                is_tmr_has_meal = True
                continue
        elif day == "明天":
            if meal['est_arrival_time'] < datetime.timestamp(datetime.now().replace(year=year, month=month, day=today, hour=23, minute=0, second=0)):
                continue
        giver_card = await db_get_gminfo(meal['giver'])
        if giver_card is None:
            giver_info = await bot.get_group_member_info(group_id="367501912", user_id=meal["giver"])
            giver_card = giver_info["card"] or giver_info["nickname"] or giver_info["user_id"]
            await db_set_gminfo(meal["giver"], giver_card)
        else:
            giver_card = giver_card.decode("utf-8")
            logger.debug(f"read user card from cache succeed: {giver_card}")
        giver_card = str(giver_card)
        msg += f"ID: {meal['id']}    状态: {meal['status']}\n热心群友：{giver_card}({meal['giver']})\n内容: {meal['meal_content']}\n预计送达时间: {datetime.fromtimestamp(meal['est_arrival_time']).strftime('%Y-%m-%d %H:%M')}"
        if meal["is_auto_good_ep"]:
            left_time = datetime.fromtimestamp(meal['order_time']) + timedelta(hours=3) - datetime.now()
            if left_time < timedelta(seconds=0):
                await clean_fake_meals()    
            else:
                msg += f"\n【若未被正式认可，该外卖将在{str(left_time)[:-7]}后自动删除。】"
        elif meal["status"] == "已隐藏":
            left_time = datetime.fromtimestamp(meal['order_time']) + timedelta(hours=2) - datetime.now()
            if left_time < timedelta(seconds=0):
                await clean_fake_meals()    
            else:
                msg += f"\n【若未被正式认可，该外卖将在{str(left_time)[:-7]}后自动删除。】"
        msg += "\n--------------------\n"
    end = time.time()
    print("time spent: ", end - start)
    if msg == "":
        msg = f"怡宝{day}还没有吃的！"
        if is_tmr_has_meal:
            msg += "\n\n\n\n                   *但是明天有吃的"
    return msg


async def get_detailed_meal(id):
    meal = db.get(Query().id == id)
    return meal


async def get_ellyesmeal_help():
    return "①.查询怡宝收到的外卖:\n发送`怡宝今天吃什么`可查询今天已经点给怡宝的外卖.\n②.使用本插件记录给怡宝点的外卖:\n请按照如下格式发送命令：怡宝今天吃 <外卖内容>【空格】<预计送达时间>\n③.更新外卖状态:\n发送：更新外卖状态 外卖ID <状态>\n提示：怡批可修改的外卖状态为：配送中/已送达/在吃。\n④.查询单个外卖的详细信息:\n发送查询外卖 <ID>;\n⑤.删除自己发的外卖信息:\n发送删除外卖 <ID>。"


@update_meal_status.handle()
async def _(event: GroupMessageEvent, args: Message = CommandArg(), state: T_State = State()):
    ges = await get_goodep_status(event.user_id)
    if not ges:
        logger.info(f"{event.user_id} is not marked as good ep, ignored")
        await ellyesmeal.finish()
    sub_commands = str(args)
    sub_commands = sub_commands.split(" ")
    if len(sub_commands) != 2:
        await update_meal_status.finish(to_img_msg("格式错误，请重新按照如下格式发送信息：更新外卖状态 外卖ID#状态"))
    meal_id = sub_commands[0].upper()
    meal_status = sub_commands[1]
    if meal_status not in ["配送中", "已送达", "在吃"]:
        if event.get_user_id() != list(global_config.superusers)[0]:
            await update_meal_status.finish(to_img_msg("请在如下状态中选择：配送中/已送达/在吃，并重新发送命令。", "状态错误"))
        else:
            pass
    queried_meal = db.get(Query().id == meal_id)
    if queried_meal:
        if queried_meal["giver"] != event.get_user_id():
            if event.get_user_id() != list(global_config.superusers)[0]:
                await update_meal_status.finish("您配吗？")
        result = db.update({"status": meal_status}, Query().id == meal_id)

        await update_meal_status.finish(to_img_msg(f"外卖{meal_id}状态已更新为：{meal_status}"))
    else:
        await update_meal_status.finish(to_img_msg(f"外卖{meal_id}不存在！"))


@delete_meal.handle()
async def _(event: GroupMessageEvent, args: Message = CommandArg(), state: T_State = State()):
    sub_commands = str(args)
    if len(sub_commands) != 4:
        await delete_meal.finish(to_img_msg("格式错误，请重新按照如下格式发送信息：删除外卖 <ID>"))
    meal_id = sub_commands.upper()
    sender = event.get_user_id()
    Mealdb = Query()
    result = db.remove((Mealdb.id == meal_id) & (Mealdb.giver == sender))
    if len(result) > 0:
        await delete_meal.finish(to_img_msg(f"外卖{meal_id}已删除"))
    else:
        await delete_meal.finish(to_img_msg(f"外卖{meal_id}不存在，或者你要删除的外卖不是你点的哦。"))


@force_delete_meal.handle()
async def _(event: GroupMessageEvent, args: Message = CommandArg(), state: T_State = State()):
    ids = str(args).split(" ")
    if ids[0] == "全部":
        year = datetime.now().year
        month = datetime.now().month
        today = datetime.now().day
        if today == 1:
            month = month - 1
            if month == 0:
                month = 12
                year = year - 1
            today = monthrange(year, month)[1] + 1
        Mealdb = Query()
        db.remove((Mealdb.est_arrival_time > datetime.timestamp(
            datetime.now().replace(year=year, month=month, day=today-1, hour=23, minute=0, second=0))) | (Mealdb.status == "在吃"))
        await force_delete_meal.finish(to_img_msg(f"全部外卖已删除"))
    for id in ids:
        db.remove(Query().id == id.upper())
    await force_delete_meal.finish(to_img_msg("已删除指定的外卖信息"))


@meal_howto.handle()
async def _(event: GroupMessageEvent):
    # if not event.group_id == 367501912:
    #     await meal_howto.finish()
    howto = "0.只有经过认证的怡批才可以使用本插件记录。\n认证方式：给怡宝点一份外卖，并发送订单截图至群内，经怡宝认可后便可获得优质怡批认证。\n或者效仿群内怡批更改群名片，符合某种命名规则的将被自动视为优质怡批。\n1.你需要填写怡宝的收货信息：\n收件人：陈泓仰 【女士】\n手机：19121671082\n地址：广东省深圳市南山区泊寓深圳（科技园店） \n   即【广东省深圳市南山区北环大道10092号】\n2.你应该给怡宝投喂什么：\n为了避免怡宝天天吃剩饭的现象发生，提高群内怡批的参与度，你应当购买小份的主食（如肠粉）/饮品（半糖少冰）/甜食（要耐放）/水果（不要瓜类）等，价格保持在20-30元左右以提升怡宝的好感度。\n3.你应该如何记录给怡宝点的外卖：\n"
    help = await get_ellyesmeal_help()
    howto += help
    await meal_howto.finish(to_img_msg(howto, "投喂指南"))


@mark_good_ep.handle()
async def _(event: GroupMessageEvent, args: Message = CommandArg(), state: T_State = State()):
    is_have_result = False
    Meal = Query()
    for ms in event.get_message():
        if ms.type == "at":
            is_have_result = True
            good_ep = ms.data["qq"]
            db.update(Meal.is_auto_good_ep == False, (Meal.giver == good_ep))
            await db_set_goodeps(good_ep, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    if is_have_result:
        await mark_good_ep.finish("ok")
    else:
        await mark_good_ep.finish("failed")

@scheduler.scheduled_job("interval", minutes=5)
async def clean_fake_meals():
    Mealdb = Query()
    db.remove((Mealdb.status == "已隐藏") & (Mealdb.order_time < datetime.timestamp(datetime.now() - timedelta(hours=2))))
    db.remove((Mealdb.is_auto_good_ep == True) & (Mealdb.order_time < datetime.timestamp(datetime.now() - timedelta(hours=3))))