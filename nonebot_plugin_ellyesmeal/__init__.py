from typing import Tuple
from nonebot.adapters.onebot.v11 import Message, GroupMessageEvent, Bot, Event, MessageSegment
from nonebot.adapters.onebot.exception import ActionFailed
from nonebot.typing import T_State
from nonebot.params import State, CommandArg, Command
from nonebot.permission import SUPERUSER, Permission
from nonebot import get_bot, get_driver
from nonebot import on_command, on_notice
from nonebot.rule import to_me, Rule
from nonebot.log import logger

from nonebot import require
require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler



from .data_source import check_id_exist, db_clean_fake_meals, del_exact_meal, get_decent_meals, get_exact_meal, get_gm_info as db_get_gminfo, insert_meal, set_gm_info as db_set_gminfo, update_autoep_status, update_exact_meal
from .data_source import set_goodeps as db_set_goodeps, get_goodep as db_get_goodep
from .auth_ep import receive_greyed_users, check_auto_good_ep, clean_greyed_user, check_real_bad_ep
from .auth_ep import blacklist
from .utils import to_img_msg, process_long_text, zh_pat

import re
import uuid

from datetime import datetime, timedelta
import time
from calendar import monthrange

global_config = get_driver().config

id_pat = re.compile(r"^[A-Za-z0-9]*$")

async def ELLYE(bot: Bot, event: Event) -> bool:
    return event.get_user_id() == "491673070"

SU_OR_ELLYE = Permission(ELLYE) | SUPERUSER

async def cc_notice_checker(event: Event) -> bool:
    return event.get_event_name() == "notice.group_card"

async def ellye_group_checker(event: GroupMessageEvent) -> bool:
    return str(event.group_id) == "367501912"

cc_rule = Rule(cc_notice_checker, ellye_group_checker)

ellyesmeal = on_command("怡宝今天吃", aliases={"怡宝今天喝", "怡宝明天吃", "怡宝明天喝", "怡宝昨天吃", "怡宝昨天喝"})
ellyesmeal_in_2days = on_command("怡宝这两天吃什么", aliases={"怡宝这两天喝什么", "怡宝这两天吃了什么", "怡宝这两天喝了什么"})
ellyesmeal_in_3days = on_command("怡宝这三天吃什么", aliases={"怡宝这三天喝什么", "怡宝这三天吃了什么", "怡宝这三天喝了什么"})
update_meal_status = on_command("更新外卖状态", aliases={"更新订单状态", "修改外卖状态", "修改订单状态", "标记外卖", "标记订单"})
delete_meal = on_command("删除外卖", aliases={"删除订单", "移除外卖", "移除订单"})
force_delete_meal = on_command("强制删除外卖", permission=SU_OR_ELLYE)
meal_howto = on_command("投食指南", aliases={"投喂指南"})
sp_whois = on_command("谁是工贼", aliases={"谁是懒狗"})
meal_help = on_command("帮助", rule=to_me())
mark_good_ep = on_command("标记优质怡批", permission=SU_OR_ELLYE)
force_gc_meal = on_command("外卖gc", permission=SU_OR_ELLYE)
card_changed = on_notice(rule=cc_rule)


async def get_goodep_status(id):
    result = await db_get_goodep(id)
    return result

async def get_card_with_cache(id):
    bot = get_bot()
    id = str(id)
    card = await db_get_gminfo(id)
    if card is None:
        try:
            giver_info = await bot.get_group_member_info(group_id="367501912", user_id=id)
            card = giver_info["card"] or giver_info["nickname"] or giver_info["user_id"]
            await db_set_gminfo(id, card)
            logger.info(f"{id}'s card is {card}, cached it")
        except ActionFailed:
            card = id
    else:
        logger.debug(f"read user card from cache succeed: {card}")
    return card


