import asyncio
import hashlib
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from db.models import Project
from services.monitoring import MonitoringService


def _make_project(**kwargs):
    defaults = {
        "external_id": "123",
        "title": "Test Project",
        "description": "Some description",
        "url": "https://example.com",
        "budget": "N/A",
        "source": "freelancehunt",
    }
    defaults.update(kwargs)
    return Project(**defaults)


def _make_service(**kwargs):
    defaults = {
        "bot": MagicMock(),
        "chat_id": 1,
        "parsers": [],
        "repository": AsyncMock(),
        "blacklist": ["design", "figma", "photoshop", "logo", "banner",
                      "smm", "seo", "copywriting", "illustration", "3d", "motion"],
        "whitelist": ["python", "ai", "bot", "telegram", "automation",
                      "api", "parser", "scraping", "crm", "backend", "integration"],
        "polling_interval": 60,
        "priority_threshold": 1,
        "ignored_log_interval_hours": 6,
    }
    defaults.update(kwargs)
    return MonitoringService(**defaults)


class TestContentHash:
    def test_hash_deterministic(self):
        p = _make_project(title="A", description="B", budget="100")
        h1 = MonitoringService._compute_content_hash(p)
        h2 = MonitoringService._compute_content_hash(p)
        assert h1 == h2

    def test_hash_changes_on_title(self):
        p1 = _make_project(title="A", description="B", budget="100")
        p2 = _make_project(title="C", description="B", budget="100")
        assert MonitoringService._compute_content_hash(p1) != MonitoringService._compute_content_hash(p2)

    def test_hash_changes_on_budget(self):
        p1 = _make_project(title="A", description="B", budget="100")
        p2 = _make_project(title="A", description="B", budget="200")
        assert MonitoringService._compute_content_hash(p1) != MonitoringService._compute_content_hash(p2)

    def test_hash_is_sha256(self):
        p = _make_project(title="T", description="D", budget="B")
        expected = hashlib.sha256("T|D|B".encode("utf-8")).hexdigest()
        assert MonitoringService._compute_content_hash(p) == expected


class TestScoring:
    def test_ai_in_title_scores_2(self):
        p = _make_project(title="AI project", description="")
        assert MonitoringService._calculate_score(p, 0) == 2

    def test_python_in_description_scores_1(self):
        p = _make_project(title="Project", description="needs python dev")
        assert MonitoringService._calculate_score(p, 0) == 1

    def test_bot_in_combined_scores_1(self):
        p = _make_project(title="Telegram bot", description="")
        assert MonitoringService._calculate_score(p, 0) == 1

    def test_automation_scores_1(self):
        p = _make_project(title="", description="automation needed")
        assert MonitoringService._calculate_score(p, 0) == 1

    def test_budget_above_threshold_scores_2(self):
        p = _make_project(title="", description="")
        assert MonitoringService._calculate_score(p, 15000) == 2

    def test_budget_below_threshold_scores_0(self):
        p = _make_project(title="", description="")
        assert MonitoringService._calculate_score(p, 5000) == 0

    def test_combined_high_score(self):
        p = _make_project(title="AI Bot", description="python automation")
        score = MonitoringService._calculate_score(p, 15000)
        assert score >= 3

    def test_zero_score(self):
        p = _make_project(title="Unknown", description="nothing relevant")
        assert MonitoringService._calculate_score(p, 0) == 0


class TestFiltering:
    def test_blacklisted_design(self):
        svc = _make_service()
        p = _make_project(title="Need design for website")
        assert svc._is_blacklisted(p) is True

    def test_blacklisted_figma(self):
        svc = _make_service()
        p = _make_project(description="Figma layout needed")
        assert svc._is_blacklisted(p) is True

    def test_not_blacklisted(self):
        svc = _make_service()
        p = _make_project(title="Python bot", description="telegram integration")
        assert svc._is_blacklisted(p) is False

    def test_whitelist_match_python(self):
        svc = _make_service()
        p = _make_project(title="Python developer needed")
        assert svc._matches_whitelist(p) is True

    def test_whitelist_match_bot(self):
        svc = _make_service()
        p = _make_project(description="build a bot")
        assert svc._matches_whitelist(p) is True

    def test_no_whitelist_match(self):
        svc = _make_service()
        p = _make_project(title="Cook needed", description="restaurant work")
        assert svc._matches_whitelist(p) is False

    def test_case_insensitive_blacklist(self):
        svc = _make_service()
        p = _make_project(title="DESIGN PROJECT")
        assert svc._is_blacklisted(p) is True

    def test_case_insensitive_whitelist(self):
        svc = _make_service()
        p = _make_project(title="PYTHON Developer")
        assert svc._matches_whitelist(p) is True


