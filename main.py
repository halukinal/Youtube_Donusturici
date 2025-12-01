"""
YouTube to Premiere Pro Downloader - Main GUI
Production-ready desktop application for downloading and optimizing YouTube videos
for Adobe Premiere Pro editing workflows.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import queue
import os
import sys
from pathlib import Path
from typing import Dict, List
from downloader_engine import DownloaderEngine, VideoJob

# Configure CustomTkinter appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class YTPremiereDownloader(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Window configuration
        self.title("YouTube to Premiere Pro Downloader")
        self.geometry("1000x800")
        self.minsize(900, 700)
        
        # Initialize downloader engine
        self.engine = DownloaderEngine()
        
        # Check FFmpeg availability
        if not self.engine.check_ffmpeg():
            messagebox.showerror(
                "FFmpeg Not Found",
                "FFmpeg is not installed or not in PATH.\n\n"
                "Please install FFmpeg:\n"
                "• Windows: Download from ffmpeg.org\n"
                "• Mac: brew install ffmpeg\n"
                "• Linux: sudo apt install ffmpeg"
            )
            self.quit()
            sys.exit(1)
        
        # Queue for thread communication
        self.update_queue = queue.Queue()
        
        # Video jobs dictionary
        self.video_jobs: Dict[str, VideoJob] = {}
        
        # UI State
        self.is_processing = False
        self.output_dir = str(Path.home() / "Downloads")
        
        # Build UI
        self.create_ui()
        
        # Enable drag and drop
        self.drop_target_register(tk.DND_FILES)
        self.dnd_bind('<<Drop>>', self.handle_drop)
        
        # Start update loop
        self.after(100, self.process_queue)
        
    def create_ui(self):
        """Build the user interface"""
        
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 10))
        
        title_label = ctk.CTkLabel(
            header,
            text="YouTube to Premiere Pro",
            font=ctk.CTkFont(size=28, weight="bold")
        )
        title_label.pack()
        
        subtitle_label = ctk.CTkLabel(
            header,
            text="Professional video downloader optimized for Adobe Premiere Pro",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        subtitle_label.pack()
        
        # Input Section
        input_frame = ctk.CTkFrame(self)
        input_frame.pack(fill="x", padx=20, pady=10)
        
        # URL Input Row
        url_row = ctk.CTkFrame(input_frame, fg_color="transparent")
        url_row.pack(fill="x", padx=15, pady=(15, 10))
        
        self.url_entry = ctk.CTkEntry(
            url_row,
            placeholder_text="Paste YouTube URL here or drag & drop...",
            height=40
        )
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.url_entry.bind("<Return>", lambda e: self.add_url())
        
        paste_btn = ctk.CTkButton(
            url_row,
            text="Paste",
            width=80,
            command=self.paste_from_clipboard
        )
        paste_btn.pack(side="left", padx=5)
        
        add_btn = ctk.CTkButton(
            url_row,
            text="Add URL",
            width=100,
            command=self.add_url
        )
        add_btn.pack(side="left")
        
        # Settings Grid
        settings_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        settings_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        # Resolution
        res_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        res_frame.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        ctk.CTkLabel(res_frame, text="Resolution", font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.resolution_var = tk.StringVar(value="1080p")
        resolution_combo = ctk.CTkComboBox(
            res_frame,
            values=["4K (2160p)", "1080p (Full HD)", "720p (HD)"],
            variable=self.resolution_var,
            state="readonly"
        )
        resolution_combo.pack(fill="x", pady=(5, 0))
        
        # Format Mode
        format_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        format_frame.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        ctk.CTkLabel(format_frame, text="Format Mode", font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.format_var = tk.StringVar(value="h264_cfr")
        format_combo = ctk.CTkComboBox(
            format_frame,
            values=[
                "Pass-through (MP4/MKV)",
                "Editor Ready (ProRes 422)",
                "Editor Ready (H.264 CFR)"
            ],
            variable=self.format_var,
            state="readonly",
            command=self.on_format_change
        )
        format_combo.pack(fill="x", pady=(5, 0))
        
        # Output Directory
        output_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        output_frame.pack(side="left", fill="x", expand=True)
        
        ctk.CTkLabel(output_frame, text="Output Directory", font=ctk.CTkFont(size=12)).pack(anchor="w")
        
        output_row = ctk.CTkFrame(output_frame, fg_color="transparent")
        output_row.pack(fill="x", pady=(5, 0))
        
        self.output_entry = ctk.CTkEntry(output_row, height=32)
        self.output_entry.insert(0, self.output_dir)
        self.output_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        browse_btn = ctk.CTkButton(
            output_row,
            text="Browse",
            width=80,
            command=self.browse_output
        )
        browse_btn.pack(side="left")
        
        # Format description
        self.format_desc = ctk.CTkLabel(
            input_frame,
            text="Fast download, no re-encoding",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.format_desc.pack(padx=15, pady=(0, 10))
        
        # Queue List
        queue_frame = ctk.CTkFrame(self)
        queue_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        queue_header = ctk.CTkFrame(queue_frame, fg_color="transparent")
        queue_header.pack(fill="x", padx=15, pady=(10, 5))
        
        ctk.CTkLabel(
            queue_header,
            text="Download Queue",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(side="left")
        
        # Scrollable frame for videos
        self.queue_scroll = ctk.CTkScrollableFrame(queue_frame, height=300)
        self.queue_scroll.pack(fill="both", expand=True, padx=15, pady=(5, 15))
        
        # Empty state
        self.empty_label = ctk.CTkLabel(
            self.queue_scroll,
            text="📹\n\nNo videos in queue\nAdd URLs to get started",
            font=ctk.CTkFont(size=14),
            text_color="gray"
        )
        self.empty_label.pack(pady=50)
        
        # Progress Section
        progress_frame = ctk.CTkFrame(self)
        progress_frame.pack(fill="x", padx=20, pady=(0, 10))
        
        # Current file progress
        current_frame = ctk.CTkFrame(progress_frame, fg_color="transparent")
        current_frame.pack(fill="x", padx=15, pady=(15, 10))
        
        current_label_row = ctk.CTkFrame(current_frame, fg_color="transparent")
        current_label_row.pack(fill="x")
        
        ctk.CTkLabel(
            current_label_row,
            text="Current File",
            font=ctk.CTkFont(size=12)
        ).pack(side="left")
        
        self.current_percent_label = ctk.CTkLabel(
            current_label_row,
            text="0%",
            font=ctk.CTkFont(size=12),
            text_color="#3b82f6"
        )
        self.current_percent_label.pack(side="right")
        
        self.current_progress = ctk.CTkProgressBar(current_frame, height=12)
        self.current_progress.pack(fill="x", pady=(5, 0))
        self.current_progress.set(0)
        
        # Total progress
        total_frame = ctk.CTkFrame(progress_frame, fg_color="transparent")
        total_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        total_label_row = ctk.CTkFrame(total_frame, fg_color="transparent")
        total_label_row.pack(fill="x")
        
        ctk.CTkLabel(
            total_label_row,
            text="Total Progress",
            font=ctk.CTkFont(size=12)
        ).pack(side="left")
        
        self.total_percent_label = ctk.CTkLabel(
            total_label_row,
            text="0%",
            font=ctk.CTkFont(size=12),
            text_color="#a855f7"
        )
        self.total_percent_label.pack(side="right")
        
        self.total_progress = ctk.CTkProgressBar(total_frame, height=12)
        self.total_progress.pack(fill="x", pady=(5, 0))
        self.total_progress.set(0)
        
        # Action Buttons
        action_frame = ctk.CTkFrame(self)
        action_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        button_row = ctk.CTkFrame(action_frame, fg_color="transparent")
        button_row.pack(fill="x", padx=15, pady=15)
        
        self.start_btn = ctk.CTkButton(
            button_row,
            text="Start Download",
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.start_download
        )
        self.start_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        clear_btn = ctk.CTkButton(
            button_row,
            text="Clear Finished",
            height=40,
            fg_color="gray30",
            hover_color="gray20",
            command=self.clear_finished
        )
        clear_btn.pack(side="left", padx=(0, 10))
        
        # Info footer
        info_label = ctk.CTkLabel(
            self,
            text="FFmpeg-powered • Hardware acceleration enabled • VFR to CFR conversion",
            font=ctk.CTkFont(size=10),
            text_color="gray40"
        )
        info_label.pack(pady=(0, 10))
    
    def on_format_change(self, choice):
        """Update description when format changes"""
        descriptions = {
            "Pass-through (MP4/MKV)": "Fast download, no re-encoding",
            "Editor Ready (ProRes 422)": "Best for heavy editing - transcodes to MOV ProRes 422",
            "Editor Ready (H.264 CFR)": "Fixes Premiere audio sync - converts to constant frame rate"
        }
        self.format_desc.configure(text=descriptions.get(choice, ""))
    
    def paste_from_clipboard(self):
        """Paste URL from clipboard"""
        try:
            clipboard_text = self.clipboard_get()
            if clipboard_text:
                self.url_entry.delete(0, tk.END)
                self.url_entry.insert(0, clipboard_text)
                if "youtube.com" in clipboard_text or "youtu.be" in clipboard_text:
                    self.add_url()
        except:
            pass
    
    def browse_output(self):
        """Browse for output directory"""
        directory = filedialog.askdirectory(initialdir=self.output_dir)
        if directory:
            self.output_dir = directory
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, directory)
    
    def add_url(self):
        """Add URL to queue"""
        url = self.url_entry.get().strip()
        if not url:
            return
        
        if url in self.video_jobs:
            messagebox.showwarning("Duplicate", "This URL is already in the queue.")
            return
        
        # Hide empty label
        self.empty_label.pack_forget()
        
        # Create video job
        job = VideoJob(url)
        self.video_jobs[url] = job
        
        # Create UI element for this job
        self.create_video_item(job)
        
        # Clear entry
        self.url_entry.delete(0, tk.END)
        
        # Fetch video info in background
        threading.Thread(
            target=self.engine.fetch_video_info,
            args=(job, self.update_queue),
            daemon=True
        ).start()
        
        self.update_start_button()
    
    def create_video_item(self, job: VideoJob):
        """Create UI element for video"""
        item_frame = ctk.CTkFrame(self.queue_scroll)
        item_frame.pack(fill="x", pady=5)
        
        content = ctk.CTkFrame(item_frame, fg_color="transparent")
        content.pack(fill="x", padx=10, pady=10)
        
        # Icon and title
        left_side = ctk.CTkFrame(content, fg_color="transparent")
        left_side.pack(side="left", fill="both", expand=True)
        
        title_row = ctk.CTkFrame(left_side, fg_color="transparent")
        title_row.pack(fill="x", anchor="w")
        
        job.status_icon = ctk.CTkLabel(title_row, text="⏳", font=ctk.CTkFont(size=16))
        job.status_icon.pack(side="left", padx=(0, 8))
        
        job.title_label = ctk.CTkLabel(
            title_row,
            text="Fetching info...",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        job.title_label.pack(side="left", anchor="w")
        
        url_label = ctk.CTkLabel(
            left_side,
            text=job.url,
            font=ctk.CTkFont(size=10),
            text_color="gray"
        )
        url_label.pack(anchor="w", pady=(2, 0))
        
        # Progress bar (hidden initially)
        job.progress_frame = ctk.CTkFrame(left_side, fg_color="transparent")
        
        job.progress_bar = ctk.CTkProgressBar(job.progress_frame, height=8)
        job.progress_bar.pack(fill="x", pady=(8, 0))
        job.progress_bar.set(0)
        
        job.progress_label = ctk.CTkLabel(
            job.progress_frame,
            text="",
            font=ctk.CTkFont(size=10),
            text_color="gray"
        )
        job.progress_label.pack(anchor="w", pady=(2, 0))
        
        job.ui_frame = item_frame
    
    def handle_drop(self, event):
        """Handle drag and drop"""
        files = self.tk.splitlist(event.data)
        for file in files:
            if "youtube.com" in file or "youtu.be" in file:
                self.url_entry.delete(0, tk.END)
                self.url_entry.insert(0, file)
                self.add_url()
    
    def start_download(self):
        """Start downloading videos"""
        if self.is_processing:
            return
        
        pending_jobs = [j for j in self.video_jobs.values() if j.status == "pending"]
        if not pending_jobs:
            messagebox.showinfo("No Videos", "No pending videos to download.")
            return
        
        self.is_processing = True
        self.start_btn.configure(state="disabled", text="Processing...")
        
        # Get settings
        resolution = self.resolution_var.get()
        format_mode = self.format_var.get()
        output_dir = self.output_entry.get()
        
        # Map format selection to engine format
        format_map = {
            "Pass-through (MP4/MKV)": "passthrough",
            "Editor Ready (ProRes 422)": "prores",
            "Editor Ready (H.264 CFR)": "h264_cfr"
        }
        
        # Start download thread
        threading.Thread(
            target=self.engine.process_queue,
            args=(pending_jobs, resolution, format_map[format_mode], output_dir, self.update_queue),
            daemon=True
        ).start()
    
    def process_queue(self):
        """Process updates from background threads"""
        try:
            while True:
                update = self.update_queue.get_nowait()
                
                url = update.get("url")
                job = self.video_jobs.get(url)
                
                if not job:
                    continue
                
                # Update job
                if "title" in update:
                    job.title = update["title"]
                    job.title_label.configure(text=job.title)
                
                if "status" in update:
                    job.status = update["status"]
                    status_icons = {
                        "pending": "⏳",
                        "downloading": "⬇️",
                        "encoding": "⚙️",
                        "finished": "✅",
                        "failed": "❌"
                    }
                    job.status_icon.configure(text=status_icons.get(job.status, "⏳"))
                
                if "progress" in update:
                    job.progress = update["progress"]
                    
                    if job.status in ["downloading", "encoding"]:
                        job.progress_frame.pack(fill="x", pady=(8, 0))
                        job.progress_bar.set(job.progress / 100)
                        
                        status_text = "Downloading" if job.status == "downloading" else "Encoding"
                        job.progress_label.configure(
                            text=f"{status_text} - {int(job.progress)}%"
                        )
                        
                        # Update current progress
                        self.current_progress.set(job.progress / 100)
                        self.current_percent_label.configure(text=f"{int(job.progress)}%")
                
                if "total_progress" in update:
                    total = update["total_progress"]
                    self.total_progress.set(total / 100)
                    self.total_percent_label.configure(text=f"{int(total)}%")
                
                if "error" in update:
                    messagebox.showerror("Download Error", update["error"])
                
                if update.get("all_complete"):
                    self.is_processing = False
                    self.start_btn.configure(state="normal", text="Start Download")
                    self.current_progress.set(0)
                    self.current_percent_label.configure(text="0%")
                    messagebox.showinfo("Complete", "All downloads finished!")
                
                self.update_start_button()
                
        except queue.Empty:
            pass
        
        self.after(100, self.process_queue)
    
    def update_start_button(self):
        """Update start button text"""
        pending_count = sum(1 for j in self.video_jobs.values() if j.status == "pending")
        if not self.is_processing:
            self.start_btn.configure(text=f"Start Download ({pending_count})")
    
    def clear_finished(self):
        """Remove finished videos from queue"""
        to_remove = []
        for url, job in self.video_jobs.items():
            if job.status == "finished":
                job.ui_frame.destroy()
                to_remove.append(url)
        
        for url in to_remove:
            del self.video_jobs[url]
        
        self.total_progress.set(0)
        self.total_percent_label.configure(text="0%")
        
        if not self.video_jobs:
            self.empty_label.pack(pady=50)
        
        self.update_start_button()


if __name__ == "__main__":
    app = YTPremiereDownloader()
    app.mainloop()