import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QListWidgetItem, QLabel, QInputDialog, QCheckBox
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QFont, QKeySequence
import pyaudio
import numpy as np



import pyaudio
import numpy as np

class PomodoroTimer(QWidget):
    def __init__(self):
        super().__init__()

        self.initUI()

    def initUI(self):
        self.setWindowTitle("Pomodoro Timer")
        self.setGeometry(300, 300, 800, 400)

        self.layout = QHBoxLayout()
        self.setLayout(self.layout)

        self.timer_layout = QVBoxLayout()
        self.timer_layout.addStretch()
        self.timer_label_layout = QHBoxLayout()
        self.timer_label_layout.addStretch()

        self.time_label = QLabel("25:00")
        font = QFont("Arial", 72)
        self.time_label.setFont(font)
        self.timer_label_layout.addWidget(self.time_label)
        self.timer_label_layout.addStretch()
        self.timer_layout.addLayout(self.timer_label_layout)

        self.error_label = QLabel("")
        font = QFont("Arial", 16)
        self.error_label.setFont(font)
        self.error_label.setStyleSheet("color: red")
        self.timer_layout.addWidget(self.error_label)
        self.timer_layout.addStretch()
        self.layout.addLayout(self.timer_layout, stretch=6)
        
        self.play_sound_checkbox = QCheckBox("Play sound after pomodoro")
        self.timer_layout.addWidget(self.play_sound_checkbox)

        self.list_layout = QVBoxLayout()
        self.layout.addLayout(self.list_layout, stretch=4)

        self.todo_list = QListWidget()
        self.list_layout.addWidget(self.todo_list)

        self.new_button = QPushButton("New task")
        self.new_button.clicked.connect(self.add_item)
        self.list_layout.addWidget(self.new_button)

        self.delete_button = QPushButton("Delete task")
        self.delete_button.clicked.connect(self.delete_item)
        self.list_layout.addWidget(self.delete_button)

        self.clear_button = QPushButton("Clear list")
        self.clear_button.clicked.connect(self.clear_list)
        self.list_layout.addWidget(self.clear_button)

        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.start_timer)
        self.list_layout.addWidget(self.start_button)
        self.start_button.setShortcut(QKeySequence("Return"))

        self.link_label = QLabel("<a href='https://friend.ucsd.edu/reasonableexpectations/downloads/Cirillo%20--%20Pomodoro%20Technique.pdf'>Learn about the Pomodoro technique</a>")
        self.link_label.setAlignment(Qt.AlignCenter)
        self.link_label.setOpenExternalLinks(True)
        self.list_layout.addWidget(self.link_label)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_time)

    def add_item(self):
        text, ok = QInputDialog.getText(self, "New Task", "Please enter a name for your task!")
        if ok and text:
            item = QListWidgetItem(text+" ")
            self.todo_list.addItem(item)
            self.todo_list.setCurrentItem(item)

    def delete_item(self):
        row = self.todo_list.currentRow()
        if row != -1:
            self.todo_list.takeItem(row)
            if self.timer.isActive():
                self.timer.stop()
                self.time_label.setText("25:00")
                self.error_label.setText("")

    def clear_list(self):
        self.todo_list.clear()
        if self.timer.isActive():
            self.timer.stop()
            self.time_label.setText("25:00")
            self.error_label.setText("")

    def start_timer(self):
        if self.todo_list.currentItem() is not None:
            self.time_label.setText("25:00")
            self.error_label.setText("")
            self.timer.start(1000)  # 1 Sekunde
        else:
            self.error_label.setText("Please choose a task from the list")
            self.error_label.setAlignment(Qt.AlignCenter)

    def update_time(self):
        time = self.time_label.text()
        minutes, seconds = map(int, time.split(":"))
        if seconds > 0:
            seconds -= 1
        elif minutes > 0:
            minutes -= 1
            seconds = 59
        else:
            
            self.timer.stop()
            self.time_label.setText("Done!")
            item = self.todo_list.currentItem()
            pomodoros = item.text().count("\u25CB")
            if pomodoros % 4 == 0 and pomodoros != 0:
                item.setText(item.text() + " " + "\u25CB")
            else:
                item.setText(item.text() + "\u25CB")
            if self.play_sound_checkbox.isChecked():
                p = pyaudio.PyAudio()
                stream = p.open(format=pyaudio.paFloat32, channels=1, rate=44100, output=True)
                volume = 0.5
                frequency = 2500
                duration = 3
                s = (np.sin(2*np.pi*np.arange(44100*duration)*frequency/44100)).astype(np.float32)
                stream.write(volume*s)
                stream.stop_stream()
                stream.close()
                p.terminate()
                        
        if self.time_label.text() != "Done!":
            self.time_label.setText(f"{minutes:02d}:{seconds:02d}")
            
            
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PomodoroTimer()
    window.show()
    sys.exit(app.exec_())
