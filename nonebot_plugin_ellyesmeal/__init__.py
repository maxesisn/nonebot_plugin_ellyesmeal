from operator import ge
from nonebot.adapters.onebot.v11 import Message, GroupMessageEvent, MessageSegment
from nonebot.typing import T_State
from nonebot.params import State, CommandArg, EventMessage
from nonebot.permission import SUPERUSER
from nonebot import get_bot, get_driver
from nonebot import on_command

from nonebot_plugin_txt2img import Txt2Img

import uuid
from tinydb import TinyDB, Query
from datetime import datetime

global_config = get_driver().config

font_size = 32

blacklist = ["114514", "昏睡", "田所", "查理酱"]

db = TinyDB('/home/maxesisn/botData/misc_data/ellyesmeal.json')

ellyesmeal = on_command("怡宝今天吃", aliases={"怡宝今天喝"})
update_meal_status = on_command("更新外卖状态")
query_meal = on_command("查询外卖")
delete_meal = on_command("删除外卖")
force_delete_meal = on_command("强制删除外卖", permission=SUPERUSER)
confirm_record = on_command("1")


@ellyesmeal.handle()
async def _(event: GroupMessageEvent, args: Message = CommandArg(), state: T_State = State()):
    group_id = event.group_id
    sub_commands = str(args).split(" ")
    if len(sub_commands) == 1 and sub_commands[0] == "什么":
        meals = await get_ellyes_meal(event.self_id)
        img = Txt2Img(font_size)
        pic = img.save("怡宝今天的菜单：", meals)
        await ellyesmeal.finish(MessageSegment.image(pic))
    if len(sub_commands) > 1 and sub_commands[1] == "帮助":
        help = await get_ellyesmeal_help()
        img = Txt2Img(font_size)
        pic = img.save("帮助：", help)
        await ellyesmeal.finish(MessageSegment.image(pic))
    state["meal_string"] = sub_commands[0]


@ellyesmeal.got("meal_string", prompt="怡宝今天吃什么？\n注：发送`怡宝今天吃什么 帮助`可查看帮助信息")
async def _(event: GroupMessageEvent, state: T_State = State()):
    time_format = "%H:%M"
    meal_string = str(state["meal_string"])
    if any(word in meal_string for word in blacklist):
        await ellyesmeal.finish("怡宴丁真，鉴定为假")
    meal_string = meal_string.strip()
    meal_string = meal_string.replace("＃", "#")
    meal_string_info = str(meal_string).split("#")
    if len(meal_string_info) == 1:
        await ellyesmeal.finish()
    if len(meal_string_info) < 4:
        img = Txt2Img(font_size)
        pic = img.save(
            "命令语法错误：", "格式错误，请按照如下格式发送信息：外卖内容#商家名#点餐渠道(可省略)#预计送达时间（hh:mm）#状态\n注：不能带空格")
        await ellyesmeal.reject(MessageSegment.image(pic))

    if len(meal_string_info) == 4:
        meal_string_info.insert(2, "<无>")

    if len(meal_string_info) == 5:
        try:
            meal_string_info[3] = meal_string_info[3].replace("：", ":")
            meal_string_info[3] = datetime.strptime(
                meal_string_info[3], time_format)
            meal_string_info[3] = meal_string_info[3].replace(
                year=datetime.now().year, month=datetime.now().month, day=datetime.now().day)
        except ValueError:
            img = Txt2Img(font_size)
            pic = img.save(
                "命令语法错误：", "格式错误，请按照如下格式发送信息：外卖内容#商家名#点餐渠道(可省略)#预计送达时间（hh:mm）#状态\n注：不能带空格")
            await ellyesmeal.reject(MessageSegment.image(pic))

    unique_id = str(uuid.uuid4())[:4]

    result = db.search(Query().id == unique_id)
    while len(result) > 0:
        unique_id = str(uuid.uuid4())[:4]
    data = {
        "id": unique_id.upper(),
        "giver": event.get_user_id(),
        "meal_content": meal_string_info[0],
        "shop": meal_string_info[1],
        "platform": meal_string_info[2],
        "est_arrival_time": datetime.timestamp(meal_string_info[3]),
        "status": meal_string_info[4]
    }
    db.insert(data)
    img = Txt2Img(font_size)
    pic = img.save("信息：", f"投喂成功！  ID: {unique_id.upper()}")
    await ellyesmeal.finish(MessageSegment.image(pic))


async def get_ellyes_meal(id):
    bot = get_bot(str(id))
    today = datetime.now().day
    Mealdb = Query()
    meals = db.search((Mealdb.est_arrival_time > datetime.timestamp(
        datetime.now().replace(day=today-1, hour=23, minute=0, second=0))) | (Mealdb.status == "在吃"))
    print(meals)
    msg = ""
    for meal in meals:
        giver_info = await bot.get_group_member_info(group_id="367501912", user_id=meal["giver"])
        giver_card = giver_info["card"] or giver_info["nickname"] or giver_info["user_id"]
        giver_card = str(giver_card)
        msg += f"ID: {meal['id']} | 热心群友：{giver_card} | 内容: {meal['meal_content']} | 商家: {meal['shop']} | 平台：{meal['platform']} | 预计送达时间: {datetime.fromtimestamp(meal['est_arrival_time']).strftime('%m-%d %H:%M')} | 状态: {meal['status']}\n"

    if msg == "":
        msg = "怡宝今天还没有吃的！"
    return msg


