import os
import time

import AppKit
import Foundation
import HIServices
import objc
import Quartz

from frame import accessibility
from frame.geometry import FocusGap, Rect

_REFRESH = 1 / 30
_BLUE_WIDTH = 2
_CORNER_RADIUS = 11
_SETTINGS_URL = (
    "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
)


class AppDelegate(AppKit.NSObject):
    def applicationDidFinishLaunching_(self, _notification):
        self.pid = os.getpid()
        self.tracked_pid = None
        self.ax_app = None
        self.gap = FocusGap()
        self.frame = None
        self.overlay = self._make_overlay()
        self._make_menu()
        accessibility.trusted(prompt=True)
        self.timer = (
            Foundation.NSTimer.timerWithTimeInterval_target_selector_userInfo_repeats_(
                _REFRESH, self, "refresh:", None, True
            )
        )
        Foundation.NSRunLoop.mainRunLoop().addTimer_forMode_(
            self.timer, Foundation.NSRunLoopCommonModes
        )
        self.refresh_(None)

    @objc.python_method
    def _make_overlay(self):
        view = AppKit.NSView.alloc().initWithFrame_(AppKit.NSMakeRect(0, 0, 0, 0))
        view.setWantsLayer_(True)
        layer = view.layer()
        layer.setBorderColor_(AppKit.NSColor.systemBlueColor().CGColor())
        layer.setBorderWidth_(_BLUE_WIDTH)
        layer.setCornerRadius_(_CORNER_RADIUS)
        layer.setCornerCurve_(Quartz.kCACornerCurveContinuous)
        layer.setMasksToBounds_(True)
        layer.setBackgroundColor_(AppKit.NSColor.clearColor().CGColor())

        window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            AppKit.NSMakeRect(0, 0, 0, 0),
            AppKit.NSWindowStyleMaskBorderless,
            AppKit.NSBackingStoreBuffered,
            False,
        )
        window.setReleasedWhenClosed_(False)
        window.setOpaque_(False)
        window.setBackgroundColor_(AppKit.NSColor.clearColor())
        window.setHasShadow_(False)
        window.setIgnoresMouseEvents_(True)
        window.setLevel_(AppKit.NSFloatingWindowLevel)
        window.setCollectionBehavior_(
            AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
            | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary
            | AppKit.NSWindowCollectionBehaviorStationary
            | AppKit.NSWindowCollectionBehaviorIgnoresCycle
        )
        window.setContentView_(view)
        return window

    @objc.python_method
    def _make_menu(self):
        self.status_item = AppKit.NSStatusBar.systemStatusBar().statusItemWithLength_(
            AppKit.NSVariableStatusItemLength
        )
        button = self.status_item.button()
        image = AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
            "macwindow", "Frame"
        )
        if image:
            image.setTemplate_(True)
            button.setImage_(image)
        else:
            button.setTitle_("Frame")
        button.setToolTip_("Frame")

        menu = AppKit.NSMenu.alloc().init()
        settings = menu.addItemWithTitle_action_keyEquivalent_(
            "Accessibility Settings…", "openSettings:", ""
        )
        settings.setTarget_(self)
        menu.addItem_(AppKit.NSMenuItem.separatorItem())
        quit_item = menu.addItemWithTitle_action_keyEquivalent_(
            "Quit Frame", "quit:", "q"
        )
        quit_item.setTarget_(self)
        self.status_item.setMenu_(menu)

    def refresh_(self, _timer):
        if not accessibility.trusted():
            self.tracked_pid = None
            self.ax_app = None
            self.gap.reset()
            self._hide()
            return

        app = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
        if app is None:
            self._missing_window()
            return
        pid = app.processIdentifier()
        if pid == self.pid:
            return
        if app.isTerminated():
            self._missing_window()
            return
        if pid != self.tracked_pid:
            self.tracked_pid = pid
            self.ax_app = HIServices.AXUIElementCreateApplication(pid)
            self.gap.reset()
            self._hide()

        screens = AppKit.NSScreen.screens()
        primary = next(
            (
                screen
                for screen in screens
                if abs(screen.frame().origin.x) < 0.5
                and abs(screen.frame().origin.y) < 0.5
            ),
            None,
        )
        if primary is None:
            self._missing_window()
            return
        screen_rects = [self._screen_rect(s) for s in screens]
        frame = accessibility.focused_window_frame(
            self.ax_app, primary.frame().size.height, screen_rects
        )
        if frame is None:
            self._missing_window()
            return

        self.gap.seen(time.monotonic())
        self._show(frame)

    @objc.python_method
    @staticmethod
    def _screen_rect(screen):
        frame = screen.frame()
        return Rect(
            frame.origin.x,
            frame.origin.y,
            frame.size.width,
            frame.size.height,
        )

    @objc.python_method
    def _show(self, frame):
        frame = frame.expanded(_BLUE_WIDTH / 2)
        if frame != self.frame:
            self.frame = frame
            self.overlay.setFrame_display_(
                AppKit.NSMakeRect(frame.x, frame.y, frame.width, frame.height),
                True,
            )
        if not self.overlay.isVisible():
            self.overlay.orderFrontRegardless()

    @objc.python_method
    def _missing_window(self):
        if self.gap.expired(time.monotonic()):
            self._hide()

    @objc.python_method
    def _hide(self):
        if self.overlay.isVisible():
            self.overlay.orderOut_(None)
        self.frame = None

    def openSettings_(self, _sender):
        AppKit.NSWorkspace.sharedWorkspace().openURL_(
            Foundation.NSURL.URLWithString_(_SETTINGS_URL)
        )

    def quit_(self, _sender):
        AppKit.NSApplication.sharedApplication().terminate_(None)

    def applicationWillTerminate_(self, _notification):
        self.timer.invalidate()
        self.overlay.close()


def main():
    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)
    app.run()
