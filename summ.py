import os
import sys
import re
from transformers import pipeline

# --- CONFIGURATION ---
TRANSCRIPT_FILE = os.path.join(os.path.dirname(__file__), "transcript.txt")
SUMMARY_FILE = os.path.join(os.path.dirname(__file__), "summary.txt")
MODEL_NAME = "facebook/bart-large-cnn"

# --- LOAD MODEL ---
print(f"🧠 Loading model: {MODEL_NAME}...")
try:
    summarizer = pipeline(
        "summarization",
        model=MODEL_NAME,
        device=-1,
        model_kwargs={"torch_dtype": "auto"}
    )
    # Use a safe, standard maximum length for BART models.
    model_max_length = 1024
    print(f"✅ Model loaded successfully. Max input tokens: {model_max_length}")
except Exception as e:
    print(f"❌ ERROR: Failed to load model. {e}")
    sys.exit(1)

# --- HELPER: LOAD TRANSCRIPT ---
def _load_transcript(file_path: str) -> str:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Transcript file '{file_path}' not found.")
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read().strip()

# --- HELPER: SPLIT INTO SENTENCES ---
def _split_into_sentences(text: str) -> list:
    """Split text into sentences using basic punctuation + capital letter logic."""
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z"“])', text)
    return [s.strip() for s in sentences if s.strip()]

# --- HELPER: ROBUST CONTENT-DEFINED CHUNKING ---
def _robust_chunking(text: str, tokenizer, max_tokens: int):
    """
    Groups sentences into chunks based on paragraphs, but also splits long paragraphs
    into sentence-level chunks if they exceed the max_tokens limit.
    """
    paragraphs = text.split('\n\n')
    chunks = []
    current_chunk_sentences = []
    current_token_count = 0

    for paragraph in paragraphs:
        if not paragraph.strip():
            continue
        
        paragraph_sentences = _split_into_sentences(paragraph)
        for sentence in paragraph_sentences:
            sentence_tokens = tokenizer.encode(sentence, add_special_tokens=False)
            
            if current_token_count + len(sentence_tokens) + 10 > max_tokens:
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

# --- HELPER: EXTRACT KEY SENTENCES (For Augmentation) ---
def _extract_key_sentences(text: str, summary: str, tokenizer, top_k=5):
    """
    Extracts sentences from the original text that are most relevant to the summary.
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
    for score, sentence in sentence_scores:
        if sentence not in seen_sentences:
            unique_sentences.append(sentence)
            seen_sentences.add(sentence)
        if len(unique_sentences) >= top_k:
            break
            
    return " ".join(unique_sentences)

# --- MAIN FUNCTION (FULLY REVISED) ---
def main():
    print("🚀 Starting Advanced Hierarchical Summarizer...\n")
    
    try:
        raw_transcript = _load_transcript(TRANSCRIPT_FILE)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(1)

    print(f"📝 Loaded {len(raw_transcript)} characters.")

    # --- STAGE 1: ROBUST CHUNKING & SUMMARIZATION ---
    chunks = _robust_chunking(
        raw_transcript, 
        summarizer.tokenizer, 
        max_tokens=model_max_length - 100 # Use a more conservative max_tokens
    )
    print(f"📑 Created {len(chunks)} robust chunks.")

    first_pass_summaries = []
    print("\n--- Pass 1: Summarizing each chunk ---")
    for idx, chunk in enumerate(chunks, 1):
        print(f"✍️ Summarizing chunk {idx}/{len(chunks)}...")
        try:
            result = summarizer(
                chunk, 
                do_sample=False, 
                truncation=True,
                max_length=250,
                min_length=50
            )
            summary = result[0]['summary_text'].strip()
            first_pass_summaries.append(summary)
        except Exception as e:
            print(f"⚠️ Failed to summarize chunk {idx}: {e}")
            fallback = chunk[:200] + "..."
            first_pass_summaries.append(fallback)
    
    # --- STAGE 2: HIERARCHICAL SUMMARIZATION ---
    combined_summaries = " ".join(first_pass_summaries)
    print("\n--- Pass 2: Creating a single summary from chunk summaries ---")
    
    # Check if the combined summaries are too long for the final pass
    if len(summarizer.tokenizer.encode(combined_summaries)) > model_max_length:
        print("⚠️ Combined summaries are too long. Truncating for final pass.")
        combined_summaries = summarizer.tokenizer.decode(
            summarizer.tokenizer.encode(combined_summaries, max_length=model_max_length - 50, truncation=True)
        )
    
    final_result = summarizer(
        combined_summaries,
        do_sample=False,
        truncation=True,
        min_length=150,
        max_length=500
    )
    final_summary = final_result[0]['summary_text'].strip()
    
    # --- STAGE 3: CONTEXTUAL AUGMENTATION ---
    print("\n--- Pass 3: Augmenting the final summary with key points from original text ---")
    key_sentences = _extract_key_sentences(raw_transcript, final_summary, summarizer.tokenizer, top_k=5)
    
    augmented_summary = f"{final_summary}\n\nKey Points from Original Text:\n- " + "\n- ".join(key_sentences.split('. '))

    # --- WRITE FINAL SUMMARY TO FILE ---
    try:
        with open(SUMMARY_FILE, 'w', encoding='utf-8') as f:
            f.write("--- FINAL AUGMENTED SUMMARY ---\n\n")
            f.write(augmented_summary + "\n\n")
            f.write("--- Detailed Chunk Summaries (for reference) ---\n")
            for idx, summary in enumerate(first_pass_summaries, 1):
                f.write(f"--- Chunk {idx} Summary ---\n")
                f.write(summary + "\n\n")

        print(f"\n✅ Done! The augmented summary and detailed summaries are saved to: {SUMMARY_FILE}")
    except Exception as e:
        print(f"❌ Failed to write to file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()