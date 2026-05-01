#!/usr/bin/env python3
"""
달리기 기록 계산 컬럼 자동 갱신 스크립트
running/*.md 파일에 평균 페이스, 1회 평균 거리 컬럼을 추가/갱신

사용법: python scripts/update_running_pace.py
"""

import re
from pathlib import Path

RUNNING_DIR = Path(__file__).parent.parent / "running"

# 기대하는 컬럼 순서
# 월 | 횟수 | 거리(km) | 시간 | 평균 페이스 | 1회 평균(km)
HEADER = "| 월 | 횟수 | 거리(km) | 시간 | 평균 페이스 | 1회 평균(km) |"
SEPARATOR = "|:--:|-----:|--------:|------|----------:|-----------:|"


def parse_time(time_str: str) -> int:
    """시간 문자열(H:MM:SS 또는 MM:SS)을 초 단위로 변환"""
    time_str = time_str.strip()
    if not time_str:
        return 0
    parts = time_str.split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    return 0


def calc_pace(seconds: int, distance_km: float) -> str:
    """평균 페이스 계산 (M'SS" 형식)"""
    if distance_km <= 0 or seconds <= 0:
        return ""
    pace_seconds = seconds / distance_km
    minutes = int(pace_seconds // 60)
    secs = int(pace_seconds % 60)
    return f"{minutes}'{secs:02d}\""


def calc_avg_distance(distance_km: float, count: int) -> str:
    """1회 평균 거리 계산"""
    if count <= 0 or distance_km <= 0:
        return ""
    return f"{distance_km / count:.1f}"


def update_file(path: Path) -> bool:
    """파일에 평균 페이스 + 1회 평균 거리 컬럼 추가/갱신"""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    updated_lines = []
    modified = False

    for line in lines:
        stripped = line.strip()

        # 헤더 행
        if stripped.startswith("|") and "월" in stripped and "횟수" in stripped:
            if stripped != HEADER:
                line = HEADER
                modified = True
            updated_lines.append(line)
            continue

        # 구분선 행
        if stripped.startswith("|") and re.search(r"[-:]{2,}", stripped) and "월" not in stripped:
            if stripped != SEPARATOR:
                line = SEPARATOR
                modified = True
            updated_lines.append(line)
            continue

        # 데이터 행
        if stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            try:
                int(cells[0])  # 월 숫자 확인
            except (ValueError, IndexError):
                updated_lines.append(line)
                continue

            month = cells[0].strip()
            count_str = cells[1].strip() if len(cells) > 1 else ""
            dist_str = cells[2].strip() if len(cells) > 2 else ""
            time_str = cells[3].strip() if len(cells) > 3 else ""

            count = int(count_str) if count_str else 0
            distance = float(dist_str) if dist_str else 0.0
            seconds = parse_time(time_str)

            pace = calc_pace(seconds, distance)
            avg_dist = calc_avg_distance(distance, count)

            new_line = f"| {month} | {count_str} | {dist_str} | {time_str} | {pace} | {avg_dist} |"

            if stripped != new_line:
                modified = True

            updated_lines.append(new_line)
            continue

        updated_lines.append(line)

    if modified:
        path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")

    return modified


def main():
    print("🏃 평균 페이스 · 1회 평균 거리 계산 중...\n")

    updated_count = 0
    for path in sorted(RUNNING_DIR.glob("*.md")):
        if path.name == "stats.md":
            continue
        year_str = path.stem
        if not year_str.isdigit():
            continue

        if update_file(path):
            print(f"  ✅ {path.name} 업데이트")
            updated_count += 1
        else:
            print(f"  ⏭️  {path.name} 변경 없음")

    print(f"\n완료: {updated_count}개 파일 업데이트")


if __name__ == "__main__":
    main()
