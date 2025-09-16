# main.py — Ultimate Aesthetic Video-to-Transcript Converter
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import os
import sys

# Import your modules
import audio
import text


class VideoTranscriptApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🎬 WhisperGlass — Video to Transcript")
        self.root.geometry("1600x900")
        self.root.state('zoomed')  # Full-screen
        self.root.configure(bg="#f8fafc")

        # Bind Escape to exit fullscreen
        self.root.bind('<Escape>', lambda e: self.root.attributes('-fullscreen', False))

        # Fonts
        self.title_font = ("Segoe UI", 24, "bold")
        self.header_font = ("Segoe UI", 14, "bold")
        self.body_font = ("Segoe UI", 11)
        self.button_font = ("Segoe UI", 11, "bold")
        self.small_font = ("Segoe UI", 9)

        # Colors
        self.colors = {
            'primary': '#6366f1',      # Indigo
            'primary_hover': '#4f46e5',
            'secondary': '#8b5cf6',    # Purple
            'success': '#10b981',      # ✅ Emerald Green
            'success_hover': '#059669',
            'surface': '#ffffff',
            'surface_lo': '#f8fafc',
            'border': '#e2e8f0',
            'text': '#1e293b',
            'text_dim': '#64748b',
            'text_placeholder': '#94a3b8',
            'shadow': '#f1f5f9',
        }

        # Variables
        self.video_path = tk.StringVar()
        self.audio_path = ""
        self.transcript_path = ""
        self.is_processing = False

        self.setup_ui()

    def setup_ui(self):
        # Main Container
        main_container = tk.Frame(self.root, bg=self.colors['surface_lo'])
        main_container.pack(fill="both", expand=True, padx=30, pady=30)

        # Paned Window
        paned_window = tk.PanedWindow(
            main_container,
            orient=tk.HORIZONTAL,
            sashrelief="flat",
            sashwidth=8,
            bg=self.colors['border']
        )
        paned_window.pack(fill="both", expand=True)

        # --- LEFT PANEL ---
        left_card = tk.Frame(
            paned_window,
            bg=self.colors['surface'],
            relief="flat",
            bd=0,
            highlightbackground=self.colors['border'],
            highlightthickness=1,
            padx=30,
            pady=40
        )
        paned_window.add(left_card, minsize=550)

        # Use grid layout for perfect alignment
        left_card.grid_rowconfigure(0, weight=1)
        left_card.grid_columnconfigure(0, weight=1)

        # Header
        header_label = tk.Label(
            left_card,
            text="📤 Upload & Convert",
            font=self.title_font,
            fg=self.colors['text'],
            bg=self.colors['surface'],
            anchor="w"
        )
        header_label.grid(row=0, column=0, sticky="w", pady=(0, 20))

        # Subtitle
        subtitle_label = tk.Label(
            left_card,
            text="Drag or browse your video. We’ll extract crystal-clear text.",
            font=self.body_font,
            fg=self.colors['text_dim'],
            bg=self.colors['surface'],
            anchor="w",
            justify="left",
            wraplength=450
        )
        subtitle_label.grid(row=1, column=0, sticky="w", pady=(0, 30))

        # VIDEO FILE Section
        video_frame = tk.Frame(left_card, bg=self.colors['surface'], pady=5)
        video_frame.grid(row=2, column=0, sticky="ew", pady=(0, 20))
        video_frame.grid_columnconfigure(0, weight=1)

        # Label
        tk.Label(
            video_frame,
            text="VIDEO FILE",
            font=self.header_font,
            fg=self.colors['text_dim'],
            bg=self.colors['surface'],
            anchor="w"
        ).grid(row=0, column=0, sticky="w", pady=(0, 5))

        # Entry Field
        entry_bg = tk.Frame(video_frame, bg=self.colors['shadow'], padx=2, pady=2)
        entry_bg.grid(row=1, column=0, sticky="ew", pady=(0, 5))

        entry_field = tk.Entry(
            entry_bg,
            textvariable=self.video_path,
            state="readonly",
            font=self.body_font,
            bg="white",
            fg=self.colors['text'],
            relief="flat",
            bd=0,
            highlightthickness=0,
            insertbackground=self.colors['success']
        )
        entry_field.grid(row=0, column=0, sticky="ew", ipady=10, padx=1)

        # Browse Button (Now Green!)
        style = ttk.Style()
        style.theme_use('clam')
        style.configure(
            "Success.TButton",
            background=self.colors['success'],
            foreground="white",
            font=self.button_font,
            borderwidth=0,
            relief="flat",
            padding=(30, 12),
            highlightthickness=0
        )
        style.map("Success.TButton",
            background=[('active', self.colors['success_hover'])],
            foreground=[('active', 'white')]
        )

        browse_btn = ttk.Button(
            video_frame,
            text="Browse File...",
            command=self.browse_file,
            style="Success.TButton"
        )
        browse_btn.grid(row=2, column=0, sticky="ew", pady=(10, 0))

        # Status Bar
        status_frame = tk.Frame(left_card, bg=self.colors['surface'], pady=5)
        status_frame.grid(row=3, column=0, sticky="ew", pady=(0, 20))

        self.status_label = tk.Label(
            status_frame,
            text="✨ Ready to convert your video.",
            font=self.body_font,
            fg=self.colors['text_dim'],
            bg=self.colors['surface'],
            anchor="w"
        )
        self.status_label.grid(row=0, column=0, sticky="w")

        # Progress Bar
        progress_frame = tk.Frame(left_card, bg=self.colors['surface'], pady=5)
        progress_frame.grid(row=4, column=0, sticky="ew", pady=(0, 30))

        style.configure(
            "Aesthetic.Horizontal.TProgressbar",
            troughcolor=self.colors['shadow'],
            background=self.colors['secondary'],
            thickness=6
        )

        self.progress_bar = ttk.Progressbar(
            progress_frame,
            style="Aesthetic.Horizontal.TProgressbar",
            mode='indeterminate',
            length=400
        )
        self.progress_bar.grid(row=0, column=0, sticky="ew", padx=20)

        # Action Buttons
        btn_frame = tk.Frame(left_card, bg=self.colors['surface'])
        btn_frame.grid(row=5, column=0, sticky="ew", pady=(0, 10))

        # Start Magic Button
        self.process_btn = ttk.Button(
            btn_frame,
            text="🚀 Start Magic",
            command=self.start_processing,
            style="Success.TButton",
            state="disabled"
        )
        self.process_btn.grid(row=0, column=0, sticky="w", padx=(0, 15))

        # Save Transcript Button
        self.save_btn = ttk.Button(
            btn_frame,
            text="💾 Save Transcript",
            command=self.save_transcript,
            style="Secondary.TButton",
            state="disabled"
        )
        self.save_btn.grid(row=0, column=1, sticky="w")

        # --- RIGHT PANEL ---
        right_card = tk.Frame(
            paned_window,
            bg=self.colors['surface'],
            relief="flat",
            bd=0,
            highlightbackground=self.colors['border'],
            highlightthickness=1,
            padx=30,
            pady=40
        )
        paned_window.add(right_card, minsize=650)

        # Header
        tk.Label(
            right_card,
            text="📜 Transcript Output",
            font=self.title_font,
            fg=self.colors['text'],
            bg=self.colors['surface'],
            anchor="w"
        ).pack(anchor="w", pady=(0, 30))

        # Transcript Viewer
        viewer_frame = tk.Frame(right_card, bg=self.colors['shadow'], padx=2, pady=2)
        viewer_frame.pack(fill="both", expand=True)

        inner_frame = tk.Frame(viewer_frame, bg="white")
        inner_frame.pack(fill="both", expand=True, padx=1, pady=1)

        self.transcript_text = scrolledtext.ScrolledText(
            inner_frame,
            wrap=tk.WORD,
            font=("Segoe UI", 12),
            bg="white",
            fg=self.colors['text'],
            relief="flat",
            bd=0,
            padx=30,
            pady=30,
            state="disabled",
            highlightthickness=0,
            insertbackground=self.colors['success'],
            spacing1=5,
            spacing3=5
        )
        self.transcript_text.pack(fill="both", expand=True)

        # Placeholder
        self.transcript_text.config(state="normal", fg=self.colors['text_placeholder'])
        self.transcript_text.insert("1.0", "Transcript will appear here after processing...\n\nDrag or browse a video to begin.")
        self.transcript_text.config(state="disabled")

        # Bind file selection
        self.video_path.trace_add("write", self.on_file_selected)

    def browse_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[
                ("Video Files", "*.mp4 *.mkv *.avi *.mov *.flv *.wmv"),
                ("All Files", "*.*")
            ]
        )
        if file_path:
            self.video_path.set(file_path)

    def on_file_selected(self, *args):
        if self.video_path.get():
            self.process_btn.config(state="normal")
            self.transcript_text.config(state="normal", fg=self.colors['text'])
            self.transcript_text.delete(1.0, tk.END)
            self.transcript_text.insert("1.0", "✅ Video loaded. Click 'Start Magic' to begin transcription.")
            self.transcript_text.config(state="disabled")
        else:
            self.process_btn.config(state="disabled")
            self.transcript_text.config(state="normal", fg=self.colors['text_placeholder'])
            self.transcript_text.delete(1.0, tk.END)
            self.transcript_text.insert("1.0", "Transcript will appear here after processing...\n\nDrag or browse a video to begin.")
            self.transcript_text.config(state="disabled")

    def start_processing(self):
        if self.is_processing:
            return

        video_file = self.video_path.get()
        if not os.path.exists(video_file):
            messagebox.showerror("Error", "Video file not found!")
            return

        self.is_processing = True
        self.process_btn.config(state="disabled", text="⏳ Brewing Magic...")
        self.progress_bar.start()
        self.status_label.config(text="Installing FFmpeg (if needed)…", fg=self.colors['secondary'])

        self.transcript_text.config(state="normal", fg=self.colors['text_dim'])
        self.transcript_text.delete(1.0, tk.END)
        self.transcript_text.insert("1.0", "Processing your video…\n\n ░░░░░░░░░░░░░░░░ 15%\n\nTranscribing audio segments…\n\n ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 60%\n\nFinalizing transcript…\n\n ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 95%")
        self.transcript_text.config(state="disabled")
        self.save_btn.config(state="disabled")

        threading.Thread(target=self.process_video, args=(video_file,), daemon=True).start()

    def process_video(self, video_path):
        try:
            self.update_status("✨ Installing/Checking FFmpeg…")
            audio.install_ffmpeg()

            self.update_status("🎵 Converting video to audio…")
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            output_dir = os.path.join(os.getcwd(), "Output")
            os.makedirs(output_dir, exist_ok=True)
            self.audio_path = os.path.join(output_dir, f"{base_name}.mp3")

            audio.video_to_audio(video_path, self.audio_path, format='mp3')

            self.update_status("🧠 Transcribing with AI…")
            self.transcript_path = text.transcribe_audio_file(
                self.audio_path,
                output_file=os.path.join(output_dir, f"{base_name}.txt"),
                chunk_duration=600,
                model_size="tiny"
            )

            with open(self.transcript_path, 'r', encoding='utf-8') as f:
                transcript_content = f.read()

            if not transcript_content.strip():
                transcript_content = "No speech detected. The video may be silent or contain unrecognizable audio."

            self.root.after(0, self.display_transcript, transcript_content)
            self.root.after(0, lambda: self.update_status("🎉 All done! Your transcript is ready."))
            self.root.after(0, lambda: messagebox.showinfo("✨ Success", f"Transcript saved to:\n{self.transcript_path}"))

        except Exception as e:
            error_msg = f"❌ Error: {str(e)}"
            self.root.after(0, lambda: messagebox.showerror("Error", error_msg))
            self.root.after(0, lambda: self.update_status("💔 Something went wrong. Try again?"))

        finally:
            self.root.after(0, self.on_processing_complete)

    def update_status(self, message):
        self.status_label.config(text=message)

    def display_transcript(self, content):
        self.transcript_text.config(state="normal", fg=self.colors['text'])
        self.transcript_text.delete(1.0, tk.END)
        self.transcript_text.insert(tk.END, content)
        self.transcript_text.config(state="disabled")
        self.save_btn.config(state="normal")

    def on_processing_complete(self):
        self.is_processing = False
        self.process_btn.config(state="normal", text="🚀 Start Magic")

    def save_transcript(self):
        if not self.transcript_path or not os.path.exists(self.transcript_path):
            messagebox.showwarning("Warning", "No transcript available to save.")
            return

        save_path = filedialog.asksaveasfilename(
            title="Save Transcript",
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            initialfile=os.path.basename(self.transcript_path)
        )
        if save_path:
            try:
                with open(self.transcript_path, 'r', encoding='utf-8') as src:
                    content = src.read()
                with open(save_path, 'w', encoding='utf-8') as dst:
                    dst.write(content)
                messagebox.showinfo("💾 Saved", f"Transcript saved to:\n{save_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save file:\n{str(e)}")


if __name__ == "__main__":
    root = tk.Tk()
    app = VideoTranscriptApp(root)
    root.mainloop()