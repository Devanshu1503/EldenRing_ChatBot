"""
Core RAG + Claude chat logic.
Retrieves relevant chunks from Chroma, then calls Claude Haiku.
"""

import os
import re
import chromadb
import anthropic
from pathlib import Path
from sentence_transformers import SentenceTransformer

CHROMA_DIR = Path(__file__).parent.parent / "rag" / "chroma_db"
TOP_K = 15

_model      = None
_collection = None
_client     = None


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _get_collection():
    global _collection
    if _collection is None:
        db = chromadb.PersistentClient(path=str(CHROMA_DIR))
        _collection = db.get_collection("eldenring")
    return _collection


def _get_claude():
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set in environment variables")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


SOURCE_LABELS = {
    "convergence":         "Convergence Mod Wiki",
    "convergence_summary": "Convergence Mod Wiki",
    "fextralife":          "Fextralife Walkthrough",
    "fanapi":              "Elden Ring Database",
    "fanapi_summary":      "Elden Ring Database",
    "quest_pdf":           "Quest Order Guide",
}

SYSTEM_PROMPT = """You are an expert guide for Elden Ring with the Convergence overhaul mod installed.

RESPONSE FORMAT — always structure answers with these sections when relevant:

**📜 Base Game** — how it works in the vanilla game (walkthrough steps, item locations, boss strategies)
**⚔️ Convergence Mod Changes** — what the mod adds, removes, or changes from the base game. If nothing changed, write "No changes from base game."
**📍 Location / How to Obtain** — where to find the item/weapon/spell, noting if the location differs between base game and mod

For purely Convergence-specific things (new classes, new spells, new weapons that don't exist in base game), skip the Base Game section and just answer directly under a **⚔️ Convergence Mod** header.

For pure walkthrough questions where the mod makes no changes, you can answer normally without sections — just note at the end if anything is different in Convergence.

IMPORTANT RULES:
- NEVER ask the player for clarification. This is an absolute rule with no exceptions.
- The conversation history is always provided. If the last topic was Godskin Matriarch and the player asks "how do I beat it?" — answer about Godskin Matriarch immediately.
- Pronouns "it/its/this/that/them/her/him" ALWAYS refer to the most recently discussed subject in history. Resolve them silently and answer.
- If the reference material contains unrelated content (e.g. other bosses), ignore it and use history context to answer. The reference material is a hint, not a constraint — history takes priority for follow-up questions.
- When listing weapons or spells, label each as:
    [Base Game] = exists in original Elden Ring
    [Convergence New] = added by the mod (includes DLC weapons)
    [Convergence Changed] = base game item with modified stats/location
- If a weapon/item location changed in Convergence vs base game, always highlight this.
- For "list all X" questions use the pre-grouped summary data. Do not invent entries.
- If retrieved material is incomplete, say so and point to convergencemod.com.
- Be practical — the player is mid-game and needs actionable advice.
- NEVER guess or hallucinate boss weaknesses, item stats, or location data. If the retrieved material doesn't contain the specific information, say exactly: "I don't have confirmed data on this — check convergencemod.com or the Convergence Discord." Do not fill gaps with base game assumptions presented as fact.
- If you use base game knowledge as a fallback, label it explicitly: "In the base game, X works because Y — but this may differ in Convergence." Never present base game info as confirmed mod behavior."""


# ── Query rewriting for follow-up questions ───────────────────────────────

FOLLOW_UP_PRONOUNS = re.compile(
    r"\b(it|its|this|that|them|they|their|her|him|he|she|"
    r"the boss|the weapon|the spell|the item|the class|the enemy)\b",
    re.IGNORECASE
)

SKIP_SUBJECTS = {
    "base game", "convergence mod", "convergence", "how to", "the mod",
    "no changes", "elden ring", "roundtable hold",
}

