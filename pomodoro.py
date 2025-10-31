import sys
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QListWidget, QListWidgetItem, QLabel, QInputDialog, QCheckBox, 
                             QSystemTrayIcon, QMenu, QAction, QCalendarWidget, QTabWidget,
                             QProgressBar, QFrame, QGridLayout, QMessageBox, QDesktopWidget)
from PyQt5.QtCore import QTimer, Qt, QPropertyAnimation, QEasingCurve, pyqtProperty, QPoint
from PyQt5.QtGui import QFont, QKeySequence, QIcon, QPainter, QColor, QPen, QCursor, QFontDatabase
import pyaudio
import numpy as np
import os
import datetime
import csv
from collections import defaultdict, Counter

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class FloatingTimer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(100, 120)
        
        self.progress = 0
        self.max_progress = 25 * 60  # 25 minutes in seconds
        self.current_task = ""
        
        # Make it draggable
        self.dragging = False
        self.drag_position = QPoint()
        
        # Position in top right corner
        self.move_to_top_right()
        
        # Make it semi-transparent
        self.setStyleSheet("background-color: rgba(255, 255, 255, 200); border-radius: 10px;")
        
    def move_to_top_right(self):
        """Position the timer in the top right corner of the screen"""
        screen_geometry = QDesktopWidget().availableGeometry()
        x = screen_geometry.width() - self.width() - 20  # 20px from right edge
        y = 20  # 20px from top
        self.move(x, y)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == Qt.RightButton:
            # Right click to show main window
            if self.parent:
                self.parent.show()
                self.parent.activateWindow()
                self.parent.raise_()

    def mouseMoveEvent(self, event):
        if self.dragging and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.dragging = False
        
    def mouseDoubleClickEvent(self, event):
        # Double click to show main window
        if self.parent:
            self.parent.show()
            self.parent.activateWindow()
            self.parent.raise_()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw background
        painter.setBrush(QColor(255, 255, 255, 200))
        painter.setPen(QPen(QColor(200, 200, 200), 2))
        painter.drawRoundedRect(2, 2, self.width()-4, self.height()-4, 10, 10)
        
        # Draw circular progress bar
        center_x = self.width() // 2
        center_y = 40
        radius = 30
        
        # Background circle
        painter.setPen(QPen(QColor(200, 200, 200), 4))
        painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)
        
        # Progress circle (tomato red)
        if self.max_progress > 0:
            angle = int(360 * self.progress / self.max_progress)
            painter.setPen(QPen(QColor(220, 80, 60), 4))
            painter.drawArc(center_x - radius, center_y - radius, radius * 2, radius * 2, 90 * 16, -angle * 16)
        
        # Time text
        painter.setPen(QColor(0, 0, 0))
        mins = int(self.max_progress - self.progress) // 60
        secs = int(self.max_progress - self.progress) % 60
        painter.drawText(center_x - 20, center_y + 5, 40, 20, Qt.AlignCenter, f"{mins:02d}:{secs:02d}")
        
        # Task name (truncated if too long)
        task_text = self.current_task[:15] + "..." if len(self.current_task) > 15 else self.current_task
        painter.drawText(5, 85, self.width()-10, 30, Qt.AlignCenter, task_text)
        
    def update_progress(self, progress, max_progress, task_name=""):
        self.progress = progress
        self.max_progress = max_progress
        self.current_task = task_name
        self.update()

