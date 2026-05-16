# 작업 노트
- Claude, Gemini, KIRO & 수동 작업

### 프로젝트 시작
- 2011년부터 관리해온 책 목록을 GitHub repo에 추가 
- repository: https://github.com/naraeun/book.journal

### 구조
- 연도별 md 파일은 `books/` 폴더에 보관
- 컬럼: `| 월 | 번호 | 제목 | 작가 | 연번호 | 카테고리 | 리뷰 | 블로그 |`
- 리뷰 파일명은 번호로 관리 (예: `reviews/2026/3156.md`)
- 다독 작가(10권 이상)별 페이지는 `authors/` 폴더에 자동 생성
- 연도별 기억에 남는 책은 `picks/` 폴더에 보관 (예: `picks/2025.md`)
- 주제별 큐레이션 목록은 `topics/` 폴더에 보관 (예: `topics/글쓰기.md`, `topics/독서.md`)
    - 책 리뷰 생성 시 `create_review.py`에서 topic 추가 여부를 함께 선택 가능
- 음악회 목록은 `music/concerts.md`, 앨범 목록은 `music/albums.md`에 보관
    - 리뷰 파일은 `reviews/music/concerts/YYYY-MM-DD.md`, `reviews/music/albums/아티스트-앨범명.md`
- 웹툰 목록은 `webtoon/webtoon.md`에 보관
    - 리뷰 파일은 `reviews/webtoon/작품명.md`
- 드라마/라디오 극장 목록은 `drama/` 폴더에 보관
    - KBS 라디오 극장: `drama/radio_theater.md`, 리뷰 파일은 `reviews/drama/radio_theater/`
    - TV/OTT 드라마: `drama/drama.md`, 리뷰 파일은 `reviews/drama/drama/`
- EBS 위대한 수업 목록은 `greatminds/greatminds.md`에 보관
    - 리뷰 파일은 `reviews/greatminds/`
- 영화 목록은 `movie/movie.md`에 보관
    - 리뷰 파일은 `reviews/movie/`
- 연극/뮤지컬 목록은 `theater/theater.md`에 보관
    - 리뷰 파일은 `reviews/theater/{날짜}.md`
- 영상(강연, 유튜브, 다큐 등) 목록은 `video/video.md`에 보관
    - 리뷰 파일은 `reviews/video/`
    - 파일명은 제목 기반 (예: `reviews/video/노벨문학상_강연_빛과_실.md`)

### 카테고리
- 알라딘 API에서 조회 (대분류>중분류)
    - 검색 순서 (fallback):
        1. 제목+작가
        2. 제목+첫번째 작가만 (여러 저자인 경우)
        3. 제목만
        4. 제목 끝 숫자 제거 후 검색 (시리즈물)
- 알라딘에 없는 책(주로 ebook)은 yes24 수동 검색
- 독서 목록에 포함된 웹툰 중에 단행본으로 나오지 않은 경우 `웹툰`으로 분류
    - 2025년 2월부터 본 웹툰은 독서 목록으로 포함하지 않고 별도로 구성
- 밀리의 서재에만 있는 책들
    - 알라딘, yes24에서 검색 안되는 도서
    - 밀리 오리지널 콘텐츠는 `밀리 오리지널`로 분류
    - 밀리의 서재 책 설명 카테고리 항목을 `밀리>(카테고리)`로 분류해서 추가
- 카테고리 수동 수정 이력
    - #429 박시백의 조선왕조실록 2: `전집/중고전집>초등(1-3)저학년` → `역사>조선사`
   

### 스크립트
- `scripts/aladin_search.py` — 알라딘 책 검색
- `scripts/analyze.py` — 전체 통계 생성 (연도별 독서량, 카테고리, 작가, 연동률)
- `scripts/create_review.py` — 리뷰 md 생성 + books 테이블 자동 연동
- `scripts/generate_authors.py` — 다독 작가(10권 이상)별 md 파일 자동 생성 (`authors/`)
- `scripts/generate_cast.py` — 라디오 극장 성우 인덱스 자동 생성 (`drama/radio_theater_cast.md`)
- `scripts/migrate_columns.py` — 기존 md 파일에 리뷰/블로그 컬럼 일괄 추가
- GitHub Actions로 `books/` 변경 시 통계 + 작가별 페이지 자동 갱신

### picks 포맷 규칙

`picks/YYYY.md` 파일 작성 시 아래 포맷을 따른다.

**파일 구조:**
```
# YYYY년 기억에 남는 책

(서두 — 한 해 회고, 읽은 권수 등 자유 서술)

---

## 제목 — 저자
\#번호 또는 [#번호](../reviews/YYYY/번호.md)

한줄 감상평
> "인용문"

---

(반복)
```

**규칙:**
- 각 책은 `## 제목 — 저자` (h2 헤더, em dash `—` 사용)
- 헤더 바로 아래에 번호 표기
  - 리뷰 파일이 있으면: `[#번호](../reviews/YYYY/번호.md)` (링크)
  - 리뷰 파일이 없으면: `\#번호` (이스케이프)
- 번호는 `books/YYYY.md` 테이블의 번호 컬럼에서 확인
- 번호 아래 빈 줄 후 감상평 서술
- 인용문은 `>` 블록쿼트 사용
- 항목 사이는 `---` 구분선으로 분리
- 인용문 없이 감상평만 있는 항목도 허용

### 앞으로 해야 할 것
- 블로그 본문 크롤링 자동화 검토
- 리뷰 템플릿 필드 추가 검토 (평점, 태그 등)
- 기존 블로그 글 일괄 전환

