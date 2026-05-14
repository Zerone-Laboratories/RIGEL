"""Unit tests for the core.os_tools module."""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# core/os_tools.py creates a module-level SysLog that writes to Logs/rigel.log.
# In environments where that file is root-owned (e.g. Docker), import fails.
# Pre-populate sys.modules with a mock so the module import succeeds.
# ---------------------------------------------------------------------------
_mock_syslog = MagicMock()
_mock_logger_module = MagicMock()
_mock_logger_module.SysLog = MagicMock(return_value=_mock_syslog)
_mock_logger_module.ColoredFormatter = MagicMock()

with patch.dict(sys.modules, {"core.logger": _mock_logger_module}):
    from core.os_tools import OSTools


class TestOSToolsInit:
    def test_default_init(self):
        tools = OSTools()
        assert tools.max_execution_time == 30
        assert tools.temp_files == []

    def test_custom_max_execution_time(self):
        tools = OSTools(max_execution_time=10)
        assert tools.max_execution_time == 10

    def test_custom_temp_dir(self, temp_dir):
        tools = OSTools(temp_dir=temp_dir)
        assert tools.temp_dir == temp_dir


class TestExecuteCommand:
    def test_simple_echo(self):
        tools = OSTools()
        result = tools.execute_command("echo hello")
        assert result["success"] is True
        assert result["exit_code"] == 0
        assert "hello" in result["stdout"]

    def test_command_not_found(self):
        tools = OSTools()
        result = tools.execute_command("nonexistent_command_xyz_123")
        assert result["success"] is False

    def test_timeout(self):
        tools = OSTools(max_execution_time=1)
        result = tools.execute_command("sleep 3", timeout=1)
        assert result["success"] is False
        assert "timed out" in result.get("error", "")

    def test_working_dir(self, temp_dir):
        tools = OSTools()
        result = tools.execute_command("pwd", working_dir=temp_dir)
        assert result["success"] is True
        assert temp_dir in result["stdout"]

    def test_stderr_captured(self):
        tools = OSTools()
        result = tools.execute_command("echo error >&2; exit 1")
        assert result["success"] is False
        assert result["exit_code"] == 1
        assert "error" in result["stderr"]


class TestCreateTempProgram:
    def test_creates_python_file(self):
        tools = OSTools()
        result = tools.create_temp_program("print('hello')", ".py")
        assert result["success"] is True
        assert os.path.exists(result["file_path"])
        assert result["file_name"].startswith("rigel_temp_")
        assert result["file_name"].endswith(".py")
        tools.cleanup()

    def test_content_written(self):
        tools = OSTools()
        content = "print('test content')"
        result = tools.create_temp_program(content, ".py")
        with open(result["file_path"]) as f:
            assert f.read() == content
        tools.cleanup()

    def test_custom_temp_dir(self, temp_dir):
        tools = OSTools(temp_dir=temp_dir)
        result = tools.create_temp_program("x=1", ".py")
        assert result["file_path"].startswith(temp_dir)
        tools.cleanup()


class TestCreateAndExecuteProgram:
    def test_execute_python(self):
        tools = OSTools()
        result = tools.create_and_execute_program(
            "print('hello from temp')", ".py", cleanup=True
        )
        assert result["success"] is True
        assert "hello from temp" in result["stdout"]
        assert result.get("cleanup") == "success"

    def test_execute_with_args(self):
        tools = OSTools()
        code = "import sys; print(sys.argv[1:])"
        result = tools.create_and_execute_program(
            code, ".py", args=["arg1", "arg2"], cleanup=True
        )
        assert result["success"] is True
        assert "arg1" in result["stdout"]
        assert "arg2" in result["stdout"]

    def test_execute_nonexistent_file(self):
        tools = OSTools()
        result = tools.execute_temp_program("/nonexistent/file.py")
        assert result["success"] is False
        assert "not found" in result.get("error", "")


class TestGetDetailedSystemInfo:
    def test_returns_success(self):
        tools = OSTools()
        result = tools.get_detailed_system_info()
        assert result["success"] is True
        info = result["info"]
        assert "platform" in info
        assert "python" in info
        assert "environment" in info


class TestFormatUptime:
    def test_seconds_only(self):
        tools = OSTools()
        assert "30 seconds" in tools._format_uptime(30)

    def test_minutes_and_seconds(self):
        tools = OSTools()
        result = tools._format_uptime(125)
        assert "2 minutes" in result
        assert "5 seconds" in result

    def test_days(self):
        tools = OSTools()
        result = tools._format_uptime(86400 * 2 + 3600)
        assert "2 days" in result
        assert "1 hour" in result

    def test_zero(self):
        tools = OSTools()
        assert "0 seconds" in tools._format_uptime(0)


class TestCleanup:
    def test_cleanup_empty(self):
        tools = OSTools()
        result = tools.cleanup()
        assert result["success"] is True
        assert result["deleted"] == []

    def test_cleanup_removes_files(self):
        tools = OSTools()
        create_result = tools.create_temp_program("x=1", ".py")
        filepath = create_result["file_path"]
        assert os.path.exists(filepath)
        result = tools.cleanup()
        assert filepath in result["deleted"]
        assert not os.path.exists(filepath)
