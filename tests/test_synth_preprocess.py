"""Unit tests for Synthesizer text preprocessing and chunking."""

import re
import math
import sys
import pytest
from unittest.mock import MagicMock

# core/synth_n_recog.py does `import whisper` at module level.
# Stub it persistently so all tests in this module can import from synth_n_recog.
_mock_whisper = MagicMock()
if "whisper" not in sys.modules:
    sys.modules["whisper"] = _mock_whisper

from core.synth_n_recog import Synthesizer, Recognizer


# ---------------------------------------------------------------------------
# Extract preprocess_for_synthesis so we can test it directly
# ---------------------------------------------------------------------------

def _preprocess(text):
    """Standalone copy of Synthesizer.synthesize's inner preprocess_for_synthesis."""
    # Strip numbered lists
    text = re.sub(r'^\s*\d+\.\s+.*$', '', text, flags=re.MULTILINE)
    # Strip bullet points
    text = re.sub(r'^\s*[-*•]\s+.*$', '', text, flags=re.MULTILINE)
    # Remove markdown bold/italic markers
    text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text)
    # Replace Latin abbreviations
    text = re.sub(r'\(e\.?g\.?\)', 'example', text, flags=re.IGNORECASE)
    text = re.sub(r'\beg\.(?![a-zA-Z])', 'example', text, flags=re.IGNORECASE)
    text = re.sub(r'\be\.g\.(?![a-zA-Z])', 'example', text, flags=re.IGNORECASE)
    # Remove inline code
    text = re.sub(r'`[^`]*`', '', text)
    # Remove markdown headings
    text = re.sub(r'^\s*#{1,6}\s+.*$', '', text, flags=re.MULTILINE)
    # Remove markdown links
    text = re.sub(r'\[.*?\]\((?:https?://|www\.)[^)]+\)', ' ', text)
    text = re.sub(r'https?://\S+|www\.\S+', ' ', text, flags=re.IGNORECASE)
    # Remove emoji
    emoji_pattern = re.compile(
        '[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF'
        '\U0001F1E0-\U0001F1FF\U00002700-\U000027BF\U00002600-\U000026FF'
        '\U0001F900-\U0001F9FF\U0001FA70-\U0001FAFF\U00002500-\U00002BEF'
        '\U0001F700-\U0001F77F]+',
        flags=re.UNICODE,
    )
    text = emoji_pattern.sub('', text)
    # Dashes → commas
    text = re.sub(r'\s*[—–]\s*', ', ', text)
    # Normalize curly apostrophes
    text = text.replace('’', "'").replace('‘', "'")
    # Remove stray punctuation
    text = re.sub(r"[^A-Za-z0-9\s\.\,\?\!\:\;\-']+", ' ', text)
    # Collapse multiple newlines
    text = re.sub(r'\n{2,}', '\n', text)
    # Strip whitespace from each line
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    result = ' '.join(lines)
    result = re.sub(r' {2,}', ' ', result)
    return result.strip()


class TestPreprocessForSynthesis:
    """Tests for the text preprocessing pipeline used before TTS."""

    def test_plain_text_passes_through(self):
        text = "Hello world, this is a test."
        out = _preprocess(text)
        assert "Hello world" in out
        assert "test" in out

    def test_removes_markdown_headings(self):
        text = "# Introduction\nThis is text."
        out = _preprocess(text)
        assert "Introduction" not in out
        assert "This is text" in out

    def test_removes_bullet_points(self):
        text = "- item one\n- item two\nPlain text."
        out = _preprocess(text)
        assert "item one" not in out
        assert "item two" not in out
        assert "Plain text" in out

    def test_removes_numbered_lists(self):
        text = "1. First item\n2. Second item\nConclusion."
        out = _preprocess(text)
        assert "First item" not in out
        assert "Second item" not in out
        assert "Conclusion" in out

    def test_removes_inline_code(self):
        text = "Run the `print()` function to output."
        out = _preprocess(text)
        assert "`" not in out
        assert "print" not in out
        assert "function" in out

    def test_removes_urls(self):
        text = "Visit https://example.com/page for more info."
        out = _preprocess(text)
        assert "https://example.com/page" not in out
        assert "more info" in out

    def test_removes_markdown_links(self):
        text = "Click [here](https://example.com) to proceed."
        out = _preprocess(text)
        assert "here" not in out
        assert "Click" in out

    def test_removes_bold_markers(self):
        text = "This is **bold** and *italic* text."
        out = _preprocess(text)
        assert "**" not in out
        assert "bold" in out
        assert "italic" in out

    def test_replaces_eg_at_end_of_sentence(self):
        # The original regex \beg\.\b requires a word boundary after the dot.
        # This means "eg." at end of string (before a newline) is matched
        # (end-of-string counts as a word boundary).
        text = "Here is an example eg.\nNext sentence."
        out = _preprocess(text)
        assert "example" in out

    def test_handles_eg_parenthetical_form(self):
        # The regex \(e\.?g\.?\) catches parenthetical form like "(e.g.)"
        text = "Use a tool (e.g.) for debugging."
        out = _preprocess(text)
        assert "(e.g.)" not in out
        assert "example" in out

    def test_normalizes_em_dash(self):
        text = "clear—your mind"
        out = _preprocess(text)
        assert "—" not in out
        assert "," in out

    def test_normalizes_curly_apostrophes(self):
        text = "it\u2019s a test"
        out = _preprocess(text)
        assert "\u2019" not in out
        assert "it's" in out

    def test_collapses_multiple_spaces(self):
        text = "word1    word2     word3"
        out = _preprocess(text)
        # After join, multiple spaces are collapsed
        assert "    " not in out

    def test_empty_string(self):
        out = _preprocess("")
        assert out == ""

    def test_only_special_chars(self):
        out = _preprocess("*** ~~~ ###")
        # After stripping formatting markers, should be essentially empty
        assert len(out) == 0 or out.isspace() or out == ""

    def test_multiline_collapsed(self):
        text = "Line one.\n\n\nLine two.\n\nLine three."
        out = _preprocess(text)
        # After processing, multi-newlines should collapse into single text
        assert "one" in out
        assert "two" in out
        assert "three" in out

    def test_emoji_removed(self):
        text = "Hello \U0001F600 world \U0001F30D test"
        out = _preprocess(text)
        assert "\U0001F600" not in out
        assert "\U0001F30D" not in out
        assert "Hello" in out
        assert "world" in out

    def test_multiple_eg_patterns(self):
        text = "Use e.g. this or eg. that or (e.g.) something."
        out = _preprocess(text)
        assert "e.g." not in out
        assert "eg." not in out
        assert "(e.g.)" not in out
        assert "example" in out

    def test_mixed_content_preserved(self):
        text = "The quick brown fox jumps over the lazy dog."
        out = _preprocess(text)
        assert "quick brown fox" in out
        assert "lazy dog" in out