class PomodoroTimer(QWidget):
    def __init__(self):
        super().__init__()
        self.tray_icon = None
        self.tray_menu = None
        self.blink_timer = None
        self.current_date = datetime.date.today()
        self.floating_timer = FloatingTimer(self)
        self.initUI()
        self.initTray()

    def initUI(self):
        self.setWindowTitle("Pomodoro Timer")
        self.setGeometry(300, 300, 900, 500)
        self.setWindowIcon(QIcon(resource_path('images/tomato.ico')))

        # Create tab widget
        self.tabs = QTabWidget()
        main_layout = QHBoxLayout()
        main_layout.addWidget(self.tabs)
        self.setLayout(main_layout)

        # Timer Tab
        timer_tab = QWidget()
        timer_layout = QHBoxLayout()
        timer_tab.setLayout(timer_layout)

        # Left side - Timer
        timer_container = QVBoxLayout()
        timer_container.addStretch()
        
        timer_display = QVBoxLayout()
        self.time_label = QLabel("25:00")
        
        # Use a nicer font for the timer
        font_family = self.get_optimal_font()
        timer_font = QFont(font_family, 72, QFont.Bold)
        self.time_label.setFont(timer_font)
        self.time_label.setAlignment(Qt.AlignCenter)
        timer_display.addWidget(self.time_label)
        
        self.error_label = QLabel("")
        self.error_label.setFont(QFont("Arial", 16))
        self.error_label.setStyleSheet("color: red")
        self.error_label.setAlignment(Qt.AlignCenter)
        timer_display.addWidget(self.error_label)
        
        timer_container.addLayout(timer_display)
        timer_container.addStretch()
        
        # Control buttons
        control_layout = QHBoxLayout()
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.start_timer)
        self.start_button.setShortcut(QKeySequence("Return"))
        control_layout.addWidget(self.start_button)

        self.reset_button = QPushButton("Reset")
        self.reset_button.clicked.connect(self.reset_timer)
        control_layout.addWidget(self.reset_button)
        
        timer_container.addLayout(control_layout)
        
        # Checkbox
        self.play_sound_checkbox = QCheckBox("Play sound when finished")
        timer_container.addWidget(self.play_sound_checkbox)
        
        timer_layout.addLayout(timer_container, stretch=6)

        # Right side - Task List
        list_layout = QVBoxLayout()
        self.date_button = QPushButton(self.current_date.strftime("%Y-%m-%d"))
        self.date_button.clicked.connect(self.show_calendar)
        list_layout.addWidget(self.date_button)

        self.todo_list = QListWidget()
        self.todo_list.itemDoubleClicked.connect(self.toggle_task_completion)
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

        timer_layout.addLayout(list_layout, stretch=4)
        
        self.tabs.addTab(timer_tab, "Timer")

        # Statistics Tab
        stats_tab = QWidget()
        stats_layout = QVBoxLayout()
        stats_tab.setLayout(stats_layout)
        
        self.stats_label = QLabel()
        self.stats_label.setAlignment(Qt.AlignTop)
        stats_layout.addWidget(self.stats_label)
        
        self.tabs.addTab(stats_tab, "Statistics")
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_time)
        self.load_tasks()
        self.update_statistics()

    def get_optimal_font(self):
        """Return the best available font for the timer"""
        # List of preferred fonts in order of preference
        preferred_fonts = [
            "Arial Rounded MT Bold",  # Soft, rounded - perfect for tomato theme
            "Segoe UI",               # Modern Windows font
            "Calibri",                # Clean and modern
            "Tahoma",                 # Clear and readable
            "Verdana",                # Widely available
            "Arial"                   # Universal fallback
        ]
        
        # Check which fonts are available
        available_fonts = QFontDatabase().families()
        
        for font in preferred_fonts:
            if font in available_fonts:
                return font
        
        return "Arial"  # Ultimate fallback

    def toggle_task_completion(self, item):
        """Toggle strike-through for completed tasks with confirmation"""
        if item.font().strikeOut():
            # If already completed, un-complete it
            font = item.font()
            font.setStrikeOut(False)
            item.setFont(font)
            item.setForeground(QColor(0, 0, 0))  # Reset to black
            self.save_tasks()
        else:
            # Ask for confirmation before marking as completed
            reply = QMessageBox.question(self, 'Confirm Completion', 
                                       f'Mark "{item.text().split(" ◯")[0]}" as completed?',
                                       QMessageBox.Yes | QMessageBox.No, 
                                       QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                font = item.font()
                font.setStrikeOut(True)
                item.setFont(font)
                # Grey out the item
                item.setForeground(QColor(128, 128, 128))
                self.save_tasks()
                
                # If this was the current task and timer is running, reset
                if self.todo_list.currentItem() == item and self.timer.isActive():
                    self.reset_timer()

    def is_task_completed(self, item):
        """Check if a task is marked as completed"""
        return item.font().strikeOut()

    def update_statistics(self):
        """Update statistics display"""
        try:
            with open("tasks.csv", 'r') as f:
                reader = csv.reader(f)
                tasks = list(reader)
        except FileNotFoundError:
            tasks = []
        
        # Calculate statistics
        total_pomodoros = sum(int(task[2]) for task in tasks)
        
        # Tasks by pomodoro count
        task_counts = Counter()
        for task in tasks:
            task_counts[task[1]] += int(task[2])
        
        # Most recent tasks
        recent_tasks = tasks[-10:] if tasks else []
        
        # Daily statistics
        daily_stats = defaultdict(int)
        for task in tasks:
            daily_stats[task[0]] += int(task[2])
        
        stats_text = f"""
        <h2>Pomodoro Statistics</h2>
        <p><b>Total Pomodoros Completed:</b> {total_pomodoros}</p>
        
        <h3>Top Tasks</h3>
        {"<br>".join(f"• {task}: {count} pomodoros" for task, count in task_counts.most_common(5)) or "No tasks yet"}
        
        <h3>Recent Activity</h3>
        {"<br>".join(f"• {task[0]}: {task[1]} ({task[2]} pomodoros)" for task in recent_tasks[-5:]) or "No recent activity"}
        
        <h3>Daily Average</h3>
        <p>{total_pomodoros / max(len(daily_stats), 1):.1f} pomodoros per day</p>
        """
        
        self.stats_label.setText(stats_text)

    def initTray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(resource_path('images/tomato.ico')))
        
        self.tray_menu = QMenu()
        self.tray_menu.addAction("Open", self.showNormal)
        self.tray_menu.addAction("Start", self.start_last_timer)
        self.tray_menu.addAction("Reset", self.reset_timer)
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        self.tray_icon.show()

    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.showNormal()

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
        # Only use the name, not the circles
        item = QListWidgetItem(name)  # Just the name, no circles
        item.setData(Qt.UserRole, (name, 0))  # Reset count for new date
        self.todo_list.addItem(item)
        self.save_tasks()
        self.error_label.setText(f"Added task: {name}")

    def duplicate_entire_list(self):
        date_str = self.calendar.selectedDate().toPyDate().strftime("%Y-%m-%d")
        
        try:
            with open("tasks.csv", 'r') as f:
                reader = csv.reader(f)
                tasks = [row for row in reader if row[0] == date_str]
                
                for task in tasks:
                    name, count = task[1], int(task[2])
                    # Only use the name, not the circles
                    item = QListWidgetItem(name)  # Just the name, no circles
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
        total_seconds = mins * 60 + secs
        
        if total_seconds > 0:
            total_seconds -= 1
            mins, secs = divmod(total_seconds, 60)
            self.time_label.setText(f"{mins:02d}:{secs:02d}")
            
            # Update floating timer
            current_item = self.todo_list.currentItem()
            task_name = current_item.data(Qt.UserRole)[0] if current_item else ""
            elapsed = (25 * 60) - total_seconds
            self.floating_timer.update_progress(elapsed, 25 * 60, task_name)
        else:
            self.timer.stop()
            self.time_label.setText("Done!")
            self.complete_pomodoro()
            return

    def blink_icon(self):
        if self.tray_icon.icon().isNull():
            self.tray_icon.setIcon(QIcon(resource_path('images/done.ico')))
        else:
            self.tray_icon.setIcon(QIcon())

    def complete_pomodoro(self):
        item = self.todo_list.currentItem()
        if item and not self.is_task_completed(item):
            name, count = item.data(Qt.UserRole)
            count += 1
            circles = '◯' * count
            item.setText(f"{name} {circles}")
            item.setData(Qt.UserRole, (name, count))
            self.save_tasks()
            
            if self.play_sound_checkbox.isChecked():
                self.play_completion_sound()
                
            self.tray_icon.showMessage("Pomodoro Timer", "Timer finished!")
            self.tray_icon.setIcon(QIcon(resource_path('images/done.ico')))
            
            self.blink_timer = QTimer()
            self.blink_timer.timeout.connect(self.blink_icon)
            self.blink_timer.start(500)
            
        self.update_statistics()

    def play_completion_sound(self):
        try:
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
        except Exception as e:
            print(f"Sound error: {e}")

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
            self.reset_timer()

    def clear_list(self):
        self.todo_list.clear()
        self.save_tasks()
        self.reset_timer()

    def start_timer(self):
        current_item = self.todo_list.currentItem()
        
        if current_item is None:
            self.error_label.setText("Please choose a task from the list")
            return
            
        if self.is_task_completed(current_item):
            self.error_label.setText("Cannot start timer for completed task")
            return
            
        # Reset tray icon properly when starting new timer
        if self.blink_timer and self.blink_timer.isActive():
            self.blink_timer.stop()
        self.tray_icon.setIcon(QIcon(resource_path('images/ongoing.ico')))
        
        self.time_label.setText("25:00")
        self.error_label.setText("")
        self.timer.start(1000)
        
        # Show floating timer and hide main window
        task_name = current_item.data(Qt.UserRole)[0] if current_item else ""
        self.floating_timer.update_progress(0, 25 * 60, task_name)
        self.floating_timer.show()
        
        # Minimize the main window
        self.hide()

    def start_last_timer(self):
        if self.todo_list.count() > 0:
            # Find the last non-completed task
            for i in range(self.todo_list.count() - 1, -1, -1):
                item = self.todo_list.item(i)
                if not self.is_task_completed(item):
                    self.todo_list.setCurrentItem(item)
                    self.start_timer()
                    return
            
            self.error_label.setText("All tasks are completed")
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
        
        # Show main window and hide floating timer
        self.show()
        self.activateWindow()
        self.raise_()
        self.floating_timer.hide()

    def closeEvent(self, event):
        self.save_tasks()
        self.floating_timer.close()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PomodoroTimer()
    window.show()
    sys.exit(app.exec_())
