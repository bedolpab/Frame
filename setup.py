from setuptools import setup

setup(
    app=["run_frame.py"],
    options={
        "py2app": {
            "packages": ["frame"],
            "includes": ["AppKit", "Foundation", "HIServices", "Quartz"],
            "argv_emulation": False,
            "plist": {
                "CFBundleIdentifier": "com.frame.app",
                "CFBundleName": "Frame",
                "CFBundleDisplayName": "Frame",
                "LSMinimumSystemVersion": "13.0",
                "LSUIElement": True,
            },
            "iconfile": "build/Frame.icns",
        }
    },
)
