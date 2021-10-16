from QWebKitView import QWebKitView
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
import sys


@pyqtSlot(name="load_started")
def load_started():
    print("Load started.")


@pyqtSlot(int, name="load_progress")
def load_progress(progress: int):
    print(f"Loading... {progress}%")


@pyqtSlot(bool, name="load_finished")
def load_finished(success: bool):
    print("Load finished. Success = ", success)


if __name__ == '__main__':
    app = QApplication(sys.argv)

    w = QWebKitView()
    w.resize(640, 480)
    w.setWindowTitle("QWebKitView")

    w.loadStarted.connect(load_started)
    w.loadProgress.connect(load_progress)
    w.loadFinished.connect(load_finished)

    w.load(QUrl("https://www.apple.com"))
    w.show()

    app.exec()
