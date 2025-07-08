import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

SERVICE_ACCOUNT_INFO = st.secrets["google_service_account"]
SPREADSHEET_ID = "15cpB2PddSHA6s_dNOuPzaTshMq9yE0WPVD8dqj_TXag"
SHEET_BASE_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit#gid="

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=scopes)
gc = gspread.authorize(creds)

@st.cache_data
def load_index_sheet():
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet("目次")
    data = ws.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    if "gid" not in df.columns:
        sheet_map = {ws.title: ws.id for ws in sh.worksheets()}
        df["gid"] = df["シート名"].map(sheet_map)
    return df

df = load_index_sheet()

st.title("活動サジェストチャット")
st.write("どんな活動を探していますか？（例：自然系、工作、料理、実験、小学生、屋外 など）")

# --- エンター押下でもボタンでも検索実行 ---
if "search_flag" not in st.session_state:
    st.session_state.search_flag = False

def run_search():
    st.session_state.search_flag = True

user_input = st.text_input(
    "キーワードを入力",
    key="search_input",
    on_change=run_search
)
search_btn = st.button("おすすめを表示", on_click=run_search)

if st.session_state.search_flag and user_input:
    st.session_state.search_flag = False  # 検索のたびにフラグリセット

    cond = (
        df["D7"].str.contains(user_input, na=False) |
        df["D17"].str.contains(user_input, na=False) |
        df["シート名"].str.contains(user_input, na=False)
    )
    for col in df.columns:
        if "分類" in col:
            cond |= df[col].str.contains(user_input, na=False)
    results = df[cond]
    top3 = results.head(3)
    others = results.iloc[3:10]

    if not top3.empty:
        st.subheader("おすすめコンテンツ")
        for _, rec in top3.iterrows():
            # 活動名
            st.write(f'### 活動名: {rec["シート名"]}' if "シート名" in rec else "")
            # テーマ＋改行＋リンク
            if "D7" in rec:
                sheet_url = SHEET_BASE_URL + str(rec["gid"]) if "gid" in rec and pd.notna(rec["gid"]) else ""
                if sheet_url:
                    st.markdown(
                        f'テーマ：{rec["D7"]}<br>'
                        f'[この活動のシートを開く]({sheet_url})',
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(f'テーマ：{rec["D7"]}<br>', unsafe_allow_html=True)
            # 参加者の反応＋改行
            if "D17" in rec:
                st.markdown(f'参加者の反応：{rec["D17"]}<br>', unsafe_allow_html=True)
            st.write("---")
        if not others.empty:
            st.subheader("その他の近いコンテンツ")
            # 活動名（リンク付き）で出す
            links = []
            for _, rec in others.iterrows():
                if "gid" in rec and pd.notna(rec["gid"]):
                    sheet_url = SHEET_BASE_URL + str(rec["gid"])
                    links.append(f'[{rec["シート名"]}]({sheet_url})')
                else:
                    links.append(rec["シート名"])
            st.markdown("、".join(links), unsafe_allow_html=True)
    else:
        st.info("条件に合うおすすめが見つかりませんでした。検索ワードを変えてみてください。")
else:
    st.write("上の検索欄に希望を入力して「おすすめを表示」ボタンを押してください。")
