"""
QWebKitView: QtWidget wrapper of macOS WebKit WKWebView, emulating QWebEngineView API.


Reference:
- Platform APIs in Qt 6: https://www.qt.io/blog/platform-apis-in-qt-6
- Qt5 QMacCocoaViewContainer: https://doc.qt.io/qt-5/qmaccocoaviewcontainer.html
- Using QMacCocoaViewContainer: https://code.activestate.com/recipes/578951-using-qmaccocoaviewcontainer-on-pyqt4/

- PyObjC: https://pyobjc.readthedocs.io/en/latest/api/module-objc.html
- WKWebView: https://developer.apple.com/documentation/webkit/wkwebview?language=objc
- WKWebView on PyObjC: https://palepoli.skr.jp/wp/2019/03/09/webkit-on-pygobject-and-pyobjc/
- WKNavigationDelegate: https://developer.apple.com/documentation/webkit/wknavigationdelegate?language=objc
- WKWebView progress: https://stackoverflow.com/questions/47988125/how-to-monitor-wkwebview-page-load-progress-in-swift
- WKWebView addObserver: https://developer.apple.com/documentation/objectivec/nsobject/1412787-addobserver?language=objc

- QWebEngineView: https://doc.qt.io/qt-5/qwebengineview.html
"""

import sys
import objc
from Cocoa import NSObject, NSWindow, NSMakeRect, NSZeroRect, NSURL, NSURLRequest, NSError, \
    NSKeyValueObservingOptionNew, NSMakeSize
from WebKit import WKWebView, WKWebViewConfiguration, WKPreferences, WKNavigation
from PyQt6.QtWidgets import QWidget
from PyQt6.QtWidgets import *
from PyQt6.QtGui import QResizeEvent, QWindow
from PyQt6.QtGui import *
from PyQt6.QtCore import QObject, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtCore import *
from typing import Optional, Callable, Any
import weakref


class QWebKitPage:
    """
    Wrapper class emulating QWebEnginePage API.
    """

    def __init__(self, wv: WKWebView) -> None:
        super().__init__()
        self._wv = objc.WeakRef(wv)

    def runJavaScript(self, scriptSource: str, resultCallback: Optional[Callable[[Any], None]] = None):
        if self._wv() is not None:
            self._wv().evaluateJavaScript_completionHandler_(scriptSource,
                                                             lambda result, error, callback=resultCallback:
                                                             self._callback(result, error, callback))

    @staticmethod
    def _callback(result, error, callback: Optional[Callable[[Any], None]] = None):
        if callback is not None:
            if error is None:
                callback(result)
            else:
                callback(error)

    def url(self) -> QUrl:
        return QUrl(self._wv.URL().absoluteString())


class QWebKitView(QWidget):
    """
    Wrapper class of macOS WebKit WKWebView, emulating QWebEngineView API.
    """

    # Signals
    loadStarted = pyqtSignal()
    loadProgress = pyqtSignal(int)
    loadFinished = pyqtSignal(bool)

    def __init__(self, parent=None):
        super(QWebKitView, self).__init__(parent)

        # Create config
        self._config = WKWebViewConfiguration.new()
        self._config.setPreferences_(WKPreferences.new())
        self._config.preferences().setJavaEnabled_(True)

        # Create WKWebView
        self._wv = WKWebView.alloc().initWithFrame_configuration_(NSZeroRect, self._config)
        self._wv.setFrameSize_(NSMakeSize(self.size().width(), self.size().height()))

        # Create wrappers
        self.setLayout(QHBoxLayout())
        self.layout().addWidget(QWidget.createWindowContainer(QWindow.fromWinId(self._wv.__c_void_p__().value)))
        self.layout().setContentsMargins(0, 0, 0, 0)

        # Add progress observer

        # NavigationDelegate must be a subclass of NSObject. As this class is already inheriting QWidget, to avoid
        # inheritance problems, _QWebKitViewObserver is created and works as a relay.
        self._observer: _QWebKitViewObserver = _QWebKitViewObserver.new()
        self._observer.set_parent(self)
        self._wv.setNavigationDelegate_(self._observer)
        self._wv.addObserver_forKeyPath_options_context_(self._observer, "estimatedProgress",
                                                         NSKeyValueObservingOptionNew, None)

        self._should_emit_progress = False  # only emit loadProgress between loadStarted and loadFinished

        # Create a QWebKitPage to emulate QWebEnginePage
        self._page = QWebKitPage(self._wv)

    def closeEvent(self, event):
        super().closeEvent(event)
        self._wv.removeObserver_forKeyPath_(self._observer, "estimatedProgress")
        self._wv.setNavigationDelegate_(0)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        if self._wv:
            self._wv.setFrameSize_(NSMakeSize(event.size().width(), event.size().height()))

    def load(self, url: QUrl):
        u = NSURL.URLWithString_(url.toString())
        r = NSURLRequest.requestWithURL_(u)
        self._wv.loadRequest_(r)

    @pyqtSlot()
    def stop(self):
        self._wv.stopLoading()
        self._should_emit_progress = False  # stop emitting loadProgress
        self.loadFinished.emit(False)

    @pyqtSlot()
    def reload(self):
        self._wv.reload()

    @pyqtSlot()
    def forward(self):
        self._wv.goForward()

    @pyqtSlot()
    def back(self):
        self._wv.goBack()

    def url(self) -> QUrl:
        return self._page.url()

    def title(self) -> str:
        return str(self._wv.title())

    def _started_provisional_navigation(self, webview: WKWebView, navigation: WKNavigation):
        self.loadStarted.emit()
        self._should_emit_progress = True  # allow emitting loadProgress

    def _finished_navigation(self, webview: WKWebView, navigation: WKNavigation):
        self._should_emit_progress = False  # stop emitting loadProgress
        self.loadFinished.emit(True)

    def _failed_navigation(self, webview: WKWebView, navigation: WKNavigation, error: NSError):
        self._should_emit_progress = False  # stop emitting loadProgress
        self.loadFinished.emit(False)

    def _failed_provisional_navigation(self, webview: WKWebView, navigation: WKNavigation, error: NSError):
        self._should_emit_progress = False  # stop emitting loadProgress
        self.loadFinished.emit(False)

    def _progress_changed(self, keyPath: str, object, change, context):
        if keyPath == "estimatedProgress":
            if self._should_emit_progress:
                self.loadProgress.emit(int(self._wv.estimatedProgress() * 100))

    def page(self) -> QWebKitPage:
        return self._page


