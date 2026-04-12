#!/usr/bin/env python3
"""
라디오 극장 성우 인덱스 자동 생성
reviews/drama/radio_theater/*.md 의 출연진을 파싱해서
성우별 출연 작품·역할을 drama/radio_theater_cast.md 에 생성

사용법: python scripts/generate_cast.py
"""

import re
from pathlib import Path
from collections import defaultdict

REVIEWS_DIR = Path(__file__).parent.parent / "reviews" / "drama" / "radio_theater"
OUTPUT_FILE = Path(__file__).parent.parent / "drama" / "radio_theater_cast.md"


def parse_cast(md_text: str) -> list[tuple[str, str]]:
    """출연진 섹션에서 (역할, 성우) 쌍을 추출"""
    cast = []
    in_cast = False
    for line in md_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- **출연진**"):
            in_cast = True
            continue
        if in_cast:
            # 들여쓰기 목록이 끝나면 종료
            if stripped.startswith("- **") or stripped == "---":
                break
            m = re.match(r"^\s*-\s+(.+):\s+(.+)$", stripped)
            if m:
                roles_str = m.group(1).strip()
                actors_str = m.group(2).strip()
                # 여러 성우가 콤마로 나열된 경우 (예: 줄순이들: 배주원, 유승희, ...)
                actors = [a.strip() for a in actors_str.split(",") if a.strip()]
                for actor in actors:
                    cast.append((roles_str, actor))
    return cast


def parse_title(md_text: str) -> str:
    """헤더에서 제목 추출"""
    for line in md_text.splitlines():
        m = re.match(r"^#\s+(.+?)\s*—", line)
        if m:
            return m.group(1).strip()
    return ""


def generate_cast_md(actor_data: dict[str, list[dict]]) -> str:
    """성우 인덱스 마크다운 생성"""
    lines = [
        "# 라디오 극장 성우 인덱스",
        "",
    ]

    for actor in sorted(actor_data.keys()):
        entries = actor_data[actor]
        lines.append(f"## {actor}")
        lines.append("")
        lines.append("| 작품 | 역할 |")
        lines.append("|------|------|")
        for entry in sorted(entries, key=lambda e: e["filename"]):
            link = f"[{entry['title']}](../reviews/drama/radio_theater/{entry['filename']})"
            lines.append(f"| {link} | {entry['roles']} |")
        lines.append("")

    return "\n".join(lines)


def main():
    print("🎙️ 라디오 극장 리뷰 로딩 중...")

    actor_data: dict[str, list[dict]] = defaultdict(list)

    review_files = sorted(REVIEWS_DIR.glob("*.md"))
    print(f"   → {len(review_files)}개 리뷰 파일 발견")

    for md_file in review_files:
        text = md_file.read_text(encoding="utf-8")
        title = parse_title(text)
        if not title:
            print(f"   ⚠️  {md_file.name}: 제목 파싱 실패, 건너뜀")
            continue

        cast = parse_cast(text)
        for roles, actor in cast:
            actor_data[actor].append({
                "title": title,
                "filename": md_file.name,
                "roles": roles,
            })

    print(f"🎭 성우 {len(actor_data)}명 수집됨")

    content = generate_cast_md(actor_data)
    OUTPUT_FILE.write_text(content, encoding="utf-8")
    print(f"✅ {OUTPUT_FILE.relative_to(OUTPUT_FILE.parent.parent)} 생성 완료")


if __name__ == "__main__":
    main()
