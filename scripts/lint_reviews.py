#!/usr/bin/env python3
"""
리뷰 마크다운 린트 스크립트
reviews/review_rules.md 기반으로 검사 및 자동 수정

사용법:
  python scripts/lint_reviews.py              # 전체 검사 (리포트만)
  python scripts/lint_reviews.py --fix        # 전체 검사 + 자동 수정
  python scripts/lint_reviews.py 3159.md      # 특정 파일 검사
  python scripts/lint_reviews.py 3159.md --fix
"""

import sys
import re
from pathlib import Path

REVIEWS_DIR = Path(__file__).parent.parent / "reviews"


def find_review_files(target: str = None) -> list[Path]:
    """검사 대상 파일 목록"""
    if target:
        matches = list(REVIEWS_DIR.rglob(target))
        if not matches:
            print(f"❌ {target}을 찾을 수 없습니다.")
            sys.exit(1)
        return matches
    return sorted(
        p for p in REVIEWS_DIR.rglob("*.md")
        if p.name != "review_rules.md"
    )


def detect_review_type(path: Path) -> str:
    """파일 경로 기반으로 리뷰 유형 판별"""
    rel = path.relative_to(REVIEWS_DIR)
    parts = rel.parts
    if len(parts) >= 2 and parts[0] == "drama":
        if parts[1] == "radio_theater":
            return "radio_theater"
        if parts[1] == "drama":
            return "drama"
    if len(parts) >= 1 and parts[0] == "webtoon":
        return "webtoon"
    if len(parts) >= 1 and parts[0] == "greatminds":
        return "greatminds"
    if len(parts) >= 1 and parts[0] == "movie":
        return "movie"
    if len(parts) >= 1 and parts[0] == "podcast":
        return "podcast"
    if len(parts) >= 2 and parts[0] == "music":
        if parts[1] == "concerts":
            return "concert"
        if parts[1] == "albums":
            return "album"
    return "book"


# 유형별 필수 메타데이터 필드
REQUIRED_META = {
    "book": ["번호", "날짜", "카테고리", "블로그"],
    "radio_theater": ["날짜", "방송", "원작", "블로그", "출연진"],
    "drama": ["날짜", "플랫폼", "방영연도", "연출", "작가", "원작", "블로그"],
    "webtoon": ["날짜", "작가", "플랫폼", "작품연도", "읽은연도", "블로그"],
    "greatminds": ["날짜", "강연자", "방영연도", "시청연도", "블로그"],
    "movie": ["날짜", "감독", "개봉연도", "블로그"],
    "podcast": ["날짜", "호스트", "블로그"],
    "concert": ["날짜", "장소", "연주자/단체", "블로그", "프로그램"],
    "album": ["날짜", "블로그"],
}


