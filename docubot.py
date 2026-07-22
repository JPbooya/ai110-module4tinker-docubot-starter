"""
Core DocuBot class responsible for:
- Loading documents from the docs/ folder
- Building a simple retrieval index (Phase 1)
- Retrieving relevant snippets (Phase 1)
- Supporting retrieval only answers
- Supporting RAG answers when paired with Gemini (Phase 2)
"""

import os
import re
import glob

WORD_RE = re.compile(r"[a-z0-9]+")

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "do", "does", "did", "have", "has", "had",
    "i", "you", "he", "she", "it", "we", "they",
    "this", "that", "these", "those",
    "in", "on", "at", "to", "for", "of", "with", "by", "from", "as",
    "and", "or", "but", "if", "so",
    "what", "which", "who", "whom", "how", "when", "where", "why",
    "there", "here", "any", "all",
}


def tokenize(text):
    """Lowercase and split text into alphanumeric words, punctuation stripped."""
    return WORD_RE.findall(text.lower())


def tokenize_query(text):
    """Tokenize and drop stopwords, so filler words don't skew relevance."""
    return [word for word in tokenize(text) if word not in STOPWORDS]


SECTION_RE = re.compile(r"(?m)^##\s+")


def split_into_sections(filename, text):
    """
    Split a document into smaller chunks along its markdown '##' headers.

    Returns a list of (label, text) tuples, where label combines the
    filename and section title, e.g. "AUTH.md - Token Generation".
    Docs with no '##' headers come back as a single "Full Document" chunk.
    """
    parts = SECTION_RE.split(text)

    if len(parts) == 1:
        body = parts[0].strip()
        return [(f"{filename} - Full Document", body)] if body else []

    chunks = []
    intro = parts[0].strip()
    if intro:
        chunks.append((f"{filename} - Overview", intro))

    for part in parts[1:]:
        title, _, body = part.partition("\n")
        body = body.strip()
        if body:
            chunks.append((f"{filename} - {title.strip()}", body))

    return chunks


class DocuBot:
    def __init__(self, docs_folder="docs", llm_client=None):
        """
        docs_folder: directory containing project documentation files
        llm_client: optional Gemini client for LLM based answers
        """
        self.docs_folder = docs_folder
        self.llm_client = llm_client

        # Load documents into memory
        self.documents = self.load_documents()  # List of (filename, text)

        # Split each document into smaller, individually retrievable sections
        self.chunks = [
            chunk
            for filename, text in self.documents
            for chunk in split_into_sections(filename, text)
        ]  # List of (label, text), e.g. ("AUTH.md - Token Generation", "...")

        # Build a retrieval index over the chunks (implemented in Phase 1)
        self.index = self.build_index(self.chunks)

    # -----------------------------------------------------------
    # Document Loading
    # -----------------------------------------------------------

    def load_documents(self):
        """
        Loads all .md and .txt files inside docs_folder.
        Returns a list of tuples: (filename, text)
        """
        docs = []
        pattern = os.path.join(self.docs_folder, "*.*")
        for path in glob.glob(pattern):
            if path.endswith(".md") or path.endswith(".txt"):
                with open(path, "r", encoding="utf8") as f:
                    text = f.read()
                filename = os.path.basename(path)
                docs.append((filename, text))
        return docs

    # -----------------------------------------------------------
    # Index Construction (Phase 1)
    # -----------------------------------------------------------

    def build_index(self, chunks):
        """
        Build a tiny inverted index mapping lowercase words to the chunk
        labels they appear in.

        Example structure:
        {
            "token": ["AUTH.md - Token Generation", "API_REFERENCE.md - Authentication Endpoints"],
            "database": ["DATABASE.md - Connection Configuration"]
        }
        """
        index = {}
        for label, text in chunks:
            for word in set(tokenize(text)):
                index.setdefault(word, []).append(label)
        return index

    # -----------------------------------------------------------
    # Scoring and Retrieval (Phase 1)
    # -----------------------------------------------------------

    def score_document(self, query, text):
        """
        TODO (Phase 1):
        Return a simple relevance score for how well the text matches the query.

        Suggested baseline:
        - Convert query into lowercase words
        - Count how many appear in the text
        - Return the count as the score
        """
        query_words = tokenize_query(query)
        text_words = tokenize(text)
        return sum(text_words.count(word) for word in query_words)

    def retrieve(self, query, top_k=3):
        """
        Use the index and scoring function to select the top_k most relevant
        section chunks (not whole documents).

        Return a list of (label, text) sorted by score descending, where
        label is "filename - section title".
        """
        query_words = tokenize_query(query)

        # Use the index to shortlist candidate chunk labels
        candidate_labels = set()
        for word in query_words:
            candidate_labels.update(self.index.get(word, []))

        # Score each candidate chunk
        scored = []
        for label, text in self.chunks:
            if label in candidate_labels:
                score = self.score_document(query, text)
                scored.append((score, label, text))

        # Sort by score descending, return (label, text) tuples
        scored.sort(key=lambda item: item[0], reverse=True)
        results = [(label, text) for _, label, text in scored]

        return results[:top_k]

    # -----------------------------------------------------------
    # Answering Modes
    # -----------------------------------------------------------

    def answer_retrieval_only(self, query, top_k=3):
        """
        Phase 1 retrieval only mode.
        Returns raw snippets and filenames with no LLM involved.
        """
        snippets = self.retrieve(query, top_k=top_k)

        if not snippets:
            return "I do not know based on these docs."

        formatted = []
        for label, text in snippets:
            formatted.append(f"[{label}]\n{text}\n")

        return "\n---\n".join(formatted)

    def answer_rag(self, query, top_k=3):
        """
        Phase 2 RAG mode.
        Uses student retrieval to select snippets, then asks Gemini
        to generate an answer using only those snippets.
        """
        if self.llm_client is None:
            raise RuntimeError(
                "RAG mode requires an LLM client. Provide a GeminiClient instance."
            )

        snippets = self.retrieve(query, top_k=top_k)

        if not snippets:
            return "I do not know based on these docs."

        return self.llm_client.answer_from_snippets(query, snippets)

    # -----------------------------------------------------------
    # Bonus Helper: concatenated docs for naive generation mode
    # -----------------------------------------------------------

    def full_corpus_text(self):
        """
        Returns all documents concatenated into a single string.
        This is used in Phase 0 for naive 'generation only' baselines.
        """
        return "\n\n".join(text for _, text in self.documents)
