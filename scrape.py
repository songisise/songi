# 산림조합중앙회 송이 공판현황 수집기
# 자료 출처: 산림조합중앙회 (https://m.nfcf.or.kr)

import json, os, re, time
from datetime import date, timedelta
import requests
from bs4 import BeautifulSoup

BASE = "https://m.nfcf.or.kr/forest/user.tdf"
HEADERS = {"User-Agent": "Mozilla/5.0 (songi-price-viewer; contact via github.com/songisise/songi)"}
OUT_DIR = "docs/data"

GRADES = ["1등품", "2등품", "생장정지품", "개산품", "등외품", "혼합품"]


def to_num(text):
    """'1,234.56kg' 또는 '543,783원' 에서 숫자만 뽑아낸다."""
    if not text:
        return 0.0
    cleaned = re.sub(r"[^0-9.]", "", text)
    if cleaned in ("", "."):
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def fetch_day(day):
    """하루치 페이지를 받아서 지역별 등급 자료로 정리한다."""
    params = {
        "a": "user.songi.SongiApp",
        "c": "1003",
        "sply_date": day.strftime("%Y%m%d"),
        "pmsh_item_c": "01",
        "mc": "MOB_CST01",
    }
    res = requests.get(BASE, params=params, headers=HEADERS, timeout=20)
    res.encoding = res.apparent_encoding
    soup = BeautifulSoup(res.text, "html.parser")

    regions = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue

        # 표 바로 위에 있는 지역 이름을 찾는다 (전체 / 강원 홍천 / 경북 울진 ...)
        name = ""
        node = table.find_previous(string=re.compile(r"\S"))
        hops = 0
        while node is not None and hops < 12:
            text = str(node).strip()
            if text and "단가는" not in text and len(text) < 20:
                name = text
                break
            node = node.find_previous(string=re.compile(r"\S"))
            hops += 1

        grades, total_kg, total_amt = {}, 0.0, 0.0
        for row in rows:
            cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
            if len(cells) < 2:
                continue
            label = cells[0]
            if label in GRADES and len(cells) >= 3:
                grades[label] = {"kg": to_num(cells[1]), "price": to_num(cells[2])}
            elif "kg" in cells[1] and "원" in (cells[2] if len(cells) > 2 else ""):
                total_kg = to_num(cells[1])
                total_amt = to_num(cells[2])

        if grades:
            regions.append({
                "name": name or "전체",
                "grades": grades,
                "total_kg": total_kg,
                "total_amt": total_amt,
            })

    if not regions:
        return None
    return {"date": day.isoformat(), "regions": regions}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # 올해 9월 1일부터 오늘까지, 그리고 지난 5년의 가을을 훑는다
    today = date.today()
    targets = []
    for year in range(today.year - 5, today.year + 1):
        start = date(year, 9, 1)
        end = min(date(year, 11, 30), today)
        day = start
        while day <= end:
            targets.append(day)
            day += timedelta(days=1)

    index = []
    for day in targets:
        path = os.path.join(OUT_DIR, f"{day.isoformat()}.json")
        recent = (today - day).days <= 10

        # 이미 받아둔 날은 건너뛴다. 단 최근 열흘은 수정될 수 있어 다시 받는다.
        if os.path.exists(path) and not recent:
            index.append(day.isoformat())
            continue

        try:
            data = fetch_day(day)
        except Exception as err:
            print(f"{day} 실패: {err}")
            continue

        if data:
            with open(path, "w", encoding="utf-8") as fp:
                json.dump(data, fp, ensure_ascii=False, indent=1)
            index.append(day.isoformat())
            print(f"{day} 저장 완료 ({len(data['regions'])}개 지역)")
        else:
            print(f"{day} 공판 없음")

        time.sleep(0.6)  # 원본 사이트에 부담 주지 않도록 천천히

    index = sorted(set(index), reverse=True)
    with open(os.path.join(OUT_DIR, "index.json"), "w", encoding="utf-8") as fp:
        json.dump({"dates": index, "updated": today.isoformat()}, fp, ensure_ascii=False, indent=1)
    print(f"\n총 {len(index)}일치 보관 중")


if __name__ == "__main__":
    main()
