import os
import re
from ctransformers import AutoModelForCausalLM
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import inch

# --- Paths ---
INPUT_FILE = os.path.join(os.path.dirname(__file__), "summary.txt")
OUTPUT_PDF = os.path.join(os.path.dirname(__file__), "expanded_notes.pdf")
MODEL_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "mistral-7b-instruct-v0.2.Q6_K.gguf")
).replace("\\", "/")

BOILERPLATE = [
    "Crash Course", "PBS", "hover.com", "episode", "studio", "filmed at",
    "subscribe", "video produced", "this video", "check out", "sponsored by"
]

# --- Load Model ---
print("🧠 Loading GGUF model...")
model = AutoModelForCausalLM.from_pretrained(
    MODEL_PATH,
    model_type="mistral",
    gpu_layers=50,
    context_length=2048
)
print("✅ Model loaded successfully.")

# --- Helpers ---
def load_text(fp):
    with open(fp, 'r', encoding='utf-8') as f:
        return f.read().strip()

def split_chunks(text):
    pattern = r'^--- Chunk (\d+) Summary ---\s*(.*?)(?=^--- Chunk \d+ Summary ---|\Z)'
    matches = re.findall(pattern, text, re.MULTILINE | re.DOTALL)
    return [(int(num), content.strip()) for num, content in sorted(matches, key=lambda x: int(x[0])) if content.strip()]

def filter_boilerplate(txt):
    return "\n".join([
        line for line in txt.splitlines()
        if not any(kw.lower() in line.lower() for kw in BOILERPLATE)
    ])

def expand_chunk(text):
    prompt = f"""<s>[INST] Expand this summary into clear, concise revision notes.

Rules:
- Do NOT include a heading
- ONLY use facts from the input—do NOT mention IBM, System/360, MIT, CTSS, Multics, or any names not in the input
- Use **bold** for key terms like **multitasking**, **virtual memory**, **protected memory**, **time sharing**, **terminal**
- Use * or - for bullet points
- Separate paragraphs with blank lines
- Complete all sentences
- Keep expansion moderate (150–250 words)

Summary:
{text}
[/INST]
Expanded Notes:
"""
    out = model(
        prompt,
        max_new_tokens=350,
        temperature=0.3,
        top_p=0.9,
        repetition_penalty=1.2
    ).strip()
    return out if out else text

def postprocess_for_pdf(text):
    # Convert **term** → <b>term</b>
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    paragraphs = []
    for para in re.split(r'\n\s*\n', text):
        p = para.strip()
        if p:
            paragraphs.append(p)
    return paragraphs

def save_pdf(main_title, sections, out_path):
    doc = SimpleDocTemplate(
        out_path,
        pagesize=letter,
        leftMargin=0.8 * inch,
        rightMargin=0.8 * inch,
        topMargin=0.8 * inch,
        bottomMargin=0.8 * inch
    )
    styles = getSampleStyleSheet()
    # Use UNIQUE style names to avoid conflicts
    styles.add(ParagraphStyle(
        name='MainTitle',
        fontSize=18,
        fontName='Helvetica-Bold',
        spaceAfter=20,
        alignment=1
    ))
    styles.add(ParagraphStyle(
        name='SubHeading',
        fontSize=15,
        fontName='Helvetica-Bold',
        spaceBefore=14,
        spaceAfter=8
    ))
    styles.add(ParagraphStyle(
        name='Body',
        fontSize=11.5,
        fontName='Helvetica',
        leading=15,
        spaceAfter=6
    ))
    styles.add(ParagraphStyle(
    name='CustomBullet',  # ← UNIQUE NAME
    fontSize=11.5,
    fontName='Helvetica',
    leftIndent=20,
    spaceAfter=6
    ))

    flow = []
    flow.append(Paragraph(main_title, styles['MainTitle']))
    flow.append(Spacer(1, 12))

    for heading, content in sections:
        flow.append(Paragraph(heading, styles['SubHeading']))
        paragraphs = postprocess_for_pdf(content)
        for p in paragraphs:
            if p.startswith(('*', '-')):
                clean = p[1:].lstrip()
                flow.append(Paragraph(f"• {clean}", styles['Bullet']))
                flow.append(Spacer(1, 8))  # ← SPACE AFTER EVERY BULLET
            else:
                flow.append(Paragraph(p, styles['Body']))
                flow.append(Spacer(1, 6))
        flow.append(Spacer(1, 14))  # Extra space between sections

    doc.build(flow)
    print(f"✅ PDF saved: {out_path}")

# --- Main ---
if __name__ == "__main__":
    text = load_text(INPUT_FILE)
    chunks = split_chunks(text)
    print(f"Found {len(chunks)} chunks.")

    SUBHEADINGS = {
        1: "Core Concepts of Operating Systems",
        2: "Atlas OS: Multitasking, Virtual & Protected Memory",
        3: "Maltix OS: Security Through Time Sharing and Terminals"
    }

    expanded = []
    for num, content in chunks:
        if num in SUBHEADINGS:
            clean = filter_boilerplate(content)
            if clean.strip():
                print(f"Expanding Chunk {num}...")
                expanded.append((SUBHEADINGS[num], expand_chunk(clean)))

    if expanded:
        save_pdf("Operating Systems – Expanded Notes", expanded, OUTPUT_PDF)
    else:
        print("⚠️ No valid content to expand.")