class TestSplitTextIntoChunks:
    """Tests for _split_text_into_chunks."""

    def test_empty_text(self):
        synth = Synthesizer()
        chunks = synth._split_text_into_chunks("", max_words=80)
        assert chunks == []

    def test_single_sentence(self):
        synth = Synthesizer()
        chunks = synth._split_text_into_chunks("Hello world.", max_words=80)
        assert len(chunks) == 1
        assert "Hello world" in chunks[0]

    def test_multiple_sentences_under_limit(self):
        synth = Synthesizer()
        text = "Hello world. How are you? I am fine."
        chunks = synth._split_text_into_chunks(text, max_words=80)
        assert len(chunks) == 1
        assert chunks[0] == "Hello world. How are you? I am fine."

    def test_splits_at_sentence_boundary(self):
        synth = Synthesizer()
        # Each sentence has 3 words, max_words=5 should force split
        text = "One two three. Four five six. Seven eight nine."
        chunks = synth._split_text_into_chunks(text, max_words=5)
        assert len(chunks) >= 2  # Should split at a sentence boundary

    def test_oversized_sentence_split(self):
        synth = Synthesizer()
        words = " ".join(f"word{i}" for i in range(20))
        chunks = synth._split_text_into_chunks(words, max_words=8)
        assert len(chunks) == 3  # 8+8+4
        assert all(len(chunk.split()) <= 8 for chunk in chunks)

    def test_strips_whitespace(self):
        synth = Synthesizer()
        chunks = synth._split_text_into_chunks("  Hello world.   ", max_words=80)
        assert chunks[0] == "Hello world."

    def test_exactly_at_limit(self):
        synth = Synthesizer()
        text = "One two three four five six seven eight."
        chunks = synth._split_text_into_chunks(text, max_words=8)
        assert len(chunks) == 1
        assert "eight" in chunks[0]

    def test_none_input_returns_empty(self):
        synth = Synthesizer()
        chunks = synth._split_text_into_chunks(None, max_words=80)
        assert chunks == []

    @pytest.mark.parametrize("max_words", [1, 5, 10, 20, 50])
    def test_various_limits(self, max_words):
        synth = Synthesizer()
        words = " ".join(f"word{i}" for i in range(30))
        chunks = synth._split_text_into_chunks(words, max_words=max_words)
        # Every chunk should respect the word limit
        for chunk in chunks:
            assert len(chunk.split()) <= max_words, \
                f"Chunk has {len(chunk.split())} words, limit is {max_words}"


class TestRecognizerConfidence:
    """Tests for Recognizer._extract_confidence."""

    def test_extracts_from_segments_avg_logprob(self):
        import math

        rec = Recognizer()
        result = {
            "segments": [
                {"avg_logprob": -0.5},
                {"avg_logprob": -1.0},
            ]
        }
        conf = rec._extract_confidence(result)
        expected = (math.exp(-0.5) + math.exp(-1.0)) / 2
        assert abs(conf - expected) < 0.001

    def test_extracts_from_segments_confidence(self):
        rec = Recognizer()
        result = {
            "segments": [
                {"confidence": 0.9},
                {"confidence": 0.7},
            ]
        }
        conf = rec._extract_confidence(result)
        assert conf == 0.8

    def test_falls_back_to_avg_logprob(self):
        import math

        rec = Recognizer()
        result = {"avg_logprob": -2.0}
        conf = rec._extract_confidence(result)
        assert abs(conf - math.exp(-2.0)) < 0.001

    def test_no_confidence_returns_zero(self):
        rec = Recognizer()
        result = {}
        conf = rec._extract_confidence(result)
        assert conf == 0.0
