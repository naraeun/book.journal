#!/usr/bin/env python3
"""
도서 검색 폴백 레이어 (B안)

알라딘 OpenAPI가 사용 불가일 때를 대비한 대체 검색 모듈.
  1. 카카오 책 검색 API로 제목·저자·출판사·ISBN·출간일 조회
  2. 조회된 ISBN으로 알라딘 상품페이지를 스크래핑해 카테고리 추출
  3. 카테고리 스크래핑 실패 시 카테고리는 빈 값으로 둔다 (호출측에서 직접 입력)

반환 dict 형식은 aladin_search 와 동일하게 맞춘다:
  {title, author, publisher, category, isbn, pubDate, cover}

환경변수:
  KAKAO_REST_API_KEY  카카오 개발자센터 REST API 키

사용법:
  python scripts/book_search.py "책제목"
  python scripts/book_search.py "책제목" "작가"
"""

import sys
import os
import re
import json
import html as htmlmod
import urllib.request
import urllib.parse

KAKAO_REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY", "")
KAKAO_URL = "https://dapi.kakao.com/v3/search/book"


# ─── 공통 ──────────────────────────────────────────────────────


def _fetch_html(url: str) -> str:
    """URL을 받아 알라딘 페이지 인코딩(euc-kr 우선)으로 디코드한 HTML 반환"""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=15).read()
    for enc in ("euc-kr", "cp949", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "ignore")


def _normalize_isbn(isbn_field: str) -> str:
    """카카오 isbn 필드는 'ISBN10 ISBN13' 형태 → ISBN13 우선 반환"""
    parts = [p for p in isbn_field.split() if p]
    for p in parts:
        if len(p) == 13:
            return p
    return parts[-1] if parts else ""


# ─── 카카오 책 검색 ────────────────────────────────────────────


