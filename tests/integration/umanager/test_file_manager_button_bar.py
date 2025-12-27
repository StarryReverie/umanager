from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from umanager.ui.widgets import FileManagerButtonBarWidget

if __name__ == "__main__":
    app = QApplication([])

    root = QWidget()
    root.setWindowTitle("FileManagerButtonBar Test")
    layout = QVBoxLayout(root)

    button_bar = FileManagerButtonBarWidget()
    button_bar.refreshRequested.connect(lambda: print("Signal: refreshRequested"))
    button_bar.createRequested.connect(lambda: print("Signal: createRequested"))
    button_bar.createDirectoryRequested.connect(lambda: print("Signal: createDirectoryRequested"))
    button_bar.openRequested.connect(lambda: print("Signal: openRequested"))
    button_bar.copyRequested.connect(lambda: print("Signal: copyRequested"))
    button_bar.cutRequested.connect(lambda: print("Signal: cutRequested"))
    button_bar.pasteRequested.connect(lambda: print("Signal: pasteRequested"))
    button_bar.deleteRequested.connect(lambda: print("Signal: deleteRequested"))
    button_bar.renameRequested.connect(lambda: print("Signal: renameRequested"))
    button_bar.showHiddenToggled.connect(
        lambda checked: print(f"Signal: showHiddenToggled={checked}")
    )

    layout.addWidget(button_bar)
    root.setLayout(layout)
    root.show()

    app.exec()
