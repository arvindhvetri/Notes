# notes_processing.py
import os
import re
from pathlib import Path
from ctransformers import AutoModelForCausalLM
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import inch

# --- CONFIGURATION ---
MODEL_PATH = "mistral-7b-instruct-v0.2.Q6_K.gguf"
BOILERPLATE = [
    "Crash Course", "PBS", "hover.com", "episode", "studio", "filmed at",
    "subscribe", "video produced", "this video", "check out", "sponsored by"
]

# --- LAZY LOADING SETUP ---
_notes_model = None

def get_notes_model():
    """
    Loads the notes generation model if it's not already loaded.
    """
    global _notes_model
    if _notes_model is None:
        print("🧠 Lazily loading notes generation model...")
        if not os.path.exists(MODEL_PATH):
            print(f"❌ ERROR: Model file not found at {MODEL_PATH}")
            raise RuntimeError("Notes model file not found.")
        try:
            _notes_model = AutoModelForCausalLM.from_pretrained(
                MODEL_PATH, model_type="mistral", gpu_layers=50, context_length=2048
            )
            print("✅ Notes generation model ready.")
        except Exception as e:
            print(f"❌ ERROR: Failed to load notes model. {e}")
            raise RuntimeError("Could not load the notes model.")
    return _notes_model

# --- HELPER FUNCTIONS ---
def split_chunks(text):
    pattern = r'^--- Chunk (\d+) Summary ---\s*(.*?)(?=^--- Chunk \d+ Summary ---|\Z)'
    matches = re.findall(pattern, text, re.MULTILINE | re.DOTALL)
    return [(int(num), content.strip()) for num, content in sorted(matches, key=lambda x: int(x[0])) if content.strip()]

def filter_boilerplate(txt):
    return "\n".join([
        line for line in txt.splitlines()
        if not any(kw.lower() in line.lower() for kw in BOILERPLATE)
    ])

# ✅ NEW: Function to generate subheadings dynamically
def generate_subheading(text):
    """Asks the model to generate a concise title for a text chunk."""
    model = get_notes_model()
    prompt = f"""[INST]Analyze the following text and create a short, descriptive subheading for it. The subheading should be a title, not a sentence. Respond with ONLY the title and nothing else.

Text:
"{text}"
[/INST]
Subheading:"""
    
    # Generate a short response for the title
    title = model(prompt, max_new_tokens=20, temperature=0.2, repetition_penalty=1.1).strip()
    
    # Clean up the title from potential quotes or markdown
    return re.sub(r'["*#]', '', title)

def expand_chunk(text):
    """Uses the model to expand a summary into detailed notes."""
    model = get_notes_model()
    prompt = f"""<s>[INST] Expand this summary into clear, concise revision notes.
Rules:
- Do NOT include a heading
- Use **bold** for key terms
- Use * or - for bullet points
- Separate paragraphs with blank lines
- Keep expansion moderate (150–250 words)

Summary:
{text}
[/INST]
Expanded Notes:"""
    out = model(
        prompt, max_new_tokens=350, temperature=0.3, top_p=0.9, repetition_penalty=1.2
    ).strip()
    return out if out else text

def postprocess_for_pdf(text):
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    paragraphs = []
    for para in re.split(r'\n\s*\n', text):
        p = para.strip()
        if p:
            paragraphs.append(p)
    return paragraphs

def save_pdf(main_title, sections, out_path):
    doc = SimpleDocTemplate(
        str(out_path), pagesize=letter,
        leftMargin=0.8*inch, rightMargin=0.8*inch,
        topMargin=0.8*inch, bottomMargin=0.8*inch
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='MainTitle', fontSize=18, fontName='Helvetica-Bold', spaceAfter=20, alignment=1))
    styles.add(ParagraphStyle(name='SubHeading', fontSize=15, fontName='Helvetica-Bold', spaceBefore=14, spaceAfter=8))
    styles.add(ParagraphStyle(name='Body', fontSize=11.5, fontName='Helvetica', leading=15, spaceAfter=6))
    styles.add(ParagraphStyle(name='CustomBullet', fontSize=11.5, fontName='Helvetica', leftIndent=20)) # Removed spaceAfter

    flow = [Paragraph(main_title, styles['MainTitle']), Spacer(1, 12)]

    for heading, content in sections:
        flow.append(Paragraph(heading, styles['SubHeading']))
        paragraphs = postprocess_for_pdf(content)
        for p in paragraphs:
            # ✅ CHANGED: Logic to handle bullet points individually
            if p.startswith(('*', '-')):
                # Split a block of bullet points into individual lines
                bullet_points = p.split('\n')
                for point in bullet_points:
                    point = point.strip()
                    if point:
                        clean_point = point[1:].lstrip() if point.startswith(('*', '-')) else point
                        flow.append(Paragraph(f"• {clean_point}", styles['CustomBullet']))
                        # Add a small spacer AFTER EACH bullet point
                        flow.append(Spacer(1, 6))
            else:
                flow.append(Paragraph(p, styles['Body']))
                flow.append(Spacer(1, 6))
        flow.append(Spacer(1, 14))

    doc.build(flow)

# --- MAIN FLASK-COMPATIBLE FUNCTION ---
def run_notes_generation(task_id, summary_path, progress_queue):
    output_dir = Path('output') / task_id / 'Notes'
    os.makedirs(output_dir, exist_ok=True)
    pdf_path = output_dir / 'expanded_notes.pdf'

    with open(summary_path, 'r', encoding='utf-8') as f:
        text = f.read()
    
    chunks = split_chunks(text)
    progress_queue.put(f"Found {len(chunks)} summary chunks to expand into notes.")

    # ✅ REMOVED: Hardcoded SUBHEADINGS dictionary is no longer needed.
    
    sections_to_expand = []
    for num, content in chunks:
        clean_content = filter_boilerplate(content)
        if clean_content.strip():
            # ✅ NEW: Generate subheading dynamically
            progress_queue.put(f"🧠 Generating subheading for chunk {num}...")
            heading = generate_subheading(clean_content)
            
            progress_queue.put(f"✍️ Expanding notes for: '{heading}'")
            expanded_text = expand_chunk(clean_content)
            sections_to_expand.append((heading, expanded_text))

    if sections_to_expand:
        progress_queue.put("📄 Generating final PDF document...")
        save_pdf("Video Lecture – Expanded Notes", sections_to_expand, pdf_path)
        progress_queue.put(f"✅ PDF saved: {pdf_path}")
        return str(pdf_path)
    else:
        raise ValueError("No valid content found in summary to generate notes.")