class _QWebKitViewObserver(NSObject):
    """
    Private helper class for WKWebView progress observation.
    Only a subclass of NSObject can be used for Key-Value Observing.
    """

    @objc.python_method
    def set_parent(self, wkv: QWebKitView):
        # QWebKitView is a Python object, so use weakref instead of objc.WeakRef
        self._wkv : QWebKitView = weakref.proxy(wkv)

    def webView_didStartProvisionalNavigation_(self, webview: WKWebView, navigation: WKNavigation):
        # https://developer.apple.com/documentation/webkit/wknavigationdelegate/1455621-webview?language=objc
        if self._wkv:
            self._wkv._started_provisional_navigation(webview, navigation)

    def webView_didFinishNavigation_(self, webview: WKWebView, navigation: WKNavigation):
        # https://developer.apple.com/documentation/webkit/wknavigationdelegate/1455629-webview?language=objc
        if self._wkv:
            self._wkv._finished_navigation(webview, navigation)

    def webView_didFailNavigation_withError_(self, webview: WKWebView, navigation: WKNavigation, error: NSError):
        # https://developer.apple.com/documentation/webkit/wknavigationdelegate/1455623-webview?language=objc
        if self._wkv:
            self._wkv._failed_navigation(webview, navigation, error)

    def webView_didFailProvisionalNavigation_withError_(self, webview: WKWebView, navigation: WKNavigation, error: NSError):
        # https://developer.apple.com/documentation/webkit/wknavigationdelegate/1455637-webview?language=objc
        if self._wkv:
            self._wkv._failed_provisional_navigation(webview, navigation, error)

    def observeValueForKeyPath_ofObject_change_context_(self, keyPath: str, object, change, context):
        # https://developer.apple.com/documentation/objectivec/nsobject/1416553-observevalueforkeypath?language=objc
        if self._wkv:
            self._wkv._progress_changed(keyPath, object, change, context)


if __name__ == '__main__':
    app = QApplication(sys.argv)

    toplevel = QWidget()
    toplevel.resize(640, 480)
    toplevel.setWindowTitle("QWidget with createWindowContainer-managed Metal Window")

    config = WKWebViewConfiguration.new()
    config.setPreferences_(WKPreferences.new())
    # config.preferences().setJavaEnabled_(True)
    #
    wv = WKWebView.alloc().initWithFrame_configuration_(NSZeroRect, config)
    window = QWindow.fromWinId(wv.__c_void_p__().value)
    # container = QWidget.createWindowContainer(window)
    # container.show()

    # toplevel.
    # layout

    toplevel.show()

    u = NSURL.URLWithString_("https://www.apple.com")
    r = NSURLRequest.requestWithURL_(u)
    wv.loadRequest_(r)

    app.exec()
