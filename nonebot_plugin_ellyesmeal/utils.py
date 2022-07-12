import re
import pytz

from nonebot_plugin_txt2img import Txt2Img
from nonebot.adapters.onebot.v11 import MessageSegment

font_size = 32
shanghai_tz = pytz.timezone('Asia/Shanghai')
zh_pat = re.compile(r"[\u4e00-\u9fa5]")

async def to_img_msg(content, title="信息"):
    img = Txt2Img(font_size)
    pic = img.save(title, content)
    return MessageSegment.image(pic)


async def process_long_text(text):
    text_length = len(text)
    text_utf8_length = len(text.encode("utf-8"))
    text_visual_length = int((text_utf8_length - text_length) / 2 + text_length)
    if text_visual_length > 43:
        text_chunks = str()
        length_counter = 0
        for char in text:
            text_chunks += char
            length_counter += 2 if re.search(zh_pat, char) else 1
            if length_counter >= 42:
                text_chunks+="\n              " # 14 spaces
                length_counter = 0
        text = text_chunks
    return text
