"""
字段校验工具：身份证、手机号、邮箱
"""
import re
from datetime import datetime


def validate_id_card(id_card: str) -> tuple[bool, str]:
    """
    身份证号校验（宽松模式）
    - 18位，前17位数字，最后一位数字或x/X
    - 第7-14位为日期，校验日期合理性
    """
    if not id_card:
        return False, "身份证号不能为空"
    if len(id_card) != 18:
        return False, "身份证号必须为18位"
    if not id_card[:17].isdigit():
        return False, "身份证号前17位必须为数字"
    if not (id_card[-1].isdigit() or id_card[-1].lower() == "x"):
        return False, "身份证号最后一位必须为数字或X"
    # 校验日期
    try:
        year = int(id_card[6:10])
        month = int(id_card[10:12])
        day = int(id_card[12:14])
        birth_date = datetime(year, month, day)
        if birth_date > datetime.now():
            return False, "出生日期不能晚于今天"
        if birth_date < datetime(1900, 1, 1):
            return False, "出生日期不能早于1900年"
    except (ValueError, TypeError):
        return False, "身份证号中的日期无效"
    return True, ""


def validate_phone(phone: str) -> tuple[bool, str]:
    """
    手机号校验
    支持格式：13800138000, +86-13800138000, +8613800138000
    返回 (是否合法, 错误信息)
    """
    if not phone:
        return False, "手机号不能为空"
    pattern = r"^(\+86[- ]?)?1[3-9]\d{9}$"
    if not re.match(pattern, phone):
        return False, "手机号格式不正确"
    return True, ""


def normalize_phone(phone: str) -> str:
    """统一手机号格式：去除+86前缀和空格，返回纯11位数字"""
    if not phone:
        return phone
    phone = phone.strip()
    # 去除 +86 前缀
    if phone.startswith("+86"):
        phone = phone[3:]
    # 去除可能的分隔符
    phone = phone.replace("-", "").replace(" ", "")
    return phone


def validate_email(email: str) -> tuple[bool, str]:
    """邮箱格式校验（简单正则）"""
    if not email:
        return False, "邮箱不能为空"
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email):
        return False, "邮箱格式不正确"
    return True, ""


def validate_password(password: str) -> tuple[bool, str]:
    """
    密码强度校验
    - 至少8位
    - 必须包含数字和字母
    """
    if not password:
        return False, "密码不能为空"
    if len(password) < 8:
        return False, "密码长度至少为8位"
    if not re.search(r"\d", password):
        return False, "密码必须包含数字"
    if not re.search(r"[a-zA-Z]", password):
        return False, "密码必须包含字母"
    return True, ""