@ellyesmeal.handle()
async def _(bot: Bot, event: GroupMessageEvent, command: Tuple[str, ...] = Command(), args: Message = CommandArg(), state: T_State = State()):
    await check_real_bad_ep(matcher=ellyesmeal, bot=bot, event=event)
    command = command[0]
    day = command[2:4]
    alters = list()
    for ms in args:
        if ms.type == "at":
            alters.append(str(ms.data["qq"]))
            args.remove(ms)
    if len(alters) == 1 and (alters[0] == "all" or alters[0] == str(event.user_id)):
        alters = list()
    state["alters"] = alters
    sub_commands = str(args).split(" ")
    for sub in sub_commands:
        if sub == "":
            sub_commands.remove(sub)
    if len(sub_commands) == 1 and ("什么" in sub_commands[0] or "啥" in sub_commands[0]):
        start_1 = time.time()
        meals = await get_ellyes_meal(event.self_id, day)
        msg = await to_img_msg(meals, f"怡宝{day}的菜单")
        start_2 = time.time()
        await ellyesmeal.send(msg)
        end = time.time()
        logger.debug(f"generate msg cost: {start_2 - start_1}")
        logger.debug(f"send msg cost: {end - start_2}")
        await ellyesmeal.finish()
    elif len(sub_commands) == 2 and ("什么" in sub_commands[0] or "啥" in sub_commands[0]) and sub_commands[1] == "-a":
        if await SU_OR_ELLYE(bot=bot, event=event):
            meals = await get_ellyes_meal(event.self_id, day, show_all=True)
            await ellyesmeal.finish(await to_img_msg(meals, f"怡宝{day}的菜单"))
        else:
            meals = await get_ellyes_meal(event.self_id, day)
            await ellyesmeal.finish(await to_img_msg(meals, f"怡宝{day}的菜单"))
    elif len(sub_commands) == 2 and ("什么" in sub_commands[0] or "啥" in sub_commands[0]) and sub_commands[1] == "-aa":
        if await SU_OR_ELLYE(bot=bot, event=event):
            meals = await get_ellyes_meal(event.self_id, day, show_all=True, include_deleted=True)
            await ellyesmeal.finish(await to_img_msg(meals, f"怡宝{day}的菜单"))
        else:
            meals = await get_ellyes_meal(event.self_id, day)
            await ellyesmeal.finish(await to_img_msg(meals, f"怡宝{day}的菜单"))
    elif len(sub_commands) == 1 and sub_commands[0] == "什么帮助":
        help = await get_ellyesmeal_help()
        await ellyesmeal.finish(await to_img_msg(help, "帮助"))
    elif len(sub_commands) > 1 and sub_commands[1] == "帮助":
        help = await get_ellyesmeal_help()
        await ellyesmeal.finish(await to_img_msg(help, "帮助"))
    else:
        ges = await get_goodep_status(event.user_id)
        state["is_auto_good_ep"] = False
        if not ges:
            nickname = await get_card_with_cache(event.user_id)
            ages = await check_auto_good_ep(event.user_id, nickname)
            if ages == 0:
                logger.info("auto good ep marked")
                state["is_hidden"] = False
                state["is_auto_good_ep"] = True
            else:
                logger.info(
                    f"{event.user_id} is not marked as good ep, marked as hidden.")
                state["is_hidden"] = True
        else:
            state["is_hidden"] = False
        if day == "昨天":
                await ellyesmeal.finish(await to_img_msg("别在这里捣乱！", "丁真的"))
        state["day"] = day
        state["meal_string_data"] = sub_commands

@ellyesmeal_in_2days.handle()
async def _(bot: Bot, event: GroupMessageEvent, command: Tuple[str, ...] = Command(), args: Message = CommandArg(), state: T_State = State()):
    await check_real_bad_ep(matcher=ellyesmeal_in_2days, bot=bot, event=event)
    start_1 = time.time()
    meals = await get_ellyes_meal(event.self_id, day="这两天")
    msg = await to_img_msg(meals, f"怡宝这两天的菜单")
    start_2 = time.time()
    await ellyesmeal.send(msg)
    end = time.time()
    logger.debug(f"generate msg cost: {start_2 - start_1}")
    logger.debug(f"send msg cost: {end - start_2}")
    await ellyesmeal.finish()

