"""Unit and integration tests for GitHub commits and developer activity analytics."""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.models.github import GitHubCommit, GitHubRepository
from app.services.analytics import calculate_user_activity


@pytest.fixture
def client():
    """TestClient fixture with application context."""
    with TestClient(app) as test_client:
        yield test_client


def test_author_distinction_and_aggregation():
    """Verify that calculate_user_activity accurately distinguishes commit authors from repository owners."""
    username = "alice"

    # Repo owned by Alice, but with commits from both Alice and Bob (contributor)
    dummy_repos = [
        GitHubRepository(
            id=101,
            name="alice-project",
            full_name="alice/alice-project",
            description="Alice's flagship repo",
            html_url="https://github.com/alice/alice-project",
            language="TypeScript",
            stargazers_count=42,
            forks_count=5,
            open_issues_count=1,
            watchers_count=42,
            size=1200,
            default_branch="main",
            created_at="2025-01-01T00:00:00Z",
            updated_at="2026-03-01T00:00:00Z",
            pushed_at="2026-03-01T00:00:00Z",
            fork=False,
            archived=False,
        ),
        GitHubRepository(
            id=102,
            name="another-repo",
            full_name="alice/another-repo",
            description="Second repo",
            html_url="https://github.com/alice/another-repo",
            language="Python",
            stargazers_count=10,
            forks_count=1,
            open_issues_count=0,
            watchers_count=10,
            size=800,
            default_branch="main",
            created_at="2025-02-01T00:00:00Z",
            updated_at="2026-03-02T00:00:00Z",
            pushed_at="2026-03-02T00:00:00Z",
            fork=False,
            archived=False,
        ),
    ]

    dummy_commits = [
        # Commit 1 by Alice
        GitHubCommit(
            sha="1111111111111111",
            short_sha="1111111",
            message="Feature: Alice initial commit",
            repository_name="alice-project",
            repository_url="https://github.com/alice/alice-project",
            author_name="Alice Dev",
            author_login="alice",
            author_avatar_url="https://avatars.githubusercontent.com/u/1?v=4",
            committed_date="2026-02-15T10:00:00Z",
            html_url="https://github.com/alice/alice-project/commit/1111111111111111",
            is_user_author=True,
        ),
        # Commit 2 by Bob (contributor to Alice's repo)
        GitHubCommit(
            sha="2222222222222222",
            short_sha="2222222",
            message="Fix: Bug fix by Bob",
            repository_name="alice-project",
            repository_url="https://github.com/alice/alice-project",
            author_name="Bob Contributor",
            author_login="bob",
            author_avatar_url="https://avatars.githubusercontent.com/u/2?v=4",
            committed_date="2026-02-16T12:00:00Z",
            html_url="https://github.com/alice/alice-project/commit/2222222222222222",
            is_user_author=False,  # Not Alice!
        ),
        # Commit 3 by Alice in another repo
        GitHubCommit(
            sha="3333333333333333",
            short_sha="3333333",
            message="Docs: Alice updated readme",
            repository_name="another-repo",
            repository_url="https://github.com/alice/another-repo",
            author_name="Alice Dev",
            author_login="alice",
            author_avatar_url="https://avatars.githubusercontent.com/u/1?v=4",
            committed_date="2026-03-01T15:00:00Z",
            html_url="https://github.com/alice/another-repo/commit/3333333333333333",
            is_user_author=True,
        ),
    ]

    activity = calculate_user_activity(username, dummy_commits, dummy_repos, partial=False)

    # 1. Total commits vs user-authored commits
    assert activity.total_commits == 3
    assert activity.user_commits == 2  # Only Alice's 2 commits, Bob's is excluded from user_commits!

    # 2. Daily breakdown checks
    feb15 = next(d for d in activity.daily_commits if d.date == "2026-02-15")
    assert feb15.count == 1
    assert feb15.user_count == 1

    feb16 = next(d for d in activity.daily_commits if d.date == "2026-02-16")
    assert feb16.count == 1
    assert feb16.user_count == 0  # Bob's commit, so user_count is 0!

    mar01 = next(d for d in activity.daily_commits if d.date == "2026-03-01")
    assert mar01.count == 1
    assert mar01.user_count == 1

    # 3. Monthly breakdown checks
    feb_month = next(m for m in activity.monthly_totals if m.month == "2026-02")
    assert feb_month.count == 2
    assert feb_month.user_count == 1

    mar_month = next(m for m in activity.monthly_totals if m.month == "2026-03")
    assert mar_month.count == 1
    assert mar_month.user_count == 1

    # 4. Most active repositories ranking
    assert len(activity.most_active_repositories) == 2
    top_repo = activity.most_active_repositories[0]
    assert top_repo.repository_name == "alice-project"
    assert top_repo.commit_count == 2
    assert top_repo.stars == 42
    assert top_repo.language == "TypeScript"

    second_repo = activity.most_active_repositories[1]
    assert second_repo.repository_name == "another-repo"
    assert second_repo.commit_count == 1
    assert second_repo.stars == 10


