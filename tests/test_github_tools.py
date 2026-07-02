from app.services.campus_agent.github_tools import (
    _parse_issue_payload,
    detect_github_task,
    parse_github_url,
    should_use_github,
    _repo_from_known_name,
)
from app.services.campus_agent.orchestrator import detect_auto_mode


def test_parse_github_url():
    repo = parse_github_url("分析仓库 https://github.com/openai/openai-python")

    assert repo is not None
    assert repo.owner == "openai"
    assert repo.repo == "openai-python"
    assert repo.full_name == "openai/openai-python"


def test_parse_github_issue_url():
    repo = parse_github_url("看看 https://github.com/openai/openai-python/issues/123")

    assert repo is not None
    assert repo.owner == "openai"
    assert repo.repo == "openai-python"
    assert repo.rest == "issues/123"


def test_parse_bare_owner_repo():
    repo = parse_github_url("下载 octocat/Hello-World 的代码")

    assert repo is not None
    assert repo.owner == "octocat"
    assert repo.repo == "Hello-World"


def test_detect_github_tasks():
    assert detect_github_task("查看这个仓库最近的 issue") == "list_issues"
    assert detect_github_task("查看 PR #3 改了什么") == "get_pr"
    assert detect_github_task("创建 issue 标题是修复问题 内容是详细描述") == "create_issue"
    assert detect_github_task("创建一个 issue，标题是优化助手，内容是补充 GitHub 模块测试") == "create_issue"
    assert detect_github_task("新建一个问题 标题是优化助手 内容是补充测试") == "create_issue"
    assert detect_github_task("看一下目录结构") == "list_contents"
    assert detect_github_task("我想学习 Dify，下载 Dify 的代码") == "download_repo"
    assert detect_github_task("下载 octocat/Hello-World 的代码") == "download_repo"
    assert detect_github_task("下载吧") == "download_repo"


def test_parse_issue_payload():
    title, body = _parse_issue_payload("给这个仓库创建一个 issue，标题是学习辅导引用错误，内容是不要显示无关引用")

    assert title == "学习辅导引用错误"
    assert body == "不要显示无关引用"


def test_parse_issue_payload_with_create_one_issue():
    title, body = _parse_issue_payload("创建一个 issue，标题是优化助手，内容是补充 GitHub 模块测试")

    assert title == "优化助手"
    assert body == "补充 GitHub 模块测试"


def test_auto_mode_detects_github():
    message = "分析仓库 https://github.com/openai/openai-python"

    assert should_use_github(message)
    assert detect_auto_mode(message) == "github"


def test_download_known_public_repo_intent():
    message = "我想学习 Dify，下载 Dify 的代码"
    repo = _repo_from_known_name(message)

    assert should_use_github(message)
    assert detect_auto_mode(message) == "github"
    assert repo is not None
    assert repo.full_name == "langgenius/dify"


if __name__ == "__main__":
    import traceback

    failed = 0
    current = globals()
    for name in sorted(key for key in current if key.startswith("test_")):
        try:
            current[name]()
            print(f"PASS {name}")
        except Exception:
            failed += 1
            print(f"FAIL {name}")
            traceback.print_exc()
    raise SystemExit(1 if failed else 0)
