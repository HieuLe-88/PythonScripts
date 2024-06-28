import os
import requests
from bs4 import BeautifulSoup
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from google.oauth2.credentials import Credentials
import webbrowser
import tkinter as tk
from tkinter import messagebox, filedialog

# Google OAuth2 credentials (replace with your own)
CLIENT_ID = 'your-client-id'
CLIENT_SECRET = 'your-client-secret'
SCOPES = ['https://www.googleapis.com/auth/userinfo.email']

class DuolingoDownloader:
    def __init__(self, master):
        self.master = master
        self.master.title("Duolingo Media Downloader")

        tk.Label(master, text="Lesson URL:").grid(row=0, column=0, padx=10, pady=5)
        self.lesson_entry = tk.Entry(master, width=50)
        self.lesson_entry.grid(row=0, column=1, padx=10, pady=5)

        self.login_button = tk.Button(master, text="Login with Google", command=self.login_google)
        self.login_button.grid(row=1, column=0, columnspan=2, pady=10)

        self.download_button = tk.Button(master, text="Download", command=self.download_media, state=tk.DISABLED)
        self.download_button.grid(row=2, column=0, columnspan=2, pady=10)

        # Google OAuth variables
        self.credentials = None
        self.session = None

    def login_google(self):
        # Create an OAuth2 flow object
        flow = Flow.from_client_config(
            client_config={
                'web': {
                    'client_id': CLIENT_ID,
                    'client_secret': CLIENT_SECRET,
                    'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                    'token_uri': 'https://oauth2.googleapis.com/token',
                    'redirect_uris': ['urn:ietf:wg:oauth:2.0:oob', 'http://localhost'],
                    'scopes': SCOPES,
                }
            },
            redirect_uri='urn:ietf:wg:oauth:2.0:oob'
        )

        # Generate authorization URL
        authorization_url, _ = flow.authorization_url(prompt='consent')

        # Open authorization URL in default web browser
        webbrowser.open(authorization_url)

        # Wait for authorization response from the server
        self.master.after(1000, lambda: self.fetch_google_token(flow))

    def fetch_google_token(self, flow):
        # Handle the callback from Google OAuth2 flow
        auth_response = self.master.clipboard_get()
        flow.fetch_token(code=auth_response)
        self.credentials = flow.credentials
        if self.credentials:
            self.session = requests.Session()
            self.session.headers.update({'Authorization': f'Bearer {self.credentials.token}'})
            self.download_button.config(state=tk.NORMAL)
            messagebox.showinfo("Success", "Logged in with Google successfully!")

    def download_media(self):
        lesson_url = self.lesson_entry.get()

        if not lesson_url:
            messagebox.showerror("Error", "Please enter a lesson URL.")
            return

        download_folder = filedialog.askdirectory()
        if not download_folder:
            messagebox.showerror("Error", "Please select a download folder.")
            return

        # Fetch the lesson page
        lesson_response = self.session.get(lesson_url)
        if lesson_response.status_code != 200:
            messagebox.showerror("Error", "Failed to load the lesson page.")
            return

        soup = BeautifulSoup(lesson_response.content, 'html.parser')
        
        # Extract and download audio and video files
        media_files = []
        audio_tags = soup.find_all('audio')
        video_tags = soup.find_all('video')
        
        for tag in audio_tags:
            source = tag.get('src')
            if source:
                media_files.append(source)
        
        for tag in video_tags:
            source = tag.get('src')
            if source:
                media_files.append(source)
        
        if not media_files:
            messagebox.showinfo("Info", "No media files found.")
            return
        
        for media_url in media_files:
            media_name = media_url.split("/")[-1]
            file_path = f"{download_folder}/{media_name}"
            try:
                media_response = self.session.get(media_url, stream=True)
                with open(file_path, 'wb') as file:
                    for chunk in media_response.iter_content(chunk_size=1024):
                        file.write(chunk)
                messagebox.showinfo("Success", f"Downloaded: {media_name}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to download {media_name}\nError: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = DuolingoDownloader(root)
    root.mainloop()
