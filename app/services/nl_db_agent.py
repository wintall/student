"""
自然语言数据库操作 Agent 核心模块
负责解析用户意图、提取参数、管理上下文记忆
"""
import json
import re
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage, HumanMessage

from app.models.user import User
from app.config import settings
from app.redis import redis_get, redis_set


MEMORY_MAX_LENGTH = 10
MEMORY_TTL = 3600

MEMORY_STORE = {}


def get_llm():
    """获取LLM模型实例"""
    api_key = settings.DEEPSEEK_API_KEY_V4 or settings.DEEPSEEK_API_KEY
    model = settings.DEEPSEEK_MODEL_V4 or settings.DEEPSEEK_MODEL
    api_base = settings.DEEPSEEK_API_URL_V4 if settings.DEEPSEEK_API_KEY_V4 else settings.DEEPSEEK_API_URL
    
    if not api_key:
        raise ValueError("DeepSeek API key 未配置")
    
    return ChatOpenAI(
        api_key=api_key,
        model=model,
        base_url=api_base,
        temperature=0.3,
        max_tokens=2000,
        timeout=60,
    )


def get_conversation_history(user_id: int) -> List[Dict[str, str]]:
    """获取用户的对话历史"""
    try:
        raw = redis_get(f"nl_db_chat:{user_id}")
        if raw:
            history = json.loads(raw)
            if len(history) > MEMORY_MAX_LENGTH:
                history = history[-MEMORY_MAX_LENGTH:]
            return history
    except Exception:
        pass
    
    if user_id in MEMORY_STORE:
        history = MEMORY_STORE[user_id]
        if len(history) > MEMORY_MAX_LENGTH:
            history = history[-MEMORY_MAX_LENGTH:]
        return history
    
    return []


def save_conversation_history(user_id: int, history: List[Dict[str, str]]):
    """保存用户的对话历史"""
    if len(history) > MEMORY_MAX_LENGTH:
        history = history[-MEMORY_MAX_LENGTH:]
    
    try:
        redis_set(f"nl_db_chat:{user_id}", json.dumps(history))
    except Exception:
        MEMORY_STORE[user_id] = history


def clear_conversation(user_id: int):
    """清除用户的对话历史"""
    try:
        redis_set(f"nl_db_chat:{user_id}", json.dumps([]))
    except Exception:
        pass
    if user_id in MEMORY_STORE:
        del MEMORY_STORE[user_id]


