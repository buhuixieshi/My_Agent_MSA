"""
从原 core/Agent/syntax_parser.py 拆出并适配。

保留解析协议：
- 对话:target|content
- 工具调用:tool|arg1|arg2
- 询问:xxx
- 切换:xxx
- 切换到xxx智能体
- 定时任务:类型|时间|内容
"""

from datetime import datetime
import re


_COMMAND_NAMES = ("对话", "工具调用", "询问", "切换", "定时任务")
_COMMAND_LINE_RE = re.compile(
    r"^\s*(?:[-*•]\s*)?(?:" + "|".join(map(re.escape, _COMMAND_NAMES)) + r")\s*:"
)


def clean_ai_thinking(text: str) -> str:
    """彻底清洗 AI 思考内容，防止语法解析误触发"""
    if not text or not isinstance(text, str):
        return ""
    if "</think>" in text:
        text = text.split("</think>")[-1]
    return text.strip()


def _normalize_text(text: str) -> str:
    return (text or "").replace("：", ":").strip()


def _is_command_line(line: str) -> bool:
    return bool(_COMMAND_LINE_RE.match(line or ""))


def _find_command_block(full_text: str, command_name: str, allow_multiline: bool = False) -> str | None:
    """
    只识别“行首指令”。

    旧逻辑使用 re.search("询问:(.*)", full_text, re.DOTALL)，会把普通正文里的
    “我想询问: ...” 也误判为协议指令。这里要求指令必须独占一行的开头，
    允许前面有列表符号，避免模型正常解释文本误触发语法分支。
    """
    pattern = re.compile(rf"^\s*(?:[-*•]\s*)?{re.escape(command_name)}\s*:\s*(.*)$")
    lines = full_text.splitlines() or [full_text]

    for index, line in enumerate(lines):
        match = pattern.match(line)
        if not match:
            continue

        value_lines = [match.group(1).strip()]
        if allow_multiline:
            for extra_line in lines[index + 1:]:
                if _is_command_line(extra_line):
                    break
                value_lines.append(extra_line.rstrip())

        value = "\n".join(value_lines).strip()
        return value or None

    return None


def to_timestamp(time_str: str) -> float:
    dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
    return dt.timestamp()


def parse_syntax(agent, task):
    raw_text = task.consume_temp_dialog_output()
    raw_text = clean_ai_thinking(raw_text)
    full_text = _normalize_text(raw_text)

    reply = full_text
    agent_call = None
    tool_call = None
    question = None
    timer_task = None

    agent_line = _find_command_block(full_text, "对话", allow_multiline=True)
    if agent_line and "|" in agent_line:
        target_id, content = agent_line.split("|", 1)
        target_id = target_id.strip()
        content = content.strip()
        if target_id and content:
            agent_call = {
                "target_id": target_id,
                "content": content,
            }

    tool_line = _find_command_block(full_text, "工具调用", allow_multiline=False)
    if tool_line:
        memory = task.consume_temp_dialog_input() or "本条记录因不知名原因丢失"
        memory += "\n调用了工具:" + tool_line
        task.tool_log.append("调用了工具:" + tool_line)
        task.push_context(agent, memory)

        parts = tool_line.split("|")
        tool_name = parts[0].strip()
        args = [p.strip() for p in parts[1:] if p.strip()]
        if tool_name:
            tool_call = {
                "tool": tool_name,
                "args": args,
            }

    question_line = _find_command_block(full_text, "询问", allow_multiline=True)
    if question_line:
        question = question_line.strip()
        if not agent_call and not tool_call:
            reply = question

    switch_line = _find_command_block(full_text, "切换", allow_multiline=False)
    if switch_line:
        agent_id = switch_line.strip()
        if agent_id:
            agent.set_default_agent(agent_id)

    for line in full_text.splitlines():
        match_switch2 = re.match(r"^\s*(?:[-*•]\s*)?切换到(\w+)智能体\s*$", line)
        if match_switch2:
            agent_id = match_switch2.group(1).strip()
            if agent_id:
                agent.set_default_agent(agent_id)
            break

    timer_line = _find_command_block(full_text, "定时任务", allow_multiline=False)
    if timer_line:
        match_timer = re.match(r"([^|]+)\|([^|]+)(?:\|(.+))?", timer_line)
        if match_timer:
            task_type = match_timer.group(1).strip()
            content = match_timer.group(2).strip()
            time_str = match_timer.group(3).strip() if match_timer.group(3) else "2026-01-31 00:00:00"
            try:
                trigger_ts = to_timestamp(time_str)
                timer_task = {
                    "task_type": task_type,
                    "time_str": time_str,
                    "trigger_timestamp": trigger_ts,
                    "content": content,
                }
            except Exception:
                pass

    task.set_temp_dialog_output({
        "final_reply": reply,
        "reply": full_text,
        "tool_call": tool_call,
        "agent_call": agent_call,
        "question": question,
        "timer_task": timer_task,
    })
