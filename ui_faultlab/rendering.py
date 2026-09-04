from __future__ import annotations

import struct
import zlib
from pathlib import Path


RGB = tuple[int, int, int]


FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "J": ("00111", "00010", "00010", "00010", "10010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    ":": ("00000", "00100", "00100", "00000", "00100", "00100", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "00100", "00100"),
    "@": ("01110", "10001", "10111", "10101", "10111", "10000", "01111"),
    "+": ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    " ": ("00000",) * 7,
}


class Canvas:
    def __init__(self, width: int, height: int, color: RGB = (245, 247, 251)):
        self.width = width
        self.height = height
        self.data = bytearray(color * (width * height))

    def rect(self, x0: int, y0: int, x1: int, y1: int, color: RGB) -> None:
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(self.width, x1), min(self.height, y1)
        row = bytes(color) * max(0, x1 - x0)
        for y in range(y0, y1):
            start = (y * self.width + x0) * 3
            self.data[start : start + len(row)] = row

    def outline(self, x0: int, y0: int, x1: int, y1: int, color: RGB, size: int = 2) -> None:
        self.rect(x0, y0, x1, y0 + size, color)
        self.rect(x0, y1 - size, x1, y1, color)
        self.rect(x0, y0, x0 + size, y1, color)
        self.rect(x1 - size, y0, x1, y1, color)

    def text(self, x: int, y: int, value: str, color: RGB = (25, 35, 55), scale: int = 2, limit: int = 70) -> None:
        cursor = x
        for char in value.upper()[:limit]:
            glyph = FONT.get(char, FONT[" "])
            for gy, row in enumerate(glyph):
                for gx, bit in enumerate(row):
                    if bit == "1":
                        self.rect(cursor + gx * scale, y + gy * scale, cursor + (gx + 1) * scale, y + (gy + 1) * scale, color)
            cursor += 6 * scale

    def write_png(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = b"".join(b"\x00" + bytes(self.data[y * self.width * 3 : (y + 1) * self.width * 3]) for y in range(self.height))

        def chunk(kind: bytes, payload: bytes) -> bytes:
            return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

        png = b"\x89PNG\r\n\x1a\n"
        png += chunk(b"IHDR", struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0))
        png += chunk(b"IDAT", zlib.compress(raw, 7))
        png += chunk(b"IEND", b"")
        path.write_bytes(png)


def render_calendar(state: dict, instruction: str, path: str | Path, width: int = 960, height: int = 640) -> None:
    c = Canvas(width, height)
    navy, blue, white = (24, 37, 66), (65, 105, 225), (255, 255, 255)
    muted, line, red, green = (104, 116, 139), (212, 218, 231), (202, 65, 75), (41, 151, 112)
    c.rect(0, 0, width, 92, navy)
    c.text(36, 28, "MINI CALENDAR", white, 3)
    # The task instruction belongs to the agent input, not to the application's UI.
    # Rendering it here creates a clickable-looking confound for visual agents.
    c.text(36, 62, "SEPTEMBER 2026", (202, 214, 240), 1, 120)
    if state["screen"] == "calendar":
        c.rect(705, 108, 910, 162, blue)
        c.text(736, 126, "+ NEW EVENT", white, 2)
        y = 180
        for event in state["events"]:
            c.rect(70, y, 890, y + 96, white)
            c.outline(70, y, 890, y + 96, line, 2)
            c.rect(70, y, 80, y + 96, blue)
            c.text(105, y + 20, event["title"], navy, 2, 45)
            c.text(105, y + 54, f"{event['date']}  {event['time']}", muted, 2)
            c.text(640, y + 54, f"ATTENDEES {len(event['attendees'])}", muted, 1)
            y += 112
    else:
        c.rect(90, 112, 870, 600, white)
        c.outline(90, 112, 870, 600, line, 2)
        c.text(128, 140, "EDIT EVENT" if state["selected_event_id"] else "CREATE EVENT", navy, 3)
        draft = state["draft"] or {"title": "", "date": "", "time": "", "attendees": []}
        fields = [
            ("title", "TITLE", draft.get("title", ""), 190),
            ("date", "DATE", draft.get("date", ""), 275),
            ("time", "TIME", draft.get("time", ""), 360),
            ("attendees", "ATTENDEES", ", ".join(draft.get("attendees", [])), 445),
        ]
        for key, label, value, y in fields:
            c.text(130, y, label, muted, 1)
            c.rect(130, y + 20, 830, y + 68, (249, 250, 252))
            c.outline(130, y + 20, 830, y + 68, blue if state["focus"] == key else line, 3 if state["focus"] == key else 2)
            c.text(150, y + 36, value or "-", navy, 2, 52)
        c.rect(610, 540, 830, 585, blue)
        c.text(680, 554, "SAVE", white, 2)
        if state["selected_event_id"]:
            c.rect(130, 540, 360, 585, red)
            c.text(190, 554, "DELETE", white, 2)
    if state.get("confirm_delete"):
        c.rect(210, 205, 750, 455, (255, 252, 252))
        c.outline(210, 205, 750, 455, red, 4)
        c.text(275, 248, "DELETE THIS EVENT", navy, 3)
        c.text(275, 300, "THIS CANNOT BE UNDONE", muted, 2)
        c.rect(470, 360, 700, 415, red)
        c.text(535, 379, "CONFIRM", white, 2)
    if state.get("toast"):
        color = green if state["toast"] in {"Saved", "Deleted"} else red
        c.rect(680, 24, 920, 72, color)
        c.text(714, 41, state["toast"], white, 2)
    c.write_png(path)
