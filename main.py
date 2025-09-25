# main_ctk.py — WhisperGlass with CTkinter
import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import os
import queue
from pathlib import Path
from PIL import Image

# Import your processing functions (make sure these exist)
from audio import start_audio
from text import start_text, save_final_transcript


class VideoTranscriptApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window setup
        self.title("WhisperGlass — Video to Transcript")
        self.geometry("1600x900")
        self.state("zoomed")
        self.set_window_icon()  # Call the method to set the icon

        # CTk Appearance
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        # Variables
        self.video_path = ctk.StringVar()
        self.transcript_path = ""
        self.is_processing = False
        self.progress_queue = queue.Queue()
        self.is_editing = False
        self.active_frame = None
        self.transcript_content = ""  # New variable to hold transcript content

        # Define colors and fonts for a consistent aesthetic
        self.colors = {
            'primary': '#6366f1',      # Indigo
            'primary_hover': '#4f46e5',
            'secondary': '#8b5cf6',    # Purple
            'success': '#10b981',      # Emerald Green
            'success_hover': '#059669',
            'surface': '#ffffff',
            'surface_lo': '#f8fafc',
            'border': '#e2e8f0',
            'text': '#1e293b',
            'text_dim': '#64748b',
            'text_placeholder': '#94a3b8',
            'shadow': '#f1f5f9',
        }
        self.title_font = ctk.CTkFont(family="Segoe UI", size=26, weight="bold")
        self.header_font = ctk.CTkFont(family="Segoe UI", size=16, weight="bold")
        self.body_font = ctk.CTkFont(family="Segoe UI", size=14)
        self.button_font = ctk.CTkFont(family="Segoe UI", size=13, weight="bold")

        # Define colors for the UI elements
        self.LIGHT_BORDER_COLOR = "#cccccc"
        self.DARK_BORDER_COLOR = "#444444"
        self.LIGHT_PANEL_BG = "#f0f0f0"
        self.DARK_PANEL_BG = "#2b2b2b"

        # Load custom icons
        self.edit_icon_image = self.load_icon("edit_icon.png")
        self.save_icon_image = self.load_icon("save_icon.png")
        self.cancel_icon_image = self.load_icon("cancel_icon.png")

        # Build UI
        self.setup_ui()
        self.process_queue_updates()

    def load_icon(self, filename, size=(16, 16)):
        """Loads a PNG icon file and returns a CTkImage object."""
        try:
            path = Path(__file__).parent.resolve() / "Static" / filename
            if os.path.exists(path):
                img = Image.open(path)
                return ctk.CTkImage(light_image=img, dark_image=img, size=size)
            else:
                print(f"Warning: Icon file '{filename}' not found. Using default text.")
                return None
        except Exception as e:
            print(f"Error loading icon '{filename}': {e}")
            return None

    def set_window_icon(self):
        """Sets a custom icon for the application window."""
        try:
            script_dir = Path(__file__).parent.resolve()
            icon_path_ico = script_dir / "Static" / "icon.ico"
            icon_path_png = script_dir / "Static" / "icon.png"

            if os.path.exists(icon_path_ico):
                self.iconbitmap(str(icon_path_ico))
            elif os.path.exists(icon_path_png):
                self.iconphoto(False, Image.open(icon_path_png))
            else:
                print("Warning: Icon file not found. Using default icon.")
        except Exception as e:
            print(f"Error setting window icon: {e}")

    def setup_ui(self):
        # ================= Main container =================
        main_container = ctk.CTkFrame(self, corner_radius=0)
        main_container.pack(fill="both", expand=True, padx=2, pady=2)

        # ================= Navbar =================
        navbar_frame = ctk.CTkFrame(main_container, fg_color="transparent", border_width=0)
        navbar_frame.pack(fill="x", pady=(20, 15))  # Added top margin

        self.title_label_nav = ctk.CTkLabel(
            navbar_frame,
            text="🎬 WhisperGlass",
            font=ctk.CTkFont(size=28, weight="bold"),
        )
        self.title_label_nav.pack(side="left", padx=(10, 20))

        self.main_btn = ctk.CTkButton(
            navbar_frame,
            text="Main",
            command=lambda: self.show_frame("main"),
            font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=8,
            width=100
        )
        self.main_btn.pack(side="left", padx=5)

        self.logs_btn = ctk.CTkButton(
            navbar_frame,
            text="Logs",
            command=lambda: self.show_frame("logs"),
            font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=8,
            width=100
        )
        self.logs_btn.pack(side="left", padx=5)

        # New Saved Transcripts Button
        self.saved_transcripts_btn = ctk.CTkButton(
            navbar_frame,
            text="Saved",
            command=lambda: self.show_frame("saved"),
            font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=8,
            width=100
        )
        self.saved_transcripts_btn.pack(side="left", padx=5)

        # ================= Main Content =================
        self.main_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        main_split = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        main_split.pack(fill="both", expand=True)

        # ---------- Left Panel (Refactored) ----------
        self.left_panel = ctk.CTkFrame(
            main_split,
            corner_radius=12,
            width=420,
            fg_color=self.cget("fg_color"),
            border_color="#cccccc",
            border_width=1
        )
        self.left_panel.pack(side="left", fill="y", padx=(20, 20), pady=15)
        self.left_panel.pack_propagate(False)
        self.left_panel.grid_columnconfigure(0, weight=1)
        self.left_panel.grid_columnconfigure(1, weight=1)

        # Header
        self.upload_header = ctk.CTkLabel(
            self.left_panel,
            text="📤 Upload & Convert",
            font=self.title_font,
            text_color=self.colors['text']
        )
        self.upload_header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=30, pady=(40, 0))

        # Subtitle
        self.upload_subtitle = ctk.CTkLabel(
            self.left_panel,
            text="Choose a video file and let AI do the rest.",
            wraplength=360,
            font=self.body_font,
            text_color=self.colors['text_dim'],
            justify="center"
        )
        self.upload_subtitle.grid(row=1, column=0, columnspan=2, sticky="ew", padx=30, pady=(0, 20))

        # Video file label
        self.video_file_label = ctk.CTkLabel(
            self.left_panel,
            text="VIDEO FILE",
            font=self.header_font,
            text_color=self.colors['text_dim']
        )
        self.video_file_label.grid(row=2, column=0, columnspan=2, sticky="w", padx=30, pady=(0, 5))

        # Video file entry
        self.entry = ctk.CTkEntry(
            self.left_panel,
            textvariable=self.video_path,
            placeholder_text="No file selected",
            font=self.body_font,
            corner_radius=6,
            height=35,
            fg_color=self.colors['shadow'],
            text_color=self.colors['text']
        )
        self.entry.grid(row=3, column=0, columnspan=2, sticky="ew", padx=30, pady=(0, 10))

        # Browse Button
        ctk.CTkButton(
            self.left_panel,
            text="Browse File...",
            command=self.browse_file,
            fg_color=self.colors['success'],
            hover_color=self.colors['success_hover'],
            font=self.button_font,
            height=35
        ).grid(row=4, column=0, columnspan=2, sticky="ew", padx=30, pady=(10, 20))

        # Status Label (multi-line capable)
        self.status_label = ctk.CTkLabel(
            self.left_panel,
            text="✨ Ready to convert your video.",
            font=self.body_font,
            text_color=self.colors['text_dim'],
            wraplength=360,
            justify="left",
            anchor="nw"
        )
        self.status_label.grid(row=5, column=0, columnspan=2, sticky="nw", padx=30, pady=(25, 5))
        self.left_panel.grid_rowconfigure(5, minsize=40)  # Reserve vertical space

        # Progress Bar
        self.progress_bar = ctk.CTkProgressBar(
            self.left_panel,
            progress_color=self.colors['secondary'],
            height=6
        )
        self.progress_bar.set(0)
        self.progress_bar.grid(row=6, column=0, columnspan=2, sticky="ew", padx=30, pady=(0, 30))

        # Action Buttons
        self.process_btn = ctk.CTkButton(
            self.left_panel,
            text="🚀 Start Magic",
            command=self.start_processing,
            state="disabled",
            fg_color=self.colors['success'],
            hover_color=self.colors['success_hover'],
            font=self.button_font,
            height=40
        )
        self.process_btn.grid(row=7, column=0, sticky="ew", padx=(30, 7.5), pady=(0, 10))

        self.save_btn = ctk.CTkButton(
            self.left_panel,
            text="💾 Save Transcript",
            command=self.save_transcript,
            state="disabled",
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_hover'],
            font=self.button_font,
            height=40
        )
        self.save_btn.grid(row=7, column=1, sticky="ew", padx=(7.5, 30), pady=(0, 10))

        # ---------- Right Panel ----------
        self.right_panel = ctk.CTkFrame(
            main_split,
            corner_radius=12,
            fg_color=self.cget("fg_color"),
            border_color="#cccccc",
            border_width=1
        )
        self.right_panel.pack(side="left", fill="both", expand=True, padx=(0, 20), pady=15)

        # Transcript section
        header_frame = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(15, 10))

        self.transcript_header = ctk.CTkLabel(header_frame, text="📜 Transcript", font=ctk.CTkFont(size=22, weight="bold"))
        self.transcript_header.pack(side="left")

        icon_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        icon_frame.pack(side="right")

        # Modified edit button to use image and no text
        self.edit_btn = ctk.CTkButton(icon_frame, width=40, text="", image=self.edit_icon_image, command=self.toggle_edit_mode)
        self.edit_btn.pack(side="left", padx=2)

        # Modified save edit button
        self.save_edit_btn = ctk.CTkButton(icon_frame, width=40, text="💾", command=self.save_edited_transcript, state="disabled")
        self.save_edit_btn.pack(side="left", padx=2)

        # New Clear Transcript Button
        self.clear_btn = ctk.CTkButton(icon_frame, text="🧹", width=40, command=self.clear_transcript)
        self.clear_btn.pack(side="left", padx=2)

        self.theme_switch = ctk.CTkSwitch(icon_frame, text="Dark Mode", command=self.toggle_theme)
        self.theme_switch.pack(side="left", padx=(15, 0))

        self.transcript_text = ctk.CTkTextbox(self.right_panel, wrap="word", font=("Segoe UI", 12))
        self.transcript_text.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.transcript_text.insert("1.0", "Transcript will appear here after processing...\n\nDrag or browse a video to begin.")
        self.transcript_text.configure(state="disabled")

        # ================= Logs Frame =================
        self.logs_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        self.logs_header = ctk.CTkLabel(self.logs_frame, text="Processing Logs", font=ctk.CTkFont(size=22, weight="bold"))
        self.logs_header.pack(anchor="w", padx=20, pady=(15, 10))

        # Log text box within a frame to control wrapping
        log_text_container = ctk.CTkFrame(self.logs_frame)
        log_text_container.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.log_text = ctk.CTkTextbox(log_text_container, wrap="word", font=("Consolas", 11))
        self.log_text.pack(fill="both", expand=True)
        self.log_text.configure(state="disabled")

        # ================= Saved Transcripts Frame =================
        self.saved_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        self.saved_header = ctk.CTkLabel(self.saved_frame, text="📂 Saved Transcripts", font=ctk.CTkFont(size=22, weight="bold"))
        self.saved_header.pack(anchor="w", padx=20, pady=(15, 10))

        saved_list_frame = ctk.CTkScrollableFrame(self.saved_frame)
        saved_list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.saved_transcript_buttons = []
        self.populate_saved_transcripts(saved_list_frame)

        # File watcher
        self.video_path.trace_add("write", self.on_file_selected)

        # Show default frame
        self.show_frame("main")

    def populate_saved_transcripts(self, container_frame):
        """Populates the saved transcripts list with buttons."""

        # Clear existing buttons
        for widget in container_frame.winfo_children():
            widget.destroy()

        try:
            output_dir = Path(__file__).parent.resolve() / "Output" / "Text"
            if not output_dir.exists():
                output_dir.mkdir(parents=True, exist_ok=True)

            transcript_files = [f for f in output_dir.iterdir() if f.suffix == ".txt"]

            if not transcript_files:
                ctk.CTkLabel(
                    container_frame,
                    text="No saved transcripts found.",
                    font=ctk.CTkFont(size=14, slant="italic")
                ).pack(padx=10, pady=10)
                return

            for file_path in transcript_files:
                file_name = file_path.name
                btn = ctk.CTkButton(
                    container_frame,
                    text=f"📄 {file_name}",
                    command=lambda p=file_path: self.load_saved_transcript(p),
                    anchor="w",
                    fg_color="transparent",
                    text_color=("black", "white"),
                    font=ctk.CTkFont(size=14)
                )
                btn.pack(fill="x", pady=2, padx=10)
                self.saved_transcript_buttons.append(btn)

        except Exception as e:
            ctk.CTkLabel(
                container_frame,
                text=f"Error loading files: {e}",
                font=ctk.CTkFont(size=14, slant="italic", weight="bold"),
                text_color="red"
            ).pack(padx=10, pady=10)

    def clear_transcript(self):
        """Clears the transcript text box and resets UI state."""
        self.transcript_text.configure(state="normal")
        self.transcript_text.delete("1.0", "end")
        self.transcript_text.insert("1.0", "Transcript will appear here after processing...\n\nDrag or browse a video to begin.")
        self.transcript_text.configure(state="disabled")
        self.video_path.set("")
        self.transcript_path = ""
        self.is_editing = False
        self.edit_btn.configure(image=self.edit_icon_image)
        self.save_edit_btn.configure(state="disabled")
        self.save_btn.configure(state="disabled")
        self.progress_bar.set(0)
        self.status_label.configure(text="✨ Ready to convert your video.")
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def load_saved_transcript(self, file_path):
        """Loads a saved transcript into the main text box."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.transcript_path = str(file_path)
            self.display_transcript(content)
            self.show_frame("main")
            self.update_status_and_log(f"✅ Loaded transcript from {file_path.name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load transcript: {e}")

    def show_frame(self, frame_name):
        if self.active_frame:
            self.active_frame.pack_forget()

        current_mode = ctk.get_appearance_mode()
        active_color = "#1f6aa5" if current_mode == "Dark" else "#3b8ed0"
        inactive_color = "#2b2b2b" if current_mode == "Dark" else "#94a3b8"

        self.main_btn.configure(fg_color=active_color if frame_name == "main" else inactive_color)
        self.logs_btn.configure(fg_color=active_color if frame_name == "logs" else inactive_color)
        self.saved_transcripts_btn.configure(fg_color=active_color if frame_name == "saved" else inactive_color)

        if frame_name == "main":
            self.main_frame.pack(fill="both", expand=True)
            self.active_frame = self.main_frame
        elif frame_name == "logs":
            self.logs_frame.pack(fill="both", expand=True)
            self.active_frame = self.logs_frame
        elif frame_name == "saved":
            self.populate_saved_transcripts(self.saved_frame.winfo_children()[1])
            self.saved_frame.pack(fill="both", expand=True)
            self.active_frame = self.saved_frame

    def toggle_theme(self):
        if self.theme_switch.get():
            ctk.set_appearance_mode("dark")
            # Update panel colors for dark mode
            self.left_panel.configure(fg_color=self.DARK_PANEL_BG, border_color=self.DARK_BORDER_COLOR)
            self.right_panel.configure(fg_color=self.DARK_PANEL_BG, border_color=self.DARK_BORDER_COLOR)
            # Update all text widgets to white in dark mode, except the entry box text
            self.title_label_nav.configure(text_color="white")
            self.upload_header.configure(text_color="white")
            self.upload_subtitle.configure(text_color="white")
            self.video_file_label.configure(text_color="white")
            # Keep the entry text dark to remain visible on the darker surface
            self.entry.configure(text_color=self.colors['text'])
            self.status_label.configure(text_color="white")
            self.transcript_header.configure(text_color="white")
            self.logs_header.configure(text_color="white")
            self.saved_header.configure(text_color="white")
        else:
            ctk.set_appearance_mode("light")
            # Update panel colors for light mode
            self.left_panel.configure(fg_color=self.cget("fg_color"), border_color=self.LIGHT_BORDER_COLOR)
            self.right_panel.configure(fg_color=self.cget("fg_color"), border_color=self.LIGHT_BORDER_COLOR)
            # Reset text colors for light mode
            self.title_label_nav.configure(text_color=self.colors['text'])
            self.upload_header.configure(text_color=self.colors['text'])
            self.upload_subtitle.configure(text_color=self.colors['text_dim'])
            self.video_file_label.configure(text_color=self.colors['text_dim'])
            self.entry.configure(text_color=self.colors['text'])
            self.status_label.configure(text_color=self.colors['text_dim'])
            self.transcript_header.configure(text_color=self.colors['text'])
            self.logs_header.configure(text_color=self.colors['text'])
            self.saved_header.configure(text_color=self.colors['text'])

        # Update button colors to reflect the new theme
        self.show_frame("main" if self.active_frame == self.main_frame else "logs")
        self.populate_saved_transcripts(self.saved_frame.winfo_children()[1])

    def toggle_edit_mode(self):
        if not self.transcript_path or not os.path.exists(self.transcript_path):
            messagebox.showwarning("Warning", "No transcript generated yet to edit.")
            return

        if self.is_editing:
            self.transcript_text.configure(state="disabled")
            self.edit_btn.configure(image=self.edit_icon_image)
            self.save_edit_btn.configure(state="disabled")
            self.is_editing = False
        else:
            self.transcript_text.configure(state="normal")
            self.edit_btn.configure(image=self.cancel_icon_image)
            self.save_edit_btn.configure(state="normal")
            self.is_editing = True

    def process_queue_updates(self):
        try:
            while True:
                message = self.progress_queue.get_nowait()
                if message.startswith("PROGRESS:"):
                    progress_value = int(message.split(":")[1])
                    self.progress_bar.set(progress_value / 100)
                # The final content is sent as a message from the backend
                elif message.startswith("FINAL_CONTENT:"):
                    self.transcript_content = message.split(":", 1)[1]
                    self.after(0, self.auto_save_transcript)  # Auto-save, no dialog
                else:
                    self.update_status_and_log(message)
                self.progress_queue.task_done()
        except queue.Empty:
            pass
        self.after(100, self.process_queue_updates)

    def browse_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[("Video Files", "*.mp4 *.mkv *.avi *.mov *.flv *.wmv"), ("All Files", "*.*")]
        )
        if file_path:
            self.video_path.set(file_path)

    def on_file_selected(self, *args):
        if self.video_path.get():
            self.process_btn.configure(state="normal")
            self.transcript_text.configure(state="normal")
            self.transcript_text.delete("1.0", "end")
            self.transcript_text.insert("1.0", "✅ Video loaded. Click 'Start Magic' to begin transcription.")
            self.transcript_text.configure(state="disabled")
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "end")
            self.log_text.configure(state="disabled")
            self.save_btn.configure(state="disabled")
            self.transcript_path = ""
            self.is_editing = False
            self.edit_btn.configure(image=self.edit_icon_image)
            self.save_edit_btn.configure(state="disabled")
        else:
            self.process_btn.configure(state="disabled")
            self.clear_transcript()

    def start_processing(self):
        if self.is_processing:
            return
        video_file = self.video_path.get()
        if not os.path.exists(video_file):
            messagebox.showerror("Error", "Video file not found!")
            return

        self.is_processing = True
        self.process_btn.configure(state="disabled", text="⏳ Brewing Magic...")
        self.progress_bar.set(0)
        self.status_label.configure(text="Starting process...")
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        self.transcript_text.configure(state="normal")
        self.transcript_text.delete("1.0", "end")
        self.transcript_text.insert("1.0", "Starting transcription...")
        self.transcript_text.configure(state="disabled")
        threading.Thread(target=self.process_video, args=(video_file,), daemon=True).start()

    def process_video(self, video_path):
        try:
            self.progress_queue.put("✨ Converting video to audio…")
            start_audio(Path(video_path), self.progress_queue)

            self.progress_queue.put("🧠 Transcribing audio with AI…")
            start_text(self.progress_queue)

        except Exception as e:
            error_msg = f"❌ Error: {str(e)}"
            self.progress_queue.put(error_msg)
            self.after(0, lambda: messagebox.showerror("Error", error_msg))
            self.progress_queue.put("💔 Something went wrong. Try again?")
        finally:
            # Note: Final content triggers auto_save via queue message "FINAL_CONTENT:..."
            pass

    def auto_save_transcript(self):
        """Automatically saves the transcript using the video's base filename."""
        if not self.transcript_content:
            self.progress_queue.put("❌ Error: No transcript content received.")
            self.on_processing_complete()
            return

        # Derive filename from video path
        video_path = Path(self.video_path.get())
        transcript_filename = f"{video_path.stem}.txt"  # Same name, .txt extension

        try:
            # Ensure output directory exists
            output_dir = Path(__file__).parent.resolve() / "Output" / "Text"
            output_dir.mkdir(parents=True, exist_ok=True)

            # Save using backend function
            self.transcript_path = save_final_transcript(self.transcript_content, transcript_filename)

            # Display in UI
            self.display_transcript(self.transcript_content)

            # Log success
            self.progress_queue.put(f"🎉 All done! Transcript saved as '{transcript_filename}'.")

            # Optional: Show info message (you can comment this out if too noisy)
            #messagebox.showinfo("✨ Success", f"Transcript saved to:\n{self.transcript_path}")

        except Exception as e:
            error_msg = f"❌ Error during save: {str(e)}"
            self.progress_queue.put(error_msg)
            messagebox.showerror("Error", error_msg)
        finally:
            self.on_processing_complete()

    def update_status_and_log(self, message):
        self.status_label.configure(text=message)
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"\n{message}")
        self.log_text.configure(state="disabled")
        self.log_text.see("end")

    def display_transcript(self, content):
        self.transcript_text.configure(state="normal")
        self.transcript_text.delete("1.0", "end")
        self.transcript_text.insert("end", content)
        self.transcript_text.configure(state="disabled")
        self.save_btn.configure(state="normal")

    def save_edited_transcript(self):
        if not self.transcript_path or not os.path.exists(self.transcript_path):
            messagebox.showwarning("Warning", "No transcript to save.")
            return
        try:
            content = self.transcript_text.get("1.0", "end").strip()
            with open(self.transcript_path, 'w', encoding='utf-8') as f:
                f.write(content)
            messagebox.showinfo("Success", f"Edits saved to:\n{self.transcript_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {str(e)}")

    def save_transcript(self):
        """Save manually — also uses auto-derived name, no dialog."""
        if not self.transcript_path or not os.path.exists(self.transcript_path):
            messagebox.showwarning("Warning", "No transcript available to save.")
            return

        # Reuse the auto-generated name logic
        video_path = Path(self.video_path.get())
        default_filename = f"{video_path.stem}.txt"
        output_dir = Path(__file__).parent.resolve() / "Output" / "Text"
        save_path = output_dir / default_filename

        try:
            content = self.transcript_text.get("1.0", "end").strip()
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(content)
            messagebox.showinfo("Success", f"Transcript saved as:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {str(e)}")

    def on_processing_complete(self):
        self.is_processing = False
        self.process_btn.configure(state="normal", text="🚀 Start Magic")


if __name__ == "__main__":
    app = VideoTranscriptApp()
    app.mainloop()