
# main.py
# 어제의 박스오피스 — KOBIS 공식 API를 이용한 영화 순위 대시보드

import datetime
import json
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import requests
import streamlit as st


# 1. 페이지 기본 설정
st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide",
)

# 2. KOBIS 공식 API 주소
API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)

# 3. 한국 시간 기준으로 어제 날짜 계산
# 배포 서버의 시간대가 달라도 한국 날짜를 정확하게 계산합니다.
KST = ZoneInfo("Asia/Seoul")
yesterday = datetime.datetime.now(KST).date() - datetime.timedelta(days=1)
target_dt = yesterday.strftime("%Y%m%d")


# 4. API 요청 함수
# 같은 날짜의 데이터는 1시간 동안 캐시에 저장하여 불필요한 요청을 줄입니다.
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_boxoffice(api_key: str, date_str: str) -> dict:
    """KOBIS API에서 지정한 날짜의 일별 박스오피스 정보를 가져옵니다."""

    response = requests.get(
        API_URL,
        params={
            "key": api_key,
            "targetDt": date_str,
        },
        timeout=15,
    )

    # HTTP 4xx, 5xx 오류가 발생하면 예외를 발생시킵니다.
    response.raise_for_status()

    # KOBIS는 인증키 오류도 HTTP 200으로 반환할 수 있습니다.
    # 따라서 JSON 응답 내부의 faultInfo도 별도로 검사해야 합니다.
    return response.json()


# 5. 대시보드 제목
st.title("🎬 어제의 박스오피스")
st.caption(
    f"조회 기준일: {yesterday.strftime('%Y년 %m월 %d일')} "
    "(한국 시간 기준)"
)

st.divider()


# 6. 비밀 금고에서 API 인증키 읽기
# 인증키를 코드에 직접 입력하거나 화면에 출력하지 않습니다.
try:
    api_key = st.secrets["KOBIS_KEY"]
except (KeyError, FileNotFoundError):
    st.error("🔑 KOBIS API 인증키를 찾을 수 없습니다.")
    st.markdown(
        """
        **다음 항목을 확인해 주세요.**

        1. Streamlit Cloud의 앱 설정에서 **Settings → Secrets**로 이동합니다.
        2. `KOBIS_KEY`라는 이름으로 인증키를 등록합니다.
        3. 키 이름과 값이 정확한지 확인한 뒤 앱을 다시 실행합니다.
        """
    )
    st.stop()

if not str(api_key).strip():
    st.error("🔑 KOBIS_KEY 값이 비어 있습니다.")
    st.info("Streamlit Cloud의 Settings → Secrets에서 인증키를 입력해 주세요.")
    st.stop()


# 7. API 호출 및 네트워크 오류 처리
try:
    with st.spinner("어제의 영화 순위를 불러오는 중입니다..."):
        data = fetch_boxoffice(str(api_key).strip(), target_dt)

except requests.exceptions.Timeout:
    st.error("⏱️ KOBIS API 응답 시간이 초과되었습니다.")
    st.info("잠시 후 새로고침해 주세요. 네트워크 연결과 API 서버 상태도 확인해 주세요.")
    st.stop()

except requests.exceptions.HTTPError as exc:
    status_code = (
        exc.response.status_code
        if exc.response is not None
        else "알 수 없음"
    )
    st.error(f"🌐 API 서버가 HTTP 오류를 반환했습니다. 상태 코드: {status_code}")
    st.info("KOBIS API 서버 상태와 요청 주소를 확인한 뒤 다시 시도해 주세요.")
    st.stop()

except requests.exceptions.RequestException:
    st.error("🌐 KOBIS API 서버에 연결하지 못했습니다.")
    st.info("인터넷 연결, API 주소, 서버 상태를 확인한 뒤 다시 시도해 주세요.")
    st.stop()

except (json.JSONDecodeError, ValueError):
    st.error("📄 API 응답을 JSON으로 읽을 수 없습니다.")
    st.info("KOBIS 서버의 응답 형식과 서버 상태를 확인해 주세요.")
    st.stop()


# 8. HTTP 상태 코드가 정상이어도 API 내부 오류를 확인합니다.
# 인증키 오류나 API 이용 제한 등이 faultInfo로 전달될 수 있습니다.
if not isinstance(data, dict):
    st.error("📄 API 응답의 형식이 예상과 다릅니다.")
    st.info("KOBIS API의 응답 상태를 확인한 뒤 다시 시도해 주세요.")
    st.stop()

if "faultInfo" in data:
    fault = data.get("faultInfo") or {}

    if isinstance(fault, dict):
        error_code = fault.get("errorCode", "미제공")
        error_message = fault.get("message", "오류 메시지가 없습니다.")
    else:
        error_code = "미제공"
        error_message = str(fault)

    st.error("⚠️ KOBIS API에서 오류를 반환했습니다.")
    st.write(f"**오류 코드:** {error_code}")
    st.write(f"**오류 내용:** {error_message}")
    st.info(
        "KOBIS_KEY 인증키의 유효성, API 이용 권한 및 이용 한도를 "
        "확인해 주세요."
    )
    st.stop()


