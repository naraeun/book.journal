#!/usr/bin/env python3
"""
리뷰 md 파일 생성 스크립트
- 책, 드라마, 라디오 극장, 영화, 웹툰, 위대한 수업 지원
- 목록 테이블에서 메타데이터 자동 조회 (책) 또는 대화형 입력 (비도서)
- 리뷰 파일 생성 + 목록 테이블 자동 업데이트

사용법:
  python scripts/create_review.py                        # 대화형 (책)
  python scripts/create_review.py 3156                   # 책 번호 지정
  python scripts/create_review.py 3156 URL               # 책 번호 + 블로그 URL
  python scripts/create_review.py --type drama            # 드라마
  python scripts/create_review.py --type radio            # 라디오 극장
  python scripts/create_review.py --type movie            # 영화
  python scripts/create_review.py --type webtoon          # 웹툰
  python scripts/create_review.py --type greatminds       # 위대한 수업
  python scripts/create_review.py --reread 1697           # 재독 업데이트 (대화형 날짜)
  python scripts/create_review.py --reread 1697 -d 2026-03-21  # 재독 + 날짜 지정
  python scripts/create_review.py --sync-reread           # 재독 목록 일괄 동기화
"""

import sys
import re
import argparse
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
BOOKS_DIR = ROOT / "books"
REVIEWS_DIR = ROOT / "reviews"
PICKS_DIR = ROOT / "picks"
TOPICS_DIR = ROOT / "topics"

# ─── 유형별 설정 ───────────────────────────────────────────────

CONTENT_TYPES = {
    "book": {
        "name": "책",
        "list_file": None,  # books/ 폴더에서 동적 검색
        "review_dir": None,  # reviews/YYYY/ 동적
    },
    "drama": {
        "name": "드라마",
        "list_file": ROOT / "drama" / "drama.md",
        "review_dir": REVIEWS_DIR / "drama" / "drama",
    },
    "radio": {
        "name": "라디오 극장",
        "list_file": ROOT / "drama" / "radio_theater.md",
        "review_dir": REVIEWS_DIR / "drama" / "radio_theater",
    },
    "movie": {
        "name": "영화",
        "list_file": ROOT / "movie" / "movie.md",
        "review_dir": REVIEWS_DIR / "movie",
    },
    "webtoon": {
        "name": "웹툰",
        "list_file": ROOT / "webtoon" / "webtoon.md",
        "review_dir": REVIEWS_DIR / "webtoon",
    },
    "greatminds": {
        "name": "위대한 수업",
        "list_file": ROOT / "greatminds" / "greatminds.md",
        "review_dir": REVIEWS_DIR / "greatminds",
    },
    "podcast": {
        "name": "팟캐스트",
        "list_file": ROOT / "podcast" / "podcast.md",
        "review_dir": REVIEWS_DIR / "podcast",
    },
}


# ─── 공통 유틸 ─────────────────────────────────────────────────


