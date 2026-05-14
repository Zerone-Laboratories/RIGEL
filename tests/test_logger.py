"""Unit tests for the core.logger module."""

import logging
from core.logger import ColoredFormatter, SysLog


class TestColoredFormatter:
    def test_formats_debug_level(self):
        fmt = ColoredFormatter("%(levelname)s - %(message)s")
        record = logging.LogRecord(
            "test", logging.DEBUG, "path", 1, "hello", (), None
        )
        output = fmt.format(record)
        assert "hello" in output
        assert "DEBUG" in output

    def test_formats_info_level(self):
        fmt = ColoredFormatter("%(levelname)s - %(message)s")
        record = logging.LogRecord(
            "test", logging.INFO, "path", 1, "info msg", (), None
        )
        output = fmt.format(record)
        assert "info msg" in output
        assert "INFO" in output

    def test_formats_error_level(self):
        fmt = ColoredFormatter("%(levelname)s - %(message)s")
        record = logging.LogRecord(
            "test", logging.ERROR, "path", 1, "bad thing", (), None
        )
        output = fmt.format(record)
        assert "bad thing" in output
        assert "ERROR" in output

    def test_has_level_colors_for_all_levels(self):
        """Every standard level should have a color mapping."""
        for level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            assert level in ColoredFormatter.LEVEL_COLORS


class TestSysLog:
    def test_create_syslog_default(self):
        syslog = SysLog(name="TestLog")
        assert isinstance(syslog.logger, logging.Logger)
        assert syslog.logger.name == "TestLog"

    def test_create_syslog_with_file(self, temp_dir):
        import os
        log_file = os.path.join(temp_dir, "test.log")
        syslog = SysLog(name="FileLog", log_file=log_file)
        # Should create a handler
        assert len(syslog.logger.handlers) >= 2  # console + file
        # Clean up handlers to avoid leaking
        for h in syslog.logger.handlers[:]:
            syslog.logger.removeHandler(h)

    def test_log_methods_dont_raise(self):
        syslog = SysLog(name="MethodTest")
        syslog.debug("debug")
        syslog.info("info")
        syslog.warning("warning")
        syslog.error("error")
        syslog.critical("critical")
        # Clean up
        for h in syslog.logger.handlers[:]:
            syslog.logger.removeHandler(h)
