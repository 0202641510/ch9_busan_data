import math
import pandas as pd
import requests
import streamlit as st

# Home.py에서 페이지 설정을 실행하므로 아래 줄은 주석 처리합니다.
# st.set_page_config(page_title="부산 맛집 지도", layout="wide")


# 1. API 호출 및 전체 데이터 수집 함수
def fetch_all_restaurants(service_key):
    url = "https://apis.data.go.kr/6260000/FoodService/getFoodKr"
    page_no = 1
    num_of_rows = 100
    all_items = []

    # 진행 상황을 보여주기 위한 상태 표시줄
    progress_text = st.empty()
    progress_bar = st.progress(0)

    while True:
        params = {
            "serviceKey": service_key,
            "pageNo": page_no,
            "numOfRows": num_of_rows,
            "resultType": "json",
        }

        try:
            response = requests.get(url, params=params, timeout=15)
        except requests.exceptions.RequestException as e:
            progress_text.empty()
            progress_bar.empty()
            st.error(f"네트워크 연결 오류가 발생했습니다: {e}")
            return None

        # JSON 파싱 시도 (인증키 오류 등으로 XML이나 HTML이 반환되는 경우 처리)
        try:
            data = response.json()
        except ValueError:
            progress_text.empty()
            progress_bar.empty()
            st.error(
                "API 응답이 JSON 형식이 아닙니다. 인증키가 올바른지 확인해주세요."
            )
            with st.expander("원본 응답 내용 확인"):
                st.text(response.text[:500])
            return None

        # 응답 구조 및 header code 확인
        body = data.get("getFoodKr")
        if not body:
            progress_text.empty()
            progress_bar.empty()
            st.error(
                "예상하지 못한 응답 구조입니다. 인증키 또는 요청 주소를 확인해주세요."
            )
            return None

        header = body.get("header", {})
        code = header.get("code")
        if code != "00":
            progress_text.empty()
            progress_bar.empty()
            msg = header.get("message", "알 수 없는 오류")
            st.error(f"API 오류가 발생했습니다. (코드: {code}, 메시지: {msg})")
            return None

        # 데이터 추출 및 누적
        total_count = int(body.get("totalCount", 0))
        items = body.get("item", [])

        if not items:
            break

        all_items.extend(items)

        # 전체 페이지 수 계산 및 진행률 업데이트
        total_pages = max(1, math.ceil(total_count / num_of_rows))
        progress_text.text(
            f"데이터 불러오는 중... ({len(all_items)} / {total_count}건)"
        )
        progress_bar.progress(min(page_no / total_pages, 1.0))

        # 모든 데이터를 다 가져왔으면 반복 종료
        if len(all_items) >= total_count or page_no >= total_pages:
            break

        page_no += 1

    progress_text.empty()
    progress_bar.empty()

    if not all_items:
        st.warning("불러온 맛집 데이터가 없습니다.")
        return pd.DataFrame()

    # 데이터프레임 변환 및 한글 열 이름으로 정리
    df = pd.DataFrame(all_items)
    column_map = {
        "MAIN_TITLE": "가게명",
        "GUGUN_NM": "구군",
        "LAT": "위도",
        "LNG": "경도",
        "RPRSNTV_MENU": "대표메뉴",
        "USAGE_DAY_WEEK_AND_TIME": "운영시간",
        "MAIN_IMG_THUMB": "사진URL",
        "ITEMCNTNTS": "소개",
        "ADDR1": "주소",
        "CNTCT_TEL": "전화번호",
    }

    # 응답에 존재하는 열만 선택하여 이름 변경
    available_cols = [col for col in column_map.keys() if col in df.columns]
    df = df[available_cols].rename(columns=column_map)

    # 지도에 표시하기 위해 위도, 경도를 숫자로 변환
    if "위도" in df.columns and "경도" in df.columns:
        df["위도"] = pd.to_numeric(df["위도"], errors="coerce")
        df["경도"] = pd.to_numeric(df["경도"], errors="coerce")

    # 결측치(NaN)를 빈 문자열로 정리 (문자열 열만 대상)
    text_cols = [col for col in df.columns if col not in ["위도", "경도"]]
    for col in text_cols:
        df[col] = df[col].fillna("").astype(str).str.strip()

    return df


# 2. 구군 및 검색어 필터링 함수
def filter_restaurants(df):
    st.subheader("맛집 검색 및 필터")
    col1, col2 = st.columns([1, 2])

    with col1:
        gugun_list = ["전체"] + sorted(
            [g for g in df["구군"].unique().tolist() if g != ""]
        )
        selected_gugun = st.selectbox("구군 선택", gugun_list)

    with col2:
        keyword = st.text_input(
            "검색어 입력 (가게명, 대표메뉴, 소개)",
            placeholder="예: 돼지국밥, 밀면, 해운대",
        )

    filtered_df = df.copy()

    # 구군 필터 적용
    if selected_gugun != "전체":
        filtered_df = filtered_df[filtered_df["구군"] == selected_gugun]

    # 검색어 필터 적용
    if keyword.strip():
        kw = keyword.strip()
        cond_title = filtered_df["가게명"].str.contains(
            kw, case=False, na=False
        )
        cond_menu = filtered_df["대표메뉴"].str.contains(
            kw, case=False, na=False
        )
        cond_desc = filtered_df["소개"].str.contains(kw, case=False, na=False)
        filtered_df = filtered_df[cond_title | cond_menu | cond_desc]

    return filtered_df


