#!/usr/bin/env python3
"""
다독 작가별 md 파일 자동 생성
books/*.md 테이블을 파싱해서 10권 이상 읽은 작가의 페이지를 authors/ 에 생성
작가별 파일에는 읽은 책 목록과 리뷰 링크가 포함됨

사용법: python scripts/generate_authors.py           # 기본 10권 이상
       python scripts/generate_authors.py --min 5   # 최소 5권 이상
"""

import sys
import re
import unicodedata
from pathlib import Path
from collections import defaultdict

BOOKS_DIR = Path(__file__).parent.parent / "books"
AUTHORS_DIR = Path(__file__).parent.parent / "authors"
REVIEWS_DIR = Path(__file__).parent.parent / "reviews"

MIN_BOOKS_DEFAULT = 10


def parse_table_rows(md_text: str) -> list[dict]:
    """마크다운 테이블에서 행 데이터 파싱"""
    rows = []
    lines = md_text.splitlines()
    header = None
    for line in lines:
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if header is None and any(k in cells for k in ["제목", "번호", "월"]):
            header = cells
            continue
        if header and all(re.fullmatch(r"[-: ]+", c) for c in cells):
            continue
        if header and len(cells) >= 4:
            rows.append(dict(zip(header, cells)))
    return rows


def load_all_books() -> list[dict]:
    """모든 연도 md 파일 로드"""
    all_books = []
    for md_file in sorted(BOOKS_DIR.glob("*.md")):
        year = md_file.stem
        if not year.isdigit():
            continue
        text = md_file.read_text(encoding="utf-8")
        rows = parse_table_rows(text)
        for row in rows:
            row["연도"] = int(year)
            all_books.append(row)
    return all_books


def split_authors(author_str: str) -> list[str]:
    """공저자 문자열을 개별 작가로 분리"""
    author_str = re.sub(r"\s*외\s*\d+명", "", author_str)
    authors = re.split(r"[,，]\s*", author_str)
    return [a.strip() for a in authors if a.strip()]


def safe_filename(name: str) -> str:
    """작가명을 파일명으로 변환 (공백→언더스코어)"""
    name = unicodedata.normalize("NFC", name)
    name = re.sub(r"[/\\:*?\"<>|]", "", name)
    name = name.replace(" ", "_")
    return name


def has_review(year: int, num: str) -> bool:
    """리뷰 파일 존재 여부 확인"""
    return (REVIEWS_DIR / str(year) / f"{num}.md").exists()


def generate_author_md(author: str, books: list[dict]) -> str:
    """작가별 md 파일 내용 생성"""
    books_sorted = sorted(books, key=lambda b: int(b.get("번호", 0)), reverse=True)

    lines = [
        f"# {author}",
        "",
        f"총 {len(books_sorted)}권",
        "",
        "| 번호 | 제목 | 연도 | 카테고리 | 리뷰 |",
        "|:----:|------|:----:|----------|:----:|",
    ]

    for b in books_sorted:
        num = b.get("번호", "")
        title = b.get("제목", "")
        year = b.get("연도", "")
        cat = b.get("카테고리", "")

        if has_review(year, num):
            review = f"[📝](../reviews/{year}/{num}.md)"
        else:
            review = ""

        lines.append(f"| {num} | {title} | {year} | {cat} | {review} |")

    return "\n".join(lines) + "\n"


def main():
    min_books = MIN_BOOKS_DEFAULT
    if "--min" in sys.argv:
        idx = sys.argv.index("--min")
        if idx + 1 < len(sys.argv):
            min_books = int(sys.argv[idx + 1])

    print(f"📚 독서 기록 로딩 중...")
    books = load_all_books()
    print(f"   → {len(books)}권 로드됨")

    # 작가별 그룹핑 (공저자 분리)
    author_books = defaultdict(list)
    for b in books:
        for author in split_authors(b.get("작가", "")):
            if author:
                author_books[author].append(b)

    # 최소 권수 필터
    qualified = {a: bs for a, bs in author_books.items() if len(bs) >= min_books}
    print(f"✍️  {min_books}권 이상 읽은 작가: {len(qualified)}명")

    # authors/ 디렉토리 생성 및 파일 쓰기
    AUTHORS_DIR.mkdir(exist_ok=True)

    existing = set(f.name for f in AUTHORS_DIR.glob("*.md"))
    generated = set()

    for author, bs in sorted(qualified.items()):
        filename = safe_filename(author) + ".md"
        content = generate_author_md(author, bs)
        (AUTHORS_DIR / filename).write_text(content, encoding="utf-8")
        generated.add(filename)

    # 더 이상 해당하지 않는 파일 삭제
    removed = existing - generated
    for f in removed:
        (AUTHORS_DIR / f).unlink()
        print(f"   🗑️  {f} 삭제됨 (기준 미달)")

    print(f"✅ authors/ 에 {len(generated)}개 파일 생성 완료")


if __name__ == "__main__":
    main()
