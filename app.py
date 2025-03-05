import os
import shutil
import threading
import time
import logging
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image
import piexif
from typing import List, Tuple, Dict
import json

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  
    filename="media_backup.log", 
    format="%(asctime)s - %(levelname)s - %(message)s"
)

class MediaBackupTool:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Media Backup Tool")
        self.root.geometry("600x400")
        self.root.resizable(True, True)
        
        self.config_file = "backup_config.json"
        self.media_extensions = self.load_config()
        self.backup_thread: Optional[threading.Thread] = None
        self.is_running = False
        
        self.setup_gui()

    def setup_gui(self):
        """Setup the GUI elements"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Source folder selection
        ttk.Label(main_frame, text="Source Folder:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.source_entry = ttk.Entry(main_frame, width=50)
        self.source_entry.grid(row=0, column=1, sticky=tk.EW, pady=5, padx=5)
        self.source_button = ttk.Button(main_frame, text="Browse", command=self.browse_source)
        self.source_button.grid(row=0, column=2, pady=5)
        
        # Destination folder selection
        ttk.Label(main_frame, text="Destination Folder:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.dest_entry = ttk.Entry(main_frame, width=50)
        self.dest_entry.grid(row=1, column=1, sticky=tk.EW, pady=5, padx=5)
        self.dest_button = ttk.Button(main_frame, text="Browse", command=self.browse_destination)
        self.dest_button.grid(row=1, column=2, pady=5)
        
        # Progress section
        self.progress_label = ttk.Label(main_frame, text="Ready to start...")
        self.progress_label.grid(row=2, column=0, columnspan=3, pady=5)
        
        self.progress_bar = ttk.Progressbar(main_frame, orient=tk.HORIZONTAL, length=500, mode='determinate')
        self.progress_bar.grid(row=3, column=0, columnspan=3, pady=5)
        
        # Buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=3, pady=10)
        
        self.start_button = ttk.Button(button_frame, text="Start Backup", command=self.start_backup)
        self.start_button.grid(row=0, column=0, padx=5)
        
        self.cancel_button = ttk.Button(button_frame, text="Cancel", command=self.cancel_backup, state=tk.DISABLED)
        self.cancel_button.grid(row=0, column=1, padx=5)
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=1, column=0, sticky=(tk.W, tk.E))

    def load_config(self) -> tuple:
        """Load configuration from JSON file or use defaults"""
        default_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', 
                            '.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv',
                            '.webm', '.m4v', '.3gp')
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    return tuple(config.get('media_extensions', default_extensions))
        except Exception as e:
            logging.error(f"Error loading config: {e}")
            # Create default config file if it doesn't exist
            try:
                with open(self.config_file, 'w') as f:
                    json.dump({'media_extensions': list(default_extensions)}, f, indent=4)
            except Exception as config_write_error:
                logging.error(f"Error creating default config: {config_write_error}")
        
        return default_extensions

    def browse_source(self):
        folder = filedialog.askdirectory()
        if folder:
            self.source_entry.delete(0, tk.END)
            self.source_entry.insert(0, folder)

    def browse_destination(self):
        folder = filedialog.askdirectory()
        if folder:
            self.dest_entry.delete(0, tk.END)
            self.dest_entry.insert(0, folder)

    def count_media_files(self, source_folder) -> Dict[str, int]:
        """Count media files in the source folder"""
        image_count = 0
        video_count = 0
        
        # Walk through source folder
        for root_dir, _, files in os.walk(source_folder):
            for file in files:
                # Check file extension
                if file.lower().endswith(self.media_extensions):
                    # Separate image and video counts
                    if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')):
                        image_count += 1
                    else:
                        video_count += 1
        
        return {
            'total': image_count + video_count,
            'images': image_count,
            'videos': video_count
        }

    def start_backup(self):
        """Start the backup process in a separate thread"""
        source = self.source_entry.get().strip()
        destination = self.dest_entry.get().strip()
        
        if not source or not destination:
            messagebox.showerror("Error", "Please select both source and destination folders")
            return
        
        if not os.path.exists(source):
            messagebox.showerror("Error", "Source folder does not exist")
            return
        
        try:
            os.makedirs(destination, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Error", f"Cannot create destination folder: {e}")
            return
        
        # Count media files
        media_counts = self.count_media_files(source)
        
        # Confirm backup
        confirm_msg = (f"Found in source folder:\n"
                       f"Total Media Files: {media_counts['total']}\n"
                       f"Images: {media_counts['images']}\n"
                       f"Videos: {media_counts['videos']}\n\n"
                       f"Do you want to proceed with the backup?")
        
        response = messagebox.askyesno("Confirm Backup", confirm_msg)
        if not response:
            return
        
        self.is_running = True
        self.start_button.config(state=tk.DISABLED)
        self.cancel_button.config(state=tk.NORMAL)
        self.source_button.config(state=tk.DISABLED)
        self.dest_button.config(state=tk.DISABLED)
        
        self.backup_thread = threading.Thread(
            target=self.run_backup,
            args=(source, destination)
        )
        self.backup_thread.start()

    def run_backup(self, source: str, destination: str):
        """Run the backup process"""
        try:
            self.copy_media(source, destination)
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
        finally:
            self.is_running = False
            self.root.after(0, self.reset_gui)

    def reset_gui(self):
        """Reset GUI elements after backup completion"""
        self.start_button.config(state=tk.NORMAL)
        self.cancel_button.config(state=tk.DISABLED)
        self.source_button.config(state=tk.NORMAL)
        self.dest_button.config(state=tk.NORMAL)
        self.update_status("Ready")

    def update_status(self, message: str):
        """Update the status bar message"""
        self.status_var.set(message)
        self.root.update_idletasks()

    def cancel_backup(self):
        """Cancel the running backup operation"""
        if self.is_running:
            self.is_running = False
            self.update_status("Cancelling backup...")
            self.cancel_button.config(state=tk.DISABLED)
            self.start_button.config(state=tk.NORMAL)
            self.source_button.config(state=tk.NORMAL)
            self.dest_button.config(state=tk.NORMAL)

    def get_media_date(self, file_path):
        """Extract date from media (EXIF for images, file mod date as fallback)"""
        logging.debug(f"Attempting to extract date for: {file_path}")
        
        try:
            if file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')):
                img = Image.open(file_path)
                if hasattr(img, '_getexif') and img._getexif() is not None:
                    exif_data = piexif.load(img.info.get('exif', b''))
                    if '0th' in exif_data and piexif.ImageIFD.DateTime in exif_data['0th']:
                        date_str = exif_data['0th'][piexif.ImageIFD.DateTime].decode('utf-8')
                        return datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
        except Exception as e:
            logging.warning(f"EXIF date extraction failed: {e}")

        # Fallback to file modification time for all files
        try:
            mod_time = os.path.getmtime(file_path)
            return datetime.fromtimestamp(mod_time)
        except Exception as e:
            logging.error(f"Failed to get modification time for {file_path}: {e}")
            return None

    def safe_copy(self, src, dst):
        """Copy file, avoiding overwrites by adding a counter suffix if needed"""
        base, ext = os.path.splitext(dst)
        counter = 1
        new_dst = dst
        while os.path.exists(new_dst):
            new_dst = f"{base}_{counter}{ext}"
            counter += 1
        shutil.copy2(src, new_dst)
        return new_dst

    def copy_media(self, source_folder, destination_folder):
        """Copy media files to destination, organizing by year and month"""
        media_to_copy: List[str] = []
        
        # Log the source and destination folders
        logging.info(f"Backup source: {source_folder}")
        logging.info(f"Backup destination: {destination_folder}")
        logging.info(f"Media extensions: {self.media_extensions}")
        
        # Walk through source folder
        for root_dir, _, files in os.walk(source_folder):
            if not self.is_running:
                break
            
            for file in files:
                # Check file extension
                if file.lower().endswith(self.media_extensions):
                    file_path = os.path.join(root_dir, file)
                    media_to_copy.append(file_path)
        
        # Log number of files found
        logging.info(f"Total media files to copy: {len(media_to_copy)}")
        
        if not media_to_copy:
            messagebox.showinfo("Backup Complete", "No media files found!")
            return

        total_media = len(media_to_copy)
        self.progress_bar["maximum"] = total_media

        folder_cache = set()
        unknown_folder = os.path.join(destination_folder, "Unknown_Date")
        os.makedirs(unknown_folder, exist_ok=True)
        folder_cache.add(unknown_folder)
        
        last_update = time.time()

        for i, file_path in enumerate(media_to_copy):
            try:
                media_date = self.get_media_date(file_path)
                if media_date is None:
                    logging.warning(f"No date found for file: {file_path}")
                    folder_path = unknown_folder
                else:
                    # Organize by Year/Month
                    folder_path = os.path.join(
                        destination_folder, 
                        media_date.strftime("%Y"),
                        media_date.strftime("%m_%B")  # Month as number_name
                    )

                # Ensure folder exists
                if folder_path not in folder_cache:
                    os.makedirs(folder_path, exist_ok=True)
                    folder_cache.add(folder_path)

                # Safe copy with unique filename
                dest_path = self.safe_copy(file_path, os.path.join(folder_path, os.path.basename(file_path)))

                # Update progress
                current_time = time.time()
                if current_time - last_update >= 0.5 or i == total_media - 1:
                    self.progress_bar["value"] = i + 1
                    self.progress_label.config(text=f"Copying {i+1}/{total_media} files...")
                    self.root.update_idletasks()
                    last_update = current_time

            except Exception as e:
                logging.error(f"Error processing {file_path}: {e}")

        # Final update
        self.progress_bar["value"] = total_media
        self.progress_label.config(text=f"Copied {total_media}/{total_media} files...")
        self.root.update_idletasks()

        messagebox.showinfo("Backup Complete", f"{total_media} media files copied! Files without metadata moved to 'Unknown_Date'.")

    def run(self):
        """Start the application"""
        self.root.mainloop()

if __name__ == "__main__":
    app = MediaBackupTool()
    app.run()
