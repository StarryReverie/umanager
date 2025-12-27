from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from umanager.ui.widgets import OverviewButtonBarWidget

if __name__ == "__main__":
    app = QApplication([])

    root = QWidget()
    root.setWindowTitle("OverviewButtonBar Test")
    layout = QVBoxLayout(root)

    button_bar = OverviewButtonBarWidget()
    button_bar.refreshDevices.connect(lambda: print("Signal: refreshDevices"))
    button_bar.viewDetails.connect(lambda: print("Signal: viewDetails"))
    button_bar.ejectDevice.connect(lambda: print("Signal: ejectDevice"))

    layout.addStretch()
    layout.addWidget(button_bar)
    root.setLayout(layout)
    root.resize(600, 200)
    root.show()

    app.exec()
