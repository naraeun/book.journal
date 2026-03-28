#!/usr/bin/env python3
"""
독서 기록 분석 스크립트
사용법: python scripts/analyze.py
결과:  analysis/stats.md, README.md의 통계 섹션 자동 갱신
"""

import re
import os
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime

BOOKS_DIR = Path(__file__).parent.parent / "books"
ANALYSIS_DIR = Path(__file__).parent.parent / "analysis"
README_PATH = Path(__file__).parent.parent / "README.md"

ANALYSIS_DIR.mkdir(exist_ok=True)


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

        # 헤더 행 감지
        if header is None and any(k in cells for k in ["제목", "번호", "월"]):
            header = cells
            continue
        # 구분선 건너뛰기
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


def analyze(books: list[dict]) -> dict:
    stats = {}

    # 연도별 독서량
    by_year = Counter(b["연도"] for b in books)
    stats["by_year"] = dict(sorted(by_year.items()))

    # 카테고리 분포 (대분류만)
    categories = []
    for b in books:
        cat = b.get("카테고리", "")
        top = cat.split(">")[0].strip() if cat else "미분류"
        categories.append(top)
    stats["by_category"] = Counter(categories).most_common(15)

    # 작가별 권수 (상위 15)
    stats["by_author"] = Counter(b.get("작가", "") for b in books).most_common(15)

    # 블로그·리뷰 연동률
    total = len(books)
    blog_linked = sum(1 for b in books if b.get("블로그", "").strip() not in ("", "-"))
    review_linked = sum(1 for b in books if b.get("리뷰", "").strip() not in ("", "-"))
    stats["blog_link_rate"] = (blog_linked, total)
    stats["review_link_rate"] = (review_linked, total)

    # 총 독서량
    stats["total"] = total

    return stats


def render_bar(value: int, max_value: int, width: int = 20) -> str:
    filled = round(value / max_value * width) if max_value else 0
    return "█" * filled + "░" * (width - filled)


def generate_stats_md(stats: dict) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# 📊 독서 통계",
        f"\n> 마지막 갱신: {now}\n",
        f"## 총 독서량: **{stats['total']}권**\n",
    ]

    # 연도별 독서량
    lines.append("## 연도별 독서량\n")
    lines.append("| 연도 | 권수 | 그래프 |")
    lines.append("|------|-----:|--------|")
    max_year_count = max(stats["by_year"].values()) if stats["by_year"] else 1
    for year, count in stats["by_year"].items():
        bar = render_bar(count, max_year_count)
        lines.append(f"| {year} | {count} | `{bar}` |")

    # 카테고리 분포
    lines.append("\n## 카테고리 분포 (상위 15)\n")
    lines.append("| 카테고리 | 권수 |")
    lines.append("|----------|-----:|")
    for cat, count in stats["by_category"]:
        lines.append(f"| {cat} | {count} |")

    # 작가별
    lines.append("\n## 많이 읽은 작가 (상위 15)\n")
    lines.append("| 작가 | 권수 |")
    lines.append("|------|-----:|")
    for author, count in stats["by_author"]:
        if author:
            lines.append(f"| {author} | {count} |")

    # 블로그·리뷰 연동률
    blog_linked, total = stats["blog_link_rate"]
    review_linked, _ = stats["review_link_rate"]
    blog_rate = f"{blog_linked/total*100:.1f}%" if total else "0%"
    review_rate = f"{review_linked/total*100:.1f}%" if total else "0%"
    lines.append("\n## 블로그·리뷰 연동률\n")
    lines.append(f"| | 연동 권수 | 비율 |")
    lines.append(f"|---|---:|---:|")
    lines.append(f"| 네이버 블로그 | {blog_linked} | {blog_rate} |")
    lines.append(f"| 리뷰 | {review_linked} | {review_rate} |")
    lines.append(f"| 전체 | {total} | — |")

    return "\n".join(lines)


def update_readme(stats_summary: str):
    """README.md의 <!-- STATS --> 블록 갱신"""
    marker_start = "<!-- STATS_START -->"
    marker_end = "<!-- STATS_END -->"

    if not README_PATH.exists():
        return

    content = README_PATH.read_text(encoding="utf-8")
    new_block = f"{marker_start}\n{stats_summary}\n{marker_end}"

    if marker_start in content:
        content = re.sub(
            rf"{re.escape(marker_start)}.*?{re.escape(marker_end)}",
            new_block,
            content,
            flags=re.DOTALL,
        )
    else:
        content += f"\n\n{new_block}\n"

    README_PATH.write_text(content, encoding="utf-8")
    print("✅ README.md 통계 섹션 갱신 완료")


def main():
    print("📚 독서 기록 로딩 중...")
    books = load_all_books()
    print(f"   → {len(books)}권 로드됨 ({len(set(b['연도'] for b in books))}개 연도)")

    print("📊 분석 중...")
    stats = analyze(books)

    stats_md = generate_stats_md(stats)
    out_path = ANALYSIS_DIR / "stats.md"
    out_path.write_text(stats_md, encoding="utf-8")
    print(f"✅ {out_path} 생성 완료")

    # README 요약 (연도별 독서량만)
    summary_lines = [f"**총 {stats['total']}권** (2011–현재)\n"]
    summary_lines.append("| 연도 | 권수 |")
    summary_lines.append("|------|-----:|")
    for year, count in stats["by_year"].items():
        summary_lines.append(f"| {year} | {count} |")
    summary_lines.append("\n자세한 통계 → [analysis/stats.md](analysis/stats.md)")

    update_readme("\n".join(summary_lines))


if __name__ == "__main__":
    main()
