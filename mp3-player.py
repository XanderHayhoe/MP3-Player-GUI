import sys
import random
import re
import os
from PyQt6.QtWidgets import (QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, 
                            QFileDialog, QSlider, QListWidget, QListWidgetItem, QLabel, QLineEdit, 
                            QProgressBar, QMessageBox, QGroupBox, QInputDialog)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtCore import Qt, QUrl, pyqtSignal, QThread
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import yt_dlp

class DownloadWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, username, playlist_id, output_folder, spotify_client):
        super().__init__()
        self.username = username
        self.playlist_id = playlist_id
        self.output_folder = output_folder
        self.songs = []
        self.sp = spotify_client

    def run(self):
        try:
            # fetch playlist
            playlist_name, song_names = self.fetch_playlist()
            
            # create folder
            playlist_folder = os.path.join(self.output_folder, self.sanitize_filename(playlist_name))
            if not os.path.exists(playlist_folder):
                os.makedirs(playlist_folder)
            
            # download
            for i, song in enumerate(song_names, start=1):
                self.progress.emit(i, song)
                file_path = self.download_song(song, playlist_folder, i, len(song_names))
                if file_path:
                    self.songs.append(file_path)
            
            self.finished.emit(playlist_folder)
            
        except Exception as e:
            self.error.emit(str(e))

    def fetch_playlist(self):
        playlist = self.sp.user_playlist(user=self.username, playlist_id=self.playlist_id)
        playlist_name = playlist['name']
        
        results = self.sp.user_playlist_tracks(user=self.username, playlist_id=self.playlist_id)
        tracks = results['items']
        
        while results['next']:
            results = self.sp.next(results)
            tracks.extend(results['items'])
        
        song_names = [item['track']['name'] + ' - ' + item['track']['artists'][0]['name'] for item in tracks]
        
        return playlist_name, song_names

    def sanitize_filename(self, name):
        return re.sub(r'[<>:"/\\|?*]', '', name)

    def download_song(self, song_name, output_folder, current, total):
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'outtmpl': f'{output_folder}/{current:03d}-%(title)s.%(ext)s',
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                search_result = ydl.extract_info(f"ytsearch1:{song_name}", download=True)
                if 'entries' in search_result:
                    video_info = search_result['entries'][0]
                    title = video_info.get('title', 'Unknown')
                    file_path = f"{output_folder}/{current:03d}-{self.sanitize_filename(title)}.mp3"
                    return file_path
            except Exception as e:
                print(f"Failed to download {song_name}: {e}")
                return None


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
        # extract just the filename without full path
        filename = os.path.basename(file_path)
        item = QListWidgetItem(filename)
        item.setData(Qt.ItemDataRole.UserRole, file_path) 
        self.list_widget.addItem(item)
    
    def add_files_to_playlist(self, file_paths):
        for file_path in file_paths:
            self.add_to_playlist(file_path)
        
        # select and play the first item if playlist empty
        if self.list_widget.count() == len(file_paths):
            self.list_widget.setCurrentRow(0)
            first_item = self.list_widget.item(0)
            if first_item:
                self.play_selected(first_item)
    
    def play_selected(self, item):
        file_path = item.data(Qt.ItemDataRole.UserRole)
        self.player.set_source(file_path)
    
    def play_next(self):
        current_row = self.list_widget.currentRow()
        if current_row < self.list_widget.count() - 1:
            next_item = self.list_widget.item(current_row + 1)
            self.list_widget.setCurrentItem(next_item)
            self.play_selected(next_item)
    
    def play_previous(self):
        current_row = self.list_widget.currentRow()
        if current_row > 0:
            previous_item = self.list_widget.item(current_row - 1)
            self.list_widget.setCurrentItem(previous_item)
            self.play_selected(previous_item)
    
    def shuffle(self):
        items = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            items.append((item.text(), item.data(Qt.ItemDataRole.UserRole)))
        
        if items:
            random.shuffle(items)
            self.list_widget.clear()
            for display_text, file_path in items:
                item = QListWidgetItem(display_text)
                item.setData(Qt.ItemDataRole.UserRole, file_path)
                self.list_widget.addItem(item)
            
            self.list_widget.setCurrentRow(0)
            if self.list_widget.item(0):
                self.play_selected(self.list_widget.item(0))
    
    def clear_playlist(self):
        self.list_widget.clear()