def check_file(path: Path) -> list[dict]:
    """파일 검사 후 문제 목록 반환"""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    issues = []
    review_type = detect_review_type(path)

    # 1. 헤더에 역할 표기 확인 (책 리뷰만)
    if review_type == "book" and lines and re.search(r"\(지은이\)|\(옮긴이\)|\(글\)|\(그림\)", lines[0]):
        issues.append({"type": "header_role", "msg": "헤더에 역할 표기 포함"})

    # 2. 유형별 메타데이터 구조 확인
    # 메타데이터는 헤더 아래 --- 구분선 전까지의 영역 (넉넉히 앞 30줄)
    meta_lines = lines[:30]
    required = REQUIRED_META.get(review_type, [])
    missing = [field for field in required if not any(f"**{field}**" in l for l in meta_lines)]
    if missing:
        issues.append({"type": "meta_missing", "msg": f"메타데이터 누락: {', '.join(missing)}"})

    # 3. 구분선 확인 — 메타데이터 아래 --- 가 있는지
    has_sep = any(l.strip() == "---" for l in lines)
    if not has_sep:
        issues.append({"type": "no_separator", "msg": "메타데이터 아래 --- 구분선 없음"})

    # 4. zero-width space
    zwsp_count = text.count("\u200b")
    if zwsp_count > 0:
        issues.append({"type": "zwsp", "msg": f"zero-width space x{zwsp_count}", "fixable": True})

    # 5. 연속 빈 줄
    if re.search(r"\n{3,}", text):
        issues.append({"type": "multi_blank", "msg": "연속 빈 줄 (2줄 이상)", "fixable": True})

    # 6. 인용 사이 간격 불균일 (빈 줄 2개 이상)
    quote_gap = re.search(r'(^>.*)\n\n\n+(^>)', text, re.MULTILINE)
    if quote_gap:
        issues.append({"type": "quote_gap", "msg": "인용 구절 사이 빈 줄 불균일", "fixable": True})

    # 7. 외부 미디어 bare link 검사 (YouTube, Apple Music)
    media_patterns = [
        r'(?<!\()https?://(?:www\.)?(?:youtube\.com|youtu\.be)/\S+',
        r'(?<!\()https?://music\.apple\.com/\S+',
    ]
    for i, line in enumerate(lines, 1):
        # 마크다운 링크 안에 있는 URL은 제외
        stripped = re.sub(r'\[.*?\]\(.*?\)', '', line)
        for pat in media_patterns:
            if re.search(pat, stripped):
                issues.append({"type": "bare_media_link", "msg": f"L{i}: bare 미디어 링크 — 마크다운 링크로 감싸주세요"})

    # 8. 미디어 링크 텍스트 비어있는지 검사
    empty_media = re.findall(r'\[\s*\]\((https?://(?:www\.)?(?:youtube\.com|youtu\.be|music\.apple\.com)/\S+?)\)', text)
    for url in empty_media:
        issues.append({"type": "empty_media_text", "msg": f"미디어 링크 텍스트 비어있음: {url}"})

    return issues


def fix_file(path: Path) -> list[str]:
    """자동 수정 가능한 항목 수정"""
    text = path.read_text(encoding="utf-8")
    original = text
    fixed = []

    # zero-width space 제거
    if "\u200b" in text:
        text = text.replace("\u200b", "")
        fixed.append("zero-width space 제거")

    # 연속 빈 줄 정리
    if re.search(r"\n{3,}", text):
        text = re.sub(r"\n{3,}", "\n\n", text)
        fixed.append("연속 빈 줄 정리")

    # 헤더 역할 표기 제거
    lines = text.splitlines()
    if lines and re.search(r"\s*\(지은이\)|\s*\(옮긴이\)|\s*\(글\)|\s*\(그림\)", lines[0]):
        lines[0] = re.sub(r"\s*\((지은이|옮긴이|글|그림)\)", "", lines[0])
        # 쉼표+공백으로 연결된 역할자도 제거
        lines[0] = re.sub(r",\s*\S+\s*\((옮긴이|글|그림)\)", "", lines[0])
        text = "\n".join(lines)
        fixed.append("헤더 역할 표기 제거")

    if text != original:
        path.write_text(text, encoding="utf-8")

    return fixed


def main():
    args = sys.argv[1:]
    do_fix = "--fix" in args
    if do_fix:
        args.remove("--fix")
    target = args[0] if args else None

    files = find_review_files(target)
    print(f"📋 {len(files)}개 파일 검사 중...\n")

    total_issues = 0
    total_fixed = 0

    for path in files:
        issues = check_file(path)
        if not issues:
            continue

        rel = path.relative_to(REVIEWS_DIR.parent)
        print(f"📄 {rel}")
        for issue in issues:
            fixable = issue.get("fixable", False)
            marker = "🔧" if fixable else "⚠️"
            print(f"  {marker} {issue['msg']}")
        total_issues += len(issues)

        if do_fix:
            fixed = fix_file(path)
            if fixed:
                for f in fixed:
                    print(f"  ✅ {f}")
                total_fixed += len(fixed)
        print()

    print(f"{'=' * 40}")
    print(f"검사 완료: {len(files)}개 파일, {total_issues}개 문제 발견")
    if do_fix:
        print(f"자동 수정: {total_fixed}건")


if __name__ == "__main__":
    main()