def fetch_blog_date(blog_url: str) -> str | None:
    """네이버 블로그에서 작성 날짜 추출 (시간 제외)"""
    url = blog_url.replace("m.blog.naver.com", "blog.naver.com").replace(
        "blog.naver.com", "m.blog.naver.com"
    )
    if not url.startswith("http"):
        url = "https://" + url
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8")
        m = re.search(r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.", html)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    except Exception as e:
        print(f"⚠️  블로그 날짜 가져오기 실패: {e}")
    return None


def get_date(blog_url: str = "") -> str:
    """블로그 URL에서 날짜 추출, 실패 시 오늘 날짜"""
    if blog_url:
        print("📅 블로그에서 날짜 가져오는 중...")
        date = fetch_blog_date(blog_url)
        if date:
            print(f"  → {date}")
            return date
    return datetime.now().strftime("%Y-%m-%d")


def title_to_filename(title: str) -> str:
    """제목을 파일명으로 변환 (공백 → 언더스코어)"""
    return title.replace(" ", "_")


def confirm(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    answer = input(f"{prompt} ({hint}): ").strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")


def ask(prompt: str, required: bool = True) -> str:
    """대화형 입력"""
    while True:
        value = input(f"{prompt}: ").strip()
        if value or not required:
            return value
        print("  ⚠️  필수 항목입니다.")


def update_list_table(list_file: Path, title: str, review_rel: str, blog_url: str = "") -> bool:
    """목록 테이블에서 제목으로 찾아 리뷰·블로그 컬럼 업데이트"""
    if not list_file.exists():
        return False

    text = list_file.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    updated = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 2:
            continue
        # 제목은 첫 번째 데이터 컬럼
        if cells[0] != title:
            continue

        # 리뷰 컬럼 찾아서 업데이트 (📝 아이콘이 없는 컬럼)
        for j, cell in enumerate(cells):
            if cell == "" or cell.isspace():
                # 빈 컬럼 중 리뷰 컬럼 위치 추정 (헤더에서 '리뷰' 찾기)
                header_line = None
                for h_line in lines:
                    h_stripped = h_line.strip()
                    if h_stripped.startswith("|") and "리뷰" in h_stripped:
                        header_line = h_stripped
                        break
                if header_line:
                    header_cells = [c.strip() for c in header_line.strip("|").split("|")]
                    try:
                        review_idx = header_cells.index("리뷰")
                        blog_idx = header_cells.index("블로그") if "블로그" in header_cells else -1
                    except ValueError:
                        break

                    if review_idx < len(cells) and not cells[review_idx]:
                        cells[review_idx] = f"[📝]({review_rel})"
                    if blog_url and blog_idx >= 0 and blog_idx < len(cells) and not cells[blog_idx]:
                        cells[blog_idx] = f"[✏️]({blog_url})"

                    lines[i] = "| " + " | ".join(cells) + " |\n"
                    updated = True
                break

        if updated:
            break

    if updated:
        list_file.write_text("".join(lines), encoding="utf-8")
    return updated


def add_to_list_table(list_file: Path, new_row: str, title: str) -> bool:
    """목록 테이블에 새 행 추가 (테이블 첫 번째 데이터 행 위치에 삽입)"""
    if not list_file.exists():
        return False

    text = list_file.read_text(encoding="utf-8")

    # 이미 존재하는지 확인
    if f"| {title} |" in text or f"| {title} " in text:
        return False

    lines = text.splitlines(keepends=True)

    # 구분선 바로 다음에 삽입 (최신이 위로)
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("|") and re.search(r"[-:]{2,}", s):
            lines.insert(i + 1, new_row)
            list_file.write_text("".join(lines), encoding="utf-8")
            return True

    return False


# ─── 책 ────────────────────────────────────────────────────────


def create_review_md(book: dict, blog_url: str = "") -> str:
    """책 리뷰 md 파일 내용 생성 (add_book.py 호환용)"""
    review_date = get_date(blog_url)
    blog_line = f"[Link]({blog_url})" if blog_url else ""

    return f"""# {book['title']} — {book['author']}

- **번호**: {book['num']}
- **날짜**: {review_date}
- **카테고리**: {book['category']}
- **블로그**: {blog_line}

---

"""


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

        review_link = f"[📝]({review_path})"
        cells[6] = review_link if len(cells) > 6 else review_link

        if blog_url and len(cells) > 7:
            if not cells[7]:
                cells[7] = f"[✏️]({blog_url})"

        lines[i] = "| " + " | ".join(cells) + " |\n"
        updated = True
        break

    if updated:
        md_file.write_text("".join(lines), encoding="utf-8")
    return updated


def list_topics() -> list[str]:
    """topics/ 폴더의 topic 이름 목록 반환"""
    if not TOPICS_DIR.exists():
        return []
    return sorted(f.stem for f in TOPICS_DIR.glob("*.md"))


def add_to_topic(topic_name: str, book: dict, year: str, review_rel: str, blog_url: str = "") -> bool:
    """topic 파일 테이블에 번호 내림차순으로 책 추가"""
    topic_file = TOPICS_DIR / f"{topic_name}.md"
    if not topic_file.exists():
        return False

    text = topic_file.read_text(encoding="utf-8")
    if f"| {book['num']} |" in text:
        print(f"  ℹ️  #{book['num']}은 이미 {topic_name}.md에 있습니다.")
        return False

    review_link = f"[📝]({review_rel})"
    blog_link = f"[✏️]({blog_url})" if blog_url else ""
    new_row = f"| {book['num']} | {book['title']} | {book['author']} | {year} | {review_link} | {blog_link} |\n"

    lines = text.splitlines(keepends=True)

    # 헤더와 구분선 이후의 데이터 행에서 번호 내림차순 위치 찾기
    insert_at = -1
    past_separator = False
    for i, line in enumerate(lines):
        s = line.strip()
        if not s.startswith("|"):
            continue
        # 구분선 감지
        cells = [c.strip() for c in s.strip("|").split("|")]
        if all(re.fullmatch(r"[-: ]+", c) for c in cells if c):
            past_separator = True
            insert_at = i + 1  # 구분선 바로 다음이 기본 삽입 위치
            continue
        if not past_separator:
            continue
        # 데이터 행에서 번호 추출
        try:
            row_num = int(cells[0])
        except (ValueError, IndexError):
            continue
        if book["num"] > row_num:
            insert_at = i
            break
        insert_at = i + 1  # 현재 행보다 작으면 다음 위치로

    if insert_at < 0:
        return False

    lines.insert(insert_at, new_row)
    topic_file.write_text("".join(lines), encoding="utf-8")
    return True


def add_reread_to_books(book_num: int, book: dict, original_date: str, reread_date: str) -> bool:
    """books/ 파일의 '한번 더 읽은 책 목록' 섹션에 재독 행 추가

    reread_date의 연도에 해당하는 books 파일에 추가한다.
    """
    reread_year = reread_date[:4]
    books_file = BOOKS_DIR / f"{reread_year}.md"
    if not books_file.exists():
        return False

    text = books_file.read_text(encoding="utf-8")

    # 이미 재독 목록에 있는지 확인 (같은 번호 + 같은 재독 날짜)
    if f"| {book_num} |" in text.split("한번 더 읽은 책 목록")[-1] if "한번 더 읽은 책 목록" in text else "":
        # 더 정밀하게: 재독 날짜까지 일치하는지 확인
        for line in text.splitlines():
            if f"| {book_num} |" in line and reread_date in line:
                return False

    reread_month = str(int(reread_date[5:7]))
    original_year = original_date[:4]
    review_link = f"[📝](../reviews/{original_year}/{book_num}.md)"
    new_row = f"| {reread_month} | {book_num} | {book['title']} | {book['author']} | {original_date} | {reread_date} | {review_link} |"

    if "한번 더 읽은 책 목록" not in text:
        # 섹션이 없으면 새로 생성
        section = f"""
---

## {reread_year}년 한번 더 읽은 책 목록

| 월 | 번호 | 제목 | 작가 | 원래 날짜 | 재독 날짜 | 리뷰 |
|:--:|:----:|------|------|:---------:|:---------:|------|
{new_row}
"""
        text = text.rstrip() + "\n" + section
    else:
        # 섹션이 있으면 재독 날짜 내림차순으로 삽입
        lines = text.splitlines(keepends=True)
        insert_at = -1
        in_reread_section = False
        past_separator = False

        for i, line in enumerate(lines):
            if "한번 더 읽은 책 목록" in line:
                in_reread_section = True
                continue
            if not in_reread_section:
                continue
            s = line.strip()
            if not s.startswith("|"):
                continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            # 구분선 감지
            if all(re.fullmatch(r"[-: ]+", c) for c in cells if c):
                past_separator = True
                insert_at = i + 1
                continue
            if not past_separator:
                continue
            # 데이터 행에서 재독 날짜 추출 (5번째 컬럼, 0-indexed)
            try:
                row_reread_date = cells[5] if len(cells) > 5 else ""
            except IndexError:
                continue
            if reread_date >= row_reread_date:
                insert_at = i
                break
            insert_at = i + 1

        if insert_at >= 0:
            lines.insert(insert_at, new_row + "\n")
            text = "".join(lines)

    books_file.write_text(text, encoding="utf-8")
    return True


def update_picks_link(book_num: int, year: str) -> bool:
    """picks/ 파일에서 링크 없는 #번호를 리뷰 링크로 교체"""
    picks_file = PICKS_DIR / f"{year}.md"
    if not picks_file.exists():
        return False

    text = picks_file.read_text(encoding="utf-8")
    pattern = rf"\\?(?<!\[)#{book_num}\b"
    replacement = f"[#{book_num}](../reviews/{year}/{book_num}.md)"
    new_text = re.sub(pattern, replacement, text)

    if new_text == text:
        return False

    picks_file.write_text(new_text, encoding="utf-8")
    return True


def create_book(book_num: int = None, blog_url: str = ""):
    """책 리뷰 생성"""
    if book_num is None:
        raw = input("📚 책 번호: ").strip()
        try:
            book_num = int(raw)
        except ValueError:
            print("❌ 번호는 숫자로 입력해주세요.")
            sys.exit(1)
    if not blog_url:
        blog_url = input("🔗 블로그 URL (선택, 엔터 건너뜀): ").strip()

    print(f"\n🔍 #{book_num} 검색 중...")
    book = find_book(book_num)

    if not book:
        print(f"❌ #{book_num}을 books/ 테이블에서 찾을 수 없습니다.")
        sys.exit(1)

    year = book["year_file"].stem
    print(f"  제목    : {book['title']}")
    print(f"  저자    : {book['author']}")
    print(f"  카테고리: {book['category']}")
    print(f"  연도    : {year}")

    review_file = REVIEWS_DIR / year / f"{book_num}.md"
    if review_file.exists():
        print(f"\n⚠️  {review_file} 이미 존재합니다.")
        if not confirm("덮어쓰시겠어요?", default=False):
            sys.exit(0)

    review_date = get_date(blog_url)
    blog_line = f"[Link]({blog_url})" if blog_url else ""

    content = f"""# {book['title']} — {book['author']}

- **번호**: {book['num']}
- **날짜**: {review_date}
- **카테고리**: {book['category']}
- **블로그**: {blog_line}

---

"""

    print(f"\n📄 생성할 파일: {review_file}")
    if not confirm("생성하시겠어요?"):
        print("취소했습니다.")
        sys.exit(0)

    review_file.parent.mkdir(parents=True, exist_ok=True)
    review_file.write_text(content, encoding="utf-8")
    print(f"✅ {review_file} 생성 완료!")

    review_rel = f"../reviews/{year}/{book_num}.md"
    if update_books_table(book, review_rel, blog_url):
        print(f"✅ {book['year_file'].name} 테이블 업데이트 완료!")
    else:
        print("⚠️  테이블 업데이트 실패 — 수동으로 확인해주세요.")

    if update_picks_link(book_num, year):
        print(f"✅ picks/{year}.md 링크 업데이트 완료!")

    topics = list_topics()
    if topics:
        print(f"\n📂 topic 추가 (사용 가능: {', '.join(topics)})")
        topic_input = input("  topic 이름 (여러 개는 쉼표 구분, 엔터 건너뜀): ").strip()
        if topic_input:
            review_rel_topic = f"../reviews/{year}/{book_num}.md"
            for t in [t.strip() for t in topic_input.split(",") if t.strip()]:
                if t in topics:
                    if add_to_topic(t, book, year, review_rel_topic, blog_url):
                        print(f"✅ topics/{t}.md 추가 완료!")
                else:
                    print(f"⚠️  '{t}' topic을 찾을 수 없습니다.")


# ─── 드라마 ────────────────────────────────────────────────────


def create_drama(blog_url: str = ""):
    """드라마 리뷰 생성"""
    cfg = CONTENT_TYPES["drama"]
    print(f"\n🎬 {cfg['name']} 리뷰 생성")

    title = ask("📺 제목")
    platform = ask("📡 플랫폼 (예: 넷플릭스, 티빙)")
    air_year = ask("📅 방영연도")
    director = ask("🎬 연출")
    writer = ask("✍️  작가")
    original = input("📖 원작 리뷰 경로 (선택, 엔터 건너뜀): ").strip()
    if not blog_url:
        blog_url = input("🔗 블로그 URL (선택, 엔터 건너뜀): ").strip()

    review_date = get_date(blog_url)
    blog_line = f"[Link]({blog_url})" if blog_url else ""
    original_line = f"[Link]({original})" if original else ""

    content = f"""# {title}

- **날짜**: {review_date}
- **플랫폼**: {platform}
- **방영연도**: {air_year}
- **연출**: {director}
- **작가**: {writer}
- **원작**: {original_line}
- **블로그**: {blog_line}

---

"""

    filename = title_to_filename(title) + ".md"
    review_file = cfg["review_dir"] / filename

    if review_file.exists():
        print(f"\n⚠️  {review_file} 이미 존재합니다.")
        if not confirm("덮어쓰시겠어요?", default=False):
            sys.exit(0)

    print(f"\n📄 생성할 파일: {review_file}")
    if not confirm("생성하시겠어요?"):
        print("취소했습니다.")
        sys.exit(0)

    review_file.parent.mkdir(parents=True, exist_ok=True)
    review_file.write_text(content, encoding="utf-8")
    print(f"✅ {review_file} 생성 완료!")

    review_rel = f"../reviews/drama/drama/{filename}"
    if not update_list_table(cfg["list_file"], title, review_rel, blog_url):
        review_link = f"[📝]({review_rel})"
        blog_link = f"[✏️]({blog_url})" if blog_url else ""
        watch_year = review_date[:4]
        new_row = f"| {title} | {director} | {writer} | {platform} | {air_year} | {watch_year} | {review_link} | {blog_link} |\n"
        if add_to_list_table(cfg["list_file"], new_row, title):
            print(f"✅ {cfg['list_file'].name} 행 추가 완료!")
        else:
            print(f"⚠️  {cfg['list_file'].name} 업데이트 실패 — 수동으로 확인해주세요.")
    else:
        print(f"✅ {cfg['list_file'].name} 테이블 업데이트 완료!")


# ─── 라디오 극장 ───────────────────────────────────────────────


def create_radio(blog_url: str = ""):
    """라디오 극장 리뷰 생성"""
    cfg = CONTENT_TYPES["radio"]
    print(f"\n📻 {cfg['name']} 리뷰 생성")

    title = ask("📻 제목")
    broadcast = ask("📅 방송 (예: 2026-03)")
    original = input("📖 원작 리뷰 경로 (선택, 엔터 건너뜀): ").strip()
    if not blog_url:
        blog_url = input("🔗 블로그 URL (선택, 엔터 건너뜀): ").strip()

    review_date = get_date(blog_url)
    blog_line = f"[Link]({blog_url})" if blog_url else ""
    original_line = f"[Link]({original})" if original else ""

    content = f"""# {title} — KBS 라디오 극장

- **날짜**: {review_date}
- **방송**: {broadcast}
- **원작**: {original_line}
- **블로그**: {blog_line}
- **출연진**:

---

"""

    filename = title_to_filename(title) + ".md"
    review_file = cfg["review_dir"] / filename

    if review_file.exists():
        print(f"\n⚠️  {review_file} 이미 존재합니다.")
        if not confirm("덮어쓰시겠어요?", default=False):
            sys.exit(0)

    print(f"\n📄 생성할 파일: {review_file}")
    if not confirm("생성하시겠어요?"):
        print("취소했습니다.")
        sys.exit(0)

    review_file.parent.mkdir(parents=True, exist_ok=True)
    review_file.write_text(content, encoding="utf-8")
    print(f"✅ {review_file} 생성 완료!")

    review_rel = f"../reviews/drama/radio_theater/{filename}"
    if not update_list_table(cfg["list_file"], title, review_rel, blog_url):
        review_link = f"[📝]({review_rel})"
        blog_link = f"[✏️]({blog_url})" if blog_url else ""
        original_link = f"[📖]({original})" if original else ""
        new_row = f"| {title} | {original_link} | {broadcast} | {review_link} | {blog_link} |\n"
        if add_to_list_table(cfg["list_file"], new_row, title):
            print(f"✅ {cfg['list_file'].name} 행 추가 완료!")
        else:
            print(f"⚠️  {cfg['list_file'].name} 업데이트 실패 — 수동으로 확인해주세요.")
    else:
        print(f"✅ {cfg['list_file'].name} 테이블 업데이트 완료!")


# ─── 영화 ──────────────────────────────────────────────────────


def create_movie(blog_url: str = ""):
    """영화 리뷰 생성"""
    cfg = CONTENT_TYPES["movie"]
    print(f"\n🎬 {cfg['name']} 리뷰 생성")

    title = ask("🎬 제목")
    director = ask("🎬 감독")
    release_year = ask("📅 개봉연도")
    if not blog_url:
        blog_url = input("🔗 블로그 URL (선택, 엔터 건너뜀): ").strip()

    review_date = get_date(blog_url)
    blog_line = f"[Link]({blog_url})" if blog_url else ""

    content = f"""# {title}

- **날짜**: {review_date}
- **감독**: {director}
- **개봉연도**: {release_year}
- **블로그**: {blog_line}

---

"""

    filename = title_to_filename(title) + ".md"
    review_file = cfg["review_dir"] / filename

    if review_file.exists():
        print(f"\n⚠️  {review_file} 이미 존재합니다.")
        if not confirm("덮어쓰시겠어요?", default=False):
            sys.exit(0)

    print(f"\n📄 생성할 파일: {review_file}")
    if not confirm("생성하시겠어요?"):
        print("취소했습니다.")
        sys.exit(0)

    review_file.parent.mkdir(parents=True, exist_ok=True)
    review_file.write_text(content, encoding="utf-8")
    print(f"✅ {review_file} 생성 완료!")

    review_rel = f"../reviews/movie/{filename}"
    if not update_list_table(cfg["list_file"], title, review_rel, blog_url):
        review_link = f"[📝]({review_rel})"
        blog_link = f"[✏️]({blog_url})" if blog_url else ""
        watch_year = review_date[:4]
        new_row = f"| {title} | {director} | {release_year} | {watch_year} | {review_link} | {blog_link} |\n"
        if add_to_list_table(cfg["list_file"], new_row, title):
            print(f"✅ {cfg['list_file'].name} 행 추가 완료!")
        else:
            print(f"⚠️  {cfg['list_file'].name} 업데이트 실패 — 수동으로 확인해주세요.")
    else:
        print(f"✅ {cfg['list_file'].name} 테이블 업데이트 완료!")


# ─── 웹툰 ─────────────────────────────────────────────────────


def create_webtoon(blog_url: str = ""):
    """웹툰 리뷰 생성"""
    cfg = CONTENT_TYPES["webtoon"]
    print(f"\n📖 {cfg['name']} 리뷰 생성")

    title = ask("📖 제목")
    author = ask("✍️  작가")
    platform = ask("📡 플랫폼 (예: 네이버 웹툰)")
    work_year = ask("📅 작품연도 (예: 2018-2021)")
    read_year = ask("📅 읽은연도")
    if not blog_url:
        blog_url = input("🔗 블로그 URL (선택, 엔터 건너뜀): ").strip()

    review_date = get_date(blog_url)
    blog_line = f"[Link]({blog_url})" if blog_url else ""

    content = f"""# {title}

- **날짜**: {review_date}
- **작가**: {author}
- **플랫폼**: {platform}
- **작품연도**: {work_year}
- **읽은연도**: {read_year}
- **블로그**: {blog_line}

---

"""

    filename = title_to_filename(title) + ".md"
    review_file = cfg["review_dir"] / filename

    if review_file.exists():
        print(f"\n⚠️  {review_file} 이미 존재합니다.")
        if not confirm("덮어쓰시겠어요?", default=False):
            sys.exit(0)

    print(f"\n📄 생성할 파일: {review_file}")
    if not confirm("생성하시겠어요?"):
        print("취소했습니다.")
        sys.exit(0)

    review_file.parent.mkdir(parents=True, exist_ok=True)
    review_file.write_text(content, encoding="utf-8")
    print(f"✅ {review_file} 생성 완료!")

    review_rel = f"../reviews/webtoon/{filename}"
    if not update_list_table(cfg["list_file"], title, review_rel, blog_url):
        review_link = f"[📝]({review_rel})"
        blog_link = f"[✏️]({blog_url})" if blog_url else ""
        new_row = f"| {title} | {author} | {platform} | {work_year} | {read_year} | {review_link} | {blog_link} |\n"
        if add_to_list_table(cfg["list_file"], new_row, title):
            print(f"✅ {cfg['list_file'].name} 행 추가 완료!")
        else:
            print(f"⚠️  {cfg['list_file'].name} 업데이트 실패 — 수동으로 확인해주세요.")
    else:
        print(f"✅ {cfg['list_file'].name} 테이블 업데이트 완료!")


# ─── 위대한 수업 ──────────────────────────────────────────────


def create_greatminds(blog_url: str = ""):
    """위대한 수업 리뷰 생성"""
    cfg = CONTENT_TYPES["greatminds"]
    print(f"\n🎓 {cfg['name']} 리뷰 생성")

    title = ask("🎓 제목")
    lecturer = ask("👤 강연자")
    air_year = ask("📅 방영연도")
    watch_year = ask("📅 시청연도")
    if not blog_url:
        blog_url = input("🔗 블로그 URL (선택, 엔터 건너뜀): ").strip()

    review_date = get_date(blog_url)
    blog_line = f"[Link]({blog_url})" if blog_url else ""

    content = f"""# {title} — EBS 위대한 수업

- **날짜**: {review_date}
- **강연자**: {lecturer}
- **방영연도**: {air_year}
- **시청연도**: {watch_year}
- **블로그**: {blog_line}
- **구성**

---

"""

    filename = title_to_filename(title) + ".md"
    review_file = cfg["review_dir"] / filename

    if review_file.exists():
        print(f"\n⚠️  {review_file} 이미 존재합니다.")
        if not confirm("덮어쓰시겠어요?", default=False):
            sys.exit(0)

    print(f"\n📄 생성할 파일: {review_file}")
    if not confirm("생성하시겠어요?"):
        print("취소했습니다.")
        sys.exit(0)

    review_file.parent.mkdir(parents=True, exist_ok=True)
    review_file.write_text(content, encoding="utf-8")
    print(f"✅ {review_file} 생성 완료!")

    review_rel = f"../reviews/greatminds/{filename}"
    if not update_list_table(cfg["list_file"], title, review_rel, blog_url):
        review_link = f"[📝]({review_rel})"
        blog_link = f"[✏️]({blog_url})" if blog_url else ""
        new_row = f"| {title} | {lecturer} | {air_year} | {watch_year} | {review_link} | {blog_link} |\n"
        if add_to_list_table(cfg["list_file"], new_row, title):
            print(f"✅ {cfg['list_file'].name} 행 추가 완료!")
        else:
            print(f"⚠️  {cfg['list_file'].name} 업데이트 실패 — 수동으로 확인해주세요.")
    else:
        print(f"✅ {cfg['list_file'].name} 테이블 업데이트 완료!")


# ─── 팟캐스트 ─────────────────────────────────────────────────


def create_podcast(blog_url: str = ""):
    """팟캐스트 리뷰 생성"""
    cfg = CONTENT_TYPES["podcast"]
    print(f"\n🎙️ {cfg['name']} 리뷰 생성")

    title = ask("🎙️ 제목")
    host = ask("👤 호스트")
    if not blog_url:
        blog_url = input("🔗 블로그 URL (선택, 엔터 건너뜀): ").strip()

    review_date = get_date(blog_url)
    blog_line = f"[Link]({blog_url})" if blog_url else ""

    content = f"""# {title}

- **날짜**: {review_date}
- **호스트**: {host}
- **블로그**: {blog_line}

---

"""

    filename = title_to_filename(title) + ".md"
    review_file = cfg["review_dir"] / filename

    if review_file.exists():
        print(f"\n⚠️  {review_file} 이미 존재합니다.")
        if not confirm("덮어쓰시겠어요?", default=False):
            sys.exit(0)

    print(f"\n📄 생성할 파일: {review_file}")
    if not confirm("생성하시겠어요?"):
        print("취소했습니다.")
        sys.exit(0)

    review_file.parent.mkdir(parents=True, exist_ok=True)
    review_file.write_text(content, encoding="utf-8")
    print(f"✅ {review_file} 생성 완료!")

    review_rel = f"../reviews/podcast/{filename}"
    if not update_list_table(cfg["list_file"], title, review_rel, blog_url):
        review_link = f"[📝]({review_rel})"
        blog_link = f"[✏️]({blog_url})" if blog_url else ""
        new_row = f"| {title} | {host} | {review_link} | {blog_link} |\n"
        if add_to_list_table(cfg["list_file"], new_row, title):
            print(f"✅ {cfg['list_file'].name} 행 추가 완료!")
        else:
            print(f"⚠️  {cfg['list_file'].name} 업데이트 실패 — 수동으로 확인해주세요.")
    else:
        print(f"✅ {cfg['list_file'].name} 테이블 업데이트 완료!")


# ─── 메인 ──────────────────────────────────────────────────────


def reread_book(book_num: int = None, reread_date: str = ""):
    """기존 리뷰 파일에 재독 업데이트 + books 재독 목록 추가"""
    if book_num is None:
        raw = input("📚 책 번호: ").strip()
        try:
            book_num = int(raw)
        except ValueError:
            print("❌ 번호는 숫자로 입력해주세요.")
            sys.exit(1)

    if not reread_date:
        reread_date = input("📅 재독 날짜 (YYYY-MM-DD, 엔터=오늘): ").strip()
        if not reread_date:
            reread_date = datetime.now().strftime("%Y-%m-%d")

    # 날짜 형식 검증
    try:
        datetime.strptime(reread_date, "%Y-%m-%d")
    except ValueError:
        print("❌ 날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식으로 입력해주세요.")
        sys.exit(1)

    print(f"\n🔍 #{book_num} 검색 중...")
    book = find_book(book_num)
    if not book:
        print(f"❌ #{book_num}을 books/ 테이블에서 찾을 수 없습니다.")
        sys.exit(1)

    original_year = book["year_file"].stem
    print(f"  제목    : {book['title']}")
    print(f"  저자    : {book['author']}")
    print(f"  원래 연도: {original_year}")

    # 리뷰 파일 확인
    review_file = REVIEWS_DIR / original_year / f"{book_num}.md"
    if not review_file.exists():
        print(f"❌ {review_file} 리뷰 파일이 없습니다. 먼저 리뷰를 생성해주세요.")
        sys.exit(1)

    # 리뷰 파일에서 원래 날짜 추출
    review_text = review_file.read_text(encoding="utf-8")
    date_match = re.search(r"\*\*날짜\*\*:\s*(\d{4}-\d{2}-\d{2})", review_text)
    if not date_match:
        print("❌ 리뷰 파일에서 날짜를 찾을 수 없습니다.")
        sys.exit(1)
    original_date = date_match.group(1)

    # 리뷰 파일에 업데이트 날짜 추가/갱신
    if "**업데이트 날짜**" in review_text:
        review_text = re.sub(
            r"(\*\*업데이트 날짜\*\*:\s*)\d{4}-\d{2}-\d{2}",
            f"\\g<1>{reread_date}",
            review_text,
        )
        print(f"  📝 업데이트 날짜 갱신: {reread_date}")
    else:
        review_text = review_text.replace(
            f"- **날짜**: {original_date}\n",
            f"- **날짜**: {original_date}\n- **업데이트 날짜**: {reread_date}\n",
        )
        print(f"  📝 업데이트 날짜 추가: {reread_date}")

    # 재독 섹션 뼈대 추가 (이미 해당 날짜 섹션이 없으면)
    reread_heading = f"### {reread_date}"
    if reread_heading not in review_text:
        review_text = review_text.rstrip() + f"\n\n---\n{reread_heading}\n\n"
        print(f"  📝 재독 섹션 추가: {reread_heading}")

    review_file.write_text(review_text, encoding="utf-8")

    # books 재독 목록 추가
    if add_reread_to_books(book_num, book, original_date, reread_date):
        reread_year = reread_date[:4]
        print(f"✅ books/{reread_year}.md 재독 목록 추가 완료!")
    else:
        print("  ℹ️  재독 목록에 이미 있거나 추가할 수 없습니다.")

    print("✅ 재독 업데이트 완료!")


def sync_reread():
    """전체 리뷰 파일을 스캔하여 누락된 재독 목록을 books/ 파일에 일괄 추가"""
    print("🔄 재독 목록 동기화 시작...\n")
    added = 0
    skipped = 0

    for year_dir in sorted(REVIEWS_DIR.iterdir()):
        if not year_dir.is_dir():
            continue
        # reviews/YYYY/ 형태만 처리
        if not re.fullmatch(r"\d{4}", year_dir.name):
            continue

        for review_file in sorted(year_dir.glob("*.md")):
            # 번호 추출
            try:
                book_num = int(review_file.stem)
            except ValueError:
                continue

            text = review_file.read_text(encoding="utf-8")

            # 업데이트 날짜 확인
            update_match = re.search(r"\*\*업데이트 날짜\*\*:\s*(\d{4}-\d{2}-\d{2})", text)
            if not update_match:
                continue

            # 원래 날짜 확인
            date_match = re.search(r"\*\*날짜\*\*:\s*(\d{4}-\d{2}-\d{2})", text)
            if not date_match:
                continue

            original_date = date_match.group(1)

            # 재독 섹션에서 모든 재독 날짜 추출 (### YYYY-MM-DD)
            reread_dates = re.findall(r"^### (\d{4}-\d{2}-\d{2})\s*$", text, re.MULTILINE)
            if not reread_dates:
                continue

            # 책 정보 조회
            book = find_book(book_num)
            if not book:
                print(f"  ⚠️  #{book_num} books/ 테이블에서 찾을 수 없음 — 건너뜀")
                continue

            for reread_date in reread_dates:
                # 이미 재독 목록에 있는지 먼저 확인
                reread_year = reread_date[:4]
                books_file = BOOKS_DIR / f"{reread_year}.md"
                if books_file.exists():
                    books_text = books_file.read_text(encoding="utf-8")
                    if f"| {book_num} |" in books_text and reread_date in books_text:
                        skipped += 1
                        continue

                # 확인 프롬프트
                print(f"  📖 #{book_num} {book['title']} ({original_date} → {reread_date})")
                if not confirm("    재독 목록에 추가할까요?"):
                    print("    건너뜀")
                    skipped += 1
                    continue

                if add_reread_to_books(book_num, book, original_date, reread_date):
                    print(f"    ✅ books/{reread_year}.md 추가")
                    added += 1
                else:
                    skipped += 1

    print(f"\n🔄 동기화 완료: {added}건 추가, {skipped}건 건너뜀")


TYPE_CHOICES = ["book", "drama", "radio", "movie", "webtoon", "greatminds", "podcast"]
TYPE_LABELS = {
    "book": "📚 책",
    "drama": "📺 드라마",
    "radio": "📻 라디오 극장",
    "movie": "🎬 영화",
    "webtoon": "📖 웹툰",
    "greatminds": "🎓 위대한 수업",
    "podcast": "🎙️ 팟캐스트",
}

CREATORS = {
    "book": create_book,
    "drama": create_drama,
    "radio": create_radio,
    "movie": create_movie,
    "webtoon": create_webtoon,
    "greatminds": create_greatminds,
    "podcast": create_podcast,
}


def main():
    parser = argparse.ArgumentParser(description="리뷰 md 파일 생성")
    parser.add_argument("book_num", nargs="?", type=int, help="책 번호 (book 유형)")
    parser.add_argument("blog_url", nargs="?", default="", help="블로그 URL")
    parser.add_argument(
        "--type", "-t",
        choices=TYPE_CHOICES,
        default=None,
        help="콘텐츠 유형",
    )
    parser.add_argument(
        "--reread", "-r",
        action="store_true",
        help="재독 업데이트 모드",
    )
    parser.add_argument(
        "--sync-reread",
        action="store_true",
        help="재독 목록 일괄 동기화",
    )
    parser.add_argument(
        "--date", "-d",
        default="",
        help="재독 날짜 (YYYY-MM-DD, reread 모드에서 사용)",
    )
    args = parser.parse_args()

    # sync-reread 모드
    if args.sync_reread:
        sync_reread()
        return

    # reread 모드
    if args.reread:
        reread_book(args.book_num, args.date)
        return

    # --type 없이 숫자만 넘기면 책으로 처리 (기존 호환)
    if args.type is None and args.book_num is not None:
        args.type = "book"

    # --type도 없고 번호도 없으면 유형 선택
    if args.type is None:
        print("📋 콘텐츠 유형을 선택하세요:\n")
        for i, key in enumerate(TYPE_CHOICES, 1):
            print(f"  {i}. {TYPE_LABELS[key]}")
        print()
        while True:
            choice = input("번호 선택: ").strip()
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(TYPE_CHOICES):
                    args.type = TYPE_CHOICES[idx]
                    break
            except ValueError:
                pass
            print("  ⚠️  올바른 번호를 입력해주세요.")

    # 유형별 생성
    if args.type == "book":
        create_book(args.book_num, args.blog_url)
    else:
        CREATORS[args.type](args.blog_url)


if __name__ == "__main__":
    main()
