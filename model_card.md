# Model Card

## Model Name

**DocuBot: SnippetSeeker 1.0**

A tool that finds the part of the project's docs that best answers a developer's question. It can also explain that answer using an LLM.

## Goal / Task

A developer types a question, like "Where is the auth token generated?" SnippetSeeker finds the doc section most likely to have the answer. It can show that section as-is, or ask Gemini to write a short answer based on it.

## Data Used

- The docs come from four markdown files in `docs/`: `AUTH.md`, `API_REFERENCE.md`, `DATABASE.md`, `SETUP.md`.
- Each file is split into smaller sections using its `##` headers. There are 29 sections total. Most are 150 to 800 characters long.
- The system only looks at words. It does not use embeddings or any outside knowledge.
- This is a small, fixed set of docs. It does not update on its own. It also does not track users or their history, so it is not a personalized recommender.

## Algorithm Summary

1. **Build an index (once, at startup):** split each doc into sections. For every word in a section, record which section it appears in.
2. **Clean the query:** lowercase the question and remove filler words like "the," "how," and "is."
3. **Shortlist:** use the index to find sections that share at least one real word with the question.
4. **Score:** count how many times the question's words appear in each shortlisted section. More matches means a higher score.
5. **Rank:** sort sections by score and keep the top 3.
6. **RAG mode only:** send those top 3 sections to Gemini. Tell it to answer using only that text, or say "I do not know" if it is not enough.

## Observed Behavior / Biases

- **Length bias (fixed):** before we removed filler words, longer sections won just by having more common words like "the." One query about the database once ranked the actual `DATABASE.md` answer last, because a longer, unrelated section had more small word matches.
- **Apostrophe bug (known, not fixed yet):** the word splitter strips apostrophes. So "What's" becomes two words: "what" and "s." The "s" is not a filler word, so it stays in the query. If some other section has its own stray "s" (from a word like "route's"), the two can match by accident. This can make an unrelated question look relevant. We chose to write this down instead of fixing it right away, to avoid causing a new bug late in the project.
- **No real understanding of meaning:** the system only matches exact words. A question that uses different words than the docs, even if it means the same thing, may get poor or no results.

## Evaluation Process

- Ran all 8 sample queries from `dataset.py` in retrieval-only mode. Checked by hand whether the top result matched the right doc and section.
- Tested one question clearly answered in the docs: "Where is the auth token generated?" The correct section, `AUTH.md - Token Generation`, showed up in the top 3.
- Tested one question clearly not covered by the docs: "What's the best recipe for chocolate chip cookies?" This test is what revealed the apostrophe bug above.
- Compared results before and after splitting docs into sections. Splitting cut down on long, irrelevant text and fixed at least one case where an unrelated doc was returned instead of "I do not know."
- Note: `evaluation.py` still checks results by exact filename. Since retrieval was changed to return section labels like `"AUTH.md - Token Generation"` instead of just `"AUTH.md"`, that script's scores are not reliable right now.

## Intended Use and Non-Intended Use

**Intended for:**
- Helping a developer working in this repo quickly find the doc section that answers their question.
- Working without an LLM, in retrieval-only mode, when no API key is set.
- Giving grounded answers in RAG mode, and saying "I do not know" instead of guessing.

**Not intended for:**
- General coding questions that are not about this repo's docs.
- Legal, security, or production decisions without a human checking the answer.
- Acting as a personal recommender. It does not know who the user is or what they've asked before.
- Answering questions about anything not written in `docs/`.

## Ideas for Improvement

1. Fix the apostrophe bug properly. For example, drop one-letter words, or handle contractions like "what's" directly.
2. Make scoring fairer by adjusting for section length, so longer sections don't win just by being longer.
3. Update `evaluation.py` to match the new section-label format, so retrieval quality can be checked automatically again.

## Personal Reflection

Building the scoring and retrieval logic taught me that "simple" keyword matching still has a lot of hidden edge cases. The first version worked, but it quietly favored long documents over relevant ones, since it counted filler words like "the" and "how." I didn't expect a few common words to cause that much bias.

Splitting the docs into smaller sections, instead of returning whole files, made the biggest difference. It cut down on noise and made the results easier to actually read and trust.

The most surprising moment was testing an unrelated question and getting a result back instead of "I do not know." Digging into it showed a small tokenizer bug with apostrophes, something I never would have found without testing an intentionally bad question. It reminded me that testing edge cases and failure modes matters as much as testing the happy path.

If I kept working on this, I would slow down and fix smaller bugs like the apostrophe issue as I find them, instead of just documenting them for later. I would also try to test retrieval more systematically, instead of relying on spot-checking a handful of queries by hand.
