"""책 기록에서 작가명을 일관되게 처리하는 공용 함수."""

import re


def split_authors(author_str: str) -> list[str]:
    """공저자 문자열을 개별 작가로 분리한다."""
    author_str = re.sub(r"\s*외\s*\d+명", "", author_str)
    authors = re.split(r"[,，]\s*", author_str)
    return [author.strip() for author in authors if author.strip()]
