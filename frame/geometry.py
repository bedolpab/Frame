import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    width: float
    height: float

    def expanded(self, amount: float) -> "Rect":
        return Rect(
            self.x - amount,
            self.y - amount,
            self.width + 2 * amount,
            self.height + 2 * amount,
        )

    def integral(self) -> "Rect":
        left, bottom = math.floor(self.x), math.floor(self.y)
        right = math.ceil(self.x + self.width)
        top = math.ceil(self.y + self.height)
        return Rect(left, bottom, right - left, top - bottom)

    def intersects(self, other: "Rect") -> bool:
        return (
            self.width > 0
            and self.height > 0
            and other.width > 0
            and other.height > 0
            and self.x < other.x + other.width
            and self.x + self.width > other.x
            and self.y < other.y + other.height
            and self.y + self.height > other.y
        )


def window_rect(
    position: tuple[float, float], size: tuple[float, float], primary_height: float
) -> Rect | None:
    x, top = position
    width, height = size
    values = (x, top, width, height, primary_height)
    if not all(math.isfinite(value) for value in values):
        return None
    if width <= 0 or height <= 0 or primary_height <= 0:
        return None
    bottom = primary_height - top - height
    if not all(math.isfinite(value) for value in (bottom, x + width, bottom + height)):
        return None
    return Rect(x, bottom, width, height).integral()


class FocusGap:
    def __init__(self, seconds: float = 0.25) -> None:
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError("seconds must be finite and non-negative")
        self.seconds = seconds
        self.last_seen = None

    def seen(self, now: float) -> None:
        self.last_seen = now

    def reset(self) -> None:
        self.last_seen = None

    def expired(self, now: float) -> bool:
        return self.last_seen is None or now - self.last_seen >= self.seconds
