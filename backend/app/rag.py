"""RAG over college mission statements.

Retrieval: local embeddings (sentence-transformers) with a TF-IDF fallback so the
app always runs. Generation: Claude (Anthropic). If no API key is set, we return
the retrieved passages with a note instead of failing.
"""
import os
import numpy as np

from . import config
from .data import load_missions

_INDEX = None  # lazy singleton


class _Index:
    def __init__(self):
        self.df = load_missions()
        self.mode = None
        self.matrix = None
        self._model = None
        self._vectorizer = None
        self._build()

    def _build(self):
        texts = self.df["mission"].tolist()
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            self.matrix = self._model.encode(texts, normalize_embeddings=True)
            self.mode = "sentence-transformers"
        except Exception:
            # Fallback keeps the demo working without the heavy model download.
            from sklearn.feature_extraction.text import TfidfVectorizer
            self._vectorizer = TfidfVectorizer(stop_words="english", max_features=4096)
            m = self._vectorizer.fit_transform(texts).toarray()
            norms = np.linalg.norm(m, axis=1, keepdims=True)
            norms[norms == 0] = 1
            self.matrix = m / norms
            self.mode = "tfidf-fallback"
        os.makedirs(config.INDEX_DIR, exist_ok=True)
        np.savez(os.path.join(config.INDEX_DIR, "mission_index.npz"),
                 matrix=self.matrix, unitids=self.df["UNITID"].values)

    def _embed_query(self, q: str) -> np.ndarray:
        if self.mode == "sentence-transformers":
            return self._model.encode([q], normalize_embeddings=True)[0]
        v = self._vectorizer.transform([q]).toarray()[0]
        n = np.linalg.norm(v) or 1.0
        return v / n

    def search(self, question: str, unitids=None, k: int = 5):
        mask = np.ones(len(self.df), dtype=bool)
        if unitids:
            wanted = set(int(u) for u in unitids)
            mask = self.df["UNITID"].isin(wanted).values
        qv = self._embed_query(question)
        sims = self.matrix @ qv
        sims = np.where(mask, sims, -1.0)
        idx = np.argsort(sims)[::-1][:k]
        results = []
        for i in idx:
            if sims[i] <= 0:
                continue
            row = self.df.iloc[i]
            results.append({
                "unitid": int(row["UNITID"]),
                "mission": row["mission"],
                "score": round(float(sims[i]), 3),
            })
        return results


def get_index() -> _Index:
    global _INDEX
    if _INDEX is None:
        _INDEX = _Index()
    return _INDEX


def status() -> dict:
    ready = _INDEX is not None or os.path.exists(
        os.path.join(config.INDEX_DIR, "mission_index.npz"))
    return {"index_ready": bool(ready), "api_key_set": bool(config.ANTHROPIC_API_KEY)}


def answer(question: str, unitids=None, college_names=None) -> dict:
    idx = get_index()
    passages = idx.search(question, unitids=unitids, k=5)
    if not passages:
        return {"answer": "No relevant mission statements found for the current shortlist.",
                "sources": [], "mode": idx.mode}

    names = {}
    if college_names:
        names = {int(u): n for u, n in college_names.items()}
    context = "\n\n".join(
        f"[{names.get(p['unitid'], p['unitid'])}] {p['mission']}" for p in passages
    )

    if not config.ANTHROPIC_API_KEY:
        return {
            "answer": ("(No ANTHROPIC_API_KEY set — showing the most relevant mission "
                       "passages instead of a synthesized answer.)\n\n" + context),
            "sources": passages, "mode": idx.mode,
        }

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        prompt = (
            "Answer the question using ONLY the college mission statements below. "
            "Name the specific colleges that fit and quote/paraphrase their stated values. "
            "If none fit, say so.\n\n"
            f"Question: {question}\n\nMission statements:\n{context}"
        )
        msg = client.messages.create(
            model=config.ANTHROPIC_MODEL, max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        return {"answer": text, "sources": passages, "mode": idx.mode}
    except Exception as e:
        return {"answer": f"(Answer generation failed: {e}. Retrieved passages below.)\n\n{context}",
                "sources": passages, "mode": idx.mode}
