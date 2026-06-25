"""Count words in text."""

def run(text: str = "") -> dict:
    words = [part for part in text.split() if part.strip()]
    return {"word_count": len(words), "text_preview": text[:80]}
