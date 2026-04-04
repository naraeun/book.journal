#!/usr/bin/env python3
"""
알라딘 API로 책 정보 검색
사용법: python scripts/aladin_search.py "책제목" "작가"
"""

import sys
import os
import re
import json
import urllib.request
import urllib.parse

TTB_KEY = os.environ.get("ALADIN_TTB_KEY", "")


def clean_author(author: str) -> str:
    """작가명에서 역할 표기 제거 (지은이, 옮긴이, 글, 그림 등)"""
    author = re.sub(r"\s*\((지은이|옮긴이|글|그림|엮은이|사진|감수)\)", "", author)
    # 역할 표기 제거 후 남은 쉼표+공백 정리
    author = re.sub(r",\s*,", ",", author)
    author = author.strip(", ")
    return author

def search_book(title: str, author: str = "") -> dict | None:
    """알라딘 API로 책 검색"""
    query = f"{title} {author}".strip().replace("/", " ")
    params = {
        "ttbkey": TTB_KEY,
        "Query": query,
        "QueryType": "Title",
        "MaxResults": 1,
        "output": "js",
        "Version": "20131101"
    }
    
    url = "http://www.aladin.co.kr/ttb/api/ItemSearch.aspx?" + urllib.parse.urlencode(params)
    
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if data.get("item"):
                item = data["item"][0]
                return {
                    "title": item.get("title", ""),
                    "author": clean_author(item.get("author", "")),
                    "publisher": item.get("publisher", ""),
                    "category": item.get("categoryName", ""),
                    "isbn": item.get("isbn13", item.get("isbn", "")),
                    "pubDate": item.get("pubDate", ""),
                    "cover": item.get("cover", "")
                }
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
    
    return None


def get_category_short(category: str) -> str:
    """카테고리에서 주요 분류만 추출 (대분류>중분류)"""
    if not category:
        return ""
    parts = category.split(">")
    if len(parts) >= 3:
        return f"{parts[1]}>{parts[2]}"  # 예: 인문학>서양철학
    elif len(parts) >= 2:
        return parts[1]
    return category


if __name__ == "__main__":
    if not TTB_KEY:
        print("Error: ALADIN_TTB_KEY 환경변수를 설정해주세요")
        print("  export ALADIN_TTB_KEY=ttbxxxxxxxx")
        sys.exit(1)
    
    if len(sys.argv) < 2:
        print("Usage: python aladin_search.py <title> [author]")
        sys.exit(1)
    
    title = sys.argv[1]
    author = sys.argv[2] if len(sys.argv) > 2 else ""
    
    result = search_book(title, author)
    
    if result:
        print(f"제목: {result['title']}")
        print(f"저자: {result['author']}")
        print(f"출판사: {result['publisher']}")
        print(f"카테고리: {result['category']}")
        print(f"카테고리(축약): {get_category_short(result['category'])}")
        print(f"ISBN: {result['isbn']}")
    else:
        print("검색 결과 없음")
