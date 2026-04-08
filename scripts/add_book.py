#!/usr/bin/env python3
"""
알라딘 API로 책 정보를 검색해서 해당 연도 md 파일에 자동 추가
--blog 옵션 사용 시 리뷰 파일 생성 + 테이블 업데이트까지 수행

사용법: python scripts/add_book.py
       python scripts/add_book.py "책제목"
       python scripts/add_book.py "책제목" "작가"
       python scripts/add_book.py "책제목" "작가" --blog "URL"
"""

import sys
import re
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from aladin_search import search_book, get_category_short
from create_review import create_review_md, find_book, update_books_table

BOOKS_DIR = Path(__file__).parent.parent / "books"
REVIEWS_DIR = Path(__file__).parent.parent / "reviews"


def parse_table(text: str) -> tuple[list[str], list[str], list[str]]:
    """md 파일에서 헤더/구분선/데이터행 분리"""
    header, separator, rows, others = None, None, [], []
    lines = text.splitlines(keepends=True)
    for line in lines:
        s = line.strip()
        if s.startswith("|") and "번호" in s and "제목" in s:
            header = line
        elif s.startswith("|") and re.search(r"[-:]{2,}", s) and header and separator is None:
            separator = line
        elif s.startswith("|") and header and separator:
            rows.append(line)
        else:
            others.append((len(rows), line))
    return header, separator, rows, others, lines


def get_last_numbers(rows: list[str]) -> tuple[int, int]:
    """테이블에서 마지막 번호(통산), 연번호 추출"""
    total_num, year_num = 0, 0
    for row in rows:
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if len(cells) >= 5:
            try:
                total_num = max(total_num, int(cells[1]))
                year_num = max(year_num, int(cells[4]))
            except ValueError:
                pass
    return total_num, year_num


def make_row(month: int, total_num: int, title: str,
             author: str, year_num: int, category: str) -> str:
    return f"| {month} | {total_num} | {title} | {author} | {year_num} | {category} | | |\n"


def insert_row(md_file: Path, new_row: str) -> bool:
    """월 순서에 맞게 행 삽입 (같은 월이면 맨 앞에)"""
    text = md_file.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    # 새 행의 월 추출
    new_month = int(new_row.strip().strip("|").split("|")[0].strip())

    header_idx = sep_idx = None
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("|") and "번호" in s:
            header_idx = i
        elif header_idx and s.startswith("|") and re.search(r"[-:]{2,}", s):
            sep_idx = i
            break

    if sep_idx is None:
        print("❌ 테이블 구조를 찾을 수 없습니다.")
        return False

    # 데이터 행 시작 위치부터 순서 탐색
    insert_at = sep_idx + 1
    for i in range(sep_idx + 1, len(lines)):
        s = lines[i].strip()
        if not s.startswith("|"):
            break
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) >= 1:
            try:
                row_month = int(cells[0])
                if row_month <= new_month:
                    insert_at = i
                    break
            except ValueError:
                pass

    lines.insert(insert_at, new_row)
    md_file.write_text("".join(lines), encoding="utf-8")
    return True