class TestLabels:
    def test_new_high(self):
        label = MonitoringService._format_label("NEW", 3)
        assert "[NEW | HIGH]" in label
        assert "🆕" in label

    def test_new_medium(self):
        label = MonitoringService._format_label("NEW", 1)
        assert "[NEW | MEDIUM]" in label

    def test_updated_high(self):
        label = MonitoringService._format_label("UPDATED", 5)
        assert "[UPDATED | HIGH]" in label
        assert "🔄" in label

    def test_updated_medium(self):
        label = MonitoringService._format_label("UPDATED", 2)
        assert "[UPDATED | MEDIUM]" in label


class TestBudgetExtraction:
    def test_simple_number(self):
        assert MonitoringService._extract_budget_value("15000 грн") == 15000

    def test_na(self):
        assert MonitoringService._extract_budget_value("N/A") == 0

    def test_with_spaces(self):
        assert MonitoringService._extract_budget_value("15 000 грн") == 15000


class TestAntiDuplicateLogging:
    def test_first_log_is_emitted(self):
        svc = _make_service(ignored_log_interval_hours=1)
        with patch("services.monitoring.logger") as mock_logger:
            svc._log_ignored("123", "blacklisted")
            mock_logger.info.assert_called_once()

    def test_duplicate_log_suppressed(self):
        svc = _make_service(ignored_log_interval_hours=1)
        with patch("services.monitoring.logger") as mock_logger:
            svc._log_ignored("123", "blacklisted")
            svc._log_ignored("123", "blacklisted")
            assert mock_logger.info.call_count == 1

    def test_different_ids_both_logged(self):
        svc = _make_service(ignored_log_interval_hours=1)
        with patch("services.monitoring.logger") as mock_logger:
            svc._log_ignored("123", "blacklisted")
            svc._log_ignored("456", "blacklisted")
            assert mock_logger.info.call_count == 2


class TestProcessProjectsOrder:
    @pytest.mark.asyncio
    async def test_skip_unchanged_project_silently(self):
        repo = AsyncMock()
        content_hash = hashlib.sha256("T|D|B".encode()).hexdigest()
        repo.get_content_hash.return_value = content_hash

        parser = AsyncMock()
        parser.fetch_projects.return_value = [
            _make_project(title="T", description="D", budget="B")
        ]

        bot = AsyncMock()
        svc = _make_service(bot=bot, parsers=[parser], repository=repo)

        await svc._process_projects()
        bot.send_message.assert_not_called()
        repo.save_project.assert_not_called()

    @pytest.mark.asyncio
    async def test_new_project_passes_filters_and_sends(self):
        repo = AsyncMock()
        repo.get_content_hash.return_value = None

        parser = AsyncMock()
        parser.fetch_projects.return_value = [
            _make_project(title="Python bot", description="telegram automation")
        ]

        bot = AsyncMock()
        svc = _make_service(bot=bot, parsers=[parser], repository=repo)

        await svc._process_projects()
        repo.save_project.assert_called_once()
        bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_updated_project_sends(self):
        repo = AsyncMock()
        repo.get_content_hash.return_value = "old_hash"

        parser = AsyncMock()
        parser.fetch_projects.return_value = [
            _make_project(title="Python bot", description="telegram automation")
        ]

        bot = AsyncMock()
        svc = _make_service(bot=bot, parsers=[parser], repository=repo)

        await svc._process_projects()
        repo.update_project.assert_called_once()
        bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_blacklisted_new_project_ignored(self):
        repo = AsyncMock()
        repo.get_content_hash.return_value = None

        parser = AsyncMock()
        parser.fetch_projects.return_value = [
            _make_project(title="Need figma design")
        ]

        bot = AsyncMock()
        svc = _make_service(bot=bot, parsers=[parser], repository=repo)

        await svc._process_projects()
        bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_whitelist_match_ignored(self):
        repo = AsyncMock()
        repo.get_content_hash.return_value = None

        parser = AsyncMock()
        parser.fetch_projects.return_value = [
            _make_project(title="Cook needed", description="restaurant work")
        ]

        bot = AsyncMock()
        svc = _make_service(bot=bot, parsers=[parser], repository=repo)

        await svc._process_projects()
        bot.send_message.assert_not_called()


class TestFormatProject:
    def test_message_contains_label(self):
        p = _make_project(title="Test", budget="1000")
        msg = MonitoringService._format_project(p, "🆕 [NEW | HIGH]")
        assert "[NEW | HIGH]" in msg
        assert "<b>Test</b>" in msg

    def test_message_truncated(self):
        p = _make_project(description="x" * 5000)
        msg = MonitoringService._format_project(p, "label")
        assert len(msg) <= 4000
