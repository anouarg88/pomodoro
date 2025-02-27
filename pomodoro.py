import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QListWidgetItem, QLabel, QInputDialog, QCheckBox, QSystemTrayIcon, QMenu, QAction, QCalendarWidget
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QFont, QKeySequence, QIcon
import pyaudio
import numpy as np
import os
import datetime
import csv

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class PomodoroTimer(QWidget):
    def __init__(self):
        super().__init__()
        self.tray_icon = None
        self.tray_menu = None
        self.blink_timer = None
        self.current_date = datetime.date.today()
        self.initUI()
        self.initTray()

    def initUI(self):
        self.setWindowTitle("Pomodoro Timer")
        self.setGeometry(300, 300, 800, 400)
        self.setWindowIcon(QIcon(resource_path('images/tomato.ico')))

        main_layout = QHBoxLayout()
        self.setLayout(main_layout)

        timer_container = QVBoxLayout()
        timer_container.addStretch()
        timer_layout = QVBoxLayout()
        self.time_label = QLabel("25:00")
        self.time_label.setFont(QFont("Arial", 72))
        self.time_label.setAlignment(Qt.AlignCenter)
        timer_layout.addWidget(self.time_label)
        
        self.error_label = QLabel("")
        self.error_label.setFont(QFont("Arial", 16))
        self.error_label.setStyleSheet("color: red")
        self.error_label.setAlignment(Qt.AlignCenter)
        timer_layout.addWidget(self.error_label)
        
        timer_container.addLayout(timer_layout)
        timer_container.addStretch()
        
        
        checkbox_layout = QHBoxLayout()
        self.play_sound_checkbox = QCheckBox("Play sound when finished")
        checkbox_layout.addWidget(self.play_sound_checkbox)
        timer_container.addLayout(checkbox_layout)
        main_layout.addLayout(timer_container, stretch=6)

        list_layout = QVBoxLayout()
        self.date_button = QPushButton(self.current_date.strftime("%Y-%m-%d"))
        self.date_button.clicked.connect(self.show_calendar)
        list_layout.addWidget(self.date_button)

        self.todo_list = QListWidget()
        list_layout.addWidget(self.todo_list)

        buttons = [
            ("New task", self.add_item),
            ("Delete task", self.delete_item),
            ("Clear list", self.clear_list)           
        ]
        for text, handler in buttons:
            btn = QPushButton(text)
            btn.clicked.connect(handler)
            list_layout.addWidget(btn)

        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.start_timer)
        self.start_button.setShortcut(QKeySequence("Return"))
        list_layout.addWidget(self.start_button)

        main_layout.addLayout(list_layout, stretch=4)
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_time)
        self.load_tasks()

    def initTray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(resource_path('images/tomato.ico')))
        
        self.tray_menu = QMenu()
        self.tray_menu.addAction("Open", self.showNormal)
        self.tray_menu.addAction("Start", self.start_last_timer)
        self.tray_menu.addAction("Reset", self.reset_timer)
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.show()

    def show_calendar(self):
        self.calendar_window = QWidget()
        self.calendar_window.setWindowTitle("Calendar")
        self.calendar_window.setGeometry(200, 200, 400, 400)

        layout = QVBoxLayout()
        self.calendar = QCalendarWidget()
        layout.addWidget(self.calendar)

        self.preview_list = QListWidget()
        layout.addWidget(QLabel("Task Preview:"))
        layout.addWidget(self.preview_list)

        btn_layout = QHBoxLayout()
        self.duplicate_btn = QPushButton("Duplicate Task")
        self.duplicate_btn.clicked.connect(self.duplicate_selected_task)
        btn_layout.addWidget(self.duplicate_btn)

        self.duplicate_all_btn = QPushButton("Duplicate Entire List")
        self.duplicate_all_btn.clicked.connect(self.duplicate_entire_list)
        btn_layout.addWidget(self.duplicate_all_btn)

        layout.addLayout(btn_layout)
        self.calendar_window.setLayout(layout)
        
        self.calendar.selectionChanged.connect(self.update_preview)
        self.update_preview()
        self.calendar_window.show()

    def update_preview(self):
        selected_date = self.calendar.selectedDate().toPyDate()
        self.show_preview(selected_date)

    def show_preview(self, date):
        self.preview_list.clear()
        date_str = date.strftime("%Y-%m-%d")
        
        try:
            with open("tasks.csv", 'r') as f:
                reader = csv.reader(f)
                tasks = []
                for row in reader:
                    if row[0] == date_str:
                        name, count = row[1], int(row[2])
                        circles = '◯' * count
                        item = QListWidgetItem(f"{name} {circles}")
                        item.setData(Qt.UserRole, (name, count, date_str))
                        tasks.append(item)
                self.preview_list.addItems([item.text() for item in tasks])
                for i in range(self.preview_list.count()):
                    self.preview_list.item(i).setData(Qt.UserRole, tasks[i].data(Qt.UserRole))
        except FileNotFoundError:
            self.preview_list.addItem("No tasks found")

    def duplicate_selected_task(self):
        selected = self.preview_list.currentItem()
        if not selected:
            self.error_label.setText("No task selected in preview")
            return
            
        name, count, date_str = selected.data(Qt.UserRole)
        item = QListWidgetItem(f"{name} ◯" * count)
        item.setData(Qt.UserRole, (name, 0))  # Reset count for new date
        self.todo_list.addItem(item)
        self.save_tasks()

    def duplicate_entire_list(self):
        date_str = self.calendar.selectedDate().toPyDate().strftime("%Y-%m-%d")
        
        try:
            with open("tasks.csv", 'r') as f:
                reader = csv.reader(f)
                tasks = [row for row in reader if row[0] == date_str]
                
                for task in tasks:
                    name, count = task[1], int(task[2])
                    item = QListWidgetItem(f"{name} ◯" * count)
                    item.setData(Qt.UserRole, (name, 0))  # Reset count for new date
                    self.todo_list.addItem(item)
                    
                self.save_tasks()
                self.error_label.setText(f"Copied {len(tasks)} tasks to today's list")
                
        except FileNotFoundError:
            self.error_label.setText("No tasks found for selected date")

    def add_item(self):
        text, ok = QInputDialog.getText(self, "New Task", "Task name:")
        if ok and text:
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, (text, 0))  # (name, count)
            self.todo_list.addItem(item)
            self.todo_list.setCurrentItem(item)
            self.save_tasks()

    def update_time(self):
        time = self.time_label.text()
        if time == "Done!":
            return

        mins, secs = map(int, time.split(":"))
        if secs > 0:
            secs -= 1
        elif mins > 0:
            mins -= 1
            secs = 59
        else:
            self.timer.stop()
            self.time_label.setText("Done!")
            self.complete_pomodoro()
            return

        self.time_label.setText(f"{mins:02d}:{secs:02d}")
        
    def blink_icon(self):
        if self.tray_icon.icon().isNull():
            self.tray_icon.setIcon(QIcon(resource_path('images/done.ico')))
        else:
            self.tray_icon.setIcon(QIcon())

    def complete_pomodoro(self):
        item = self.todo_list.currentItem()
        if item:
            name, count = item.data(Qt.UserRole)
            count += 1
            circles = '◯' * count
            item.setText(f"{name} {circles}")
            item.setData(Qt.UserRole, (name, count))
            self.save_tasks()
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
            self.tray_icon.showMessage("Pomodoro Timer", "Timer finished")
            self.tray_icon.setIcon(QIcon(resource_path('images/done.ico')))
            self.blink_timer = QTimer()
            self.blink_timer.timeout.connect(self.blink_icon)
            self.blink_timer.start(500)  # 500 Millisekunden

    def save_tasks(self):
        tasks = []
        for i in range(self.todo_list.count()):
            item = self.todo_list.item(i)
            name, count = item.data(Qt.UserRole)
            tasks.append([self.current_date.strftime("%Y-%m-%d"), name, str(count)])
        
        try:
            with open("tasks.csv", 'r') as f:
                reader = csv.reader(f)
                existing_tasks = [row for row in reader]
        except FileNotFoundError:
            existing_tasks = []
        
        # Remove tasks for current date
        existing_tasks = [task for task in existing_tasks if task[0] != self.current_date.strftime("%Y-%m-%d")]
        
        # Add current tasks
        existing_tasks.extend(tasks)
        
        # Write to file
        with open("tasks.csv", 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(existing_tasks)

    def load_tasks(self):
        self.todo_list.clear()
        date_str = self.current_date.strftime("%Y-%m-%d")
        
        try:
            with open("tasks.csv", 'r') as f:
                reader = csv.reader(f)
                for row in reader:
                    if row[0] == date_str:
                        name, count = row[1], int(row[2])
                        circles = '◯' * count
                        item = QListWidgetItem(f"{name} {circles}")
                        item.setData(Qt.UserRole, (name, count))
                        self.todo_list.addItem(item)
        except FileNotFoundError:
            pass



    def delete_item(self):
        row = self.todo_list.currentRow()
        if row != -1:
            self.todo_list.takeItem(row)
            self.save_tasks()
            if self.timer.isActive():
                self.timer.stop()
                self.time_label.setText("25:00")
                self.error_label.setText("")
                self.tray_icon.setIcon(QIcon(resource_path('images/tomato.ico')))

    def clear_list(self):
        self.todo_list.clear()
        self.save_tasks()
        if self.timer.isActive():
            self.timer.stop()
            self.time_label.setText("25:00")
            self.error_label.setText("")
            self.tray_icon.setIcon(QIcon(resource_path('images/tomato.ico')))

    def start_timer(self):
        if self.todo_list.currentItem() is not None:
            self.time_label.setText("25:00")
            self.error_label.setText("")
            self.timer.start(1000)
            self.tray_icon.setIcon(QIcon(resource_path('images/ongoing.ico')))
        else:
            self.error_label.setText("Please choose a task from the list")

    def start_last_timer(self):
        if self.todo_list.count() > 0:
            self.todo_list.setCurrentRow(self.todo_list.count() - 1)
            self.start_timer()
        else:
            self.error_label.setText("Please add a task to the list")

    def reset_timer(self):
        self.timer.stop()
        self.time_label.setText("25:00")
        self.error_label.setText("")
        self.tray_icon.setIcon(QIcon(resource_path('images/tomato.ico')))
        if self.blink_timer is not None:
            self.blink_timer.stop()
            self.blink_timer = None

    def closeEvent(self, event):
        self.save_tasks()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PomodoroTimer()
    window.show()
    sys.exit(app.exec_())
