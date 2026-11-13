import importlib.util
import sys
import types
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

import frame
from frame.geometry import FocusGap, Rect


class PythonMethod:
    def __init__(self, function):
        self.callable = function


class ObjCMeta(type):
    def __new__(metaclass, name, bases, namespace):
        python_methods = set()
        selectors = set()
        for key, value in list(namespace.items()):
            if isinstance(value, PythonMethod):
                python_methods.add(key)
                namespace[key] = value.callable
            elif isinstance(value, types.FunctionType):
                selectors.add(key)
        namespace["_python_methods"] = python_methods
        namespace["_selectors"] = selectors
        return super().__new__(metaclass, name, bases, namespace)


class NSObject(metaclass=ObjCMeta):
    pass


def load_app():
    appkit: Any = types.ModuleType("AppKit")
    appkit.NSObject = NSObject
    for name in (
        "NSWorkspace",
        "NSScreen",
        "NSView",
        "NSWindow",
        "NSColor",
        "NSStatusBar",
        "NSImage",
        "NSMenu",
        "NSMenuItem",
        "NSApplication",
    ):
        setattr(appkit, name, mock.Mock(name=name))
    appkit.NSMakeRect = lambda x, y, width, height: (x, y, width, height)
    for name, value in (
        ("NSWindowStyleMaskBorderless", 0),
        ("NSBackingStoreBuffered", 2),
        ("NSFloatingWindowLevel", 3),
        ("NSWindowCollectionBehaviorCanJoinAllSpaces", 1),
        ("NSWindowCollectionBehaviorFullScreenAuxiliary", 2),
        ("NSWindowCollectionBehaviorStationary", 4),
        ("NSWindowCollectionBehaviorIgnoresCycle", 8),
        ("NSVariableStatusItemLength", -1),
        ("NSApplicationActivationPolicyAccessory", 1),
    ):
        setattr(appkit, name, value)
    foundation: Any = types.ModuleType("Foundation")
    foundation.NSTimer = mock.Mock()
    foundation.NSRunLoop = mock.Mock()
    foundation.NSRunLoopCommonModes = "common"
    foundation.NSURL = mock.Mock()
    ax: Any = types.ModuleType("HIServices")
    ax.AXUIElementCreateApplication = mock.Mock(side_effect=lambda pid: object())
    quartz: Any = types.ModuleType("Quartz")
    quartz.kCACornerCurveContinuous = "continuous"
    objc: Any = types.ModuleType("objc")
    objc.python_method = PythonMethod
    accessibility: Any = types.ModuleType("frame.accessibility")
    accessibility.trusted = mock.Mock(return_value=True)
    accessibility.focused_window_frame = mock.Mock(return_value=Rect(10, 20, 300, 200))
    spec = importlib.util.spec_from_file_location(
        "frame._app_under_test",
        Path(__file__).resolve().parents[1] / "frame" / "app.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module: Any = importlib.util.module_from_spec(spec)
    modules = {
        "AppKit": appkit,
        "Foundation": foundation,
        "HIServices": ax,
        "Quartz": quartz,
        "objc": objc,
        "frame.accessibility": accessibility,
    }
    with (
        mock.patch.dict(sys.modules, modules),
        mock.patch.object(
            frame,
            "accessibility",
            accessibility,
            create=True,
        ),
    ):
        spec.loader.exec_module(module)
    return module


class AppTest(unittest.TestCase):
    def setUp(self):
        self.app = load_app()
        self.delegate = self.app.AppDelegate()
        self.delegate.pid = 100
        self.delegate.tracked_pid = None
        self.delegate.ax_app = None
        self.delegate.gap = FocusGap()
        self.delegate.frame = None
        self.overlay = mock.Mock()
        self.visible = False
        self.overlay.isVisible.side_effect = lambda: self.visible
        self.overlay.orderFrontRegardless.side_effect = self.show_overlay
        self.overlay.orderOut_.side_effect = self.hide_overlay
        self.delegate.overlay = self.overlay
        self.frontmost = mock.Mock()
        self.frontmost.processIdentifier.return_value = 200
        self.frontmost.isTerminated.return_value = False
        self.workspace = self.app.AppKit.NSWorkspace.sharedWorkspace.return_value
        self.workspace.frontmostApplication.return_value = self.frontmost
        screen = mock.Mock()
        screen.frame.return_value = types.SimpleNamespace(
            origin=types.SimpleNamespace(x=0, y=0),
            size=types.SimpleNamespace(width=1440, height=900),
        )
        self.app.AppKit.NSScreen.screens.return_value = [screen]
        self.clock = mock.patch.object(self.app.time, "monotonic", return_value=10)
        self.now = self.clock.start()
        self.addCleanup(self.clock.stop)

    def show_overlay(self):
        self.visible = True

    def hide_overlay(self, _sender):
        self.visible = False

    def test_framework_imports_do_not_leak(self):
        names = (
            "AppKit",
            "Foundation",
            "HIServices",
            "Quartz",
            "objc",
            "frame.accessibility",
        )
        originals = {name: types.ModuleType(name) for name in names}
        original_ax = originals["frame.accessibility"]
        with (
            mock.patch.dict(sys.modules, originals),
            mock.patch.object(
                frame,
                "accessibility",
                original_ax,
                create=True,
            ),
        ):
            load_app()
            for name, module in originals.items():
                self.assertIs(sys.modules[name], module)
            self.assertIs(getattr(frame, "accessibility", None), original_ax)

    def test_only_native_callbacks_are_exposed_as_selectors(self):
        self.assertEqual(
            self.app.AppDelegate._selectors,
            {
                "applicationDidFinishLaunching_",
                "refresh_",
                "openSettings_",
                "quit_",
                "applicationWillTerminate_",
            },
        )
        self.assertEqual(
            self.app.AppDelegate._python_methods,
            {
                "_make_overlay",
                "_make_menu",
                "_screen_rect",
                "_show",
                "_missing_window",
                "_hide",
            },
        )

    def test_menu_uses_frame_name(self):
        self.delegate._make_menu()
        image_factory = (
            self.app.AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_
        )
        image_factory.assert_called_once_with("macwindow", "Frame")
        button = self.delegate.status_item.button.return_value
        button.setToolTip_.assert_called_once_with("Frame")
        menu = self.app.AppKit.NSMenu.alloc.return_value.init.return_value
        menu.addItemWithTitle_action_keyEquivalent_.assert_any_call(
            "Quit Frame", "quit:", "q"
        )

    def test_menu_fallback_uses_frame_name(self):
        self.app.AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_.return_value = None
        self.delegate._make_menu()
        button = self.delegate.status_item.button.return_value
        button.setTitle_.assert_called_once_with("Frame")

    def test_overlay_close_does_not_release_python_owned_window(self):
        overlay = self.delegate._make_overlay()
        overlay.setReleasedWhenClosed_.assert_called_once_with(False)
        overlay.setIgnoresMouseEvents_.assert_called_once_with(True)

    def test_launch_schedules_timer_in_common_modes_and_refreshes(self):
        with (
            mock.patch.object(
                self.delegate, "_make_overlay", return_value=self.overlay
            ),
            mock.patch.object(self.delegate, "_make_menu"),
            mock.patch.object(self.delegate, "refresh_") as refresh,
        ):
            self.delegate.applicationDidFinishLaunching_(None)
        self.app.accessibility.trusted.assert_called_once_with(prompt=True)
        factory = self.app.Foundation.NSTimer.timerWithTimeInterval_target_selector_userInfo_repeats_
        factory.assert_called_once_with(
            self.app._REFRESH, self.delegate, "refresh:", None, True
        )
        self.app.Foundation.NSRunLoop.mainRunLoop.return_value.addTimer_forMode_.assert_called_once_with(
            factory.return_value, self.app.Foundation.NSRunLoopCommonModes
        )
        refresh.assert_called_once_with(None)

    def test_refresh_shows_frame_without_redundant_native_updates(self):
        self.delegate.refresh_(None)
        self.delegate.refresh_(None)
        self.assertTrue(self.visible)
        self.overlay.setFrame_display_.assert_called_once_with((9, 19, 302, 202), True)
        self.overlay.orderFrontRegardless.assert_called_once_with()
        self.app.HIServices.AXUIElementCreateApplication.assert_called_once_with(200)

    def test_permission_revocation_clears_tracking_immediately(self):
        self.delegate.refresh_(None)
        self.app.accessibility.trusted.return_value = False
        self.delegate.refresh_(None)
        self.assertFalse(self.visible)
        self.assertIsNone(self.delegate.frame)
        self.assertIsNone(self.delegate.tracked_pid)
        self.assertIsNone(self.delegate.ax_app)
        self.assertTrue(self.delegate.gap.expired(10))
        self.app.accessibility.focused_window_frame.assert_called_once()

    def test_permission_restoration_recreates_handle_for_same_pid(self):
        self.delegate.refresh_(None)
        old_handle = self.delegate.ax_app
        self.app.accessibility.trusted.return_value = False
        self.delegate.refresh_(None)
        self.app.accessibility.trusted.return_value = True
        self.delegate.refresh_(None)
        self.assertIsNot(self.delegate.ax_app, old_handle)
        self.assertEqual(self.app.HIServices.AXUIElementCreateApplication.call_count, 2)
        self.assertTrue(self.visible)

    def test_missing_window_obeys_focus_gap(self):
        self.delegate.refresh_(None)
        self.app.accessibility.focused_window_frame.return_value = None
        self.now.return_value = 10.249
        self.delegate.refresh_(None)
        self.assertTrue(self.visible)
        self.now.return_value = 10.25
        self.delegate.refresh_(None)
        self.assertFalse(self.visible)

    def test_switching_apps_does_not_keep_previous_border_during_gap(self):
        self.delegate.refresh_(None)
        self.frontmost.processIdentifier.return_value = 300
        self.app.accessibility.focused_window_frame.return_value = None
        self.delegate.refresh_(None)
        self.assertFalse(self.visible)
        self.assertEqual(self.delegate.tracked_pid, 300)

    def test_menu_keeps_outline_without_querying_own_ax_window(self):
        self.delegate.refresh_(None)
        self.frontmost.processIdentifier.return_value = self.delegate.pid
        self.now.return_value = 20
        self.delegate.refresh_(None)
        self.assertTrue(self.visible)
        self.app.accessibility.focused_window_frame.assert_called_once()

    def test_missing_frontmost_app_terminated_app_and_missing_screen_expire(self):
        for state in ("no_app", "terminated", "no_screen"):
            with self.subTest(state=state):
                self.workspace.frontmostApplication.return_value = self.frontmost
                self.frontmost.isTerminated.return_value = False
                self.now.return_value = 10
                self.delegate.refresh_(None)
                if state == "no_app":
                    self.workspace.frontmostApplication.return_value = None
                elif state == "terminated":
                    self.frontmost.isTerminated.return_value = True
                else:
                    self.app.AppKit.NSScreen.screens.return_value = []
                self.now.return_value = 11
                self.delegate.refresh_(None)
                self.assertFalse(self.visible)

    def test_termination_invalidates_timer_before_closing_overlay(self):
        calls = mock.Mock()
        self.delegate.timer = calls.timer
        self.delegate.overlay = calls.overlay
        self.delegate.applicationWillTerminate_(None)
        self.assertEqual(
            calls.mock_calls,
            [
                mock.call.timer.invalidate(),
                mock.call.overlay.close(),
            ],
        )


if __name__ == "__main__":
    unittest.main()