@ellyesmeal_in_3days.handle()
async def _(bot: Bot, event: GroupMessageEvent, command: Tuple[str, ...] = Command(), args: Message = CommandArg(), state: T_State = State()):
    await check_real_bad_ep(matcher=ellyesmeal_in_3days, bot=bot, event=event)
    start_1 = time.time()
    meals = await get_ellyes_meal(event.self_id, day="这三天")
    msg = await to_img_msg(meals, f"怡宝这三天的菜单")
    start_2 = time.time()
    await ellyesmeal.send(msg)
    end = time.time()
    logger.debug(f"generate msg cost: {start_2 - start_1}")
    logger.debug(f"send msg cost: {end - start_2}")
    await ellyesmeal.finish()


@ellyesmeal.got("meal_string_data")
async def _(bot: Bot, event: GroupMessageEvent, state: T_State = State()):
    meal_string_data: list[str] = state["meal_string_data"]

    day = state["day"]
    meal_string = "".join(meal_string_data)

    if any(word in meal_string for word in blacklist):
        await receive_greyed_users([event.user_id])
        await ellyesmeal.finish(await to_img_msg("怡宴丁真，鉴定为假", "整蛊的"))

    meal_string = meal_string.strip()
    if meal_string == "":
        await ellyesmeal.finish()
    if meal_string.endswith(("?", "？")):
        await ellyesmeal.finish()
    if not zh_pat.search(meal_string):
        await receive_greyed_users([event.user_id])
        await ellyesmeal.finish(await to_img_msg("怡宴丁真，鉴定为假", "卑鄙的"))
    if meal_string == "我":
        await receive_greyed_users([event.user_id])
        await ellyesmeal.finish(await to_img_msg("怡宴丁真，鉴定为做梦", "虚无缥缈的"))
    if len(meal_string) > 30:
        await receive_greyed_users([event.user_id])
        await ellyesmeal.finish(await to_img_msg("怡宴丁真，鉴定为假", "虚伪的"))
    if meal_string.startswith("什么-"):
        if not await SU_OR_ELLYE(bot=bot, event=event):
            await receive_greyed_users([event.user_id])
            await ellyesmeal.finish(await to_img_msg("别在这里捣乱！", "丁真的"))
        else:
            await ellyesmeal.finish(await to_img_msg("参数错误，目前可用的参数为：-a、-aa"))

    est_arrival_time = meal_string_data[-1]
    est_arrival_time = re.sub(r'[^\w]', '', est_arrival_time)
    est_arrival_time = est_arrival_time.replace("：", ":").replace(":", "")
    is_tomorrow = True if day == "明天" else False
    is_time_recorded = True

    if est_arrival_time.endswith(("送达", "送到")):
        est_arrival_time = est_arrival_time[:-2]
    if est_arrival_time.endswith("到"):
        est_arrival_time = est_arrival_time[:-1]

    # 判断时间是否为 HHMM 格式
    if est_arrival_time.isdigit():
        est_arrival_time = int(est_arrival_time)
        if est_arrival_time < 100 or est_arrival_time > 2400:
            is_time_recorded = False
        else:
            minute = int(est_arrival_time % 100)
            hour = int(est_arrival_time / 100)
            if minute > 59 or hour > 23:
                is_time_recorded = False
            else:
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
        await ellyesmeal.finish(await to_img_msg("怡宴丁真，鉴定为假", "错误的"))

    if is_time_recorded:
        meal_string_data = meal_string_data[:-1]
    meal_string = "+".join(meal_string_data).strip()

    meal_string = await process_long_text(meal_string)

    while True:
        unique_id = str(uuid.uuid4())[:4]
        result = await check_id_exist(unique_id)
        if not result:
            break
    
    data = {
        "id": unique_id.upper(),
        "giver": event.get_user_id(),
        "meal_content": meal_string,
        "order_time": datetime.timestamp(datetime.now()),
        "est_arrival_time": est_arrival_time.timestamp(),
        "status": "已下单" if not state["is_hidden"] else "已隐藏",
        "is_auto_good_ep": state["is_auto_good_ep"],
        "alters": state["alters"]
    }
    await insert_meal(data)
    if state["is_hidden"]:
        await ellyesmeal.finish(await to_img_msg(f"投喂成功，但由于您暂未通过优质怡批认证，暂时隐藏。\nID: {unique_id.upper()}"))
    elif state["is_auto_good_ep"]:
        await ellyesmeal.finish(await to_img_msg(f"投喂成功，由于您的群名片符合规范，自动认证为优质怡批。\nID: {unique_id.upper()}"))
    else:
        await ellyesmeal.finish(await to_img_msg(f"投喂成功！  ID: {unique_id.upper()}"))


