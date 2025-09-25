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
print("🧠 Loading model...")
model = AutoModelForCausalLM.from_pretrained(
    MODEL_PATH,
    model_type="mistral",
    gpu_layers=50,
    context_length=2048
)
print("✅ Model ready.")

# --- Helpers ---
def load_text(fp):
    with open(fp, 'r', encoding='utf-8') as f:
        return f.read().strip()

def split_chunks(text):
    pattern = r'^--- Chunk (\d+) Summary ---\s*(.*?)(?=^--- Chunk \d+ Summary ---|\Z)'
    matches = re.findall(pattern, text, re.MULTILINE | re.DOTALL)
    sorted_chunks = sorted(matches, key=lambda x: int(x[0]))
    return [(int(num), content.strip()) for num, content in sorted_chunks if content.strip()]

def filter_boilerplate(txt):
    return "\n".join([
        line for line in txt.splitlines()
        if not any(kw.lower() in line.lower() for kw in BOILERPLATE)
    ])

def expand_content(text):
    prompt = f"""<s>[INST] Expand this summary into clear, concise revision notes.

Rules:
- Do NOT include a heading
- Use **bold** for key terms like **multitasking**
- Use * or - for bullet points
- Separate paragraphs with blank lines
- Keep close to original facts; no invented names/dates
- Max 200 words

Summary:
{text}
[/INST]
Expanded Notes:
"""
    out = model(
        prompt,
        max_new_tokens=250,
        temperature=0.3,
        top_p=0.9,
        repetition_penalty=1.2
    ).strip()
    return out if out else text

def postprocess_for_pdf(text):
    """Convert **term** to <b>term</b> and split into paragraphs/bullets"""
    # Convert **word** to <b>word</b>
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    paragraphs = []
    for para in re.split(r'\n\s*\n', text):
        p = para.strip()
        if p:
            paragraphs.append(p)
    return paragraphs

def save_pdf(main_title, sections, out_path):
    doc = SimpleDocTemplate(
        out_path, pagesize=letter,
        leftMargin=0.8*inch, rightMargin=0.8*inch,
        topMargin=0.8*inch, bottomMargin=0.8*inch
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='MainTitle',
        fontSize=18,
        fontName='Helvetica-Bold',
        spaceAfter=20,
        alignment=1  # center
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
        name='BulletItem',
        fontSize=11.5,
        fontName='Helvetica',
        leftIndent=20,
        spaceAfter=6
    ))

    flow = []
    # Main title
    flow.append(Paragraph(main_title, styles['MainTitle']))
    flow.append(Spacer(1, 12))

    # Subsections
    for subheading, content in sections:
        flow.append(Paragraph(subheading, styles['SubHeading']))
        paragraphs = postprocess_for_pdf(content)
        for p in paragraphs:
            if p.startswith(('*', '-')):
                # Clean bullet marker and use bullet style
                clean_text = p[1:].lstrip()
                flow.append(Paragraph(f"• {clean_text}", styles['BulletItem']))
            else:
                flow.append(Paragraph(p, styles['Body']))
            flow.append(Spacer(1, 4))
        flow.append(Spacer(1, 14))

    doc.build(flow)
    print(f"✅ PDF saved: {out_path}")

# --- Main ---
text = load_text(INPUT_FILE)
chunks = split_chunks(text)
print(f"Found {len(chunks)} chunks.")

# Define subheadings manually
SUBHEADINGS = {
    1: "Core Concepts of Operating Systems",
    2: "Atlas OS: Multitasking, Virtual & Protected Memory",
    3: "Maltix OS: Security and Time-Sharing Architecture"
}

sections_to_expand = []
for num, content in chunks:
    if num in SUBHEADINGS:
        clean = filter_boilerplate(content)
        if clean.strip():
            print(f"Expanding Chunk {num}...")
            expanded = expand_content(clean)
            sections_to_expand.append((SUBHEADINGS[num], expanded))

if sections_to_expand:
    save_pdf("Operating Systems – Expanded Notes", sections_to_expand, OUTPUT_PDF)
else:
    print("⚠️ No valid content to expand.")