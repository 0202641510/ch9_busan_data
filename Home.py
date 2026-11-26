import importlib.util
from pathlib import Path
import streamlit as st

# 페이지 기본 설정 (전체 앱에서 한 번만 실행)
st.set_page_config(page_title="부산 데이터 분석 실습", layout="wide")


# 파일 경로를 직접 찾아 모듈을 불러오고 실행하는 함수
def run_page_module(filename):
    base_dir = Path(__file__).parent
    candidates = [
        base_dir / filename,
        base_dir / "pages" / filename,
    ]

    for path in candidates:
        if path.exists():
            spec = importlib.util.spec_from_file_location(path.stem, str(path))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # 파일 안에 main() 함수가 정의되어 있으면 실행하고, 없으면 불러올 때 이미 실행됨
            if hasattr(module, "main"):
                module.main()
            return

    st.error(
        f"'{filename}' 파일을 찾을 수 없습니다. '{base_dir}' 폴더 안에 파일 이름과 확장자(.py)가 정확히 일치하는지 확인해주세요."
    )


# 홈 화면 안내 함수
def show_home():
    st.title("부산 공공데이터 분석 실습")
    st.write("왼쪽 사이드바에서 실행할 실습 프로그램을 선택해주세요.")
    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.subheader("1. 부산 상권 탐색기")
            st.write("- 부산 상가(상권)정보 CSV 데이터 분석")
            st.write("- 구, 동, 업종별 필터링 및 TOP 10 차트")
            st.write("- Folium 지도 시각화 및 브랜드 대결")

    with col2:
        with st.container(border=True):
            st.subheader("2. 부산 맛집 지도")
            st.write("- 부산 맛집 OPEN API 실시간 연동")
            st.write("- 구군 및 키워드(가게, 메뉴, 소개) 검색")
            st.write("- 위치 지도, 사진 카드, 목록 표 출력")


# 메인 실행 함수
def main():
    st.sidebar.title("실습 메뉴")
    menu = st.sidebar.radio(
        "이동할 화면을 선택하세요",
        ["홈", "1. 부산 상권 탐색기", "2. 부산 맛집 지도"],
    )
    st.sidebar.divider()

    if menu == "홈":
        show_home()
    elif menu == "1. 부산 상권 탐색기":
        run_page_module("1_부산_상권_탐색기.py")
    elif menu == "2. 부산 맛집 지도":
        run_page_module("2_부산_맛집_지도.py")


if __name__ == "__main__":
    main()