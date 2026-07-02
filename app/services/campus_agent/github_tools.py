"""GitHub REST API tools for the football assistant."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User
from app.services.campus_agent.pending_actions import create_pending_action


GITHUB_URL_RE = re.compile(r"https?://github\.com/(?P<owner>[^/\s]+)/(?P<repo>[^/\s#?]+)(?:/(?P<rest>[^\s]+))?", re.I)
GITHUB_DOWNLOAD_MAX_BYTES = 300 * 1024 * 1024
GITHUB_DOWNLOAD_MAX_FILES = 30000
KNOWN_PUBLIC_REPOS = {
    "dify": ("langgenius", "dify"),
    "langchain": ("langchain-ai", "langchain"),
    "langgraph": ("langchain-ai", "langgraph"),
    "fastapi": ("fastapi", "fastapi"),
    "vue": ("vuejs", "core"),
    "react": ("facebook", "react"),
}


@dataclass(frozen=True)
class GitHubRepoRef:
    owner: str
    repo: str
    rest: str = ""

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.repo}"


def should_use_github(message: str) -> bool:
    text = message or ""
    if "github.com/" in text.lower():
        return True
    if _is_download_repo_intent(text):
        return True
    github_words = ["GitHub", "github", "仓库", "repo", "issue", "issues", "PR", "pull request", "Pull Request"]
    action_words = ["查看", "查询", "列出", "创建", "新建", "分析", "详情"]
    return any(word in text for word in github_words) and any(word in text for word in action_words)


def parse_github_url(message: str) -> GitHubRepoRef | None:
    match = GITHUB_URL_RE.search(message or "")
    if not match:
        shorthand = re.search(
            r"(?:仓库|repo)?[:： ]*([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)(?:\.git)?",
            message or "",
            re.I,
        )
        if not shorthand:
            return None
        return GitHubRepoRef(shorthand.group(1), shorthand.group(2).removesuffix(".git"))
    return GitHubRepoRef(
        owner=match.group("owner"),
        repo=match.group("repo").removesuffix(".git"),
        rest=match.group("rest") or "",
    )


def detect_github_task(message: str) -> str:
    text = message or ""
    if _is_download_repo_intent(text):
        return "download_repo"
    if _is_create_issue_intent(text):
        return "create_issue"
    if re.search(r"(?:PR|pr|pull request|Pull Request)\s*#?\d+", text) or "/pull/" in text:
        return "get_pr"
    if re.search(r"issue\s*#?\d+", text, re.I) or "/issues/" in text:
        return "get_issue"
    if any(word in text for word in ["issue", "issues", "问题列表", "缺陷列表"]):
        return "list_issues"
    if any(word in text for word in ["目录", "文件", "结构", "树"]):
        return "list_contents"
    return "repo_summary"


def _is_download_repo_intent(text: str) -> bool:
    compact = re.sub(r"\s+", "", text or "", flags=re.I).lower()
    if not any(word in compact for word in ["下载", "拉取", "克隆", "clone", "download"]):
        return False
    if compact in {"下载", "下载吧", "拉取", "拉取吧", "克隆", "克隆吧", "clone", "download"}:
        return True
    if any(word in compact for word in ["github", "仓库", "repo", "代码", "源码", "项目"]):
        return True
    if re.search(r"[a-z0-9_.-]+/[a-z0-9_.-]+", compact, re.I):
        return True
    return any(alias in compact for alias in KNOWN_PUBLIC_REPOS)


def _repo_from_known_name(message: str) -> GitHubRepoRef | None:
    compact = re.sub(r"[\s，。！？,.!?：:；;]+", "", message or "").lower()
    for alias, (owner, repo) in KNOWN_PUBLIC_REPOS.items():
        if alias in compact:
            return GitHubRepoRef(owner, repo)
    return None


def _is_create_issue_intent(text: str) -> bool:
    compact = re.sub(r"\s+", "", text or "", flags=re.I).lower()
    if re.search(r"(创建|新建|新增|提交|提|开)(一个|1个|一条|条|个)?(github)?(issue|问题|缺陷|bug)", compact, re.I):
        return True
    if ("标题" in text and any(word in text for word in ["内容", "正文"]) and any(word in compact for word in ["issue", "问题", "缺陷", "bug"])):
        return True
    return False


def handle_github_message(
    *,
    db: Session,
    user: User,
    session_id: str,
    message: str,
    previous_context: dict | None = None,
) -> tuple[str, dict[str, Any]]:
    repo = parse_github_url(message) or _repo_from_known_name(message) or _repo_from_context(previous_context)
    if not repo:
        return (
            "请把 GitHub 仓库地址发给我，例如：https://github.com/owner/repo。也可以说“下载 Dify 的代码”。",
            {"task": "github_missing_repo"},
        )
    task = _continued_task(message, previous_context) or detect_github_task(message)
    try:
        if task == "download_repo":
            repo_data = github_get(f"/repos/{repo.owner}/{repo.repo}")
            result = download_public_repo(repo, repo_data)
            return _format_download_result(repo, repo_data, result), {
                "task": task,
                "repo": repo.full_name,
                "repo_data": _compact_repo(repo_data),
                "download": result,
            }
        if task == "create_issue":
            return _prepare_create_issue(
                db=db,
                user=user,
                session_id=session_id,
                repo=repo,
                message=message,
                previous_context=previous_context,
            )
        if task == "get_pr":
            number = _parse_number(message, repo.rest, "pull") or _parse_number(message, repo.rest, "pr")
            if not number:
                return "请说明要查看的 PR 编号，例如：查看 PR #3。", {"task": task, "repo": repo.full_name}
            pr = github_get(f"/repos/{repo.owner}/{repo.repo}/pulls/{number}")
            return _format_pr(pr), {"task": task, "repo": repo.full_name, "number": number, "item": _compact_issue_like(pr)}
        if task == "get_issue":
            number = _parse_number(message, repo.rest, "issues") or _parse_number(message, repo.rest, "issue")
            if not number:
                return "请说明要查看的 issue 编号，例如：查看 issue #12。", {"task": task, "repo": repo.full_name}
            issue = github_get(f"/repos/{repo.owner}/{repo.repo}/issues/{number}")
            return _format_issue(issue), {"task": task, "repo": repo.full_name, "number": number, "item": _compact_issue_like(issue)}
        if task == "list_issues":
            issues = github_get(f"/repos/{repo.owner}/{repo.repo}/issues", {"state": "open", "per_page": "8"})
            return _format_issue_list(repo, issues), {"task": task, "repo": repo.full_name, "items": [_compact_issue_like(i) for i in issues]}
        if task == "list_contents":
            path = _parse_path(message)
            contents = github_get(f"/repos/{repo.owner}/{repo.repo}/contents/{urllib.parse.quote(path)}" if path else f"/repos/{repo.owner}/{repo.repo}/contents")
            return _format_contents(repo, contents, path), {"task": task, "repo": repo.full_name, "path": path, "items": _compact_contents(contents)}
        repo_data = github_get(f"/repos/{repo.owner}/{repo.repo}")
        contents = github_get(f"/repos/{repo.owner}/{repo.repo}/contents")
        return _format_repo_summary(repo_data, contents), {
            "task": task,
            "repo": repo.full_name,
            "repo_data": _compact_repo(repo_data),
            "items": _compact_contents(contents),
        }
    except GitHubApiError as exc:
        return f"GitHub 请求失败：{exc.user_message}", {"task": task, "repo": repo.full_name, "error": exc.user_message}


def execute_github_pending_action(args: dict) -> tuple[bool, str, dict[str, Any]]:
    action = args.get("action")
    if action != "create_issue":
        return False, "不支持的 GitHub 待确认动作。", {}
    repo = args.get("repo") or {}
    owner = repo.get("owner")
    repo_name = repo.get("repo")
    title = args.get("title")
    body = args.get("body") or ""
    if not owner or not repo_name or not title:
        return False, "创建 issue 缺少仓库或标题。", {}
    try:
        result = github_post(f"/repos/{owner}/{repo_name}/issues", {"title": title, "body": body})
    except GitHubApiError as exc:
        return False, f"创建 GitHub issue 失败：{exc.user_message}", {"error": exc.user_message}
    url = result.get("html_url") or ""
    number = result.get("number")
    return True, f"已创建 GitHub issue #{number}：{url}", {"number": number, "url": url, "repo": f"{owner}/{repo_name}"}


class GitHubApiError(Exception):
    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message


def github_get(path: str, params: dict[str, str] | None = None) -> Any:
    return _github_request("GET", path, params=params)


def github_post(path: str, payload: dict[str, Any]) -> Any:
    return _github_request("POST", path, payload=payload)


def _github_request(method: str, path: str, *, params: dict[str, str] | None = None, payload: dict[str, Any] | None = None) -> Any:
    if not settings.GITHUB_TOKEN:
        raise GitHubApiError("后端还没有配置 GITHUB_TOKEN。")
    base = (settings.GITHUB_API_BASE or "https://api.github.com").rstrip("/")
    url = f"{base}{path if path.startswith('/') else '/' + path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "CampusFootballAssistant/1.0",
    }
    last_exc: Exception | None = None
    for _ in range(3):
        try:
            resp = requests.request(
                method,
                url,
                params=params,
                json=payload,
                headers=headers,
                timeout=settings.GITHUB_TIMEOUT_SECONDS,
            )
            if resp.status_code == 401:
                raise GitHubApiError("GitHub Token 无效或已过期。")
            if resp.status_code == 403:
                raise GitHubApiError(f"GitHub 权限不足或频率受限。{_github_error_detail(resp)}".strip())
            if resp.status_code == 404:
                raise GitHubApiError("仓库或资源不存在，或者当前 Token 没有访问权限。")
            if resp.status_code >= 400:
                raise GitHubApiError(f"HTTP {resp.status_code} {_github_error_detail(resp)}".strip())
            return resp.json() if resp.text.strip() else {}
        except GitHubApiError:
            raise
        except requests.RequestException as exc:
            last_exc = exc
    if os.name == "nt":
        try:
            return _github_request_powershell(method, url, params=params, payload=payload)
        except GitHubApiError:
            raise
        except Exception as exc:
            raise GitHubApiError(f"无法连接 GitHub：{last_exc}；PowerShell 兜底也失败：{exc}")
    raise GitHubApiError(f"无法连接 GitHub：{last_exc}")


def _github_error_detail(resp: requests.Response) -> str:
    try:
        data = resp.json()
        return data.get("message") or resp.text[:200]
    except Exception:
        return resp.text[:200]


def _github_request_powershell(method: str, url: str, *, params: dict[str, str] | None = None, payload: dict[str, Any] | None = None) -> Any:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    env = os.environ.copy()
    env["GITHUB_TOKEN_FOR_REQUEST"] = settings.GITHUB_TOKEN
    env["GITHUB_METHOD_FOR_REQUEST"] = method
    env["GITHUB_URL_FOR_REQUEST"] = url
    body_json = json.dumps(payload or {}, ensure_ascii=False)
    env["GITHUB_BODY_FOR_REQUEST"] = body_json
    script = r"""