def _kakao_request(query: str, size: int = 10) -> list[dict]:
    """카카오 책 검색 API 호출 → 원시 documents 리스트 반환"""
    if not KAKAO_REST_API_KEY:
        print("⚠️  KAKAO_REST_API_KEY 환경변수가 없습니다.", file=sys.stderr)
        return []

    params = {"query": query, "target": "title", "size": size}
    url = KAKAO_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url, headers={"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("documents", [])
    except Exception as e:
        print(f"카카오 검색 오류: {e}", file=sys.stderr)
        return []


def _kakao_to_result(doc: dict) -> dict:
    """카카오 document → 공통 result dict (카테고리는 아직 비움)"""
    authors = doc.get("authors", []) or []
    translators = doc.get("translators", []) or []
    # 기존 테이블 표기 규칙: 저자, 역자 순서로 쉼표 연결
    author = ", ".join([a for a in (authors + translators) if a])

    pub_date = doc.get("datetime", "")
    if pub_date:
        pub_date = pub_date[:10]  # YYYY-MM-DD

    return {
        "title": doc.get("title", ""),
        "author": author,
        "publisher": doc.get("publisher", ""),
        "category": "",  # 카카오는 카테고리 미제공 → 알라딘 스크래핑으로 보완
        "isbn": _normalize_isbn(doc.get("isbn", "")),
        "pubDate": pub_date,
        "cover": doc.get("thumbnail", ""),
    }


# ─── 알라딘 카테고리 스크래핑 ──────────────────────────────────


def scrape_aladin_category(isbn: str = "", title: str = "") -> str:
    """ISBN(우선) 또는 제목으로 알라딘 상품페이지를 찾아 카테고리 추출.

    반환값은 전체 분류 문자열 (예: '국내도서>예술/대중문화>미술').
    실패 시 빈 문자열.
    """
    item_id = _find_aladin_item_id(isbn, title)
    if not item_id:
        return ""
    return _scrape_category_from_product(item_id)


def _find_aladin_item_id(isbn: str = "", title: str = "") -> str:
    """알라딘 검색으로 상품 ItemId 추출. ISBN 검색을 우선 시도."""
    queries = []
    if isbn:
        queries.append(isbn)
    if title:
        queries.append(title)

    for q in queries:
        url = (
            "https://www.aladin.co.kr/search/wsearchresult.aspx?"
            "SearchTarget=Book&SearchWord=" + urllib.parse.quote(q)
        )
        try:
            html = _fetch_html(url)
        except Exception as e:
            print(f"알라딘 검색 오류: {e}", file=sys.stderr)
            continue

        # 책 제목 링크(class="bo3")에 붙은 ItemId 가 실제 도서 상품이다.
        m = re.search(
            r'ItemId=(\d+)"\s+class="bo3"', html
        )
        if m:
            return m.group(1)

    return ""


def _scrape_category_from_product(item_id: str) -> str:
    """상품페이지 breadcrumb에서 대표 분류 추출.

    실제 breadcrumb은 '&nbsp;>&nbsp;' 구분자로 연결된다. 상단 카테고리
    메뉴에도 '국내도서</a>'가 등장하므로, 이 구분자가 뒤따르는 구간만
    실제 분류로 인정한다. 책에 분류가 여러 개면 첫 번째(대표)를 쓴다.

    breadcrumb 예:
      국내도서</a>&nbsp;>&nbsp;<a href='...CID=517'>예술/대중문화</a>
      &nbsp;>&nbsp;<a href='...CID=50965'>미술</a>
      &nbsp;>&nbsp;<a href='...CID=50980...'><b>미술관/박물관/미술기행</b></a>
    """
    url = f"https://www.aladin.co.kr/shop/wproduct.aspx?ItemId={item_id}"
    try:
        html = _fetch_html(url)
    except Exception as e:
        print(f"알라딘 상품페이지 오류: {e}", file=sys.stderr)
        return ""

    # 실제 breadcrumb은 '국내도서</a>' 바로 뒤에 '&nbsp;>&nbsp;' 구분자가
    # 온다. 상단 카테고리 메뉴는 '<div'/'</h3>'/'</div>'가 뒤따르므로 제외된다.
    start = -1
    for mm in re.finditer(r"국내도서</a>\s*&nbsp;\s*(?:>|&gt;)\s*&nbsp;", html):
        start = mm.start()
        break
    if start == -1:
        return ""

    segment = html[start:start + 600]

    # 분류 체인 링크 텍스트를 순서대로 수집 (<b> 포함/미포함 모두)
    parts = re.findall(
        r"wbrowse\.aspx\?CID=\d+[^>]*>\s*(?:<b>)?\s*([^<]+?)\s*(?:</b>)?\s*</a>",
        segment,
    )
    chain = ["국내도서"] + [htmlmod.unescape(p).strip() for p in parts if p.strip()]

    # 연속 중복 제거
    cleaned = []
    for c in chain:
        if c and (not cleaned or cleaned[-1] != c):
            cleaned.append(c)

    return ">".join(cleaned)


def get_category_short(category: str) -> str:
    """전체 분류에서 주요 분류만 추출 (대분류>중분류).

    aladin_search.get_category_short 와 동일 규칙.
    """
    if not category:
        return ""
    parts = category.split(">")
    if len(parts) >= 3:
        return f"{parts[1]}>{parts[2]}"  # 예: 예술/대중문화>미술
    elif len(parts) >= 2:
        return parts[1]
    return category


# ─── 공개 API (aladin_search 호환) ─────────────────────────────


def search_book(title: str, author: str = "") -> dict | None:
    """카카오로 검색 후 알라딘 카테고리 보완. 단일 결과 반환."""
    results = search_book_multi(title, author, max_results=1)
    return results[0] if results else None


def search_book_multi(title: str, author: str = "", max_results: int = 10) -> list[dict]:
    """카카오로 복수 검색 후 각 결과에 알라딘 카테고리를 채워 반환."""
    query = f"{title} {author}".strip()
    docs = _kakao_request(query, size=max_results)

    # 작가 포함 검색 실패 시 제목만으로 재시도
    if not docs and author:
        docs = _kakao_request(title, size=max_results)

    results = []
    for doc in docs:
        r = _kakao_to_result(doc)
        # 카테고리 보완 (ISBN 우선, 없으면 제목)
        r["category"] = scrape_aladin_category(r["isbn"], r["title"])
        results.append(r)
    return results


# ─── CLI ──────────────────────────────────────────────────────


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python book_search.py <title> [author]")
        sys.exit(1)

    title = sys.argv[1]
    author = sys.argv[2] if len(sys.argv) > 2 else ""

    result = search_book(title, author)
    if result:
        print(f"제목    : {result['title']}")
        print(f"저자    : {result['author']}")
        print(f"출판사  : {result['publisher']}")
        print(f"카테고리: {result['category']}")
        print(f"축약    : {get_category_short(result['category'])}")
        print(f"ISBN    : {result['isbn']}")
        print(f"출간일  : {result['pubDate']}")
    else:
        print("검색 결과 없음")