def extract_intent_and_params(message: str, history: List[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    解析用户意图和参数
    返回: {"intent": "create_student|query_student|update_student|delete_student|unknown", "params": {...}}
    """
    intent_keywords = {
        "create_student": ["新增学生", "添加学生", "创建学生", "插入学生", "增加学生"],
        "query_student": ["查询学生", "查找学生", "搜索学生", "查看学生", "找学生"],
        "update_student": ["更新学生", "修改学生", "编辑学生", "更改学生"],
        "delete_student": ["删除学生", "移除学生", "删掉学生"],
        "create_teacher": ["新增教师", "添加教师", "创建教师", "插入教师"],
        "query_teacher": ["查询教师", "查找教师", "搜索教师", "查看教师"],
        "update_teacher": ["更新教师", "修改教师", "编辑教师"],
        "delete_teacher": ["删除教师", "移除教师"],
        "create_clazz": ["新增班级", "添加班级", "创建班级"],
        "query_clazz": ["查询班级", "查找班级", "搜索班级"],
        "update_clazz": ["更新班级", "修改班级"],
        "delete_clazz": ["删除班级"],
        "create_course": ["新增课程", "添加课程", "创建课程"],
        "query_course": ["查询课程", "查找课程", "搜索课程"],
        "update_course": ["更新课程", "修改课程"],
        "delete_course": ["删除课程"],
    }
    
    intent = "unknown"
    for intent_type, keywords in intent_keywords.items():
        for keyword in keywords:
            if keyword in message:
                intent = intent_type
                break
        if intent != "unknown":
            break
    
    params = {}
    
    name_match = re.search(r'(?:姓名|name)\s*[:：=号]?\s*([\u4e00-\u9fa5a-zA-Z]{2,10})', message)
    if not name_match:
        name_match = re.search(r'([\u4e00-\u9fa5]{2,4})(?=\s*，|\s*。|\s*的|\s*是|\s*学)', message)
    if name_match:
        params["姓名"] = name_match.group(1)
    
    student_no_match = re.search(r'(?:学号|student_no|studentNo)\s*[:：=号]?\s*([A-Za-z]?\d{4,12})', message)
    if not student_no_match:
        student_no_match = re.search(r'([A-Za-z]?\d{4,12})\s*(?:号|学号)', message)
    if not student_no_match:
        student_no_match = re.search(r'([A-Za-z]+\d{4,12})', message)
    if student_no_match:
        params["学号"] = student_no_match.group(1)
    
    id_card_match = re.search(r'(?:身份证|身份证号|id_card|idCard)\s*[:：=号]?\s*(\d{15,18})', message)
    if not id_card_match:
        id_card_match = re.search(r'(\d{15,18})\s*(?:身份证)', message)
    if not id_card_match:
        id_card_match = re.search(r'(\d{18})', message)
    if id_card_match:
        params["身份证号"] = id_card_match.group(1)
    
    gender_match = re.search(r'(?:性别|gender)\s*[:：=]?\s*(男|女|1|2)', message)
    if not gender_match:
        gender_match = re.search(r'(男|女)', message)
    if gender_match:
        gender_val = gender_match.group(1)
        if gender_val == "男":
            params["性别"] = "1"
        elif gender_val == "女":
            params["性别"] = "2"
        else:
            params["性别"] = gender_val
    
    clazz_id_match = re.search(r'(?:班级ID|班级id|clazz_id|clazzId|班级编号)\s*[:：=号为]?\s*(\d+)', message)
    if not clazz_id_match:
        clazz_id_match = re.search(r'(?:班级)\s*(\d+)', message)
    if clazz_id_match:
        params["班级ID"] = clazz_id_match.group(1)
    
    return {"intent": intent, "params": params}


def get_required_params(intent: str) -> List[str]:
    """获取指定操作需要的必填参数"""
    required_params = {
        "create_student": ["姓名", "学号", "身份证号", "性别", "班级ID"],
        "create_teacher": ["姓名", "工号", "身份证号", "性别", "部门ID"],
        "create_clazz": ["名称", "编号", "部门ID"],
        "create_course": ["名称", "编号", "学分", "学时"],
        "update_student": ["学号"],
        "update_teacher": ["工号"],
        "update_clazz": ["编号"],
        "update_course": ["编号"],
        "delete_student": ["学号"],
        "delete_teacher": ["工号"],
        "delete_clazz": ["编号"],
        "delete_course": ["编号"],
    }
    return required_params.get(intent, [])


def check_missing_params(intent: str, params: Dict[str, str]) -> List[str]:
    """检查缺少的必填参数"""
    required = get_required_params(intent)
    return [param for param in required if param not in params]


def build_prompt_with_history(message: str, history: List[Dict[str, str]], user: User, db: Session) -> str:
    """构建包含历史记录的提示词"""
    from app.services.nl_db_tools import get_user_permission_list, PERMISSIONS
    
    user_perms = get_user_permission_list(user, db)
    perm_descriptions = "\n".join([f"- {perm}: {PERMISSIONS[perm]}" for perm in user_perms])
    
    history_str = ""
    if history:
        history_str = "\n## 对话历史\n"
        for msg in history:
            if msg.get("role") == "user":
                history_str += f"用户: {msg.get('content', '')}\n"
            else:
                history_str += f"助手: {msg.get('content', '')}\n"
    
    prompt = f"""
你是一个学生信息管理系统的智能助手。

## 核心指令
**上下文记忆**: 你必须记住对话历史。如果上一轮中你询问了缺少的参数，用户这一轮回复了参数值，你应该将这些参数补充到之前的操作中，继续完成创建/更新操作。

## 你的能力
你可以操作以下数据表：
- student（学生表）：姓名、学号、身份证号、性别、班级ID、入学日期、状态
- teacher（教职工表）：姓名、工号、身份证号、性别、部门ID、职位、职称、入职日期、状态
- clazz（班级表）：名称、编号、部门ID、年级、辅导员ID、状态
- course（课程表）：名称、编号、学分、学时、课程类型、部门ID、教师ID、描述、状态

## 当前权限
{perm_descriptions}

## 用户请求
{history_str}
用户: {message}

## 请执行以下步骤：
1. 分析用户的意图（新增/查询/更新/删除）和目标表
2. 提取用户提供的所有参数
3. 如果参数不完整，列出缺少的必填参数并友好地询问用户补充
4. 如果参数完整，直接输出JSON格式的工具调用指令

## 输出格式
如果需要补充参数，请直接用自然语言回复用户，不需要JSON格式。

如果可以执行操作，请输出JSON格式：
{{
    "action": "工具名称",
    "params": {{参数键值对}}
}}

可用工具名称:
- create_student: 创建学生
- query_student: 查询学生
- update_student: 更新学生
- delete_student: 删除学生
- create_teacher: 创建教师
- query_teacher: 查询教师
- update_teacher: 更新教师
- delete_teacher: 删除教师
- create_clazz: 创建班级
- query_clazz: 查询班级
- update_clazz: 更新班级
- delete_clazz: 删除班级
- create_course: 创建课程
- query_course: 查询课程
- update_course: 更新课程
- delete_course: 删除课程

## 参数说明
- 性别: 1=男, 2=女
- 日期格式: YYYY-MM-DD
- 状态: 1=正常, 0=禁用
    """.strip()
    
    return prompt


def run_agent(user: User, message: str, db: Session) -> Dict[str, Any]:
    """执行Agent并返回结果"""
    try:
        history = get_conversation_history(user.id)
        
        intent_result = extract_intent_and_params(message, history)
        intent = intent_result["intent"]
        params = intent_result["params"]
        
        combined_params = params.copy()
        previous_intent = intent
        
        if intent == "unknown" and history:
            for msg in reversed(history):
                if msg.get("role") == "user":
                    prev_result = extract_intent_and_params(msg.get("content", ""))
                    if prev_result["intent"] != "unknown":
                        previous_intent = prev_result["intent"]
                        for key, value in prev_result["params"].items():
                            if key not in combined_params:
                                combined_params[key] = value
                        break
        
        intent = previous_intent
        
        if intent == "unknown":
            llm = get_llm()
            prompt = build_prompt_with_history(message, history, user, db)
            result = llm.invoke(prompt)
            reply = str(result.content)
            
            try:
                json_result = json.loads(reply.strip())
                if "action" in json_result and "params" in json_result:
                    return {
                        "success": True,
                        "reply": "",
                        "tool_calls": [{"tool": json_result["action"], "args": json_result["params"]}],
                        "tool_results": [],
                        "has_data": True,
                    }
            except:
                pass
            
            save_conversation_history(user.id, history + [{"role": "user", "content": message}, {"role": "assistant", "content": reply}])
            
            return {
                "success": True,
                "reply": reply,
                "tool_calls": [],
                "tool_results": [],
                "has_data": False,
            }
        
        missing_params = check_missing_params(intent, combined_params)
        
        if missing_params:
            reply = f"我需要以下信息来完成{intent}操作：\n\n"
            reply += "| 参数 | 状态 |\n"
            reply += "|------|------|\n"
            
            required = get_required_params(intent)
            for param in required:
                if param in combined_params:
                    reply += f"| 已填 {param} | {combined_params[param]} |\n"
                else:
                    reply += f"| **{param}** | 缺失 |\n"
            
            reply += f"\n请补充以下必填参数：{', '.join(missing_params)}"
            
            save_conversation_history(user.id, history + [{"role": "user", "content": message}, {"role": "assistant", "content": reply}])
            
            return {
                "success": True,
                "reply": reply,
                "tool_calls": [],
                "tool_results": [],
                "has_data": False,
            }
        
        tool_map = {
            "create_student": "create_student",
            "query_student": "query_student",
            "update_student": "update_student",
            "delete_student": "delete_student",
            "create_teacher": "create_teacher",
            "query_teacher": "query_teacher",
            "update_teacher": "update_teacher",
            "delete_teacher": "delete_teacher",
            "create_clazz": "create_clazz",
            "query_clazz": "query_clazz",
            "update_clazz": "update_clazz",
            "delete_clazz": "delete_clazz",
            "create_course": "create_course",
            "query_course": "query_course",
            "update_course": "update_course",
            "delete_course": "delete_course",
        }
        
        tool_name = tool_map.get(intent)
        
        if not tool_name:
            reply = f"抱歉，我无法识别您的操作意图：{message}"
            save_conversation_history(user.id, history + [{"role": "user", "content": message}, {"role": "assistant", "content": reply}])
            return {
                "success": True,
                "reply": reply,
                "tool_calls": [],
                "tool_results": [],
                "has_data": False,
            }
        
        tool_params = {}
        param_mapping = {
            "姓名": "name",
            "学号": "student_no",
            "身份证号": "id_card",
            "性别": "gender",
            "班级ID": "clazz_id",
            "入学日期": "enrollment_date",
            "状态": "status",
            "工号": "teacher_no",
            "部门ID": "department_id",
            "职位": "position",
            "职称": "title",
            "入职日期": "hire_date",
            "名称": "name",
            "编号": "code",
            "年级": "grade",
            "辅导员ID": "counselor_id",
            "学分": "credits",
            "学时": "hours",
            "课程类型": "course_type",
            "教师ID": "teacher_id",
            "描述": "description",
        }
        
        for key, value in combined_params.items():
            if key in param_mapping:
                tool_params[param_mapping[key]] = value
        
        save_conversation_history(user.id, history + [{"role": "user", "content": message}])
        
        return {
            "success": True,
            "reply": "",
            "tool_calls": [{"tool": tool_name, "args": tool_params}],
            "tool_results": [],
            "has_data": True,
        }
        
    except Exception as e:
        return {
            "success": False,
            "reply": f"处理请求时发生错误: {str(e)}",
            "tool_calls": [],
            "tool_results": [],
            "has_data": False,
        }