$ErrorActionPreference = 'Stop'
$headers = @{
  Accept = 'application/vnd.github+json'
  Authorization = "Bearer $env:GITHUB_TOKEN_FOR_REQUEST"
  'X-GitHub-Api-Version' = '2022-11-28'
  'User-Agent' = 'CampusFootballAssistant/1.0'
}
$method = $env:GITHUB_METHOD_FOR_REQUEST
$uri = $env:GITHUB_URL_FOR_REQUEST
$body = $env:GITHUB_BODY_FOR_REQUEST
if ($method -eq 'GET') {
  $result = Invoke-RestMethod -Method $method -Uri $uri -Headers $headers -TimeoutSec 20
} else {
  $result = Invoke-RestMethod -Method $method -Uri $uri -Headers $headers -Body $body -ContentType 'application/json; charset=utf-8' -TimeoutSec 20
}
$result | ConvertTo-Json -Depth 20 -Compress
"""
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        env=env,
        capture_output=True,
        text=True,
        timeout=settings.GITHUB_TIMEOUT_SECONDS + 10,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip()
        if "401" in msg:
            raise GitHubApiError("GitHub Token 无效或已过期。")
        if "403" in msg:
            raise GitHubApiError("GitHub 权限不足或频率受限。")
        if "404" in msg:
            raise GitHubApiError("仓库或资源不存在，或者当前 Token 没有访问权限。")
        raise GitHubApiError(msg[:300] or "PowerShell 请求 GitHub 失败。")
    output = (proc.stdout or "").strip()
    return json.loads(output) if output else {}


def _download_root() -> Path:
    root = Path(settings.ABS_UPLOAD_DIR).resolve() / "github_repos"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_repo_dir(repo: GitHubRepoRef, branch: str) -> Path:
    safe_owner = re.sub(r"[^A-Za-z0-9_.-]+", "_", repo.owner)
    safe_repo = re.sub(r"[^A-Za-z0-9_.-]+", "_", repo.repo)
    safe_branch = re.sub(r"[^A-Za-z0-9_.-]+", "_", branch or "main")
    return _download_root() / f"{safe_owner}__{safe_repo}__{safe_branch}"


def _ensure_inside(child: Path, parent: Path) -> None:
    child_resolved = child.resolve()
    parent_resolved = parent.resolve()
    if child_resolved != parent_resolved and parent_resolved not in child_resolved.parents:
        raise GitHubApiError("下载包包含不安全路径，已拒绝解压。")


def _download_file(url: str, target: Path) -> int:
    headers = {"User-Agent": "CampusFootballAssistant/1.0", "Accept": "application/vnd.github+json"}
    if settings.GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN}"
    total = 0
    try:
        with requests.get(url, headers=headers, stream=True, timeout=max(settings.GITHUB_TIMEOUT_SECONDS, 30), allow_redirects=True) as resp:
            if resp.status_code == 401:
                raise GitHubApiError("GitHub Token 无效或已过期。")
            if resp.status_code == 403:
                raise GitHubApiError("GitHub 权限不足或频率受限。")
            if resp.status_code == 404:
                raise GitHubApiError("仓库源码包不存在，或当前 Token 没有访问权限。")
            if resp.status_code >= 400:
                raise GitHubApiError(f"下载源码失败：HTTP {resp.status_code}")
            with target.open("wb") as out:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > GITHUB_DOWNLOAD_MAX_BYTES:
                        raise GitHubApiError("仓库源码包超过 300MB，已停止下载。")
                    out.write(chunk)
    except requests.RequestException as exc:
        raise GitHubApiError(f"下载 GitHub 源码失败：{exc}") from exc
    return total


def _extract_zip_safely(zip_path: Path, target_dir: Path) -> tuple[int, int]:
    temp_dir = target_dir.with_name(target_dir.name + "__tmp")
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    file_count = 0
    total_size = 0
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = [info for info in archive.infolist() if not info.is_dir()]
            if len(infos) > GITHUB_DOWNLOAD_MAX_FILES:
                raise GitHubApiError(f"仓库文件数超过 {GITHUB_DOWNLOAD_MAX_FILES}，已拒绝解压。")
            for info in archive.infolist():
                raw_name = info.filename.replace("\\", "/")
                if not raw_name or raw_name.startswith("/") or ".." in Path(raw_name).parts:
                    raise GitHubApiError("下载包包含不安全路径，已拒绝解压。")
                destination = temp_dir / raw_name
                _ensure_inside(destination, temp_dir)
                total_size += max(info.file_size, 0)
                if total_size > GITHUB_DOWNLOAD_MAX_BYTES:
                    raise GitHubApiError("仓库解压后超过 300MB，已拒绝保存。")
                archive.extract(info, temp_dir)
                if not info.is_dir():
                    file_count += 1
        children = list(temp_dir.iterdir())
        source_root = children[0] if len(children) == 1 and children[0].is_dir() else temp_dir
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        for child in source_root.iterdir():
            shutil.move(str(child), str(target_dir / child.name))
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
    return file_count, total_size


def download_public_repo(repo: GitHubRepoRef, repo_data: dict | None = None) -> dict[str, Any]:
    branch = (repo_data or {}).get("default_branch") or "main"
    target_dir = _safe_repo_dir(repo, branch)
    zip_path = target_dir.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    archive_url = f"https://api.github.com/repos/{repo.owner}/{repo.repo}/zipball/{urllib.parse.quote(branch)}"
    downloaded_bytes = _download_file(archive_url, zip_path)
    try:
        file_count, total_size = _extract_zip_safely(zip_path, target_dir)
    finally:
        zip_path.unlink(missing_ok=True)
    return {
        "path": str(target_dir),
        "branch": branch,
        "downloaded_bytes": downloaded_bytes,
        "file_count": file_count,
        "total_size": total_size,
    }


def _prepare_create_issue(
    *,
    db: Session,
    user: User,
    session_id: str,
    repo: GitHubRepoRef,
    message: str,
    previous_context: dict | None = None,
) -> tuple[str, dict[str, Any]]:
    title, body = _parse_issue_payload(message)
    draft = _create_issue_draft(previous_context)
    title = title or draft.get("title", "")
    body = body or draft.get("body", "")
    if not title:
        return (
            "创建 issue 还缺少标题。你可以说：给这个仓库创建一个 issue，标题是……，内容是……",
            {"task": "create_issue", "repo": repo.full_name, "missing": ["title"], "draft": {"body": body}},
        )
    action = create_pending_action(
        db,
        user=user,
        session_id=session_id,
        tool_code="github_create_issue",
        args={
            "action": "create_issue",
            "repo": {"owner": repo.owner, "repo": repo.repo},
            "title": title,
            "body": body,
        },
        summary=f"在 {repo.full_name} 创建 issue：{title}",
        risk="medium",
    )
    reply = (
        f"请确认是否在 GitHub 仓库 {repo.full_name} 创建 issue：\n"
        f"- 标题：{title}\n"
        f"- 内容：{body or '（空）'}\n\n"
        f"待确认动作 ID：{action.id}。回复“确认 {action.id}”后执行，10 分钟内有效。"
    )
    return reply, {"task": "create_issue", "repo": repo.full_name, "pending_action_id": action.id}


def _parse_issue_payload(message: str) -> tuple[str, str]:
    text = message or ""
    title = ""
    body = ""
    title_match = re.search(r"标题(?:是|为|[:：])\s*(.+?)(?:内容(?:是|为|[:：])|正文(?:是|为|[:：])|$)", text, re.S)
    if title_match:
        title = title_match.group(1).strip(" \n，,。")
    body_match = re.search(r"(?:内容|正文)(?:是|为|[:：])\s*(.+)$", text, re.S)
    if body_match:
        body = body_match.group(1).strip()
    if not title:
        match = re.search(r"(?:创建|新建|新增|提交|提|开)\s*(?:一个|1个|一条|条|个)?\s*(?:github\s*)?(?:issue|问题|缺陷|bug)[，, ]*(.+)$", text, re.I)
        if match:
            title = match.group(1).strip(" \n，,。")
    return title[:180], body[:8000]


def _continued_task(message: str, previous_context: dict | None) -> str | None:
    data = (previous_context or {}).get("tool_data") or {}
    if data.get("task") == "create_issue" and data.get("missing"):
        if "标题" in (message or "") or "内容" in (message or "") or len((message or "").strip()) >= 2:
            return "create_issue"
    return None


def _create_issue_draft(previous_context: dict | None) -> dict[str, str]:
    data = (previous_context or {}).get("tool_data") or {}
    draft = data.get("draft") or {}
    return draft if isinstance(draft, dict) else {}


def _repo_from_context(previous_context: dict | None) -> GitHubRepoRef | None:
    data = (previous_context or {}).get("tool_data") or {}
    repo = data.get("repo")
    if isinstance(repo, str) and "/" in repo:
        owner, repo_name = repo.split("/", 1)
        return GitHubRepoRef(owner, repo_name)
    return None


def _parse_number(message: str, rest: str, kind: str) -> int | None:
    patterns = [
        rf"{kind}s?/#?(\d+)",
        rf"{kind}s?\s*#?(\d+)",
        r"#(\d+)",
    ]
    text = f"{message or ''} /{rest or ''}"
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return int(match.group(1))
    return None


def _parse_path(message: str) -> str:
    match = re.search(r"(?:目录|路径|path)[:： ]*([A-Za-z0-9_./-]+)", message or "", re.I)
    if not match:
        return ""
    path = match.group(1).strip("/ ")
    if ".." in path:
        return ""
    return path


def _format_repo_summary(repo: dict, contents: list[dict] | dict) -> str:
    items = _compact_contents(contents)[:12]
    lines = [
        f"仓库：{repo.get('full_name')}",
        f"描述：{repo.get('description') or '暂无描述'}",
        f"语言：{repo.get('language') or '未知'}，Stars：{repo.get('stargazers_count', 0)}，Forks：{repo.get('forks_count', 0)}，Open issues：{repo.get('open_issues_count', 0)}",
        f"默认分支：{repo.get('default_branch') or 'main'}",
        "",
        "根目录主要内容：",
    ]
    lines.extend(f"- {item['type']} {item['name']}" for item in items)
    return "\n".join(lines)


def _format_contents(repo: GitHubRepoRef, contents: list[dict] | dict, path: str) -> str:
    items = _compact_contents(contents)
    title = f"{repo.full_name}/{path}" if path else repo.full_name
    if not items:
        return f"{title} 下没有读取到目录内容。"
    lines = [f"{title} 目录内容："]
    lines.extend(f"- {item['type']} {item['name']}" for item in items[:30])
    return "\n".join(lines)


def _format_issue_list(repo: GitHubRepoRef, issues: list[dict]) -> str:
    real_issues = [item for item in issues if not item.get("pull_request")]
    if not real_issues:
        return f"{repo.full_name} 当前没有读取到 open issue。"
    lines = [f"{repo.full_name} 最近 open issue："]
    for item in real_issues[:8]:
        lines.append(f"- #{item.get('number')} {item.get('title')}（{item.get('state')}）")
    return "\n".join(lines)


def _format_issue(issue: dict) -> str:
    return "\n".join(
        [
            f"Issue #{issue.get('number')}：{issue.get('title')}",
            f"状态：{issue.get('state')}，作者：{(issue.get('user') or {}).get('login')}",
            f"链接：{issue.get('html_url')}",
            "",
            (issue.get("body") or "暂无正文")[:1200],
        ]
    )


def _format_pr(pr: dict) -> str:
    return "\n".join(
        [
            f"PR #{pr.get('number')}：{pr.get('title')}",
            f"状态：{pr.get('state')}，作者：{(pr.get('user') or {}).get('login')}",
            f"分支：{(pr.get('head') or {}).get('ref')} -> {(pr.get('base') or {}).get('ref')}",
            f"链接：{pr.get('html_url')}",
            "",
            (pr.get("body") or "暂无正文")[:1200],
        ]
    )


def _format_size(value: int | float | None) -> str:
    number = float(value or 0)
    for unit in ["B", "KB", "MB", "GB"]:
        if number < 1024 or unit == "GB":
            return f"{number:.1f}{unit}" if unit != "B" else f"{int(number)}B"
        number /= 1024
    return f"{number:.1f}GB"


def _format_download_result(repo: GitHubRepoRef, repo_data: dict, result: dict[str, Any]) -> str:
    path = result.get("path") or ""
    return "\n".join([
        f"已下载公开仓库源码：{repo.full_name}",
        f"描述：{repo_data.get('description') or '暂无描述'}",
        f"默认分支：{result.get('branch') or repo_data.get('default_branch') or 'main'}",
        f"文件数：{result.get('file_count', 0)}，大小约：{_format_size(result.get('total_size'))}",
        f"本地路径：{path}",
        "",
        f"下一步可以直接说：分析项目 {path}",
        "说明：我只下载并解压源码，不会自动运行其中的任何代码。",
    ])


def _compact_repo(repo: dict) -> dict:
    return {
        "full_name": repo.get("full_name"),
        "description": repo.get("description"),
        "language": repo.get("language"),
        "stars": repo.get("stargazers_count"),
        "forks": repo.get("forks_count"),
        "open_issues": repo.get("open_issues_count"),
        "default_branch": repo.get("default_branch"),
        "url": repo.get("html_url"),
    }


def _compact_contents(contents: list[dict] | dict) -> list[dict]:
    if isinstance(contents, dict):
        contents = [contents]
    if not isinstance(contents, list):
        return []
    return [
        {
            "name": item.get("name"),
            "path": item.get("path"),
            "type": "dir" if item.get("type") == "dir" else "file",
            "size": item.get("size"),
        }
        for item in contents
    ]


def _compact_issue_like(item: dict) -> dict:
    return {
        "number": item.get("number"),
        "title": item.get("title"),
        "state": item.get("state"),
        "user": (item.get("user") or {}).get("login"),
        "url": item.get("html_url"),
    }
