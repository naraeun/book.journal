#!/usr/bin/env python3
"""
리뷰 md 파일 생성 스크립트
- books/ 테이블에서 메타데이터 자동 조회
- reviews/YYYY/번호.md 생성
- books/ 테이블의 리뷰·블로그 컬럼 자동 업데이트

사용법:
  python scripts/create_review.py              # 대화형
  python scripts/create_review.py 3156         # 번호 지정
  python scripts/create_review.py 3156 URL     # 번호 + 블로그 URL
"""

import sys
import re
from datetime import datetime
from pathlib import Path

BOOKS_DIR = Path(__file__).parent.parent / "books"
REVIEWS_DIR = Path(__file__).parent.parent / "reviews"


def find_book(book_num: int) -> dict | None:
    """books/ 폴더의 모든 md 파일에서 번호로 책 정보 검색"""
    for md_file in sorted(BOOKS_DIR.glob("*.md"), reverse=True):
        text = md_file.read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) < 6:
                continue
            try:
                num = int(cells[1])
            except ValueError:
                continue
            if num == book_num:
                return {
                    "year_file": md_file,
                    "month": cells[0],
                    "num": num,
                    "title": cells[2],
                    "author": cells[3],
                    "year_num": cells[4],
                    "category": cells[5],
                    "review": cells[6] if len(cells) > 6 else "",
                    "blog": cells[7] if len(cells) > 7 else "",
                }
    return None


def create_review_md(book: dict, blog_url: str = "") -> str:
    """리뷰 md 파일 내용 생성"""
    today = datetime.now().strftime("%Y.%-m.%-d")
    blog_line = f"[Link]({blog_url})" if blog_url else ""

    content = f"""# {book['title']} — {book['author']}

- **번호**: {book['num']}
- **날짜**: {today}
- **카테고리**: {book['category']}
- **블로그**: {blog_line}

---

"""
    return content


def get_year_from_file(md_file: Path) -> str:
    """파일명에서 연도 추출 (예: 2026.md → 2026)"""
    return md_file.stem


def update_books_table(book: dict, review_path: str, blog_url: str = "") -> bool:
    """books/ 테이블의 리뷰·블로그 컬럼 업데이트"""
    md_file = book["year_file"]
    text = md_file.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    updated = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 6:
            continue
        try:
            num = int(cells[1])
        except ValueError:
            continue
        if num != book["num"]:
            continue

        # 리뷰 컬럼 업데이트
        review_link = f"[📝]({review_path})"
        cells[6] = review_link if len(cells) > 6 else review_link

        # 블로그 컬럼 업데이트
        if blog_url and len(cells) > 7:
            if not cells[7]:
                cells[7] = f"[✏️]({blog_url})"

        # 행 재구성
        lines[i] = "| " + " | ".join(cells) + " |\n"
        updated = True
        break

    if updated:
        md_file.write_text("".join(lines), encoding="utf-8")
    return updated


def confirm(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    answer = input(f"{prompt} ({hint}): ").strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")


def main():
    # 인자 파싱
    if len(sys.argv) >= 2:
        try:
            book_num = int(sys.argv[1])
        except ValueError:
            print("❌ 번호는 숫자로 입력해주세요.")
            sys.exit(1)
        blog_url = sys.argv[2] if len(sys.argv) >= 3 else ""
    else:
        raw = input("📚 책 번호: ").strip()
        try:
            book_num = int(raw)
        except ValueError:
            print("❌ 번호는 숫자로 입력해주세요.")
            sys.exit(1)
        blog_url = input("🔗 블로그 URL (선택, 엔터 건너뜀): ").strip()

    # 책 검색
    print(f"\n🔍 #{book_num} 검색 중...")
    book = find_book(book_num)

    if not book:
        print(f"❌ #{book_num}을 books/ 테이블에서 찾을 수 없습니다.")
        sys.exit(1)

    year = get_year_from_file(book["year_file"])
    print(f"  제목    : {book['title']}")
    print(f"  저자    : {book['author']}")
    print(f"  카테고리: {book['category']}")
    print(f"  연도    : {year}")

    # 이미 리뷰가 있는지 확인
    review_file = REVIEWS_DIR / year / f"{book_num}.md"
    if review_file.exists():
        print(f"\n⚠️  {review_file} 이미 존재합니다.")
        if not confirm("덮어쓰시겠어요?", default=False):
            sys.exit(0)

    # 리뷰 생성
    content = create_review_md(book, blog_url)

    print(f"\n📄 생성할 파일: {review_file}")
    if not confirm("생성하시겠어요?"):
        print("취소했습니다.")
        sys.exit(0)

    review_file.parent.mkdir(parents=True, exist_ok=True)
    review_file.write_text(content, encoding="utf-8")
    print(f"✅ {review_file} 생성 완료!")

    # books 테이블 업데이트
    review_rel = f"../reviews/{year}/{book_num}.md"
    if update_books_table(book, review_rel, blog_url):
        print(f"✅ {book['year_file'].name} 테이블 업데이트 완료!")
    else:
        print("⚠️  테이블 업데이트 실패 — 수동으로 확인해주세요.")


if __name__ == "__main__":
    main()