# 3. 지도 시각화 함수 (st.map)
def show_map(df):
    st.subheader("맛집 위치 지도")
    if "위도" not in df.columns or "경도" not in df.columns:
        st.info("위도와 경도 정보가 없어 지도를 표시할 수 없습니다.")
        return

    map_df = df.dropna(subset=["위도", "경도"]).copy()
    # 부산 지역 범위를 크게 벗어나는 이상치 좌표 제외
    map_df = map_df[(map_df["위도"] > 34.0) & (map_df["경도"] > 128.0)]

    if map_df.empty:
        st.info("지도에 표시할 유효한 위치 정보가 없습니다.")
        return

    map_df = map_df.rename(columns={"위도": "lat", "경도": "lon"})
    st.map(map_df[["lat", "lon"]])


# 4. 사진 카드 6개 (3열 x 2행) 출력 함수
def show_photo_cards(df):
    st.subheader("추천 맛집 사진 카드 (상위 6곳)")
    if df.empty:
        st.info("표시할 맛집이 없습니다.")
        return

    top6_df = df.head(6).reset_index(drop=True)

    # 3열씩 2줄로 배치
    for row_idx in range(0, len(top6_df), 3):
        cols = st.columns(3)
        for col_idx in range(3):
            item_idx = row_idx + col_idx
            if item_idx >= len(top6_df):
                break

            row = top6_df.iloc[item_idx]
            with cols[col_idx]:
                with st.container(border=True):
                    img_url = row.get("사진URL", "")
                    if img_url.startswith("http"):
                        st.image(img_url, use_container_width=True)
                    else:
                        st.caption("등록된 사진이 없습니다.")

                    st.markdown(f"**{row.get('가게명', '이름 없음')}**")
                    st.caption(f"지역: {row.get('구군', '-')}")
                    st.write(f"대표메뉴: {row.get('대표메뉴', '-')}")
                    st.write(f"운영시간: {row.get('운영시간', '-')}")

                    # 소개 글이 길 경우 80자까지만 요약 표시
                    desc = row.get("소개", "")
                    if len(desc) > 80:
                        desc = desc[:80] + "..."
                    if desc:
                        st.caption(desc)


# 5. 전체 목록 표 출력 함수
def show_table(df):
    st.subheader("맛집 목록 표")
    if df.empty:
        st.info("조건에 맞는 맛집이 없습니다.")
        return

    # 표에서 보기 좋도록 사진URL과 좌표 열은 제외한 목록 구성
    display_cols = [
        col
        for col in [
            "가게명",
            "구군",
            "대표메뉴",
            "운영시간",
            "주소",
            "전화번호",
            "소개",
        ]
        if col in df.columns
    ]
    st.dataframe(df[display_cols], use_container_width=True, hide_index=True)


# 메인 실행 함수
def main():
    st.title("부산 맛집 지도")

    # session_state 초기화
    if "food_df" not in st.session_state:
        st.session_state["food_df"] = None

    # 사이드바에서 인증키 입력 및 데이터 불러오기 버튼 배치
    st.sidebar.header("API 설정")
    service_key = st.sidebar.text_input(
        "공공데이터포털 인증키 (Decoding 권장)",
        type="password",
        help="공공데이터포털에서 발급받은 일반 인증키를 입력하세요.",
    )

    if st.sidebar.button("부산 맛집 데이터 불러오기", type="primary"):
        if not service_key.strip():
            st.sidebar.warning("인증키를 먼저 입력해주세요.")
        else:
            result_df = fetch_all_restaurants(service_key.strip())
            if result_df is not None:
                st.session_state["food_df"] = result_df
                st.sidebar.success(f"총 {len(result_df)}건 불러오기 완료")

    # session_state에 저장된 데이터가 있을 때만 화면 출력
    df = st.session_state["food_df"]
    if df is None:
        st.info(
            "왼쪽 사이드바에 인증키를 입력하고 '부산 맛집 데이터 불러오기' 버튼을 눌러주세요."
        )
        return

    if df.empty:
        return

    st.metric("불러온 전체 맛집 수", f"{len(df):,}곳")
    st.divider()

    # 필터링 적용
    filtered_df = filter_restaurants(df)
    st.write(f"검색 결과: 총 **{len(filtered_df):,}곳**")

    # 지도, 사진 카드, 목록 표 순서로 출력
    show_map(filtered_df)
    st.divider()
    show_photo_cards(filtered_df)
    st.divider()
    show_table(filtered_df)


if __name__ == "__main__":
    main()