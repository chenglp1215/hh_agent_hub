from abc import ABC, abstractmethod
from typing import List
from dataclasses import dataclass
from tortoise.expressions import Q
from models.knowledge_base import ContentBlock


@dataclass
class SearchResult:
    chunk_id: int
    heading_path: str
    content: str
    source_file: str
    score: float


class KnowledgeRetriever(ABC):
    @abstractmethod
    async def search(self, kb_ids: List[int], query: str, top_k: int = 5) -> List[SearchResult]:
        ...


class KeywordRetriever(KnowledgeRetriever):
    async def search(self, kb_ids: List[int], query: str, top_k: int = 5) -> List[SearchResult]:
        if not kb_ids:
            return []
        keywords = self._extract_keywords(query)
        results = []
        for kw in keywords:
            blocks = await ContentBlock.filter(
                Q(kb_id__in=kb_ids),
                Q(body__icontains=kw) | Q(heading_path__icontains=kw),
            ).limit(top_k * 2)
            for b in blocks:
                score = 0.5
                if kw.lower() in (b.heading_path or "").lower():
                    score += 0.5
                results.append(SearchResult(
                    chunk_id=b.id, heading_path=b.heading_path or b.source_file,
                    content=b.body, source_file=b.source_file, score=score,
                ))
        results.sort(key=lambda r: r.score, reverse=True)
        seen = set()
        unique = []
        for r in results:
            if r.chunk_id not in seen:
                seen.add(r.chunk_id)
                unique.append(r)
        return unique[:top_k]

    def _extract_keywords(self, query: str) -> List[str]:
        import re
        tokens = re.findall(r"[一-鿿]+|[a-zA-Z]+", query)
        stopwords = {"的", "是", "在", "和", "了", "有", "我", "你", "他", "她", "它", "们", "这", "那", "吗", "呢", "吧", "啊"}
        return [t for t in tokens if t.lower() not in stopwords]


class KnowledgeInjector:
    def __init__(self, retriever: KnowledgeRetriever):
        self.retriever = retriever

    async def inject(self, kb_ids: List[int], user_query: str, base_prompt: str, max_tokens: int = 2000) -> str:
        if not kb_ids:
            return base_prompt
        results = await self.retriever.search(kb_ids, user_query, top_k=5)
        injected = []
        token_count = 0
        for r in results:
            estimated = len(r.content) // 2
            if token_count + estimated > max_tokens:
                break
            injected.append(f"### {r.heading_path}\n{r.content}")
            token_count += estimated
        if injected:
            base_prompt += "\n\n## 参考资料（来自知识库）\n" + "\n\n".join(injected)
        return base_prompt


knowledge_injector = KnowledgeInjector(KeywordRetriever())
