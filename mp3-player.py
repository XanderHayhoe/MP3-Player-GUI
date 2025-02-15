import sys
import random
from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QFileDialog, QSlider, QListWidget
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtCore import Qt, QUrl

class AudioPlayer(QMediaPlayer):
    def __init__(self):
        super().__init__()
        self.audio_output = QAudioOutput()
        self.setAudioOutput(self.audio_output)
        self.mediaStatusChanged.connect(self.on_media_status_changed)
        
    def set_source(self, file_path):
        self.setSource(QUrl.fromLocalFile(file_path))
        self.play()
    
    def set_volume(self, volume):
        self.audio_output.setVolume(volume / 100.0)
    
    def on_media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.parent().playlist.play_next()

class Controls(QWidget):
    def __init__(self, player, playlist):
        super().__init__()
        self.player = player
        self.playlist = playlist
        
        self.open_button = QPushButton("Open MP3")
        self.play_button = QPushButton("Play")
        self.pause_button = QPushButton("Pause")
        self.stop_button = QPushButton("Stop")
        self.next_button = QPushButton("Next")
        self.previous_button = QPushButton("Previous")
        self.shuffle_button = QPushButton("Shuffle")
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.valueChanged.connect(self.adjust_volume)
        
        self.open_button.clicked.connect(self.open_file)
        self.play_button.clicked.connect(self.player.play)
        self.pause_button.clicked.connect(self.player.pause)
        self.stop_button.clicked.connect(self.player.stop)
        self.next_button.clicked.connect(self.playlist.play_next)
        self.previous_button.clicked.connect(self.playlist.play_previous)
        self.shuffle_button.clicked.connect(self.playlist.shuffle)
        self.seek_slider.sliderMoved.connect(self.player.setPosition)
        
        self.player.positionChanged.connect(self.update_position)
        self.player.durationChanged.connect(self.update_duration)
        
        layout = QVBoxLayout()
        layout.addWidget(self.seek_slider)
        layout.addWidget(self.volume_slider)
        layout.addWidget(self.open_button)
        layout.addWidget(self.play_button)
        layout.addWidget(self.pause_button)
        layout.addWidget(self.stop_button)
        layout.addWidget(self.next_button)
        layout.addWidget(self.previous_button)
        layout.addWidget(self.shuffle_button)
        self.setLayout(layout)
        
    def open_file(self):
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Open MP3 Files", "", "MP3 Files (*.mp3)")
        if file_paths:
            for file_path in file_paths:
                self.playlist.add_to_playlist(file_path)
    
    def update_position(self, position):
        self.seek_slider.setValue(position)
    
    def update_duration(self, duration):
        self.seek_slider.setRange(0, duration)
    
    def adjust_volume(self, volume):
        self.player.set_volume(volume)

class Playlist(QWidget):
    def __init__(self, player):
        super().__init__()
        self.player = player
        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.play_selected)
        
        layout = QVBoxLayout()
        layout.addWidget(self.list_widget)
        self.setLayout(layout)
        
    def add_to_playlist(self, file_path):
        self.list_widget.addItem(file_path)
    
    def play_selected(self, item):
        self.player.set_source(item.text())
    
    def play_next(self):
        current_row = self.list_widget.currentRow()
        if current_row < self.list_widget.count() - 1:
            next_item = self.list_widget.item(current_row + 1)
            self.list_widget.setCurrentItem(next_item)
            self.player.set_source(next_item.text())
    
    def play_previous(self):
        current_row = self.list_widget.currentRow()
        if current_row > 0:
            previous_item = self.list_widget.item(current_row - 1)
            self.list_widget.setCurrentItem(previous_item)
            self.player.set_source(previous_item.text())
    
    def shuffle(self):
        items = [self.list_widget.item(i).text() for i in range(self.list_widget.count())]
        if items:
            random.shuffle(items)
            self.list_widget.clear()
            for item in items:
                self.list_widget.addItem(item)
            self.list_widget.setCurrentRow(0)
            self.player.set_source(items[0])

class MP3Player(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MP3 Player")
        self.setGeometry(100, 100, 400, 400)
        
        self.player = AudioPlayer()
        self.playlist = Playlist(self.player)
        self.player.setParent(self)
        self.controls = Controls(self.player, self.playlist)
        
        layout = QVBoxLayout()
        layout.addWidget(self.playlist)
        layout.addWidget(self.controls)
        
        self.setLayout(layout)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = MP3Player()
    player.show()
    sys.exit(app.exec())
