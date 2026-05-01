#!/usr/bin/env python3
"""
달리기 기록 통계 스크립트
running/*.md 파일을 파싱하여 running/stats.md 자동 생성

사용법: python scripts/analyze_running.py
"""

import re
from pathlib import Path
from datetime import datetime

RUNNING_DIR = Path(__file__).parent.parent / "running"
STATS_PATH = RUNNING_DIR / "stats.md"


def parse_time(time_str: str) -> int:
    """시간 문자열(H:MM:SS)을 초 단위로 변환"""
    time_str = time_str.strip()
    if not time_str:
        return 0
    parts = time_str.split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    return 0


def format_time(seconds: int) -> str:
    """초를 H:MM:SS 형식으로 변환"""
    if seconds == 0:
        return ""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h}:{m:02d}:{s:02d}"


def format_pace(seconds: int, distance: float) -> str:
    """평균 페이스 계산 (M'SS" 형식)"""
    if distance <= 0 or seconds <= 0:
        return ""
    pace_seconds = seconds / distance
    minutes = int(pace_seconds // 60)
    secs = int(pace_seconds % 60)
    return f"{minutes}'{secs:02d}\""


def parse_year_file(path: Path) -> list[dict]:
    """연도별 md 파일에서 월별 데이터 파싱"""
    text = path.read_text(encoding="utf-8")
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 4:
            continue
        try:
            month = int(cells[0])
        except ValueError:
            continue
        count_str = cells[1].strip()
        dist_str = cells[2].strip()
        time_str = cells[3].strip()
        if not count_str:
            continue
        rows.append({
            "month": month,
            "count": int(count_str),
            "distance": float(dist_str) if dist_str else 0.0,
            "seconds": parse_time(time_str),
        })
    return rows


def load_all_data() -> dict[int, list[dict]]:
    """모든 연도 파일 로드"""
    data = {}
    for path in sorted(RUNNING_DIR.glob("*.md")):
        if path.name == "stats.md":
            continue
        year_str = path.stem
        if not year_str.isdigit():
            continue
        rows = parse_year_file(path)
        if rows:
            data[int(year_str)] = rows
    return data


def render_bar(value: float, max_value: float, width: int = 20) -> str:
    if max_value == 0:
        return "░" * width
    filled = round(value / max_value * width)
    return "█" * filled + "░" * (width - filled)


def generate_stats(data: dict[int, list[dict]]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 전체 합산
    total_count = 0
    total_distance = 0.0
    total_seconds = 0
    year_summaries = []

    for year in sorted(data.keys()):
        rows = data[year]
        y_count = sum(r["count"] for r in rows)
        y_dist = sum(r["distance"] for r in rows)
        y_secs = sum(r["seconds"] for r in rows)
        months_with_data = len(rows)
        monthly_avg = round(y_dist / months_with_data, 1) if months_with_data else 0
        total_count += y_count
        total_distance += y_dist
        total_seconds += y_secs
        year_summaries.append({
            "year": year,
            "count": y_count,
            "distance": y_dist,
            "seconds": y_secs,
            "monthly_avg": monthly_avg,
        })

    # 월별 합산 (전체 연도)
    month_totals = {}
    for year, rows in data.items():
        for r in rows:
            m = r["month"]
            if m not in month_totals:
                month_totals[m] = {"count": 0, "distance": 0.0, "seconds": 0}
            month_totals[m]["count"] += r["count"]
            month_totals[m]["distance"] += r["distance"]
            month_totals[m]["seconds"] += r["seconds"]

    lines = [
        "# 🏃 달리기 통계",
        f"\n> 마지막 갱신: {now}\n",
        "## 총 기록",
        f"- 총 횟수: **{total_count}회**",
        f"- 총 거리: **{total_distance:,.1f}km**",
        f"- 총 시간: **{format_time(total_seconds)}**",
        f"- 평균 페이스: **{format_pace(total_seconds, total_distance)}**",
    ]

    # 연도별 요약
    lines.append("\n## 연도별 요약\n")
    lines.append("| 연도 | 횟수 | 거리(km) | 시간 | 평균 페이스 | 월평균 거리 | 그래프 |")
    lines.append("|------|-----:|--------:|------|----------:|----------:|--------|")
    max_dist = max((s["distance"] for s in year_summaries), default=1)
    for s in year_summaries:
        bar = render_bar(s["distance"], max_dist)
        pace = format_pace(s["seconds"], s["distance"])
        lines.append(
            f"| {s['year']} | {s['count']} | {s['distance']:.1f} | "
            f"{format_time(s['seconds'])} | {pace} | {s['monthly_avg']} | `{bar}` |"
        )

    # 월별 추이
    lines.append("\n## 월별 추이 (전체 합산)\n")
    lines.append("| 월 | 횟수 | 거리(km) | 1회 평균(km) | 평균 페이스 | 그래프 |")
    lines.append("|:--:|-----:|--------:|-----------:|----------:|--------|")
    max_month_dist = max((v["distance"] for v in month_totals.values()), default=1)
    for m in range(1, 13):
        if m in month_totals:
            mt = month_totals[m]
            bar = render_bar(mt["distance"], max_month_dist)
            pace = format_pace(mt["seconds"], mt["distance"])
            avg_per_run = round(mt["distance"] / mt["count"], 1) if mt["count"] > 0 else 0
            lines.append(f"| {m} | {mt['count']} | {mt['distance']:.1f} | {avg_per_run} | {pace} | `{bar}` |")
        else:
            lines.append(f"| {m} | | | | | |")

    # 월별 기록 Top 5
    all_months = []
    for year, rows in data.items():
        for r in rows:
            all_months.append({
                "year": year,
                "month": r["month"],
                "count": r["count"],
                "distance": r["distance"],
                "seconds": r["seconds"],
            })

    # 평균 페이스 Top 5 (페이스가 낮을수록 빠름, 거리 0 제외)
    pace_ranked = sorted(
        [m for m in all_months if m["distance"] > 0 and m["seconds"] > 0],
        key=lambda m: m["seconds"] / m["distance"],
    )[:5]

    lines.append("\n## 평균 페이스 Top 5 (월 기준)\n")
    lines.append("| 순위 | 연도 | 월 | 거리(km) | 시간 | 평균 페이스 |")
    lines.append("|:----:|------|:--:|--------:|------|----------:|")
    for i, m in enumerate(pace_ranked, 1):
        pace = format_pace(m["seconds"], m["distance"])
        lines.append(
            f"| {i} | {m['year']} | {m['month']} | {m['distance']:.1f} | "
            f"{format_time(m['seconds'])} | {pace} |"
        )

    # 평균 거리 Top 5 (월 거리가 높은 순)
    dist_ranked = sorted(all_months, key=lambda m: m["distance"], reverse=True)[:5]

    lines.append("\n## 월간 거리 Top 5\n")
    lines.append("| 순위 | 연도 | 월 | 횟수 | 거리(km) | 평균 페이스 |")
    lines.append("|:----:|------|:--:|-----:|--------:|----------:|")
    for i, m in enumerate(dist_ranked, 1):
        pace = format_pace(m["seconds"], m["distance"])
        lines.append(
            f"| {i} | {m['year']} | {m['month']} | {m['count']} | "
            f"{m['distance']:.1f} | {pace} |"
        )

    return "\n".join(lines) + "\n"


def main():
    print("🏃 달리기 기록 로딩 중...")
    data = load_all_data()
    if not data:
        print("❌ running/ 폴더에 데이터가 없습니다.")
        return

    total_months = sum(len(rows) for rows in data.values())
    print(f"   → {len(data)}개 연도, {total_months}개월 데이터 로드됨")

    print("📊 통계 생성 중...")
    stats_md = generate_stats(data)
    STATS_PATH.write_text(stats_md, encoding="utf-8")
    print(f"✅ {STATS_PATH} 생성 완료!")


if __name__ == "__main__":
    main()
