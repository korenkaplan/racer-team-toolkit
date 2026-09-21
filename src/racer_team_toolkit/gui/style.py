"""Application stylesheet for the Racer Team Toolkit GUI."""

APP_STYLESHEET = """
QMainWindow {
    background-color: #0b1220;
}

QWidget {
    background-color: #0f1724;
    color: #e7eef7;
    font-family: "Inter", "Segoe UI", "Helvetica Neue", Arial;
    font-size: 13px;
}

QLabel {
    background-color: transparent;
}

QToolTip {
    background-color: #172234;
    color: #ffffff;
    border: 1px solid #31455f;
    padding: 6px 8px;
}

#sidebar {
    background-color: #0a111d;
    border-right: 1px solid #1f2e43;
}

#sidebarTitle {
    font-size: 18px;
    font-weight: 700;
    color: #ffffff;
}

#sidebarSubtitle {
    color: #70839b;
    font-size: 11px;
}

#sidebarButton {
    background-color: transparent;
    border: none;
    border-radius: 9px;
    padding: 12px 14px;
    text-align: left;
    color: #a8b6c8;
    min-height: 18px;
}

#sidebarButton:hover {
    background-color: #142136;
    color: #ffffff;
}

#sidebarButton:checked {
    background-color: #17365d;
    color: #ffffff;
    font-weight: 600;
    border-left: 3px solid #4b9cff;
}

#versionLabel {
    color: #53667e;
    font-size: 10px;
}

#pageTitle {
    font-size: 29px;
    font-weight: 700;
    color: #ffffff;
}

#pageSubtitle {
    font-size: 14px;
    color: #8496ab;
}

#toolCard,
#workflowCard,
#devicePanel,
#actionCard {
    background-color: #141f2f;
    border: 1px solid #22344a;
    border-radius: 13px;
}

#toolCard {
    min-height: 116px;
}

#toolCard:hover,
#actionCard:hover {
    background-color: #18263a;
    border: 1px solid #3b78bc;
}

#cardTitle,
#panelTitle,
#sectionTitle {
    color: #ffffff;
    font-weight: 700;
    background-color: transparent;
}

#cardTitle,
#panelTitle {
    font-size: 16px;
}

#sectionTitle {
    font-size: 17px;
}

#cardDescription,
#panelStatus,
#mutedText,
#deviceSerial,
#pathLabel {
    color: #8193a9;
    background-color: transparent;
}

#cardDescription {
    font-size: 12px;
}

#panelStatus,
#mutedText,
#deviceSerial,
#pathLabel {
    font-size: 11px;
}

#deviceRow,
#selectionRow {
    background-color: #0f1927;
    border: 1px solid #22344a;
    border-radius: 9px;
}

#deviceName {
    font-size: 13px;
    font-weight: 600;
    color: #f5f8fc;
    background-color: transparent;
}

#deviceConnected,
#successText {
    color: #44d18b;
    background-color: transparent;
}

#warningText {
    color: #f5c451;
    background-color: transparent;
}

#errorText,
#missingText {
    color: #ff7070;
    background-color: transparent;
}

#missingText {
    font-weight: 600;
}

#emptyState {
    color: #70839b;
    background-color: transparent;
    padding: 16px;
}

#statusPill {
    background-color: #192a40;
    border: 1px solid #2a4463;
    border-radius: 10px;
    color: #a9c8eb;
    padding: 4px 9px;
    font-size: 10px;
    font-weight: 600;
}

#workflowSteps {
    color: #768aa2;
    font-size: 11px;
    background-color: transparent;
}

QPushButton {
    border-radius: 8px;
    padding: 9px 14px;
    min-height: 18px;
}

#primaryButton {
    background-color: #1976ed;
    border: 1px solid #2c88f4;
    color: #ffffff;
    font-weight: 600;
}

#primaryButton:hover {
    background-color: #2787f5;
}

#primaryButton:pressed {
    background-color: #1465ca;
}

#primaryButton:disabled {
    background-color: #1d2b3e;
    border-color: #293b50;
    color: #5d7086;
}

#secondaryButton {
    background-color: #182638;
    border: 1px solid #2b4059;
    color: #d5dfeb;
}

#secondaryButton:hover {
    background-color: #20334a;
    border-color: #3c6794;
}

#secondaryButton:disabled {
    color: #5b6d82;
    border-color: #243448;
}

#dangerButton {
    background-color: #8c2f38;
    border: 1px solid #b23e49;
    color: #ffffff;
    font-weight: 600;
}

#dangerButton:hover {
    background-color: #a83a45;
}

#dangerButton:disabled {
    background-color: #35242d;
    border-color: #4a303a;
    color: #735b65;
}

#modeButton {
    background-color: #182638;
    border: 1px solid #2b4059;
    color: #aebccc;
    padding: 8px 13px;
}

#modeButton:hover {
    background-color: #20334a;
}

#modeButton:checked {
    background-color: #173d68;
    border: 1px solid #2f82dd;
    color: #ffffff;
    font-weight: 600;
}

QCheckBox {
    color: #c7d3e0;
    spacing: 7px;
    background-color: transparent;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #405772;
    background-color: #0d1724;
}

QCheckBox::indicator:checked {
    background-color: #1976ed;
    border: 1px solid #4297f7;
}

#folderCombo,
QComboBox {
    background-color: #0f1927;
    border: 1px solid #2b4059;
    border-radius: 8px;
    padding: 8px 11px;
    color: #e7eef7;
    min-height: 19px;
}

QComboBox:hover {
    border-color: #3c6794;
}

QComboBox::drop-down {
    border: none;
    width: 26px;
}

QComboBox QAbstractItemView {
    background-color: #121e2e;
    color: #e7eef7;
    selection-background-color: #1d5f9e;
    border: 1px solid #2b4059;
}

#installLog,
QPlainTextEdit {
    background-color: #09111c;
    border: 1px solid #22344a;
    border-radius: 9px;
    color: #c9d8e8;
    padding: 10px;
    font-family: "SF Mono", "Cascadia Code", "Consolas", monospace;
    font-size: 11px;
    selection-background-color: #245c8f;
}

#installProgress,
#operationProgress,
QProgressBar {
    background-color: #0c1622;
    border: 1px solid #2a3d54;
    border-radius: 8px;
    min-height: 20px;
    text-align: center;
    color: #e9f2fb;
}

#installProgress::chunk,
#operationProgress::chunk,
QProgressBar::chunk {
    background-color: #1976ed;
    border-radius: 7px;
}

#dataTable,
QTableWidget {
    background-color: #0e1825;
    alternate-background-color: #111d2c;
    border: 1px solid #22344a;
    border-radius: 8px;
    gridline-color: #203047;
    color: #dce6f1;
    selection-background-color: #1e4f7c;
}

QHeaderView::section {
    background-color: #172438;
    color: #aebed0;
    border: none;
    border-right: 1px solid #23364c;
    border-bottom: 1px solid #23364c;
    padding: 8px;
    font-weight: 600;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollArea > QWidget > QWidget {
    background-color: transparent;
}

QScrollBar:vertical {
    background-color: #0c1521;
    width: 10px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: #32475f;
    border-radius: 5px;
    min-height: 28px;
}

QScrollBar::handle:vertical:hover {
    background-color: #42617f;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: #0c1521;
    height: 10px;
}

QScrollBar::handle:horizontal {
    background-color: #32475f;
    border-radius: 5px;
    min-width: 28px;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0;
}
"""
