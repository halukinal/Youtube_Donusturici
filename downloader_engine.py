"""
YouTube to Premiere Pro Downloader - Core Engine
Handles all download, transcoding, and hardware acceleration logic.
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
            
            # Check for NVIDIA NVENC
            if "h264_nvenc" in encoders:
                return "nvenc"
            
            # Check for Apple VideoToolbox (Mac)
            if platform.system() == "Darwin" and "h264_videotoolbox" in encoders:
                return "videotoolbox"
            
            # Check for Intel Quick Sync Video
            if "h264_qsv" in encoders:
                return "qsv"
            
            return None
        except:
            return None
    
    def fetch_video_info(self, job: VideoJob, update_queue: queue.Queue):
        """Fetch video metadata"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False
            }
            
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
            update_queue.put({
                'url': job.url,
                'title': f"Error: {str(e)[:50]}",
                'status': 'failed'
            })
    
    def progress_hook(self, d: Dict, job: VideoJob, update_queue: queue.Queue):
        """Hook for yt-dlp progress updates"""
        if d['status'] == 'downloading':
            try:
                # Calculate percentage
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
            
            # Retry mechanism
            for attempt in range(self.retry_attempts):
                try:
                    if format_mode == "passthrough":
                        success = self.download_passthrough(
                            job, resolution, output_dir, update_queue
                        )
                    elif format_mode == "prores":
                        success = self.download_and_transcode_prores(
                            job, resolution, output_dir, update_queue
                        )
                    elif format_mode == "h264_cfr":
                        success = self.download_and_transcode_h264_cfr(
                            job, resolution, output_dir, update_queue
                        )
                    
                    if success:
                        break
                    
                except Exception as e:
                    if attempt == self.retry_attempts - 1:
                        update_queue.put({
                            'url': job.url,
                            'status': 'failed',
                            'error': f"Failed after {self.retry_attempts} attempts: {str(e)}"
                        })
            
            if success:
                completed += 1
                update_queue.put({
                    'url': job.url,
                    'status': 'finished',
                    'total_progress': (completed / total_jobs) * 100
                })
            else:
                update_queue.put({
                    'url': job.url,
                    'status': 'failed'
                })
        
        update_queue.put({'all_complete': True})
    
    def download_passthrough(
        self,
        job: VideoJob,
        resolution: str,
        output_dir: str,
        update_queue: queue.Queue
    ) -> bool:
        """Download video without re-encoding"""
        try:
            # Map resolution to format
            format_map = {
                "4K (2160p)": "bestvideo[height<=2160]+bestaudio/best",
                "1080p (Full HD)": "bestvideo[height<=1080]+bestaudio/best",
                "720p (HD)": "bestvideo[height<=720]+bestaudio/best"
            }
            
            output_template = os.path.join(output_dir, '%(title)s.%(ext)s')
            
            ydl_opts = {
                'format': format_map.get(resolution, 'bestvideo+bestaudio/best'),
                'outtmpl': output_template,
                'merge_output_format': 'mp4',
                'postprocessors': [{
                    'key': 'FFmpegMetadata',
                    'add_metadata': True,
                }],
                'progress_hooks': [lambda d: self.progress_hook(d, job, update_queue)],
                'quiet': False,
                'no_warnings': False
            }
            
            update_queue.put({
                'url': job.url,
                'status': 'downloading'
            })
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([job.url])
            
            return True
            
        except Exception as e:
            print(f"Passthrough error: {e}")
            return False
    
    def download_and_transcode_h264_cfr(
        self,
        job: VideoJob,
        resolution: str,
        output_dir: str,
        update_queue: queue.Queue
    ) -> bool:
        """
        Download and transcode to H.264 with Constant Frame Rate
        Fixes VFR issues in Premiere Pro
        """
        try:
            # First, download the video
            temp_file = os.path.join(output_dir, f"temp_{job.video_info['id']}.%(ext)s")
            
            format_map = {
                "4K (2160p)": "bestvideo[height<=2160]+bestaudio/best",
                "1080p (Full HD)": "bestvideo[height<=1080]+bestaudio/best",
                "720p (HD)": "bestvideo[height<=720]+bestaudio/best"
            }
            
            ydl_opts = {
                'format': format_map.get(resolution, 'bestvideo+bestaudio/best'),
                'outtmpl': temp_file,
                'merge_output_format': 'mkv',
                'progress_hooks': [lambda d: self.progress_hook(d, job, update_queue)],
                'quiet': True
            }
            
            update_queue.put({
                'url': job.url,
                'status': 'downloading'
            })
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(job.url, download=True)
                downloaded_file = ydl.prepare_filename(info)
            
            # Now transcode with FFmpeg to CFR H.264
            update_queue.put({
                'url': job.url,
                'status': 'encoding',
                'progress': 0
            })
            
            output_file = os.path.join(
                output_dir,
                f"{self.sanitize_filename(job.title)}_CFR.mp4"
            )
            
            # Detect frame rate from source
            fps = self.detect_frame_rate(downloaded_file)
            
            # Build FFmpeg command for H.264 CFR encoding
            ffmpeg_cmd = self.build_h264_cfr_command(
                downloaded_file,
                output_file,
                fps
            )
            
            # Execute FFmpeg with progress tracking
            self.run_ffmpeg_with_progress(
                ffmpeg_cmd,
                job,
                update_queue,
                self.get_video_duration(downloaded_file)
            )
            
            # Clean up temp file
            if os.path.exists(downloaded_file):
                os.remove(downloaded_file)
            
            return True
            
        except Exception as e:
            print(f"H.264 CFR error: {e}")
            return False
    
    def download_and_transcode_prores(
        self,
        job: VideoJob,
        resolution: str,
        output_dir: str,
        update_queue: queue.Queue
    ) -> bool:
        """
        Download and transcode to ProRes 422
        Best quality for editing
        """
        try:
            # Download phase
            temp_file = os.path.join(output_dir, f"temp_{job.video_info['id']}.%(ext)s")
            
            format_map = {
                "4K (2160p)": "bestvideo[height<=2160]+bestaudio/best",
                "1080p (Full HD)": "bestvideo[height<=1080]+bestaudio/best",
                "720p (HD)": "bestvideo[height<=720]+bestaudio/best"
            }
            
            ydl_opts = {
                'format': format_map.get(resolution, 'bestvideo+bestaudio/best'),
                'outtmpl': temp_file,
                'merge_output_format': 'mkv',
                'progress_hooks': [lambda d: self.progress_hook(d, job, update_queue)],
                'quiet': True
            }
            
            update_queue.put({
                'url': job.url,
                'status': 'downloading'
            })
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(job.url, download=True)
                downloaded_file = ydl.prepare_filename(info)
            
            # Transcode to ProRes
            update_queue.put({
                'url': job.url,
                'status': 'encoding',
                'progress': 0
            })
            
            output_file = os.path.join(
                output_dir,
                f"{self.sanitize_filename(job.title)}_ProRes.mov"
            )
            
            fps = self.detect_frame_rate(downloaded_file)
            
            # Build ProRes FFmpeg command
            ffmpeg_cmd = self.build_prores_command(
                downloaded_file,
                output_file,
                fps
            )
            
            # Execute with progress
            self.run_ffmpeg_with_progress(
                ffmpeg_cmd,
                job,
                update_queue,
                self.get_video_duration(downloaded_file)
            )
            
            # Cleanup
            if os.path.exists(downloaded_file):
                os.remove(downloaded_file)
            
            return True
            
        except Exception as e:
            print(f"ProRes error: {e}")
            return False
    
    def build_h264_cfr_command(
        self,
        input_file: str,
        output_file: str,
        fps: float
    ) -> List[str]:
        """
        Build FFmpeg command for H.264 CFR encoding
        
        Key flags explained:
        -r {fps}: Force constant frame rate (fixes VFR issues in Premiere)
        -c:v: Video codec selection (hardware accelerated if available)
        -preset slow: Better compression (use 'fast' for speed)
        -crf 18: High quality (lower = better, 18 is visually lossless)
        -pix_fmt yuv420p: Standard pixel format for compatibility
        -c:a aac -b:a 320k: High quality audio for editing
        -movflags +faststart: Optimize for streaming/preview
        """
        cmd = ["ffmpeg", "-i", input_file]
        
        # Video encoding with hardware acceleration if available
        if self.hw_encoder == "nvenc":
            cmd.extend([
                "-c:v", "h264_nvenc",
                "-preset", "slow",
                "-cq", "18",  # Quality for NVENC
                "-r", str(fps)
            ])
        elif self.hw_encoder == "videotoolbox":
            cmd.extend([
                "-c:v", "h264_videotoolbox",
                "-b:v", "10M",  # Bitrate for VideoToolbox
                "-r", str(fps)
            ])
        elif self.hw_encoder == "qsv":
            cmd.extend([
                "-c:v", "h264_qsv",
                "-preset", "slow",
                "-global_quality", "18",
                "-r", str(fps)
            ])
        else:
            # Software encoding (CPU)
            cmd.extend([
                "-c:v", "libx264",
                "-preset", "slow",
                "-crf", "18",
                "-r", str(fps)
            ])
        
        # Audio: High-quality AAC for editing
        cmd.extend([
            "-c:a", "aac",
            "-b:a", "320k",
            "-ar", "48000"  # Professional audio sample rate
        ])
        
        # Output settings
        cmd.extend([
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-y",  # Overwrite output
            output_file
        ])
        
        return cmd
    
    def build_prores_command(
        self,
        input_file: str,
        output_file: str,
        fps: float
    ) -> List[str]:
        """
        Build FFmpeg command for ProRes 422 encoding
        
        Key flags explained:
        -c:v prores_ks: High-quality ProRes encoder
        -profile:v 2: ProRes 422 (0=Proxy, 1=LT, 2=Standard, 3=HQ)
        -vendor apl0: Apple-compatible vendor code
        -pix_fmt yuv422p10le: 10-bit 4:2:2 color (editing grade)
        -c:a pcm_s16le: Uncompressed PCM audio (lossless)
        """
        cmd = [
            "ffmpeg",
            "-i", input_file,
            "-c:v", "prores_ks",
            "-profile:v", "2",  # ProRes 422 Standard
            "-vendor", "apl0",
            "-pix_fmt", "yuv422p10le",  # 10-bit 4:2:2
            "-r", str(fps),  # Constant frame rate
            "-c:a", "pcm_s16le",  # Uncompressed audio
            "-ar", "48000",
            "-y",
            output_file
        ]
        
        return cmd
    
    def detect_frame_rate(self, video_file: str) -> float:
        """Detect video frame rate using FFprobe"""
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=r_frame_rate",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_file
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            fps_str = result.stdout.strip()
            
            # Parse fraction (e.g., "30000/1001" for 29.97)
            if '/' in fps_str:
                num, den = map(int, fps_str.split('/'))
                fps = num / den
            else:
                fps = float(fps_str)
            
            # Round to common frame rates
            if 23 < fps < 25:
                return 24
            elif 24 < fps < 26:
                return 25
            elif 29 < fps < 31:
                return 30
            elif 59 < fps < 61:
                return 60
            else:
                return round(fps)
                
        except:
            return 30  # Default fallback
    
    def get_video_duration(self, video_file: str) -> float:
        """Get video duration in seconds"""
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_file
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except:
            return 0
    
    def run_ffmpeg_with_progress(
        self,
        cmd: List[str],
        job: VideoJob,
        update_queue: queue.Queue,
        duration: float
    ):
        """Run FFmpeg and parse progress"""
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        time_pattern = re.compile(r'time=(\d+):(\d+):(\d+\.\d+)')
        
        for line in process.stdout:
            match = time_pattern.search(line)
            if match and duration > 0:
                hours, minutes, seconds = match.groups()
                current_time = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                progress = (current_time / duration) * 100
                
                update_queue.put({
                    'url': job.url,
                    'progress': min(progress, 99)  # Cap at 99% until done
                })
        
        process.wait()
        
        if process.returncode != 0:
            raise Exception("FFmpeg encoding failed")
    
    def sanitize_filename(self, filename: str) -> str:
        """Remove invalid characters from filename"""
        # Remove invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        # Limit length
        return filename[:200]