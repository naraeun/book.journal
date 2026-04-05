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


def check_file(path: Path) -> list[dict]:
    """파일 검사 후 문제 목록 반환"""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    issues = []

    # 1. 헤더에 역할 표기 확인
    if lines and re.search(r"\(지은이\)|\(옮긴이\)|\(글\)|\(그림\)", lines[0]):
        issues.append({"type": "header_role", "msg": "헤더에 역할 표기 포함"})

    # 2. 메타데이터 구조 확인
    has_num = any("**번호**" in l for l in lines[:10])
    has_date = any("**날짜**" in l for l in lines[:10])
    has_cat = any("**카테고리**" in l for l in lines[:10])
    has_blog = any("**블로그**" in l for l in lines[:10])
    if not all([has_num, has_date, has_cat, has_blog]):
        missing = []
        if not has_num: missing.append("번호")
        if not has_date: missing.append("날짜")
        if not has_cat: missing.append("카테고리")
        if not has_blog: missing.append("블로그")
        issues.append({"type": "meta_missing", "msg": f"메타데이터 누락: {', '.join(missing)}"})

    # 3. 구분선 확인
    if "---" not in text.split("\n\n", 1)[0] if "\n\n" in text else text:
        has_sep = any(l.strip() == "---" for l in lines[:15])
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