async def get_ellyes_meal(id, day, show_all=False, include_deleted=False):
    year = datetime.now().year
    month = datetime.now().month
    today = datetime.now().day
    if today == 1:
        month = month - 1
        if month == 0:
            month = 12
            year = year - 1
        today = monthrange(year, month)[1] + 1

    meals = await get_decent_meals()
    meals = list(meals)
    
    if not include_deleted:
        meals = [meal for meal in meals if meal["status"] != "已删除"]

    msg_parts = list()
    is_tmr_has_meal = False
    for meal in meals:
        
        mp = str()
        if meal["status"] == "已隐藏" and not show_all:
            continue
        
        tonight_late_time = datetime.timestamp(datetime(year=year, month=month, day=today, hour=23, minute=59))
        tonight_early_time = datetime.timestamp(datetime(year=year, month=month, day=today, hour=0, minute=0))
        match day:
            case "这三天":
                pass
            case "这两天":
                # 明天才到的不要
                if meal['est_arrival_time'] > tonight_late_time:
                    continue
            case "今天":
                # 明天才到的不要
                if meal['est_arrival_time'] > tonight_late_time:
                    is_tmr_has_meal = True
                    continue
                # 昨天到的也不要，但是在吃的除外
                if meal['est_arrival_time'] < tonight_early_time and meal['status'] != "在吃":
                    continue
            case "明天":
                # 今晚之前到的不要
                if meal['est_arrival_time'] < tonight_late_time:
                    continue
            case "昨天":
                # 今天0:00之后到的不要
                if meal['est_arrival_time'] > tonight_early_time:
                    continue
    
        giver_card = await get_card_with_cache(meal["giver"])
        giver_full_info = f"{giver_card}({meal['giver']})"
        giver_full_info = await process_long_text(giver_full_info)

        if "alters" in meal:
            alters = meal["alters"]
            alter_str_parts = list()
            if len(alters) > 0:
                for alt in alters:
                    alt_nn = await get_card_with_cache(alt)
                    alter_str_parts.append(f"{alt_nn}({alt})")
                alter_str = "\n              ".join(alter_str_parts)
            else:
                alter_str = None
        else:
            alter_str = None

        if not alter_str:
            mp += f"ID: {meal['id']}      状态: {meal['status']}\n热心群友：    {giver_full_info}\n内容:         {meal['meal_content']}\n预计送达时间: {datetime.fromtimestamp(meal['est_arrival_time']).strftime('%Y-%m-%d %H:%M')}"
        else:
            mp += f"ID: {meal['id']}      状态: {meal['status']}\n热心群友：    {alter_str}\n记录者：      {giver_full_info}\n内容:         {meal['meal_content']}\n预计送达时间: {datetime.fromtimestamp(meal['est_arrival_time']).strftime('%Y-%m-%d %H:%M')}"    
        if meal["is_auto_good_ep"]:
            left_time = datetime.fromtimestamp(meal['order_time']) + timedelta(hours=3) - datetime.now()
            if left_time < timedelta(seconds=0):
                await clean_fake_meals()    
            else:
                mp += f"\n【若未被正式认可，该外卖将在{str(left_time)[:-7]}后自动删除。】"
        elif meal["status"] == "已隐藏":
            left_time = datetime.fromtimestamp(meal['order_time']) + timedelta(hours=2) - datetime.now()
            if left_time < timedelta(seconds=0):
                await clean_fake_meals()    
            else:
                mp += f"\n【若未被正式认可，该外卖将在{str(left_time)[:-7]}后自动删除。】"
        if mp:
            msg_parts.append(mp)
    if len(msg_parts) == 0:
        msg = f"怡宝{day}还没有吃的！"
        if is_tmr_has_meal:
            msg += "\n\n                        *但是明天有吃的"
    else:
        msg = "\n---------------------------------------------------------".join(msg_parts)
    return msg


