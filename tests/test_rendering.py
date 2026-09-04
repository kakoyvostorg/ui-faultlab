import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.state import initial_state
from ui_faultlab.rendering import Canvas, render_calendar


class RenderingTest(unittest.TestCase):
    def test_task_instruction_is_not_rendered_as_application_ui(self):
        instruction = "Create a secret task that must stay outside the screenshot"
        rendered_text = []
        original = Canvas.text

        def capture(canvas, x, y, value, *args, **kwargs):
            rendered_text.append(value)
            return original(canvas, x, y, value, *args, **kwargs)

        with tempfile.TemporaryDirectory() as directory, patch.object(Canvas, "text", capture):
            render_calendar(initial_state(1), instruction, Path(directory) / "screen.png")

        self.assertNotIn(instruction, rendered_text)
        self.assertIn("SEPTEMBER 2026", rendered_text)


if __name__ == "__main__":
    unittest.main()
