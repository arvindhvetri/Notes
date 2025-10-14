# summary_processing.py
import os
import re
from pathlib import Path
from transformers import pipeline

# --- CONFIGURATION ---
MODEL_NAME = "facebook/bart-large-cnn"

# --- LAZY LOADING SETUP (for performance) ---
_summarizer = None

def get_summarizer():
    """
    Loads the model if it's not already loaded (Singleton pattern).
    """
    global _summarizer
    if _summarizer is None:
        print(f"🧠 Lazily loading summarization model: {MODEL_NAME}...")
        try:
            _summarizer = pipeline("summarization", model=MODEL_NAME, device=-1)
            print("✅ Summarization model loaded successfully.")
        except Exception as e:
            print(f"❌ ERROR: Failed to load summarization model. {e}")
            raise RuntimeError("Could not load the summarization model.")
    return _summarizer

# --- HELPER FUNCTIONS (from your summ.py) ---
def _split_into_sentences(text: str) -> list:
    """Split text into sentences using basic punctuation + capital letter logic."""
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z"“])', text)
    return [s.strip() for s in sentences if s.strip()]

def _robust_chunking(text: str, tokenizer, max_tokens: int):
    """
    Groups sentences into chunks based on paragraphs, but also splits long paragraphs.
    (Logic from summ.py)
    """
    paragraphs = text.split('\n\n')
    chunks = []
    current_chunk_sentences = []
    current_token_count = 0

    for paragraph in paragraphs:
        if not paragraph.strip(): continue
        for sentence in _split_into_sentences(paragraph):
            sentence_tokens = tokenizer.encode(sentence, add_special_tokens=False)
            if current_token_count + len(sentence_tokens) > max_tokens:
                if current_chunk_sentences:
                    chunks.append(" ".join(current_chunk_sentences))
                current_chunk_sentences = [sentence]
                current_token_count = len(sentence_tokens)
            else:
                current_chunk_sentences.append(sentence)
                current_token_count += len(sentence_tokens)
    
    if current_chunk_sentences:
        chunks.append(" ".join(current_chunk_sentences))
    return chunks

def _extract_key_sentences(text: str, summary: str, tokenizer, top_k=5):
    """
    Extracts unique, relevant sentences from the original text.
    (Logic from summ.py)
    """
    sentences = _split_into_sentences(text)
    summary_tokens = set(tokenizer.encode(summary, add_special_tokens=False))
    
    sentence_scores = []
    for sentence in sentences:
        sentence_tokens = set(tokenizer.encode(sentence, add_special_tokens=False))
        common_tokens = len(summary_tokens.intersection(sentence_tokens))
        score = common_tokens / len(sentence_tokens) if len(sentence_tokens) > 0 else 0
        sentence_scores.append((score, sentence))
        
    sentence_scores.sort(key=lambda x: x[0], reverse=True)
    
    unique_sentences = []
    seen_sentences = set()
    for _, sentence in sentence_scores:
        if sentence not in seen_sentences:
            unique_sentences.append(sentence)
            seen_sentences.add(sentence)
        if len(unique_sentences) >= top_k:
            break
            
    return " ".join(unique_sentences)


# --- MAIN FLASK-COMPATIBLE FUNCTION (with advanced logic from summ.py) ---
def run_summarization(task_id, transcript_path, progress_queue):
    summarizer = get_summarizer()
    MODEL_MAX_LENGTH = 1024

    output_dir = Path('output') / task_id / 'Summary'
    os.makedirs(output_dir, exist_ok=True)
    summary_path = output_dir / 'summary.txt'

    with open(transcript_path, 'r', encoding='utf-8') as f:
        raw_transcript = f.read()
    progress_queue.put(f"📝 Loaded {len(raw_transcript)} characters for summary.")

    # --- STAGE 1: ROBUST CHUNKING & FIRST-PASS SUMMARIZATION ---
    chunks = _robust_chunking(raw_transcript, summarizer.tokenizer, MODEL_MAX_LENGTH - 100)
    progress_queue.put(f"📑 Created {len(chunks)} robust chunks for the first pass.")

    first_pass_summaries = []
    progress_queue.put("--- Pass 1: Summarizing each chunk ---")
    for idx, chunk in enumerate(chunks, 1):
        progress_queue.put(f"✍️ Summarizing chunk {idx}/{len(chunks)}...")
        try:
            result = summarizer(chunk, max_length=250, min_length=40, do_sample=False, truncation=True)
            first_pass_summaries.append(result[0]['summary_text'].strip())
        except Exception as e:
            # ✅ NEW: Robust error handling for individual chunks (from summ.py)
            progress_queue.put(f"⚠️ Failed to summarize chunk {idx}: {e}. Using fallback.")
            fallback = chunk[:200] + "..."
            first_pass_summaries.append(fallback)

    # --- STAGE 2: HIERARCHICAL SUMMARIZATION ---
    progress_queue.put("--- Pass 2: Creating a single summary from chunk summaries ---")
    combined_summaries = " ".join(first_pass_summaries)
    
    # ✅ NEW: Check if combined summaries are too long for the model (from summ.py)
    if len(summarizer.tokenizer.encode(combined_summaries)) > MODEL_MAX_LENGTH:
        progress_queue.put("⚠️ Combined summaries are too long. Truncating for final pass.")
        combined_summaries = summarizer.tokenizer.decode(
            summarizer.tokenizer.encode(combined_summaries, max_length=MODEL_MAX_LENGTH - 50, truncation=True)
        )
    
    final_result = summarizer(combined_summaries, do_sample=False, truncation=True, min_length=150, max_length=500)
    final_summary = final_result[0]['summary_text'].strip()

    # --- STAGE 3: CONTEXTUAL AUGMENTATION ---
    progress_queue.put("--- Pass 3: Augmenting summary with key points from original text ---")
    key_sentences = _extract_key_sentences(raw_transcript, final_summary, summarizer.tokenizer, top_k=5)
    
    # ✅ NEW: Formatting from summ.py
    augmented_summary = f"{final_summary}\n\nKey Points from Original Text:\n- " + "\n- ".join(key_sentences.split('. '))

    # --- WRITE FINAL COMPREHENSIVE SUMMARY TO FILE ---
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("--- FINAL AUGMENTED SUMMARY ---\n\n")
        f.write(augmented_summary + "\n\n")
        f.write("--- Detailed Chunk Summaries (for reference) ---\n\n")
        for idx, summary in enumerate(first_pass_summaries, 1):
            f.write(f"--- Chunk {idx} Summary ---\n")
            f.write(summary + "\n\n")

    progress_queue.put(f"✅ Advanced summary saved to: {summary_path}")
    return str(summary_path)