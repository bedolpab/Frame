import HIServices
import objc

from frame.geometry import Rect, window_rect

_TIMEOUT = 0.05


def trusted(prompt=False):
    if prompt:
        HIServices.AXIsProcessTrustedWithOptions(
            {HIServices.kAXTrustedCheckOptionPrompt: True}
        )
    return bool(HIServices.AXIsProcessTrusted())


def _attribute(element: object, name: str) -> object | None:
    try:
        error, value = HIServices.AXUIElementCopyAttributeValue(element, name, None)
        return value if error == HIServices.kAXErrorSuccess else None
    except (objc.error, TypeError, ValueError):
        return None


def focused_window_frame(
    application: object, primary_height: float, screens: list[Rect]
) -> Rect | None:
    try:
        HIServices.AXUIElementSetMessagingTimeout(application, _TIMEOUT)
        window = _attribute(application, HIServices.kAXFocusedWindowAttribute)
        if window is None:
            return None
        HIServices.AXUIElementSetMessagingTimeout(window, _TIMEOUT)
        if _attribute(window, HIServices.kAXMinimizedAttribute):
            return None

        position = _attribute(window, HIServices.kAXPositionAttribute)
        size = _attribute(window, HIServices.kAXSizeAttribute)
        if position is None or size is None:
            return None
        ok, point = HIServices.AXValueGetValue(
            position, HIServices.kAXValueTypeCGPoint, None
        )
        if not ok:
            return None
        ok, dimensions = HIServices.AXValueGetValue(
            size, HIServices.kAXValueTypeCGSize, None
        )
        if not ok:
            return None
        frame = window_rect(
            (point.x, point.y),
            (dimensions.width, dimensions.height),
            primary_height,
        )
    except (objc.error, TypeError, ValueError):
        return None

    if frame is None or not any(frame.intersects(screen) for screen in screens):
        return None
    return frame
