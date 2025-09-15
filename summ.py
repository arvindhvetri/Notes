import os
import sys
from llama_cpp import Llama

# CONFIGURATION
TRANSCRIPT_FILE = "transcript.txt"       # Input: your transcribed text
SUMMARY_FILE = "summary.txt"             # Output: your summary
LLM_MODEL_PATH = "tinyllama.Q4_K_M.gguf" # Must be in same folder
MAX_TOKENS = 1024                        # Max length of summary
N_THREADS = os.cpu_count()               # Use all CPU cores


def load_and_summarize():
    """
    Load quantized LLM, summarize transcript, then free memory immediately.
    No caching. No disk writes except final summary.txt.
    """
    if not os.path.exists(TRANSCRIPT_FILE):
        print(f"❌ ERROR: Transcript file '{TRANSCRIPT_FILE}' not found.")
        print("Make sure you've run the audio-to-text script first.")
        sys.exit(1)

    if not os.path.exists(LLM_MODEL_PATH):
        print(f"❌ ERROR: Model file '{LLM_MODEL_PATH}' not found.")
        print("Download it from: https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf")
        print("Place it in the same folder as this script.")
        sys.exit(1)

    # Read transcript
    with open(TRANSCRIPT_FILE, 'r', encoding='utf-8') as f:
        transcript = f.read().strip()

    if not transcript:
        print("⚠️  Transcript is empty. Nothing to summarize.")
        return

    print(f"📝 Loaded {len(transcript)} characters from '{TRANSCRIPT_FILE}'")
    print("🧠 Loading TinyLlama-1.1B (Q4_K_M) model into RAM...")

    # Load model (in-memory only, no cache)
    llm = Llama(
        model_path=LLM_MODEL_PATH,
        n_ctx=2048,
        n_threads=N_THREADS,
        n_gpu_layers=0,           # Force CPU-only
        verbose=False,
        flash_attn=False,
    )

    prompt = f"""<|system|>
You are a concise summarizer. Extract key points from the following transcript.
Keep it under 300 words. Focus on main topics, decisions, names, and conclusions.
Do not add opinions or extra information.
<|user|>
{transcript}
<|assistant|>
Summary:"""

    print("✍️  Generating summary...")

    response = llm(
        prompt,
        max_tokens=MAX_TOKENS,
        stop=["<|user|>", "<|assistant|>"],
        echo=False,
        temperature=0.2,
    )

    summary = response['choices'][0]['text'].strip()

    # Free memory immediately
    del llm

    # Write summary
    with open(SUMMARY_FILE, 'w', encoding='utf-8') as f:
        f.write(summary)

    print(f"\n✅ Summary generated!")
    print(f"📄 Saved to: {SUMMARY_FILE}")
    print("\n" + "="*50)
    print(summary)
    print("="*50)


if __name__ == "__main__":
    print("🚀 Starting standalone text summarizer...\n")
    load_and_summarize()