"""Unit tests for the core.logger module."""

import logging
import pytest
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
        # Should have at least a console handler
        assert len(syslog.logger.handlers) >= 1
        # Clean up handlers to avoid leaking
        for h in syslog.logger.handlers[:]:
            syslog.logger.removeHandler(h)

    def test_create_syslog_with_file(self, temp_dir):
        import os
        log_file = os.path.join(temp_dir, "test.log")
        syslog = SysLog(name="FileLog", log_file=log_file)
        # Should create a file handler in addition to console
        assert len(syslog.logger.handlers) >= 2  # console + file
        file_handlers = [h for h in syslog.logger.handlers
                         if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) >= 1, "Expected a FileHandler to be created"
        # Clean up handlers to avoid leaking
        for h in syslog.logger.handlers[:]:
            h.close()
            syslog.logger.removeHandler(h)

    def test_create_syslog_with_absolute_path(self, temp_dir):
        import os
        log_file = os.path.join(temp_dir, "abs_test.log")
        syslog = SysLog(name="AbsLog", log_file=log_file)
        assert len(syslog.logger.handlers) >= 2
        for h in syslog.logger.handlers[:]:
            h.close()
            syslog.logger.removeHandler(h)

    def test_create_syslog_with_custom_level(self):
        syslog = SysLog(name="DebugLog", level=logging.DEBUG)
        assert syslog.logger.level == logging.DEBUG
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

    @pytest.mark.parametrize("level,level_name", [
        (logging.DEBUG, "DEBUG"),
        (logging.INFO, "INFO"),
        (logging.WARNING, "WARNING"),
        (logging.ERROR, "ERROR"),
        (logging.CRITICAL, "CRITICAL"),
    ])
    def test_all_log_levels_supported(self, level, level_name):
        syslog = SysLog(name=f"Level{level_name}", level=level)
        assert syslog.logger.level == level
        # Each log method should work without error
        syslog.debug("test")
        syslog.info("test")
        syslog.warning("test")
        syslog.error("test")
        syslog.critical("test")
        for h in syslog.logger.handlers[:]:
            syslog.logger.removeHandler(h)
