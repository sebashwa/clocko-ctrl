import unittest
from render_helpers import TextFormatting, TextScrolling

class TestTextFormatting(unittest.TestCase):
    def test_split_for_wrapping_splits_long_text_into_segments(self):
        text = "This is very long text which is probably split"
        result = TextFormatting.split_for_wrapping(text, 16)

        assert result == ["This is very", "long text which", "is probably", "split"]

class TestTextScrolling(unittest.TestCase):
    def test_scroll_shows_the_next_segment_when_direction_is_forward(self):
        TextScrolling.maybe_scroll("This text should scroll", 16)
        TextScrolling.forwards = True
        TextScrolling.current_index = 1
        assert TextScrolling.scroll() == "is text should s"

    def test_scroll_shows_the_previous_segment_if_direction_is_backwards(self):
        TextScrolling.maybe_scroll("This text should scroll", 16)
        TextScrolling.forwards = False
        TextScrolling.current_index = 2
        assert TextScrolling.scroll() == "his text should "

    def test_scroll_shows_start_of_text_for_three_calls(self):
        TextScrolling.maybe_scroll("This text should scroll", 16)
        TextScrolling.forwards = True
        TextScrolling.current_index = 0

        assert TextScrolling.scroll() == "This text should"
        assert TextScrolling.scroll() == "This text should"
        assert TextScrolling.scroll() == "his text should "

    def test_scroll_shows_end_of_text_for_three_calls(self):
        TextScrolling.maybe_scroll("This text should scroll", 16)
        TextScrolling.forwards = False
        TextScrolling.current_index = 7

        assert TextScrolling.scroll() == "xt should scroll"
        assert TextScrolling.scroll() == "xt should scroll"
        assert TextScrolling.scroll() == "ext should scrol"

if __name__ == '__main__':
    unittest.main()