def confirm(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    answer = input(f"{prompt} ({hint}): ").strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")


def main():
    now = datetime.now()
    year, month = now.year, now.month

    # 인자 파싱 (--blog 옵션 분리)
    args = sys.argv[1:]
    blog_url = ""
    if "--blog" in args:
        idx = args.index("--blog")
        if idx + 1 < len(args):
            blog_url = args[idx + 1]
            args = args[:idx] + args[idx + 2:]
        else:
            args = args[:idx]

    if len(args) >= 1:
        title_input = args[0]
        author_input = args[1] if len(args) >= 2 else ""
    else:
        title_input = input("📚 책 제목: ").strip()
        author_input = input("✍️  작가 (선택, 엔터 건너뜀): ").strip()
        if not blog_url:
            blog_url = input("🔗 블로그 URL (선택, 엔터 건너뜀): ").strip()

    if not title_input:
        print("❌ 제목을 입력해주세요.")
        sys.exit(1)

    # 알라딘 검색
    print(f"\n🔍 알라딘에서 '{title_input}' 검색 중...")
    result = search_book(title_input, author_input)

    if not result:
        print("❌ 검색 결과가 없습니다. 직접 입력하시겠어요?")
        if not confirm("직접 입력", default=True):
            sys.exit(0)
        result = {
            "title": title_input,
            "author": author_input,
            "category": input("카테고리 (예: 소설/시/희곡>한국소설): ").strip(),
        }
    else:
        category_short = get_category_short(result["category"])
        print(f"\n검색 결과:")
        print(f"  제목    : {result['title']}")
        print(f"  저자    : {result['author']}")
        print(f"  카테고리: {category_short}")

        if not confirm("\n이 책이 맞나요?"):
            print("직접 입력으로 전환합니다.")
            title_input = input(f"제목 [{title_input}]: ").strip() or title_input
            result["author"] = input(f"저자 [{result['author']}]: ").strip() or result["author"]
            category_short = input(f"카테고리 [{category_short}]: ").strip() or category_short

        result["category"] = get_category_short(result["category"])

    # 연도/월 확인
    year_input = input(f"\n연도 [{year}]: ").strip()
    month_input = input(f"월 [{month}]: ").strip()
    year = int(year_input) if year_input else year
    month = int(month_input) if month_input else month

    # md 파일 확인
    md_file = BOOKS_DIR / f"{year}.md"
    if not md_file.exists():
        print(f"\n⚠️  {md_file.name} 파일이 없습니다.")
        if confirm("새로 만드시겠어요?"):
            md_file.write_text(
                f"# {year}년 독서 목록\n\n"
                "| 월 | 번호 | 제목 | 작가 | 연번호 | 카테고리 | 리뷰 | 블로그 |\n"
                "|:--:|:----:|------|------|:------:|----------|------|--------|\n",
                encoding="utf-8"
            )
        else:
            sys.exit(0)

    # 번호 자동 계산
    text = md_file.read_text(encoding="utf-8")
    rows = [l for l in text.splitlines()
            if l.strip().startswith("|")
            and not re.search(r"[-:]{2,}", l)
            and "번호" not in l]
    last_total, last_year_num = get_last_numbers(rows)

    total_num = last_total + 1
    year_num = last_year_num + 1

    total_input = input(f"통산 번호 [{total_num}]: ").strip()
    year_num_input = input(f"연번호 [{year_num}]: ").strip()
    total_num = int(total_input) if total_input else total_num
    year_num = int(year_num_input) if year_num_input else year_num

    # 최종 확인 — 제목은 사용자가 입력한 원본 사용
    new_row = make_row(month, total_num, title_input,
                       result["author"], year_num, result["category"])
    print(f"\n추가할 행:\n{new_row.strip()}")

    if not confirm("\n{year}.md에 추가하시겠어요?".format(year=year)):
        print("취소했습니다.")
        sys.exit(0)

    if insert_row(md_file, new_row):
        print(f"✅ {year}.md에 추가 완료!")

        # 블로그 URL이 있으면 리뷰 파일도 생성
        if blog_url:
            print(f"\n📝 리뷰 생성 중 (#{total_num})...")
            book = find_book(total_num)
            if book:
                review_file = REVIEWS_DIR / str(year) / f"{total_num}.md"
                review_file.parent.mkdir(parents=True, exist_ok=True)
                content = create_review_md(book, blog_url)
                review_file.write_text(content, encoding="utf-8")
                print(f"✅ {review_file} 생성 완료!")

                review_rel = f"../reviews/{year}/{total_num}.md"
                if update_books_table(book, review_rel, blog_url):
                    print(f"✅ {year}.md 테이블 업데이트 완료!")
                else:
                    print("⚠️  테이블 업데이트 실패 — 수동으로 확인해주세요.")
            else:
                print(f"⚠️  #{total_num}을 테이블에서 찾을 수 없습니다.")
    else:
        print("❌ 추가 실패")


if __name__ == "__main__":
    main()