# 9. 영화 목록 가져오기
boxoffice_result = data.get("boxOfficeResult")

if not isinstance(boxoffice_result, dict):
    st.error("📄 API 응답에 박스오피스 결과가 없습니다.")
    st.info("응답 구조와 KOBIS API 서버 상태를 확인해 주세요.")
    st.stop()

movies = boxoffice_result.get("dailyBoxOfficeList", [])

if not isinstance(movies, list) or len(movies) == 0:
    st.warning("📭 조회된 영화 목록이 없습니다.")
    st.info(
        "해당 날짜의 집계가 완료되지 않았거나 API 응답에 문제가 있을 수 있습니다. "
        "조회 기준일과 KOBIS의 일별 박스오피스 자료를 확인해 주세요."
    )
    st.stop()


# 10. 데이터를 표와 그래프에 사용하기 쉽게 정리합니다.
df = pd.DataFrame(movies)

# 화면에 필요한 항목이 실제 응답에 있는지 확인합니다.
required_columns = [
    "rank",
    "movieNm",
    "openDt",
    "audiCnt",
    "audiAcc",
    "scrnCnt",
]

missing_columns = [col for col in required_columns if col not in df.columns]

if missing_columns:
    st.error("📄 API 응답에 필요한 영화 정보가 일부 누락되었습니다.")
    st.write(f"누락된 항목: {', '.join(missing_columns)}")
    st.info("KOBIS API 응답 구조가 변경되었는지 확인해 주세요.")
    st.stop()

# API의 숫자는 문자열이므로 정렬과 그래프에 사용할 수 있도록 변환합니다.
numeric_columns = ["rank", "audiCnt", "audiAcc", "scrnCnt"]

for col in numeric_columns:
    df[col] = pd.to_numeric(df[col], errors="coerce")

# 필수 숫자 항목이 올바르지 않은 행은 제외합니다.
df = df.dropna(subset=["rank", "audiCnt", "audiAcc", "scrnCnt"])

if df.empty:
    st.warning("표시할 수 있는 영화 데이터가 없습니다.")
    st.info("API 응답의 숫자 항목이 올바른지 확인해 주세요.")
    st.stop()

# 숫자형 순위 기준으로 표와 지표를 정렬합니다.
df = df.sort_values("rank").reset_index(drop=True)


# 11. 1위 영화 정보 — 지표 카드 3개
top_movie = df.iloc[0]

st.subheader(f"🏆 오늘의 주인공: {top_movie['movieNm']}")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="🍿 어제 관객수",
        value=f"{int(top_movie['audiCnt']):,}명",
    )

with col2:
    st.metric(
        label="🎟️ 누적 관객수",
        value=f"{int(top_movie['audiAcc']):,}명",
    )

with col3:
    st.metric(
        label="🖥️ 스크린수",
        value=f"{int(top_movie['scrnCnt']):,}개",
    )


# 12. 전체 박스오피스 순위표
st.divider()
st.subheader("📋 어제의 전체 순위")

table = df[
    ["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]
].copy()

# 열 이름을 한국어로 바꿉니다.
table.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수",
]

# 개봉일은 YYYYMMDD 형식을 YYYY.MM.DD 형식으로 표시합니다.
table["개봉일"] = (
    table["개봉일"]
    .fillna("")
    .astype(str)
    .apply(
        lambda value: (
            f"{value[:4]}.{value[4:6]}.{value[6:8]}"
            if len(value) == 8 and value.isdigit()
            else value
        )
    )
)

# 관객수와 스크린수에 천 단위 구분 기호를 적용합니다.
for col in ["순위", "관객수", "누적관객", "스크린수"]:
    table[col] = table[col].map(lambda value: f"{int(value):,}")

st.dataframe(
    table,
    hide_index=True,
    use_container_width=True,
)


# 13. 관객수 상위 5편 막대그래프
st.divider()
st.subheader("📊 관객수 TOP 5")

top5 = (
    df.sort_values("audiCnt", ascending=False)
    .head(5)
    .sort_values("audiCnt", ascending=True)
    .copy()
)

# 막대 끝에 관객수를 표시하기 위한 문자열을 만듭니다.
top5["관객수 표시"] = top5["audiCnt"].map(lambda value: f"{int(value):,}명")

fig = px.bar(
    top5,
    x="audiCnt",
    y="movieNm",
    orientation="h",
    text="관객수 표시",
    labels={
        "audiCnt": "관객수(명)",
        "movieNm": "영화명",
    },
)

fig.update_traces(
    textposition="outside",
    cliponaxis=False,
)

fig.update_layout(
    xaxis=dict(
        tickformat=",",
        title="관객수(명)",
    ),
    yaxis_title="영화명",
    showlegend=False,
    margin=dict(l=10, r=70, t=20, b=20),
)

st.plotly_chart(fig, use_container_width=True)

# 14. 데이터 출처 표시
st.caption("데이터 출처: 영화진흥위원회(KOBIS) 영화관입장권통합전산망 오픈 API")