def test_commits_endpoint_mocked(client):
    """Verify GET /api/github/commits/{username} route returns properly formatted response."""
    mock_commits = [
        GitHubCommit(
            sha="abcdef1234567890",
            short_sha="abcdef1",
            message="Initial project commit",
            repository_name="demo-repo",
            repository_url="https://github.com/mockuser/demo-repo",
            author_name="Mock Developer",
            author_login="mockuser",
            author_avatar_url="https://avatars.githubusercontent.com/u/999?v=4",
            committed_date="2026-03-10T12:00:00Z",
            html_url="https://github.com/mockuser/demo-repo/commit/abcdef1234567890",
            is_user_author=True,
        )
    ]

    with patch("app.api.routes.github.get_github_commits", return_value=(mock_commits, False)):
        response = client.get("/api/github/commits/mockuser")
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "mockuser"
        assert data["total_commits"] == 1
        assert data["user_commits"] == 1
        assert len(data["commits"]) == 1
        assert data["commits"][0]["short_sha"] == "abcdef1"
        assert data["commits"][0]["is_user_author"] is True
        assert data["partial"] is False


def test_activity_endpoint_mocked(client):
    """Verify GET /api/github/activity/{username} route returns aggregated activity."""
    mock_commits = [
        GitHubCommit(
            sha="abcdef1234567890",
            short_sha="abcdef1",
            message="Initial project commit",
            repository_name="demo-repo",
            repository_url="https://github.com/mockuser/demo-repo",
            author_name="Mock Developer",
            author_login="mockuser",
            author_avatar_url="https://avatars.githubusercontent.com/u/999?v=4",
            committed_date="2026-03-10T12:00:00Z",
            html_url="https://github.com/mockuser/demo-repo/commit/abcdef1234567890",
            is_user_author=True,
        )
    ]
    mock_repos = [
        GitHubRepository(
            id=999,
            name="demo-repo",
            full_name="mockuser/demo-repo",
            description="Mock repo",
            html_url="https://github.com/mockuser/demo-repo",
            language="Python",
            stargazers_count=15,
            forks_count=2,
            open_issues_count=0,
            watchers_count=15,
            size=500,
            default_branch="main",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-03-10T00:00:00Z",
            pushed_at="2026-03-10T00:00:00Z",
            fork=False,
            archived=False,
        )
    ]

    with patch("app.api.routes.github.get_github_repositories", return_value=mock_repos):
        with patch("app.api.routes.github.get_github_commits", return_value=(mock_commits, False)):
            response = client.get("/api/github/activity/mockuser")
            assert response.status_code == 200
            data = response.json()
            assert data["username"] == "mockuser"
            assert data["total_commits"] == 1
            assert data["user_commits"] == 1
            assert len(data["daily_commits"]) == 1
            assert data["daily_commits"][0]["date"] == "2026-03-10"
            assert len(data["monthly_totals"]) == 1
            assert data["monthly_totals"][0]["month"] == "2026-03"
            assert len(data["most_active_repositories"]) == 1
            assert data["most_active_repositories"][0]["repository_name"] == "demo-repo"
            assert data["most_active_repositories"][0]["stars"] == 15


def test_commits_endpoint_nonexistent_user(client):
    """Verify 404 response when querying commits for an invalid user."""
    invalid_user = "user-that-definitely-does-not-exist-9876543210"
    response = client.get(f"/api/github/commits/{invalid_user}")
    assert response.status_code == 404
