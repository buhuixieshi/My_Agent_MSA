"""
OpenViking 封装层。

这里集中处理原 Agent.py / Skill_manager.py 中直接访问 OpenViking 的逻辑。
"""

import asyncio
import tempfile
from pathlib import Path
from typing import Any

from app import config
from app.logger import debug_log, log
from app.text_utils import clean_text


class VikingStore:
    def __init__(self):
        self.mock = config.MOCK_VIKING
        self.client = None
        self.sync_client = None
        self.TextPart = None

        config.VIKING_DATA_DIR.mkdir(parents=True, exist_ok=True)

        if self.mock:
            log("OpenViking mock mode enabled")
            return

        try:
            import openviking as ov
            from openviking.message import TextPart

            self.TextPart = TextPart

            # 对齐原 Agent.py：GLOBAL_VIKING_CLIENT = ov.OpenViking(path="./viking_data")
            self.client = ov.OpenViking(path=str(config.VIKING_DATA_DIR))
            self.client.initialize()

            # 对齐原 Skill_manager.py：ov.SyncOpenViking(path=data_path)
            self.sync_client = ov.SyncOpenViking(path=str(config.VIKING_DATA_DIR))
            self.sync_client.initialize()

            log(f"OpenViking initialized at {config.VIKING_DATA_DIR}")
        except Exception as exc:
            self.mock = True
            log(f"OpenViking import/init failed, fallback to mock mode: {exc}")

    def full_session_id(self, agent_id: str, session_id: str) -> str:
        agent_id = agent_id or "main"
        return f"{agent_id}_{session_id}"

    def _ensure_session(self, agent_id: str, session_id: str):
        if self.mock:
            return None

        full_id = self.full_session_id(agent_id, session_id)
        try:
            self.client.create_session(full_id)
        except Exception:
            pass

        session = self.client.session(session_id=full_id)
        try:
            asyncio.run(session.load())
        except RuntimeError:
            pass

        return session

    def search_context(self, user_id: str, session_id: str, agent_id: str, query: str,
                       max_messages: int, max_tokens: int, commit_limit: int) -> dict[str, Any]:
        if self.mock:
            return {
                "session_summary": "",
                "memories": [],
                "recent_messages": [
                    {"role": "system", "content": "MOCK_VIKING=true：当前未连接真实 OpenViking，上下文为空。"}
                ],
                "error": "",
            }

        messages = []
        memories = []
        session_summary = ""

        try:
            session = self._ensure_session(agent_id, session_id)
            full_id = self.full_session_id(agent_id, session_id)

            # 对齐原 Agent.get_context_sync：
            # commit_limit == 0 时使用 ov_session.get_context_for_search(query=query, max_messages=6)
            if not commit_limit:
                ctx = asyncio.run(session.get_context_for_search(
                    query=query,
                    max_messages=max_messages or config.DEFAULT_MAX_MESSAGES,
                ))
                for msg in ctx.get("current_messages", []):
                    try:
                        if not msg.parts:
                            continue
                        content = clean_text(msg.parts[0].text)
                        if content and "智能体返回：" not in content:
                            messages.append({"role": msg.role, "content": content})
                    except Exception:
                        continue

            # 对齐原 Agent.get_context_sync：
            # commit_limit > 0 时使用 get_session_context(full_session_id, token_budget=2048)
            else:
                ctx = self.client.get_session_context(
                    full_id,
                    token_budget=max_tokens or config.DEFAULT_TOKEN_BUDGET,
                )

                latest_summary = ctx.get("latest_archive_overview", "").strip()
                if latest_summary:
                    session_summary = latest_summary

                for arc in ctx.get("pre_archive_abstracts", []):
                    abs_txt = arc.get("abstract", "").strip()
                    if abs_txt:
                        memories.append({
                            "memory_id": arc.get("id", ""),
                            "content": abs_txt,
                            "score": 0.0,
                            "token_count": 0,
                        })

                for msg in ctx.get("messages", []):
                    try:
                        if not msg.get("parts"):
                            continue
                        text = clean_text(msg["parts"][0]["text"])
                        if text and "智能体返回：" not in text:
                            messages.append({"role": msg["role"], "content": text})
                    except Exception:
                        continue

            return {
                "session_summary": session_summary,
                "memories": memories,
                "recent_messages": messages,
                "error": "",
            }
        except Exception as exc:
            debug_log(f"search_context failed: {exc}")
            return {"session_summary": "", "memories": [], "recent_messages": [], "error": str(exc)}

    def append_turn(self, user_id: str, session_id: str, agent_id: str, task_id: str,
                    user_message: str, assistant_message: str, tool_summaries: list[str],
                    commit_limit: int) -> tuple[bool, str]:
        if self.mock:
            debug_log(f"mock append_turn user={user_id} session={session_id} task={task_id}")
            return True, ""

        try:
            session = self._ensure_session(agent_id, session_id)

            # 对齐原 Agent.add_message：
            # self.ov_session.add_message(role, [TextPart(text=content)])
            session.add_message("user", [self.TextPart(text=f"<{session_id}>{user_message}")])
            session.add_message("assistant", [self.TextPart(text=assistant_message)])

            for summary in tool_summaries or []:
                if summary:
                    session.add_message("assistant", [self.TextPart(text=f"工具摘要：{summary}")])

            if commit_limit and len(getattr(session, "messages", [])) > commit_limit:
                debug_log(f"[session-commit] {agent_id}_{session_id} 提交 {len(session.messages)} 条记录")
                session.commit()

            return True, ""
        except Exception as exc:
            debug_log(f"append_turn failed: {exc}")
            return False, str(exc)

    def add_skill_document(self, skill_name: str, version: str, content: str, source_path: str) -> tuple[bool, str, str]:
        if self.mock:
            return True, f"mock://skills/{skill_name}/{version or 'latest'}", ""

        try:
            source = Path(source_path) if source_path else None

            if source and source.exists():
                skill_md_path = source
            else:
                tmpdir = tempfile.mkdtemp(prefix=f"skill-{skill_name}-")
                skill_md_path = Path(tmpdir) / "SKILL.md"
                skill_md_path.write_text(content or "", encoding="utf-8")

            add_result = self.sync_client.add_skill(str(skill_md_path), wait=True)
            uri = add_result.get("uri", "") if isinstance(add_result, dict) else ""
            return True, uri, ""
        except Exception as exc:
            debug_log(f"add_skill_document failed: {exc}")
            return False, "", str(exc)

    def list_skill_docs(self, simple: bool = True) -> tuple[list[str], str]:
        if self.mock:
            return ["mock-weather", "mock-file"], ""

        try:
            names = self.sync_client.ls("viking://agent/skills/", simple=simple)
            if isinstance(names, list):
                if simple:
                    return [str(x) for x in names], ""
                return [str(x.get("name", x)) for x in names], ""
            return [], ""
        except Exception as exc:
            return [], str(exc)

    def read_skill_doc(self, skill_name: str, doc_type: str) -> tuple[bool, str, str]:
        if self.mock:
            return True, f"MOCK skill doc: {skill_name}/{doc_type}", ""

        doc_name = {
            "abstract": ".abstract.md",
            "overview": ".overview.md",
            "manual": "SKILL.md",
        }.get(doc_type or "manual", "SKILL.md")

        try:
            uri = f"viking://agent/skills/{skill_name}/{doc_name}"
            content = self.sync_client.read(uri) or ""
            return True, content, ""
        except Exception as exc:
            return False, "", str(exc)

    def search_skill_docs(self, query: str, skill_names: list[str], top_k: int, max_tokens: int) -> tuple[list[dict[str, Any]], str]:
        try:
            hits = []
            names = skill_names
            if not names:
                names, err = self.list_skill_docs(simple=True)
                if err:
                    return [], err

            for name in names[: top_k or 5]:
                ok, content, err = self.read_skill_doc(name, "overview")
                if not ok:
                    ok, content, err = self.read_skill_doc(name, "manual")
                if ok and content:
                    hits.append({
                        "skill_name": name,
                        "doc_id": f"{name}-overview",
                        "chunk_id": "overview-001",
                        "version": "",
                        "title": f"{name} 使用说明",
                        "content": content[:max_tokens or 2500],
                        "token_count": 0,
                        "score": 0.0,
                    })
            return hits, ""
        except Exception as exc:
            return [], str(exc)


store = VikingStore()
