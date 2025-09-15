import os
import sys
import google.generativeai as genai
from dotenv import load_dotenv
# --- CONFIGURATION ---
SUMMARY_FILE = os.path.join(os.path.dirname(__file__), "summary.txt")
DETAILED_NOTES_FILE = os.path.join(os.path.dirname(__file__), "detailed_notes.txt")

# Set your Gemini API key
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("❌ ERROR: GEMINI_API_KEY not found. Please set it as an environment variable.")
    sys.exit(1)

# --- HELPER: LOAD SUMMARY ---
def _load_summary(file_path: str) -> str:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Summary file '{file_path}' not found.")
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read().strip()

# --- MAIN FUNCTION ---
def main():
    print("📚 Starting Enhanced Detailed Notes Generator with Gemini...\n")
    
    # Load the summary
    try:
        summary_content = _load_summary(SUMMARY_FILE)
        print(f"📝 Loaded summary from: {SUMMARY_FILE}")
    except FileNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(1)

    # Configure Gemini
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-pro')  # Fast and cost-effective

    # --- ENHANCED PROMPT ---
    prompt = f"""
    You are a world-class computer science educator and curriculum designer. Your task is to transform the provided summary into an in-depth, university-level study guide on the history and evolution of operating systems.

    🚫 STRICTLY REMOVE: All mentions of sponsorships, advertisements, production credits, TV plugs, or brand endorsements (e.g., Hover, PBS, Crash Course credits). This is purely academic content.

    ✍️ INSTRUCTIONS FOR CONTENT:
    1.  **Expand Every Concept**: For each key point, provide:
        - Clear, textbook-style definitions.
        - Historical context (dates, people, institutions).
        - Technical significance and impact on modern computing.
        - Real-world examples or analogies for clarity.
    2.  **Structure Logically**: Use hierarchical headings (##, ###, ####) and bullet points. Follow chronological order: Batch Processing → Device Drivers → Multitasking → Virtual Memory → Time-Sharing → Unix → MS-DOS → Modern OS.
    3.  **Correct Errors**: Fix transcription errors
    4.  **Be Comprehensive**: Assume the reader has no prior knowledge. Explain key terms 

    ❓ ADD A SECTION: "## 💡 10 Key Questions & Answers"
    - Create 10 thoughtful, exam-style Q&As that test deep understanding of the topic.
    - Format: "Q1. [Question] \nA1. [Detailed Answer]"
    - Cover major innovations, key figures, and technical trade-offs.

    🔗 ADD A SECTION: "## 🌐 Further Learning Resources"
    - **Articles**: Provide 3 high-quality, authoritative web articles (include full URLs).
    - **Videos**: Provide 3 relevant YouTube video links (include full URLs).

    SUMMARY TO EXPAND:
    ```
    {summary_content}
    ```
    """

    print("🧠 Sending enhanced request to Gemini...")
    try:
        response = model.generate_content(prompt)
        detailed_notes = response.text.strip()
        print("✅ Received enhanced detailed notes from Gemini.")
    except Exception as e:
        print(f"❌ Failed to generate notes with Gemini: {e}")
        sys.exit(1)

    # Save the detailed notes
    try:
        with open(DETAILED_NOTES_FILE, 'w', encoding='utf-8') as f:
            f.write(detailed_notes)
        print(f"📄 Enhanced detailed notes saved to: {DETAILED_NOTES_FILE}")
    except Exception as e:
        print(f"❌ Failed to write detailed notes to file: {e}")
        sys.exit(1)

    # Display a preview
    print("\n" + "="*60)
    print("🎯 PREVIEW OF ENHANCED DETAILED NOTES")
    print("="*60)
    print(detailed_notes[:800] + "..." if len(detailed_notes) > 800 else detailed_notes)
    print("="*60 + "\n")

if __name__ == "__main__":
    main()