async def get_ellyesmeal_help():
    return '''
①.查询怡宝收到的外卖:
发送: 怡宝[昨/今/明]天[吃/喝]什么
②.使用本插件记录给怡宝点的外卖:
按如下格式发送命令: 
   怡宝[今/明]天[吃/喝] <外卖内容>【空格】<预计送达时间>
                                          【hh:mm】格式
提示：
   如果你想帮别人记录，则在保持原有命令的基础上@该群友。
③.更新外卖状态:
发送: 更新外卖状态 外卖ID <状态>
提示: 怡批可修改的外卖状态为：配送中/已送达/在吃
      怡宝可额外修改的外卖状态为：吃完了/扔了/退了
④.查询单个外卖的详细信息:
发送: 查询外卖 <ID>
⑤.删除自己发的外卖信息:
发送: 删除外卖 <ID>
'''


@update_meal_status.handle()
async def _(bot:Bot, event: GroupMessageEvent, args: Message = CommandArg(), state: T_State = State()):
    await check_real_bad_ep(matcher=update_meal_status, bot=bot, event=event)
    sub_commands = str(args)
    sub_commands = sub_commands.split(" ")
    if len(sub_commands) < 2:
        await update_meal_status.finish(await to_img_msg("格式错误，请重新按照如下格式发送信息：更新外卖状态 外卖ID 状态"))
    meal_ids = list()
    for sub in sub_commands:
        if len(sub) == 4 and re.search(id_pat, sub):
            meal_ids.append(sub.upper())
    meal_status = sub_commands[-1]

    privilledged_users = [list(global_config.superusers)[0], "491673070"]
    is_priviledged = True if event.get_user_id() in privilledged_users else False

    if (meal_status not in ["配送中", "已送达", "在吃"]) and (not is_priviledged):
        await update_meal_status.finish(await to_img_msg("怡批只能在如下状态中选择：配送中/已送达/在吃", "权限不足"))

    if (meal_status not in ["配送中", "已送达", "在吃", "吃完了", "扔了", "退了"]) and is_priviledged:
        await update_meal_status.finish(await to_img_msg("您只能在如下状态中选择：配送中/已送达/在吃/吃完了/扔了/退了", "状态错误"))

    msg = ""
    for meal_id in meal_ids:
        msg += f"外卖{meal_id}: "
        queried_meal = await get_exact_meal(meal_id)
        if queried_meal:
            if queried_meal["giver"] != event.get_user_id() and not is_priviledged:
                msg += "权限不足，无法更新状态\n"
            elif queried_meal["status"] == "已隐藏":
                msg += "该外卖已被隐藏，无法更新状态\n"
            elif (queried_meal["status"] in ["吃完了", "扔了", "退了"]) and not is_priviledged:
                msg += "该外卖生命周期已结束，无法修改状态\n"
            else:
                result = await update_exact_meal(meal_id, "status", meal_status)
                msg += f"状态已更新为：{meal_status}\n"
        else:
            msg += "外卖不存在\n"
    await update_meal_status.finish(await to_img_msg(msg))


@delete_meal.handle()
async def _(bot:Bot, event: GroupMessageEvent, args: Message = CommandArg(), state: T_State = State()):
    await check_real_bad_ep(matcher=delete_meal, bot=bot, event=event)
    sub_commands = str(args).split(" ")
    msg = ""
    for meal_id in sub_commands:
        if len(meal_id) != 4 or not re.search(id_pat, meal_id):
            await delete_meal.finish(await to_img_msg("格式错误，请重新按照如下格式发送信息：删除外卖 <ID>【四位字母/数字】"))
        meal_id = meal_id.upper()
        msg += f"外卖{meal_id}: "
        sender = event.get_user_id()

        result = await del_exact_meal(meal_id, "giver", sender)

        if result.deleted_count:
            msg += "已删除\n"
        else:
            msg += f"外卖不存在，或者你要删除的外卖不是你点的哦\n"

    await delete_meal.finish(await to_img_msg(msg))

