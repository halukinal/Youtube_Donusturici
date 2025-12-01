"""
YouTube to Premiere Pro Downloader - Core Engine
Handles all download, transcoding, and hardware acceleration logic.
Updated for 2025 YouTube Bot Protection bypass.
"""

import yt_dlp
import subprocess
import os
import re
import platform
from pathlib import Path
from typing import Dict, List, Optional
import queue


class VideoJob:
    """Represents a single video download job"""
    def __init__(self, url: str):
        self.url = url
        self.title = "Fetching info..."
        self.status = "pending"  # pending, downloading, encoding, finished, failed
        self.progress = 0
        self.thumbnail = None
        self.video_info = None
        
        # UI references (set by main.py)
        self.ui_frame = None
        self.status_icon = None
        self.title_label = None
        self.progress_frame = None
        self.progress_bar = None
        self.progress_label = None


class DownloaderEngine:
    """Core engine for downloading and processing videos"""
    
    def __init__(self):
        self.hw_encoder = self.detect_hardware_encoder()
        self.retry_attempts = 3
        
        # Anti-Bot Configuration
        # YouTube 403 hatalarını aşmak için özel başlıklar ve istemci ayarları
        self.common_opts = {
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': False,
            'ignoreerrors': False,
            'logtostderr': False,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
            },
            # iOS istemcisi (varsayılan) şu an 403 hatası veriyor, 'web' veya 'android' daha stabil.
            'extractor_args': {
                'youtube': {
                    'player_client': ['web', 'android']
                }
            }
        }
    
    def check_ffmpeg(self) -> bool:
        """Check if FFmpeg is installed"""
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                check=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def detect_hardware_encoder(self) -> Optional[str]:
        """
        Detect available hardware encoder for FFmpeg
        Returns: 'nvenc', 'videotoolbox', 'qsv', or None
        """
        try:
            result = subprocess.run(
                ["ffmpeg", "-encoders"],
                capture_output=True,
                text=True,
                check=True
            )
            encoders = result.stdout
            
            if "h264_nvenc" in encoders:
                return "nvenc"
            if platform.system() == "Darwin" and "h264_videotoolbox" in encoders:
                return "videotoolbox"
            if "h264_qsv" in encoders:
                return "qsv"
            return None
        except:
            return None
    
    def fetch_video_info(self, job: VideoJob, update_queue: queue.Queue):
        """Fetch video metadata"""
        try:
            # Temel ayarlara extract_flat ekle
            ydl_opts = self.common_opts.copy()
            ydl_opts.update({
                'extract_flat': False
            })
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(job.url, download=False)
                job.video_info = info
                job.title = info.get('title', 'Unknown Title')
                job.thumbnail = info.get('thumbnail')
                
                update_queue.put({
                    'url': job.url,
                    'title': job.title,
                    'thumbnail': job.thumbnail
                })
        except Exception as e:
            error_msg = str(e)
            if "403" in error_msg:
                error_msg = "YouTube Access Denied (403). Try updating yt-dlp."
            
            update_queue.put({
                'url': job.url,
                'title': f"Error: {error_msg[:50]}...",
                'status': 'failed'
            })
    
    def progress_hook(self, d: Dict, job: VideoJob, update_queue: queue.Queue):
        """Hook for yt-dlp progress updates"""
        if d['status'] == 'downloading':
            try:
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                downloaded = d.get('downloaded_bytes', 0)
                
                if total > 0:
                    percent = (downloaded / total) * 100
                    job.progress = percent
                    update_queue.put({
                        'url': job.url,
                        'status': 'downloading',
                        'progress': percent
                    })
            except:
                pass
        
        elif d['status'] == 'finished':
            update_queue.put({
                'url': job.url,
                'progress': 100
            })
    
    def process_queue(
        self,
        jobs: List[VideoJob],
        resolution: str,
        format_mode: str,
        output_dir: str,
        update_queue: queue.Queue
    ):
        """Process all jobs in queue"""
        total_jobs = len(jobs)
        completed = 0
        
        for job in jobs:
            success = False
            for attempt in range(self.retry_attempts):
                try:
                    if format_mode == "passthrough":
                        success = self.download_passthrough(job, resolution, output_dir, update_queue)
                    elif format_mode == "prores":
                        success = self.download_and_transcode_prores(job, resolution, output_dir, update_queue)
                    elif format_mode == "h264_cfr":
                        success = self.download_and_transcode_h264_cfr(job, resolution, output_dir, update_queue)
                    
                    if success:
                        break
                except Exception as e:
                    if attempt == self.retry_attempts - 1:
                        update_queue.put({
                            'url': job.url,
                            'status': 'failed',
                            'error': f"Failed: {str(e)}"
                        })
            
            if success:
                completed += 1
                update_queue.put({
                    'url': job.url,
                    'status': 'finished',
                    'total_progress': (completed / total_jobs) * 100
                })
            else:
                update_queue.put({'url': job.url, 'status': 'failed'})
        
        update_queue.put({'all_complete': True})
    
    def download_passthrough(self, job: VideoJob, resolution: str, output_dir: str, update_queue: queue.Queue) -> bool:
        try:
            format_map = {
                "4K (2160p)": "bestvideo[height<=2160]+bestaudio/best",
                "1080p (Full HD)": "bestvideo[height<=1080]+bestaudio/best",
                "720p (HD)": "bestvideo[height<=720]+bestaudio/best"
            }
            
            output_template = os.path.join(output_dir, '%(title)s.%(ext)s')
            
            ydl_opts = self.common_opts.copy()
            ydl_opts.update({
                'format': format_map.get(resolution, 'bestvideo+bestaudio/best'),
                'outtmpl': output_template,
                'merge_output_format': 'mp4',
                'postprocessors': [{'key': 'FFmpegMetadata', 'add_metadata': True}],
                'progress_hooks': [lambda d: self.progress_hook(d, job, update_queue)],
                'quiet': False
            })
            
            update_queue.put({'url': job.url, 'status': 'downloading'})
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([job.url])
            return True
        except Exception as e:
            print(f"Passthrough error: {e}")
            return False
    
    def download_and_transcode_h264_cfr(self, job: VideoJob, resolution: str, output_dir: str, update_queue: queue.Queue) -> bool:
        try:
            temp_file = os.path.join(output_dir, f"temp_{job.video_info['id']}.%(ext)s")
            
            format_map = {
                "4K (2160p)": "bestvideo[height<=2160]+bestaudio/best",
                "1080p (Full HD)": "bestvideo[height<=1080]+bestaudio/best",
                "720p (HD)": "bestvideo[height<=720]+bestaudio/best"
            }
            
            ydl_opts = self.common_opts.copy()
            ydl_opts.update({
                'format': format_map.get(resolution, 'bestvideo+bestaudio/best'),
                'outtmpl': temp_file,
                'merge_output_format': 'mkv',
                'progress_hooks': [lambda d: self.progress_hook(d, job, update_queue)],
            })
            
            update_queue.put({'url': job.url, 'status': 'downloading'})
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(job.url, download=True)
                downloaded_file = ydl.prepare_filename(info)
            
            update_queue.put({'url': job.url, 'status': 'encoding', 'progress': 0})
            output_file = os.path.join(output_dir, f"{self.sanitize_filename(job.title)}_CFR.mp4")
            fps = self.detect_frame_rate(downloaded_file)
            ffmpeg_cmd = self.build_h264_cfr_command(downloaded_file, output_file, fps)
            
            self.run_ffmpeg_with_progress(ffmpeg_cmd, job, update_queue, self.get_video_duration(downloaded_file))
            
            if os.path.exists(downloaded_file): os.remove(downloaded_file)
            return True
        except Exception as e:
            print(f"H.264 CFR error: {e}")
            return False
    
    def download_and_transcode_prores(self, job: VideoJob, resolution: str, output_dir: str, update_queue: queue.Queue) -> bool:
        try:
            temp_file = os.path.join(output_dir, f"temp_{job.video_info['id']}.%(ext)s")
            format_map = {
                "4K (2160p)": "bestvideo[height<=2160]+bestaudio/best",
                "1080p (Full HD)": "bestvideo[height<=1080]+bestaudio/best",
                "720p (HD)": "bestvideo[height<=720]+bestaudio/best"
            }
            ydl_opts = self.common_opts.copy()
            ydl_opts.update({
                'format': format_map.get(resolution, 'bestvideo+bestaudio/best'),
                'outtmpl': temp_file,
                'merge_output_format': 'mkv',
                'progress_hooks': [lambda d: self.progress_hook(d, job, update_queue)],
            })
            
            update_queue.put({'url': job.url, 'status': 'downloading'})
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(job.url, download=True)
                downloaded_file = ydl.prepare_filename(info)
            
            update_queue.put({'url': job.url, 'status': 'encoding', 'progress': 0})
            output_file = os.path.join(output_dir, f"{self.sanitize_filename(job.title)}_ProRes.mov")
            fps = self.detect_frame_rate(downloaded_file)
            ffmpeg_cmd = self.build_prores_command(downloaded_file, output_file, fps)
            
            self.run_ffmpeg_with_progress(ffmpeg_cmd, job, update_queue, self.get_video_duration(downloaded_file))
            
            if os.path.exists(downloaded_file): os.remove(downloaded_file)
            return True
        except Exception as e:
            print(f"ProRes error: {e}")
            return False
            
    def build_h264_cfr_command(self, input_file: str, output_file: str, fps: float) -> List[str]:
        cmd = ["ffmpeg", "-i", input_file]
        if self.hw_encoder == "nvenc":
            cmd.extend(["-c:v", "h264_nvenc", "-preset", "slow", "-cq", "18", "-r", str(fps)])
        elif self.hw_encoder == "videotoolbox":
            cmd.extend(["-c:v", "h264_videotoolbox", "-b:v", "10M", "-r", str(fps)])
        elif self.hw_encoder == "qsv":
            cmd.extend(["-c:v", "h264_qsv", "-preset", "slow", "-global_quality", "18", "-r", str(fps)])
        else:
            cmd.extend(["-c:v", "libx264", "-preset", "slow", "-crf", "18", "-r", str(fps)])
        cmd.extend(["-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-y", output_file])
        return cmd
    
    def build_prores_command(self, input_file: str, output_file: str, fps: float) -> List[str]:
        return ["ffmpeg", "-i", input_file, "-c:v", "prores_ks", "-profile:v", "2", "-vendor", "apl0", 
                "-pix_fmt", "yuv422p10le", "-r", str(fps), "-c:a", "pcm_s16le", "-ar", "48000", "-y", output_file]
    
    def detect_frame_rate(self, video_file: str) -> float:
        try:
            cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate", 
                   "-of", "default=noprint_wrappers=1:nokey=1", video_file]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            fps_str = result.stdout.strip()
            if '/' in fps_str:
                num, den = map(int, fps_str.split('/'))
                fps = num / den
            else:
                fps = float(fps_str)
            if 23 < fps < 25: return 24
            elif 24 < fps < 26: return 25
            elif 29 < fps < 31: return 30
            elif 59 < fps < 61: return 60
            else: return round(fps)
        except:
            return 30
    
    def get_video_duration(self, video_file: str) -> float:
        try:
            cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_file]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except:
            return 0
    
    def run_ffmpeg_with_progress(self, cmd: List[str], job: VideoJob, update_queue: queue.Queue, duration: float):
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, bufsize=1)
        time_pattern = re.compile(r'time=(\d+):(\d+):(\d+\.\d+)')
        for line in process.stdout:
            match = time_pattern.search(line)
            if match and duration > 0:
                h, m, s = match.groups()
                current = int(h) * 3600 + int(m) * 60 + float(s)
                update_queue.put({'url': job.url, 'progress': min((current / duration) * 100, 99)})
        process.wait()
        if process.returncode != 0: raise Exception("FFmpeg encoding failed")
    
    def sanitize_filename(self, filename: str) -> str:
        return re.sub(r'[<>:"/\\|?*]', '', filename)[:200]