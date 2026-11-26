import streamlit as st
import pandas as pd
import altair as alt
import folium
from streamlit_folium import st_folium

# 페이지 기본 설정
st.set_page_config(page_title="우리 동네 상권 탐색기", layout="wide")


# 1. 데이터 불러오기 함수 (필요한 열만 읽고 캐싱 처리)
@st.cache_data
def load_data(file_path):
    use_cols = [
        "상호명",
        "지점명",
        "상권업종대분류명",
        "상권업종중분류명",
        "상권업종소분류명",
        "시군구명",
        "행정동명",
        "도로명주소",
        "경도",
        "위도",
    ]
    df = pd.read_csv(file_path, usecols=use_cols, encoding="utf-8")
    # 지도 시각화를 위해 위도, 경도 결측치 제거 및 숫자형 변환
    df = df.dropna(subset=["위도", "경도"])
    df["위도"] = pd.to_numeric(df["위도"], errors="coerce")
    df["경도"] = pd.to_numeric(df["경도"], errors="coerce")
    df = df.dropna(subset=["위도", "경도"])
    return df


# 2. 조건 필터링 함수 (시군구 -> 행정동 -> 업종 대분류)
def filter_region_category(df):
    st.sidebar.header("지역 및 업종 선택")

    # 시군구 선택
    gu_list = sorted(df["시군구명"].dropna().unique().tolist())
    selected_gu = st.sidebar.selectbox("시군구 선택", gu_list)
    filtered_df = df[df["시군구명"] == selected_gu]

    # 행정동 선택 ('전체' 포함)
    dong_list = ["전체"] + sorted(
        filtered_df["행정동명"].dropna().unique().tolist()
    )
    selected_dong = st.sidebar.selectbox("행정동 선택", dong_list)
    if selected_dong != "전체":
        filtered_df = filtered_df[filtered_df["행정동명"] == selected_dong]

    # 업종 대분류 선택 ('전체' 포함)
    cat_list = ["전체"] + sorted(
        filtered_df["상권업종대분류명"].dropna().unique().tolist()
    )
    selected_cat = st.sidebar.selectbox("업종 대분류 선택", cat_list)
    if selected_cat != "전체":
        filtered_df = filtered_df[
            filtered_df["상권업종대분류명"] == selected_cat
        ]

    return filtered_df, selected_gu, selected_dong, selected_cat


# 3. 상권업종소분류명 TOP 10 가로 막대그래프 출력 함수
def show_top10_chart(df):
    st.subheader("상권업종소분류명 TOP 10")
    if df.empty:
        st.info("선택한 조건에 해당하는 데이터가 없습니다.")
        return

    top10 = df["상권업종소분류명"].value_counts().head(10).reset_index()
    top10.columns = ["상권업종소분류명", "업소수"]

    chart = (
        alt.Chart(top10)
        .mark_bar()
        .encode(
            x=alt.X("업소수:Q", title="업소 수"),
            y=alt.Y("상권업종소분류명:N", sort="-x", title="업종 소분류"),
            tooltip=["상권업종소분류명", "업소수"],
        )
        .properties(height=350)
    )
    st.altair_chart(chart, use_container_width=True)


# 4. Folium 지도 시각화 함수 (Esri.WorldStreetMap 타일 사용)
def show_folium_map(df):
    st.subheader("상권 위치 지도 (Folium)")
    if df.empty:
        st.info("지도에 표시할 데이터가 없습니다.")
        return

    # 지도 중심 좌표 설정
    center_lat = df["위도"].mean()
    center_lon = df["경도"].mean()

    # 무료 Esri.WorldStreetMap 타일 적용
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=14,
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
        attr="Esri.WorldStreetMap",
    )

    # 브라우저 렌더링 과부하 방지를 위해 최대 500개까지만 마커 표시
    max_markers = 500
    if len(df) > max_markers:
        st.caption(
            f"데이터가 많아 {max_markers}개 업소만 지도에 무작위로 표시합니다."
        )
        map_df = df.sample(n=max_markers, random_state=42)
    else:
        map_df = df

    for _, row in map_df.iterrows():
        store_name = str(row["상호명"])
        branch_name = str(row["지점명"]) if pd.notna(row["지점명"]) else ""
        popup_text = f"{store_name} {branch_name} ({row['상권업종소분류명']})"
        folium.CircleMarker(
            location=[row["위도"], row["경도"]],
            radius=5,
            color="blue",
            fill=True,
            fill_color="blue",
            fill_opacity=0.6,
            popup=folium.Popup(popup_text, max_width=250),
        ).add_to(m)

    st_folium(m, width=1000, height=500, returned_objects=[])