async def get_detailed_meal(id):
    meal = db.get(Query().id == id)
    return meal


async def get_ellyesmeal_help():
    return "如何查询怡宝收到的外卖？发送`怡宝今天吃什么`可查询今天已经点给怡宝的外卖.\n如何使用本插件记录给怡宝点的外卖？\n请按照如下格式发送命令：\n怡宝今天吃 外卖内容#商家名#点餐渠道(可省略)#预计送达时间#状态\n如何更新外卖状态？\n发送：更新外卖状态 外卖ID#<状态>\n提示：外卖状态可为：未送达/xx号门xxx取件码/已送达之类，无格式限制。\n如何查询单个外卖的详细信息？发送查询外卖 <ID>即可。\n如何删除自己发的外卖信息？\n发送删除外卖<ID>即可。"


@update_meal_status.handle()
async def _(event: GroupMessageEvent, args: Message = CommandArg(), state: T_State = State()):
    sub_commands = str(args)
    sub_commands = sub_commands.replace("＃", "#")
    sub_commands = sub_commands.split("#")
    if len(sub_commands) != 2:
        await update_meal_status.finish("格式错误，请重新按照如下格式发送信息：更新外卖状态 外卖ID#状态")
    meal_id = sub_commands[0].upper()
    meal_status = sub_commands[1]
    queried_meal = db.get(Query().id == meal_id)
    if queried_meal:
        if queried_meal["giver"] != event.get_user_id():
            if queried_meal["giver"] != global_config.superusers[0]:
                await update_meal_status.finish("您配吗？")
        result = db.update({"status": meal_status}, Query().id == meal_id)

        await update_meal_status.finish(f"外卖{meal_id}状态已更新为：{meal_status}")
    else:
        await update_meal_status.finish(f"外卖{meal_id}不存在！")


@query_meal.handle()
async def _(event: GroupMessageEvent, args: Message = CommandArg(), state: T_State = State()):
    bot_id = event.self_id
    bot = get_bot(str(bot_id))
    sub_commands = str(args).split("#")
    meal = await get_detailed_meal(id=sub_commands[0].upper())
    if len(sub_commands) == 2 and sub_commands[0] == "":
        sub_commands.pop(0)
    if len(sub_commands) != 1:
        await query_meal.finish("格式错误，请重新按照如下格式发送信息：查询外卖<ID>")
    if not meal:
        await query_meal.finish(f"外卖{sub_commands[0]}不存在！")
    giver_info = await bot.get_group_member_info(group_id="367501912", user_id=meal["giver"])
    giver_card = giver_info["card"] or giver_info["nickname"] or giver_info["user_id"]
    giver_card = str(giver_card)
    msg = f"ID: {meal['id']}\n热心群友：{giver_card}({meal['giver']})\n内容: {meal['meal_content']}\n商家: {meal['shop']}\n平台：{meal['platform']}\n预计送达时间: {datetime.fromtimestamp(meal['est_arrival_time']).strftime('%Y-%m-%d %H:%M')}\n状态: {meal['status']}"
    img = Txt2Img(font_size)
    pic = img.save("信息：", msg)
    await ellyesmeal.finish(MessageSegment.image(pic))


@delete_meal.handle()
async def _(event: GroupMessageEvent, args: Message = CommandArg(), state: T_State = State()):
    sub_commands = str(args)
    sub_commands = sub_commands.replace("＃", "#")
    sub_commands = sub_commands.split("#")
    if len(sub_commands) == 2 and sub_commands[0] == "":
        sub_commands.pop(0)
    if len(sub_commands) != 1:
        await delete_meal.finish("格式错误，请重新按照如下格式发送信息：删除外卖<ID>")
    meal_id = sub_commands[0].upper()
    sender = event.get_user_id()
    Mealdb = Query()
    result = db.remove((Mealdb.id == meal_id) & (Mealdb.giver == sender))
    print(result)
    if result[0] > 0:
        await delete_meal.finish(f"外卖{meal_id}已删除")
    else:
        await delete_meal.finish(f"外卖{meal_id}不存在，或者你要删除的外卖不是你点的哦")


@force_delete_meal.handle()
async def _(event: GroupMessageEvent, args: Message = CommandArg(), state: T_State = State()):
    ids = str(args).split(" ")
    for id in ids:
        db.remove(Query().id == id.upper())
    await force_delete_meal.finish("已删除指定的外卖信息")

@confirm_record.handle()
async def _(event: GroupMessageEvent, msg: Message = EventMessage(), state: T_State = State()):
    for seg in event.get_message():
        print(seg)