class Controls(QWidget):
    def __init__(self, player, playlist):
        super().__init__()
        self.player = player
        self.playlist = playlist
        
        self.open_button = QPushButton("Open MP3")
        self.open_folder_button = QPushButton("Open Folder")
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
        self.open_folder_button.clicked.connect(self.open_folder)
        self.play_button.clicked.connect(self.player.play)
        self.pause_button.clicked.connect(self.player.pause)
        self.stop_button.clicked.connect(self.player.stop)
        self.next_button.clicked.connect(self.playlist.play_next)
        self.previous_button.clicked.connect(self.playlist.play_previous)
        self.shuffle_button.clicked.connect(self.playlist.shuffle)
        self.seek_slider.sliderMoved.connect(self.player.setPosition)
        
        self.player.positionChanged.connect(self.update_position)
        self.player.durationChanged.connect(self.update_duration)
        
        # control layout
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.play_button)
        button_layout.addWidget(self.pause_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.next_button)
        button_layout.addWidget(self.previous_button)
        button_layout.addWidget(self.shuffle_button)
        
        file_buttons_layout = QHBoxLayout()
        file_buttons_layout.addWidget(self.open_button)
        file_buttons_layout.addWidget(self.open_folder_button)
        
        layout = QVBoxLayout()
        layout.addWidget(self.seek_slider)
        layout.addWidget(QLabel("Volume:"))
        layout.addWidget(self.volume_slider)
        layout.addLayout(button_layout)
        layout.addLayout(file_buttons_layout)
        
        self.setLayout(layout)
        
    def open_file(self):
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Open MP3 Files", "", "MP3 Files (*.mp3)")
        if file_paths:
            self.playlist.add_files_to_playlist(file_paths)
    
    def open_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder Containing MP3s")
        if folder_path:
            # Find all MP3 files in the selected folder
            mp3_files = []
            for file in os.listdir(folder_path):
                if file.lower().endswith('.mp3'):
                    mp3_files.append(os.path.join(folder_path, file))
            
            if mp3_files:
                # Sort files alphabetically
                mp3_files.sort()
                self.playlist.add_files_to_playlist(mp3_files)
                QMessageBox.information(self, "Folder Loaded", 
                                     f"Successfully loaded {len(mp3_files)} songs from the folder.")
            else:
                QMessageBox.warning(self, "No MP3 Files", 
                                 "No MP3 files were found in the selected folder.")
    
    def update_position(self, position):
        self.seek_slider.setValue(position)
    
    def update_duration(self, duration):
        self.seek_slider.setRange(0, duration)
    
    def adjust_volume(self, volume):
        self.player.set_volume(volume)


class SpotifyDownloader(QWidget):
    download_complete = pyqtSignal(str)
    
    def __init__(self, spotify_client=None):
        super().__init__()
        self.sp = spotify_client
        self.username_label = QLabel("Spotify Username:")
        self.username_input = QLineEdit()
        self.playlist_label = QLabel("Spotify Playlist URL:")
        self.playlist_input = QLineEdit()
        self.download_button = QPushButton("Download Playlist")
        self.download_button.clicked.connect(self.start_download)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        
        self.status_label = QLabel("Enter a Spotify playlist URL to download")
        
        layout = QVBoxLayout()
        layout.addWidget(self.username_label)
        layout.addWidget(self.username_input)
        layout.addWidget(self.playlist_label)
        layout.addWidget(self.playlist_input)
        layout.addWidget(self.download_button)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
    
    def start_download(self):
        if not self.sp:
            QMessageBox.warning(self, "Error", "Spotify client not initialized!")
            return
            
        username = self.username_input.text().strip()
        playlist_url = self.playlist_input.text().strip()
        
        if not username or not playlist_url:
            QMessageBox.warning(self, "Input Error", "Please enter both username and playlist URL")
            return
        
        try:
            playlist_id = self.extract_playlist_id(playlist_url)
            output_folder = QFileDialog.getExistingDirectory(self, "Select Output Directory")
            
            if output_folder:
                self.download_button.setEnabled(False)
                self.status_label.setText("Fetching playlist information...")
                self.progress_bar.setValue(0)
                
                # Create worker thread
                self.download_thread = DownloadWorker(username, playlist_id, output_folder, self.sp)
                self.download_thread.progress.connect(self.update_progress)
                self.download_thread.finished.connect(self.download_finished)
                self.download_thread.error.connect(self.download_error)
                self.download_thread.start()
        
        except ValueError as e:
            QMessageBox.warning(self, "Invalid URL", str(e))
    
    def extract_playlist_id(self, playlist_url):
        match = re.search(r'playlist/([a-zA-Z0-9]+)', playlist_url)
        if match:
            return match.group(1)
        else:
            raise ValueError("Invalid Spotify Playlist URL")
    
    def update_progress(self, current, song_name):
        try:
            # get total from thread
            total = len(self.download_thread.sp.user_playlist_tracks(
                user=self.download_thread.username, 
                playlist_id=self.download_thread.playlist_id
            )['items'])
            
            percentage = int((current / total) * 100)
            self.progress_bar.setValue(percentage)
            self.status_label.setText(f"Downloading {current}/{total}: {song_name}")
        except Exception as e:
            self.status_label.setText(f"Downloading: {song_name}")
            # just show indeterminate progress if we cant get the total
            self.progress_bar.setRange(0, 0)
    
    def download_finished(self, playlist_folder):
        self.download_button.setEnabled(True)
        self.status_label.setText(f"Download complete! Files saved to: {playlist_folder}")
        self.progress_bar.setValue(100)
        
        self.download_complete.emit(playlist_folder)
    
    def download_error(self, error_message):
        self.download_button.setEnabled(True)
        self.status_label.setText(f"Error: {error_message}")
        QMessageBox.critical(self, "Download Error", error_message)


class SpotifyPlayerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Spotify Playlist Downloader & Player")
        self.setGeometry(100, 100, 800, 600)
        
        # initialize Spotify client
        self.sp = self.setup_spotify_client()
        self.player = AudioPlayer()
        self.playlist = Playlist(self.player)
        self.player.setParent(self)
        self.controls = Controls(self.player, self.playlist)
        

        self.downloader = SpotifyDownloader(self.sp)
        self.downloader.download_complete.connect(self.load_downloaded_playlist)
        
        player_group = QGroupBox("MP3 Player")
        player_layout = QVBoxLayout()
        player_layout.addWidget(self.playlist)
        player_layout.addWidget(self.controls)
        player_group.setLayout(player_layout)
        
        downloader_group = QGroupBox("Spotify Downloader")
        downloader_layout = QVBoxLayout()
        downloader_layout.addWidget(self.downloader)
        downloader_group.setLayout(downloader_layout)
        
        main_layout = QVBoxLayout()
        main_layout.addWidget(downloader_group)
        main_layout.addWidget(player_group)
        
        self.setLayout(main_layout)
    
    def setup_spotify_client(self):
        load_dotenv()
        client_id = os.getenv("CLIENT_ID")
        client_secret = os.getenv("CLIENT_SECRET")
        redirect_uri = os.getenv("REDIRECT_URI", "http://localhost:8888/callback")
        
        if not client_id or not client_secret:
            client_id, ok1 = QInputDialog.getText(self, "Spotify API", "Enter your Spotify Client ID:")
            if not ok1 or not client_id:
                QMessageBox.warning(self, "Missing Credentials", 
                                 "Client ID is required. Get one from https://developer.spotify.com/dashboard/")
                return None
                
            client_secret, ok2 = QInputDialog.getText(self, "Spotify API", "Enter your Spotify Client Secret:")
            if not ok2 or not client_secret:
                QMessageBox.warning(self, "Missing Credentials", 
                                 "Client Secret is required. Get one from https://developer.spotify.com/dashboard/")
                return None
            save = QMessageBox.question(self, "Save Credentials", 
                                    "Do you want to save these credentials for future use?",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if save == QMessageBox.StandardButton.Yes:
                with open(".env", "w") as f:
                    f.write(f"CLIENT_ID={client_id}\n")
                    f.write(f"CLIENT_SECRET={client_secret}\n")
                    f.write(f"REDIRECT_URI={redirect_uri}\n")
        
        try:
            return spotipy.Spotify(auth_manager=SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                scope="playlist-read-private"
            ))
        except Exception as e:
            QMessageBox.critical(self, "Spotify API Error", f"Failed to initialize Spotify client: {str(e)}")
            return None
    
    def load_downloaded_playlist(self, folder_path):
        self.playlist.clear_playlist()

        mp3_files = []
        for file in os.listdir(folder_path):
            if file.endswith('.mp3'):
                mp3_files.append(os.path.join(folder_path, file))
        
        # Add to playlist
        if mp3_files:
            self.playlist.add_files_to_playlist(mp3_files)
            QMessageBox.information(self, "Playlist Loaded", 
                                  f"Successfully loaded {len(mp3_files)} songs to the playlist.")
        else:
            QMessageBox.warning(self, "No MP3 Files", 
                              "No MP3 files were found in the downloaded folder.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    player_app = SpotifyPlayerApp()
    player_app.show()
    sys.exit(app.exec())