@force_delete_meal.handle()
async def _(event: GroupMessageEvent, args: Message = CommandArg(), state: T_State = State()):
    ids = str(args).split(" ")
    for id in ids:
        await del_exact_meal(id.upper())
    await force_delete_meal.finish(await to_img_msg("已删除指定的外卖信息"))


@meal_howto.handle()
async def _(bot:Bot, event: GroupMessageEvent):
    await check_real_bad_ep(matcher=meal_howto, bot=bot, event=event)
    # if not event.group_id == 367501912:
    #     await meal_howto.finish()
    howto = '''
0.只有经过认证的优质怡批才可以使用本插件记录。
认证方式：给怡宝点一份外卖，并发送订单截图至群内，经怡宝认可后便可获得优质怡批认证。
或者效仿群内怡批更改群名片，符合某种神秘命名规则的将被自动视为优质怡批。
-----
1.你需要填写怡宝的收货信息：
收件人：陈泓仰 【女士】
手机：19121671082
[公寓地址]
   广东省深圳市南山区泊寓深圳（科技园店）
即【广东省深圳市南山区北环大道10092号】
[公司地址]
   广东省深圳市创益科技大厦美团外卖柜 
-----
2.你应该给怡宝投喂什么：
为了避免怡宝天天吃剩饭的现象发生，提高群内怡批的参与度，你应当购买小份的主食（如肠粉）/饮品（半糖少冰）/甜食（要耐放）/水果（不要瓜类）等，价格保持在20-30元左右以提升怡宝的好感度。
-----
3.你应该在什么时间投喂：
工作日早10点至下午3点，地址为公司地址；
工作日晚9点至早8点，地址为公寓地址；
休息日全天均为公寓地址。
-----
4.你应该如何记录给怡宝点的外卖：'''
    help = await get_ellyesmeal_help()
    howto += help
    await meal_howto.finish(await to_img_msg(howto, "投喂指南"))

@meal_help.handle()
async def _(bot:Bot, event: GroupMessageEvent):
    if not event.group_id == 367501912:
        await meal_help.finish()
    await check_real_bad_ep(matcher=meal_help, bot=bot, event=event)
    help = await get_ellyesmeal_help()
    await meal_help.finish(await to_img_msg(help, "投喂指南"))

@sp_whois.handle()
async def _(bot:Bot, event: GroupMessageEvent):
    if event.group_id != 367501912:
        await sp_whois.finish()
    await check_real_bad_ep(matcher=sp_whois, bot=bot, event=event)
    await sp_whois.finish(MessageSegment.at(event.get_user_id()) + "\n"+MessageSegment.image(file="http://q2.qlogo.cn/headimg_dl?dst_uin=491673070&spec=100&t=1657289812436")+"\n怡宝")


@mark_good_ep.handle()
async def _(event: GroupMessageEvent, args: Message = CommandArg(), state: T_State = State()):
    is_have_result = False
    for ms in event.get_message():
        if ms.type == "at":
            is_have_result = True
            good_ep = ms.data["qq"]
            good_ep = str(good_ep)
            await update_autoep_status(good_ep, False)
            await db_set_goodeps(good_ep, datetime.now())
            await clean_greyed_user(good_ep)

    if is_have_result:
        await mark_good_ep.finish("ok")
    else:
        await mark_good_ep.finish("failed")

@card_changed.handle()
async def _(event: Event):
    await db_set_gminfo(event.user_id, event.card_new)
    logger.info(f"user {event.user_id} changed card to {event.card_new}")

@force_gc_meal.handle()
async def _():
    await db_clean_fake_meals(force=True)
    await force_gc_meal.finish("ok")

@scheduler.scheduled_job("interval", minutes=5)
async def clean_fake_meals():
    await db_clean_fake_meals()

