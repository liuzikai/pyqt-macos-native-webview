# QWebKitView - PyQt Widget of macOS Native WKWebView

QWebKitView wraps WKWebView as a QWidget with PyObjC and Qt's support of native window.
The interface emulates QWebEngineView. Only part of the functions are implemented.

Safari-based WKWebView is clearly using less CPU and memory than the Chromium-based QWebEngineView
on my machine. No more fan blowing :)

The code is written for PyQt6. But PyQt5 should also work.