"""Tests for Step 8: GitHub Issues Analytics (PR exclusion, parsing, aggregation, endpoints)."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db.session import init_db
from app.models.github import GitHubIssue, GitHubRepository
from app.services.analytics import calculate_issue_analytics


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    init_db()


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def _repo(name="demo-repo", full="alice/demo-repo"):
    return GitHubRepository(
        id=1,
        name=name,
        full_name=full,
        description=None,
        html_url=f"https://github.com/{full}",
        language="Python",
        stargazers_count=5,
        forks_count=1,
        open_issues_count=2,
        watchers_count=5,
        size=10,
        default_branch="main",
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-02T00:00:00Z",
        pushed_at="2024-01-02T00:00:00Z",
        fork=False,
        archived=False,
    )


def _issues_payload():
    return [
        {
            "id": 101,
            "number": 7,
            "title": "Bug: crash on empty input",
            "state": "open",
            "user": {"login": "alice", "avatar_url": "https://avatars/u/1"},
            "labels": [{"name": "bug"}, {"name": "good first issue"}],
            "created_at": "2024-05-01T10:00:00Z",
            "updated_at": "2024-05-03T10:00:00Z",
            "closed_at": None,
            "html_url": "https://github.com/alice/demo-repo/issues/7",
        },
        {
            # A pull request masquerading as an issue — must be excluded
            "id": 102,
            "number": 8,
            "title": "Fix crash",
            "state": "open",
            "user": {"login": "bob"},
            "labels": [],
            "created_at": "2024-05-02T10:00:00Z",
            "updated_at": "2024-05-02T11:00:00Z",
            "closed_at": None,
            "html_url": "https://github.com/alice/demo-repo/pull/8",
            "pull_request": {"url": "https://api.github.com/repos/alice/demo-repo/pulls/8"},
        },
        {
            "id": 103,
            "number": 6,
            "title": "Docs update",
            "state": "closed",
            "user": {"login": "carol"},
            "labels": "documentation",  # tolerate legacy string shape
            "created_at": "2024-04-01T10:00:00Z",
            "updated_at": "2024-04-02T10:00:00Z",
            "closed_at": "2024-04-02T12:00:00Z",
            "html_url": "https://github.com/alice/demo-repo/issues/6",
        },
    ]


def test_prs_excluded_and_fields_parsed():
    from app.services import github as gh_service

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.ok = True
    fake_resp.json.return_value = _issues_payload()

    with (
        patch.object(gh_service, "get_github_repositories", return_value=[_repo()]),
        patch("app.services.github._github_get", return_value=fake_resp),
    ):
        gh_service.clear_github_cache()
        issues, partial = gh_service.get_github_issues("alice", limit=30)

    assert partial is False
    assert len(issues) == 2  # PR excluded
    assert all("pull" not in i.html_url for i in issues)
    by_number = {i.number: i for i in issues}
    bug = by_number[7]
    assert bug.title == "Bug: crash on empty input"
    assert bug.state == "open"
    assert bug.repository_name == "demo-repo"
    assert bug.author_login == "alice"
    assert bug.labels == ["bug", "good first issue"]
    assert bug.created_at.startswith("2024-05-01")
    assert bug.closed_at is None
    assert bug.is_user_author is True
    docs = by_number[6]
    assert docs.state == "closed"
    assert docs.closed_at == "2024-04-02T12:00:00Z"
    assert docs.is_user_author is False


def test_issue_analytics_grouping_and_math():
    issues = [
        GitHubIssue(
            id=1, number=1, title="a", state="open", repository_name="Repo-A",
            repository_url="https://github.com/x/Repo-A", author_login="alice",
            author_avatar_url=None, labels=["bug", "ui"], created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-02T00:00:00Z", closed_at=None,
            html_url="https://github.com/x/Repo-A/issues/1", is_user_author=True,
        ),
        GitHubIssue(
            id=2, number=2, title="b", state="closed", repository_name="Repo-A",
            repository_url="https://github.com/x/Repo-A", author_login="bob",
            author_avatar_url=None, labels=["bug"], created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-03T00:00:00Z", closed_at="2024-01-03T00:00:00Z",
            html_url="https://github.com/x/Repo-A/issues/2", is_user_author=False,
        ),
        GitHubIssue(
            id=3, number=3, title="c", state="open", repository_name="Repo-B",
            repository_url="https://github.com/x/Repo-B", author_login="alice",
            author_avatar_url=None, labels=[], created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-04T00:00:00Z", closed_at=None,
            html_url="https://github.com/x/Repo-B/issues/3", is_user_author=True,
        ),
    ]
    result = calculate_issue_analytics("alice", issues)

    assert result.total_issues == 3
    assert result.open_issues == 2
    assert result.closed_issues == 1
    assert result.open_issues + result.closed_issues == result.total_issues

    # Repo grouping sums back to the total
    assert sum(r.total_count for r in result.issues_by_repository) == 3
    repo_a = next(r for r in result.issues_by_repository if r.repository_name == "Repo-A")
    assert (repo_a.open_count, repo_a.closed_count, repo_a.total_count) == (1, 1, 2)
    # Ranked: Repo-A (2) before Repo-B (1)
    assert result.issues_by_repository[0].repository_name == "Repo-A"

    # Label grouping: bug x2, ui x1, ranked desc
    assert result.issues_by_label[0].label == "bug"
    assert result.issues_by_label[0].count == 2
    assert sum(l.count for l in result.issues_by_label) == 3  # 2 labels on issue 1 + 1 on issue 2


def test_issues_endpoints_mocked(client):
    with (
        patch("app.api.routes.github.get_github_repositories", return_value=[_repo()]),
        patch("app.api.routes.github.get_github_issues") as mock_issues,
    ):
        from app.services import github as gh_service

        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.ok = True
        fake_resp.json.return_value = _issues_payload()
        with patch("app.services.github._github_get", return_value=fake_resp):
            gh_service.clear_github_cache()
            parsed, _ = gh_service.get_github_issues("alice")
        mock_issues.return_value = (parsed, False)

        res = client.get("/api/github/issues/alice?limit=10")
        assert res.status_code == 200
        body = res.json()
        assert body["username"] == "alice"
        assert body["total_issues"] == 2
        assert body["open_issues"] == 1
        assert body["closed_issues"] == 1
        assert body["open_issues"] + body["closed_issues"] == body["total_issues"]
        first = body["issues"][0]
        for field in (
            "title", "repository_name", "state", "author_login", "labels",
            "created_at", "updated_at", "closed_at", "html_url",
        ):
            assert field in first

        res2 = client.get("/api/github/issues/alice/analytics")
        assert res2.status_code == 200
        agg = res2.json()
        assert agg["total_issues"] == 2
        assert agg["open_issues"] + agg["closed_issues"] == agg["total_issues"]
        assert agg["issues_by_repository"][0]["total_count"] >= 1
        assert any(l["label"] == "bug" for l in agg["issues_by_label"])


def test_issues_limit_bounds(client):
    assert client.get("/api/github/issues/alice?limit=0").status_code == 422
    assert client.get("/api/github/issues/alice?limit=100").status_code == 422
    assert client.get("/api/github/issues/alice/analytics?limit=0").status_code == 422


def test_rate_limit_sets_partial_flag():
    from app.services import github as gh_service

    limited = MagicMock()
    limited.status_code = 403
    limited.ok = False

    with (
        patch.object(gh_service, "get_github_repositories", return_value=[_repo()]),
        patch("app.services.github._github_get", return_value=limited),
    ):
        gh_service.clear_github_cache()
        issues, partial = gh_service.get_github_issues("alice")
    assert issues == []
    assert partial is True
