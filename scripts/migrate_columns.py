#!/usr/bin/env python3
"""
기존 연도별 md 파일에 리뷰|블로그 컬럼을 일괄 추가하는 마이그레이션 스크립트
사용법: python scripts/migrate_columns.py
       python scripts/migrate_columns.py --dry-run  (실제 변경 없이 미리보기)
"""

import re
import argparse
from pathlib import Path

BOOKS_DIR = Path(__file__).parent.parent / "books"


def migrate_file(md_file: Path, dry_run: bool = False) -> bool:
    text = md_file.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    new_lines = []
    changed = False
    header_found = False

    for line in lines:
        stripped = line.strip()

        # 헤더 행 감지: | 로 시작하고 "카테고리" 포함, 리뷰 컬럼 아직 없는 경우
        if (stripped.startswith("|")
                and "카테고리" in stripped
                and "리뷰" not in stripped):
            header_found = True
            new_line = line.rstrip()
            # 끝 | 앞에 새 컬럼 삽입
            if new_line.endswith("|"):
                new_line = new_line + " 리뷰 | 블로그 |"
            else:
                new_line = new_line + " | 리뷰 | 블로그 |"
            new_lines.append(new_line + "\n")
            changed = True
            continue

        # 구분선 행: |:--:| 패턴, 헤더 직후
        if (header_found
                and stripped.startswith("|")
                and re.search(r"[-:]{2,}", stripped)
                and "리뷰" not in stripped):
            new_line = line.rstrip()
            if new_line.endswith("|"):
                new_line = new_line + "------|--------|"
            else:
                new_line = new_line + "|------|--------|"
            new_lines.append(new_line + "\n")
            header_found = False
            continue

        # 데이터 행: | 로 시작, 헤더가 이미 처리됐고 리뷰 컬럼 없는 행
        if (stripped.startswith("|")
                and "카테고리" not in stripped
                and not re.search(r"[-:]{3,}", stripped)
                and "리뷰" not in stripped
                and "|" in stripped):
            # 컬럼 수 확인 (6개면 기존 형식)
            cols = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cols) == 6:
                new_line = line.rstrip()
                if new_line.endswith("|"):
                    new_line = new_line + " | |"
                else:
                    new_line = new_line + " | | |"
                new_lines.append(new_line + "\n")
                changed = True
                continue

        new_lines.append(line)

    if not changed:
        return False

    if dry_run:
        print(f"\n--- {md_file.name} 미리보기 ---")
        for l in new_lines[:10]:
            print(l, end="")
    else:
        md_file.write_text("".join(new_lines), encoding="utf-8")

    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="변경 없이 미리보기만")
    args = parser.parse_args()

    md_files = sorted(BOOKS_DIR.glob("*.md"))
    if not md_files:
        print(f"❌ {BOOKS_DIR} 에 md 파일이 없습니다.")
        return

    success, skipped = 0, 0
    for md_file in md_files:
        result = migrate_file(md_file, dry_run=args.dry_run)
        if result:
            success += 1
            if not args.dry_run:
                print(f"✅ {md_file.name} 변환 완료")
        else:
            skipped += 1
            print(f"⏭️  {md_file.name} 건너뜀 (이미 변환됨 또는 해당 없음)")

    print(f"\n{'[미리보기]' if args.dry_run else '[완료]'} "
          f"변환 {success}개 / 건너뜀 {skipped}개")


if __name__ == "__main__":
    main()