def extract_subject(history: list[dict]) -> str:
    """
    Extract the main subject from the last USER message — most reliable source
    since the user explicitly named what they were asking about.
    Falls back to scanning the last assistant message.
    """
    # Priority 1: last USER message proper nouns
    last_user = next(
        (m["content"] for m in reversed(history) if m["role"] == "user"), None
    )
    if last_user:
        seqs = re.findall(
            r"(?:[A-Z][a-z']+(?:\s+(?:of\s+|the\s+)?[A-Z][a-z']+)*)",
            last_user
        )
        for s in seqs:
            if s.lower() not in SKIP_SUBJECTS and len(s) > 4:
                return s

    # Priority 2: last ASSISTANT message — strip emoji/headers first
    last_asst = next(
        (m["content"] for m in reversed(history) if m["role"] == "assistant"), None
    )
    if last_asst:
        # Remove emoji and markdown headers so they don't pollute extraction
        clean = re.sub(r"[^\x00-\x7F]", " ", last_asst[:500])
        clean = re.sub(r"^#+\s*", "", clean, flags=re.MULTILINE)
        # Bold **Name**
        bold = re.findall(r"\*\*([A-Z][^*]{2,40})\*\*", clean)
        for b in bold:
            if b.lower() not in SKIP_SUBJECTS:
                return b
        # Title-case sequence
        seqs = re.findall(r"(?:[A-Z][a-z']+(?:\s+(?:of\s+|the\s+)?[A-Z][a-z']+)+)", clean)
        for s in seqs:
            if s.lower() not in SKIP_SUBJECTS:
                return s

    return ""


def rewrite_query(question: str, history: list[dict] | None) -> str:
    """Expand vague follow-up queries with the subject from recent history."""
    if not history:
        return question

    q = question.strip()
    is_short    = len(q.split()) <= 8
    has_pronoun = bool(FOLLOW_UP_PRONOUNS.search(q))

    if not (is_short or has_pronoun):
        return question

    subject = extract_subject(history)
    if subject and subject.lower() not in q.lower():
        return f"{subject}: {q}"

    return question


# ── Retrieval ─────────────────────────────────────────────────────────────

def retrieve(query: str) -> list[dict]:
    embedding = _get_model().encode([query])[0].tolist()
    results = _get_collection().query(
        query_embeddings=[embedding],
        n_results=TOP_K,
        include=["documents", "metadatas"],
    )
    chunks = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        chunks.append({
            "text":   doc,
            "source": meta.get("source", ""),
            "title":  meta.get("title", ""),
        })
    return chunks


def build_context(chunks: list[dict]) -> str:
    parts = []
    for c in chunks:
        label = SOURCE_LABELS.get(c["source"], c["source"])
        parts.append(f"[{label}] {c['title']}\n{c['text']}")
    return "\n\n---\n\n".join(parts)


# ── Main entry point ──────────────────────────────────────────────────────

def ask(question: str, history: list[dict] | None = None) -> str:
    """
    history: list of {"role": "user"|"assistant", "content": str}
    Returns the assistant reply as a string.
    """
    # Rewrite vague follow-up queries before hitting the vector DB
    retrieval_query = rewrite_query(question, history)
    subject_hint    = retrieval_query if retrieval_query != question else ""

    chunks  = retrieve(retrieval_query)
    context = build_context(chunks)

    # Build message list: clean history + current question with context
    messages = []
    if history:
        for msg in history[-10:]:
            if msg["role"] == "user":
                content = msg["content"]
                if "Reference material from the game database:" in content:
                    content = content.split("Question: ", 1)[-1] if "Question: " in content else content
                messages.append({"role": "user", "content": content})
            else:
                messages.append(msg)

    # If vague follow-up, make the resolved subject unmissable for Claude
    if subject_hint:
        subject_only = subject_hint.split(":")[0].strip()
        preamble = (
            f"CONTEXT: This is a follow-up question about [{subject_only}] "
            f"from earlier in this conversation. Answer about [{subject_only}] directly. "
            f"Do not ask for clarification.\n\n"
        )
    else:
        preamble = ""

    messages.append({
        "role": "user",
        "content": (
            f"{preamble}"
            f"Reference material from the game database:\n\n{context}\n\n"
            f"Question: {question}"
        ),
    })

    response = _get_claude().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    return response.content[0].text
