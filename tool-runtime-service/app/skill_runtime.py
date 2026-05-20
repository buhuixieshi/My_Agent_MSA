from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable

from app import config


class SkillRuntime:
    """
    OpenClaw / ClawHub skill runtime for My_Agent_MSA.

    Skill logic is kept outside server.py. ClawHub download/install/list/uninstall
    commands run on an external VM by default, while the installed files still go
    to the shared skill directory.

    Shared directory layout for all users:

        /app/workspace/skill/<skill_slug>/SKILL.md
        /app/workspace/skill/<skill_slug>/scripts/<skill_slug>.py
        /app/workspace/skill/viking_data/

    The external VM must mount the same shared directory. If the path is different
    on the VM, set CLAW_EXTERNAL_VM_SKILL_ROOT_DIR to that VM-side path.
    """

    def __init__(self) -> None:
        self.skill_root = Path(config.SKILL_ROOT_DIR)
        self.viking_data_dir = Path(config.SKILL_VIKING_DATA_DIR)
        self._client = None

    def _ensure_dirs(self) -> None:
        self.skill_root.mkdir(parents=True, exist_ok=True)
        self.viking_data_dir.mkdir(parents=True, exist_ok=True)

    def _get_viking_client(self):
        self._ensure_dirs()
        if self._client is not None:
            return self._client

        try:
            import openviking as ov
        except Exception as exc:
            raise RuntimeError(
                "openviking is not installed in tool-runtime-service. "
                "Add openviking to requirements.txt and rebuild the image."
            ) from exc

        if hasattr(ov, "SyncOpenViking"):
            client = ov.SyncOpenViking(path=str(self.viking_data_dir))
        else:
            client = ov.OpenViking(path=str(self.viking_data_dir))

        client.initialize()
        self._client = client
        return client

    @staticmethod
    def _format_completed_process(proc: subprocess.CompletedProcess) -> str:
        stdout = (proc.stdout or "").strip()
        stderr = (proc.stderr or "").strip()

        if proc.returncode == 0:
            return stdout or "执行成功（无输出）"

        output = f"执行失败，退出码：{proc.returncode}"
        if stdout:
            output += f"\n[stdout]\n{stdout}"
        if stderr:
            output += f"\n[stderr]\n{stderr}"
        return output

    def _run_local_command(self, command: list[str], cwd: Path | None = None, timeout: int | None = None) -> str:
        self._ensure_dirs()
        proc = subprocess.run(
            command,
            cwd=str(cwd or self.skill_root),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout or config.DEFAULT_TIMEOUT_SECONDS,
        )
        return self._format_completed_process(proc)

    def _external_vm_target(self) -> str:
        user = config.CLAW_EXTERNAL_VM_USER.strip()
        host = config.CLAW_EXTERNAL_VM_HOST.strip()
        if not host:
            raise RuntimeError("CLAW_EXTERNAL_VM_HOST is required when CLAW_DOWNLOAD_MODE=external-vm")
        return f"{user}@{host}" if user else host

    def _ssh_base_command(self) -> list[str]:
        command = ["ssh", "-p", str(config.CLAW_EXTERNAL_VM_PORT)]
        if not config.CLAW_EXTERNAL_VM_STRICT_HOST_KEY_CHECKING:
            command.extend([
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
            ])
        if config.CLAW_EXTERNAL_VM_SSH_KEY:
            command.extend(["-i", config.CLAW_EXTERNAL_VM_SSH_KEY])
        command.append(self._external_vm_target())
        return command

    def _run_external_vm_shell(self, script: str, timeout: int | None = None) -> str:
        proc = subprocess.run(
            self._ssh_base_command() + [script],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout or config.DEFAULT_TIMEOUT_SECONDS,
        )
        return self._format_completed_process(proc)

    def _run_clawhub(self, args: list[str], timeout: int | None = None) -> str:
        """Run clawhub on the configured external VM by default."""
        clawhub_bin = config.CLAW_EXTERNAL_VM_CLAWHUB_BIN or "clawhub"

        if config.CLAW_DOWNLOAD_MODE in {"local", "container"}:
            return self._run_local_command([clawhub_bin, *args], timeout=timeout)

        if config.CLAW_DOWNLOAD_MODE not in {"external-vm", "external_vm", "ssh"}:
            raise RuntimeError(f"unsupported CLAW_DOWNLOAD_MODE={config.CLAW_DOWNLOAD_MODE!r}")

        quoted = " ".join(shlex.quote(str(part)) for part in [clawhub_bin, *args])
        return self._run_external_vm_shell(quoted, timeout=timeout)

    @staticmethod
    def _first_arg(args: list[str], kwargs: dict[str, str], *names: str) -> str:
        for name in names:
            value = kwargs.get(name)
            if value:
                return str(value)
        return str(args[0]) if args else ""

    def _skill_md_path(self, skill_slug: str) -> Path:
        skill_dir = self.skill_root / skill_slug
        for filename in ("SKILL.md", "skill.md"):
            candidate = skill_dir / filename
            if candidate.exists():
                return candidate
        return skill_dir / "SKILL.md"

    def dispatch(
        self,
        tool_name: str,
        args: list[str],
        kwargs: dict[str, str],
        user_workspace: Path,
        timeout: int,
    ) -> str:
        name = (tool_name or "").strip()

        if name == "clawhub-search":
            keyword = self._first_arg(args, kwargs, "keyword", "query")
            return self.clawhub_search(keyword, timeout=timeout)

        if name == "clawhub-install":
            skill_slug = self._first_arg(args, kwargs, "skill_slug", "skill", "name")
            return self.clawhub_install(skill_slug, timeout=timeout)

        if name == "clawhub-list":
            return self.clawhub_list(timeout=timeout)

        if name == "skill-list":
            return self.skill_list()

        if name == "skill-list-simple":
            return self.skill_list_simple()

        if name == "skill-delete":
            skill_slug = self._first_arg(args, kwargs, "skill_slug", "skill", "name")
            return self.skill_delete(skill_slug, timeout=timeout)

        if name == "skill-abstract":
            skill_name = self._first_arg(args, kwargs, "skill_name", "skill", "name")
            return self.skill_abstract(skill_name)

        if name == "skill-overview":
            skill_name = self._first_arg(args, kwargs, "skill_name", "skill", "name")
            return self.skill_overview(skill_name)

        if name == "skill-manual":
            skill_name = self._first_arg(args, kwargs, "skill_name", "skill", "name")
            return self.skill_manual(skill_name)

        if name == "add-skill-to-viking":
            skill_slug = self._first_arg(args, kwargs, "skill_slug", "skill", "name")
            return self.add_skill_to_viking(skill_slug)

        return self.run_skill(name, args=args, user_workspace=user_workspace, timeout=timeout)

    def clawhub_search(self, keyword: str, timeout: int) -> str:
        if not keyword:
            return "错误：搜索关键词不能为空"
        return self._run_clawhub(["search", keyword], timeout=timeout)

    def clawhub_install(self, skill_slug: str, timeout: int) -> str:
        if not skill_slug:
            return "错误：技能名称不能为空"

        self._ensure_dirs()
        vm_skill_root = config.CLAW_EXTERNAL_VM_SKILL_ROOT_DIR
        result = self._run_clawhub(
            ["install", skill_slug, "--dir", vm_skill_root, "--force"],
            timeout=timeout,
        )
        add_result = self.add_skill_to_viking(skill_slug)

        if add_result.startswith("✅"):
            return f"✅ 安装并导入 Viking 知识库：{skill_slug}\n{add_result}\n{result}"
        return f"⚠️ 安装命令已执行，但导入技能失败：{add_result}\n{result}"

    def add_skill_to_viking(self, skill_slug: str) -> str:
        if not skill_slug:
            return "❌ 技能名称不能为空"

        try:
            skill_md_path = self._skill_md_path(skill_slug)
            if not skill_md_path.exists():
                return f"❌ 技能 {skill_slug} 不存在，缺少 SKILL.md"

            client = self._get_viking_client()
            add_result = client.add_skill(str(skill_md_path), wait=True)
            uri = add_result.get("uri", "") if isinstance(add_result, dict) else ""
            return f"✅ 技能导入成功：{skill_slug} | URI: {uri}"
        except Exception as exc:
            return f"❌ 导入技能失败：{exc}"

    def clawhub_list(self, timeout: int) -> str:
        return self._run_clawhub(["list"], timeout=timeout)

    def skill_delete(self, skill_slug: str, timeout: int) -> str:
        if not skill_slug:
            return "错误：技能名称不能为空"

        try:
            self._get_viking_client().rm(f"viking://agent/skills/{skill_slug}")
        except Exception:
            pass

        uninstall_result = self._run_clawhub(["uninstall", "--yes", skill_slug], timeout=timeout)

        skill_dir = self.skill_root / skill_slug
        if skill_dir.exists():
            shutil.rmtree(skill_dir)

        return f"✅ 技能已完全卸载（Viking 已移除 + 文件夹已删除）：{skill_slug}\n{uninstall_result}"

    def skill_list(self) -> str:
        try:
            skills = self._get_viking_client().ls("viking://agent/skills/")
            if not skills:
                return "📭 Viking 知识库中暂无任何技能"

            output = "📚 已安装技能列表：\n"
            for index, skill in enumerate(skills, 1):
                if isinstance(skill, dict):
                    name = skill.get("name", "未命名")
                    desc = skill.get("abstract", "无描述")
                else:
                    name = str(skill)
                    desc = ""
                output += f"{index}. {name} - {desc}\n"
            return output.strip()
        except Exception as exc:
            return f"❌ 获取技能列表失败：{exc}"

    def skill_list_simple(self) -> str:
        try:
            names = self._get_viking_client().ls("viking://agent/skills/", simple=True)
            if not names:
                return "📭 暂无技能"
            return "已安装技能：\n" + "\n".join(f"- {name}" for name in names)
        except Exception as exc:
            return f"❌ 获取失败：{exc}"

    def skill_abstract(self, skill_name: str) -> str:
        if not skill_name:
            return "读取 abstract 失败，请提供技能名"
        try:
            return self._get_viking_client().read(f"viking://agent/skills/{skill_name}/.abstract.md") or "无简介"
        except Exception:
            return f"读取 abstract 失败,请检查知识库中是否有名为{skill_name}的技能"

    def skill_overview(self, skill_name: str) -> str:
        if not skill_name:
            return "读取 overview 失败，请提供技能名"
        try:
            return self._get_viking_client().read(f"viking://agent/skills/{skill_name}/.overview.md") or "无使用说明"
        except Exception:
            return f"读取 overview 失败,请检查知识库中是否有名为{skill_name}的技能"

    def skill_manual(self, skill_name: str) -> str:
        if not skill_name:
            return "读取 SKILL.md 失败，请提供技能名"
        try:
            return self._get_viking_client().read(f"viking://agent/skills/{skill_name}/SKILL.md") or "无执行文档"
        except Exception:
            return f"读取 SKILL.md 失败,请检查知识库中是否有名为{skill_name}的技能"

    def run_skill(self, skill_name: str, args: Iterable[str], user_workspace: Path, timeout: int) -> str:
        if not skill_name:
            return "错误：技能名称不能为空"

        skill_dir = self.skill_root / skill_name
        script_file = skill_dir / "scripts" / f"{skill_name}.py"

        if not script_file.exists():
            return self.skill_overview(skill_name)

        command = [sys.executable, str(script_file), *[str(arg) for arg in args]]
        proc = subprocess.run(
            command,
            cwd=str(skill_dir),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            env={
                **os.environ,
                "MY_AGENT_WORKSPACE": str(user_workspace),
                "MY_AGENT_SKILL_ROOT": str(self.skill_root),
                "MY_AGENT_SKILL_DIR": str(skill_dir),
            },
        )
        output = self._format_completed_process(proc)
        command_text = " ".join(command)
        return f"【执行完成：{skill_name}】\n命令：{command_text}\n结果：{output}"


skill_runtime = SkillRuntime()