# 5. 브랜드 대결 기능 함수
def show_brand_battle(df):
    st.header("부산 브랜드 대결")

    # 브랜드 입력 및 음식 업종 필터 체크박스
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        brand_a = st.text_input("브랜드 A 이름", value="스타벅스")
    with col2:
        brand_b = st.text_input("브랜드 B 이름", value="메가")
    with col3:
        st.write("")
        st.write("")
        only_food = st.checkbox(
            "음식 업종만 보기 (메가박스 등 제외)", value=True
        )

    if not brand_a.strip() or not brand_b.strip():
        st.warning("두 브랜드 이름을 모두 입력해주세요.")
        return

    # 음식 업종만 보기 체크 시 필터링
    target_df = df.copy()
    if only_food:
        target_df = target_df[target_df["상권업종대분류명"] == "음식"]

    # 상호명에 각 브랜드 이름이 포함된 데이터 추출 (결측치 제외)
    df_a = target_df[
        target_df["상호명"].str.contains(brand_a, case=False, na=False)
    ].copy()
    df_a["브랜드"] = brand_a
    df_a["color"] = "#00704A"  # 브랜드 A 색상 (초록 계열)

    df_b = target_df[
        target_df["상호명"].str.contains(brand_b, case=False, na=False)
    ].copy()
    df_b["브랜드"] = brand_b
    df_b["color"] = "#FFCC00"  # 브랜드 B 색상 (노랑 계열)

    # 브랜드별 매장 수 metric 출력
    m_col1, m_col2 = st.columns(2)
    m_col1.metric(f"{brand_a} 매장 수", f"{len(df_a):,}개")
    m_col2.metric(f"{brand_b} 매장 수", f"{len(df_b):,}개")

    battle_df = pd.concat([df_a, df_b], ignore_index=True)

    if battle_df.empty:
        st.info("검색된 브랜드 매장이 없습니다.")
        return

    # 구별 매장 수 비교 Altair 막대그래프 (나란히 배치)
    st.subheader("구별 매장 수 비교")
    gu_counts = (
        battle_df.groupby(["시군구명", "브랜드"]).size().reset_index(name="매장수")
    )

    battle_chart = (
        alt.Chart(gu_counts)
        .mark_bar()
        .encode(
            x=alt.X("시군구명:N", title="시군구"),
            y=alt.Y("매장수:Q", title="매장 수"),
            color=alt.Color(
                "브랜드:N",
                scale=alt.Scale(
                    domain=[brand_a, brand_b], range=["#00704A", "#FFCC00"]
                ),
            ),
            xOffset="브랜드:N",
            tooltip=["시군구명", "브랜드", "매장수"],
        )
        .properties(height=400)
    )
    st.altair_chart(battle_chart, use_container_width=True)

    # st.map에 브랜드별로 색을 다르게 표시 (lat, lon, color 열 사용)
    st.subheader("브랜드별 매장 위치 분포 (st.map)")
    map_data = battle_df[["위도", "경도", "color"]].rename(
        columns={"위도": "lat", "경도": "lon"}
    )
    st.map(map_data, color="color")

    # 검색된 상호명 목록 확인 (오탐지 확인용)
    st.subheader("검색된 상호명 목록 확인")
    tab_a, tab_b = st.tabs([f"{brand_a} 검색 결과", f"{brand_b} 검색 결과"])
    with tab_a:
        st.write("검색된 고유 상호명:", df_a["상호명"].unique().tolist())
        st.dataframe(
            df_a[
                [
                    "상호명",
                    "지점명",
                    "상권업종대분류명",
                    "상권업종소분류명",
                    "시군구명",
                    "도로명주소",
                ]
            ],
            use_container_width=True,
        )
    with tab_b:
        st.write("검색된 고유 상호명:", df_b["상호명"].unique().tolist())
        st.dataframe(
            df_b[
                [
                    "상호명",
                    "지점명",
                    "상권업종대분류명",
                    "상권업종소분류명",
                    "시군구명",
                    "도로명주소",
                ]
            ],
            use_container_width=True,
        )


# 메인 실행 함수
def main():
    st.title("우리 동네 상권 탐색기 (부산)")

    file_path = "소상공인시장진흥공단_상가(상권)정보_부산_202609.csv"

    try:
        df = load_data(file_path)
    except FileNotFoundError:
        st.error(
            f"파일을 찾을 수 없습니다: {file_path}. 같은 폴더에 파일이 있는지 확인해주세요."
        )
        return

    # 1. 전체 업소 수 표시
    st.metric("부산 전체 업소 수", f"{len(df):,}개")
    st.divider()

    # 탭으로 기능 구분 (지역별 상권 탐색 / 브랜드 대결)
    tab1, tab2 = st.tabs(["지역 및 업종별 탐색", "브랜드 대결"])

    with tab1:
        # 2. 조건 필터링
        filtered_df, selected_gu, selected_dong, selected_cat = (
            filter_region_category(df)
        )

        # 3. 선택한 조건의 업소 수 표시
        st.subheader(
            f"선택 조건: {selected_gu} > {selected_dong} > {selected_cat}"
        )
        st.metric("조건 충족 업소 수", f"{len(filtered_df):,}개")

        # TOP 10 그래프 및 지도 배치
        col_left, col_right = st.columns([1, 1])
        with col_left:
            show_top10_chart(filtered_df)
        with col_right:
            show_folium_map(filtered_df)

        # 업소 목록 표 및 CSV 다운로드
        st.subheader("업소 목록")
        st.dataframe(filtered_df, use_container_width=True)

        csv_data = filtered_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="검색 결과 CSV 다운로드",
            data=csv_data,
            file_name=f"부산상권_{selected_gu}_{selected_dong}_{selected_cat}.csv",
            mime="text/csv",
        )

    with tab2:
        # 5. 브랜드 대결 실행
        show_brand_battle(df)


if __name__ == "__main__":
    main()