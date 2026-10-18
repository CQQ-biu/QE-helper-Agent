"""按 section → paragraph → sentence → token 递归切分知识文档。"""
import re
from typing import Callable, List, Optional


class RecursiveSemanticChunker:
    """优先保留自然语义边界，超长句子才降级为 token 切分。"""

    _token_pattern = re.compile(
        r"\s+|[\u3400-\u9fff]|[A-Za-z0-9]+(?:[-_./][A-Za-z0-9]+)*|[^\w\s]",
        re.UNICODE,
    )
    _section_pattern = re.compile(
        r"(?m)^(?=#{1,6}\s+|第[一二三四五六七八九十百0-9]+[章节篇部]\s*|"
        r"(?:\d+(?:\.\d+){0,3})[、.\s]+[^\n]+$)"
    )
    _paragraph_pattern = re.compile(r"\n\s*\n+")
    _sentence_pattern = re.compile(
        r"[。！？；!?;]+[”’）】》\"']*\s*|[.!?]+[\"”’')]*\s+(?=[A-Z0-9])"
    )

    def __init__(self, chunk_size: int, chunk_overlap: int):
        if chunk_size <= 0:
            raise ValueError("chunk_size 必须大于0")
        if chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap 必须大于等于0且小于chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._splitters: List[Callable[[str], List[str]]] = [
            lambda text: self._split_at_positions(text, self._section_pattern, before_match=True),
            lambda text: self._split_at_positions(text, self._paragraph_pattern),
            lambda text: self._split_at_positions(text, self._sentence_pattern),
        ]

    def split(self, text: str) -> List[str]:
        """递归拆成语义单元，再按 token 预算合并并加入重叠。"""
        normalized = re.sub(r"[ \t]+", " ", text.replace("\r\n", "\n").replace("\r", "\n"))
        normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
        if not normalized:
            return []
        units = self._recursive_split(normalized, level=0)
        return self._pack_with_overlap(units)

    def count_tokens(self, text: str) -> int:
        """模型无关估算：中文单字、英文单词、数字和标点分别计为 token。"""
        return sum(1 for token in self._token_pattern.findall(text) if not token.isspace())

    def _recursive_split(self, text: str, level: int, max_tokens: Optional[int] = None) -> List[str]:
        limit = max_tokens or self.chunk_size
        if self.count_tokens(text) <= limit:
            return [text]
        if level >= len(self._splitters):
            return self._split_by_tokens(text, limit)

        parts = self._splitters[level](text)
        if len(parts) == 1:
            return self._recursive_split(text, level + 1, limit)

        result: List[str] = []
        for part in parts:
            if part.strip():
                if level == 0:
                    result.extend(self._split_section_with_heading(part, limit))
                else:
                    result.extend(self._recursive_split(part, level + 1, limit))
        return result

    def _split_section_with_heading(self, section: str, limit: int) -> List[str]:
        """长章节拆分后为每个子块保留标题，避免标题和正文失去关联。"""
        first_line, separator, body = section.strip().partition("\n")
        if not separator or not self._section_pattern.match(first_line) or not body.strip():
            return self._recursive_split(section, 1, limit)
        remaining = limit - self.count_tokens(first_line)
        if remaining <= 0:
            return self._split_by_tokens(section, limit)
        body_parts = self._recursive_split(body.strip(), 1, remaining)
        return [self._join(first_line, part) for part in body_parts]

    @staticmethod
    def _split_at_positions(text: str, pattern: re.Pattern, before_match: bool = False) -> List[str]:
        if before_match:
            positions = [match.start() for match in pattern.finditer(text) if match.start() > 0]
        else:
            positions = [match.end() for match in pattern.finditer(text) if match.end() < len(text)]
        if not positions:
            return [text]
        boundaries = [0, *positions, len(text)]
        return [text[start:end] for start, end in zip(boundaries, boundaries[1:]) if text[start:end].strip()]

    def _split_by_tokens(self, text: str, limit: int) -> List[str]:
        tokens = self._token_pattern.findall(text)
        parts: List[str] = []
        current: List[str] = []
        count = 0
        overlap_size = min(self.chunk_overlap, max(0, limit - 1))
        for token in tokens:
            increment = 0 if token.isspace() else 1
            if increment and count >= limit:
                parts.append("".join(current).strip())
                boundary_space = current[-1] if current and current[-1].isspace() else ""
                overlap = self._last_tokens("".join(current), overlap_size)
                current = [overlap, boundary_space] if overlap else []
                count = self.count_tokens(overlap)
            current.append(token)
            count += increment
        if current and "".join(current).strip():
            parts.append("".join(current).strip())
        return parts

    def _pack_with_overlap(self, units: List[str]) -> List[str]:
        chunks: List[str] = []
        current_units: List[str] = []
        for unit in units:
            unit = unit.strip()
            if not unit:
                continue
            candidate = self._join_units([*current_units, unit])
            if current_units and self.count_tokens(candidate) > self.chunk_size:
                chunks.append(self._join_units(current_units).strip())
                current_units = self._semantic_overlap(current_units)
                while current_units and self.count_tokens(self._join_units([*current_units, unit])) > self.chunk_size:
                    current_units.pop(0)
            current_units.append(unit)
        if current_units:
            chunks.append(self._join_units(current_units).strip())
        return chunks

    def _semantic_overlap(self, units: List[str]) -> List[str]:
        """只复用完整语义单元；不为了重叠从普通句子中间截断。"""
        overlap: List[str] = []
        for unit in reversed(units):
            candidate = [unit, *overlap]
            if self.count_tokens(self._join_units(candidate)) > self.chunk_overlap:
                break
            overlap = candidate
        return overlap

    def _join_units(self, units: List[str]) -> str:
        result = ""
        for unit in units:
            result = self._join(result, unit)
        return result

    @staticmethod
    def _join(left: str, right: str) -> str:
        if not left:
            return right
        if left[-1:].isspace() or right[:1].isspace():
            return left + right
        return left + "\n" + right

    def _last_tokens(self, text: str, amount: int) -> str:
        if amount <= 0:
            return ""
        tokens = self._token_pattern.findall(text)
        seen = 0
        start = len(tokens)
        while start > 0 and seen < amount:
            start -= 1
            if not tokens[start].isspace():
                seen += 1
        return "".join(tokens[start:]).strip()
