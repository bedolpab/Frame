import importlib.util
import sys
import types
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

import frame
from frame.geometry import Rect


class AXElement:
    def __init__(self, attributes):
        self.attributes = attributes


class AXValue:
    def __init__(self, kind, value):
        self.kind, self.value = kind, value


ax: Any = types.ModuleType("HIServices")
ax.kAXErrorSuccess = 0
ax.kAXFocusedWindowAttribute = "AXFocusedWindow"
ax.kAXMinimizedAttribute = "AXMinimized"
ax.kAXPositionAttribute = "AXPosition"
ax.kAXSizeAttribute = "AXSize"
ax.kAXValueTypeCGPoint = 1
ax.kAXValueTypeCGSize = 2
ax.AXUIElementSetMessagingTimeout = lambda *_: 0


def copy_attribute(element, name, _):
    return (0, element.attributes[name]) if name in element.attributes else (-1, None)


def get_value(value, kind, _):
    valid = isinstance(value, AXValue) and value.kind == kind
    return (True, value.value) if valid else (False, None)


ax.AXUIElementCopyAttributeValue = copy_attribute
ax.AXValueGetValue = get_value
objc: Any = types.ModuleType("objc")
objc.error = type("ObjCError", (Exception,), {})
spec = importlib.util.spec_from_file_location(
    "frame._accessibility_under_test",
    Path(__file__).resolve().parents[1] / "frame" / "accessibility.py",
)
assert spec is not None and spec.loader is not None
accessibility = importlib.util.module_from_spec(spec)
with mock.patch.dict(sys.modules, {"HIServices": ax, "objc": objc}):
    spec.loader.exec_module(accessibility)


class AccessibilityTest(unittest.TestCase):
    def test_module_does_not_replace_real_accessibility(self):
        self.assertIsNot(sys.modules.get("frame.accessibility"), accessibility)
        self.assertIsNot(getattr(frame, "accessibility", None), accessibility)

    def test_trust_check_without_prompt(self):
        with (
            mock.patch.object(
                ax, "AXIsProcessTrusted", return_value=False, create=True
            ),
            mock.patch.object(
                ax, "AXIsProcessTrustedWithOptions", create=True
            ) as prompt,
        ):
            self.assertFalse(accessibility.trusted())
            prompt.assert_not_called()

    def test_trust_check_with_prompt(self):
        with (
            mock.patch.object(ax, "AXIsProcessTrusted", return_value=True, create=True),
            mock.patch.object(ax, "kAXTrustedCheckOptionPrompt", "prompt", create=True),
            mock.patch.object(
                ax, "AXIsProcessTrustedWithOptions", create=True
            ) as prompt,
        ):
            self.assertTrue(accessibility.trusted(prompt=True))
            prompt.assert_called_once_with({"prompt": True})

    def test_native_errors_return_no_frame(self):
        for error in (
            objc.error("native failure"),
            TypeError("invalid element"),
            ValueError("invalid value"),
        ):
            with (
                self.subTest(error=error),
                mock.patch.object(
                    ax, "AXUIElementSetMessagingTimeout", side_effect=error
                ),
            ):
                self.assertIsNone(self.frame())

    def test_unexpected_errors_are_not_hidden(self):
        with (
            mock.patch.object(
                ax, "AXUIElementCopyAttributeValue", side_effect=RuntimeError("bug")
            ),
            self.assertRaises(RuntimeError),
        ):
            self.frame()

    def test_attribute_native_error_returns_none(self):
        with mock.patch.object(
            ax,
            "AXUIElementCopyAttributeValue",
            side_effect=objc.error("native failure"),
        ):
            self.assertIsNone(self.frame())

    def test_invalid_ax_values_return_no_frame(self):
        for results in (
            ((False, None),),
            ((True, types.SimpleNamespace(x=100, y=80)), (False, None)),
        ):
            with (
                self.subTest(results=results),
                mock.patch.object(ax, "AXValueGetValue", side_effect=results),
            ):
                self.assertIsNone(self.frame())

    def frame(self, *, minimized=False, position=(100, 80)):
        window = AXElement(
            {
                "AXMinimized": minimized,
                "AXPosition": AXValue(
                    1, types.SimpleNamespace(x=position[0], y=position[1])
                ),
                "AXSize": AXValue(2, types.SimpleNamespace(width=400, height=200)),
            }
        )
        app = AXElement({"AXFocusedWindow": window})
        return accessibility.focused_window_frame(app, 900, [Rect(0, 0, 1440, 900)])

    def test_focused_window(self):
        self.assertEqual(self.frame(), Rect(100, 620, 400, 200))

    def test_no_focused_window(self):
        self.assertIsNone(
            accessibility.focused_window_frame(
                AXElement({}), 900, [Rect(0, 0, 1440, 900)]
            )
        )

    def test_does_not_use_main_window_fallback(self):
        window = AXElement({})
        app = AXElement({"AXMainWindow": window})
        self.assertIsNone(
            accessibility.focused_window_frame(app, 900, [Rect(0, 0, 1440, 900)])
        )

    def test_minimized_and_offscreen_windows(self):
        self.assertIsNone(self.frame(minimized=True))
        self.assertIsNone(self.frame(position=(2000, 80)))


if __name__ == "__main__":
    unittest.main()
