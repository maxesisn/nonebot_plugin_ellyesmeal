from nonebot_plugin_txt2img import Txt2Img
from nonebot.adapters.onebot.v11 import MessageSegment

font_size = 32

def to_img_msg(content, title="信息"):
    img = Txt2Img(font_size)
    pic = img.save(title, content)
    return MessageSegment.image(pic)