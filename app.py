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

# 検索フォーム
with st.form(key="search_form"):
    user_input = st.text_input("キーワードを入力", "")
    submit = st.form_submit_button("おすすめを表示")

if submit and user_input:
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
    others = results.iloc[3:15]  # 12件

    if not top3.empty:
        st.subheader("おすすめコンテンツ")
        for _, rec in top3.iterrows():
            # 活動名（リンク付き）
            if "シート名" in rec and "gid" in rec:
                url = SHEET_BASE_URL + str(rec["gid"])
                st.markdown(f'### 活動名：[{rec["シート名"]}]({url})')
            # テーマ＋改行
            if "D7" in rec:
                st.write(f'テーマ：{rec["D7"]}\n')
            # 参加者の反応＋改行
            if "D17" in rec:
                st.write(f'参加者の反応：{rec["D17"]}\n')
            st.write("---")
        st.subheader("その他の近いコンテンツ")
        if not others.empty:
            links = [
                f'[{rec["シート名"]}]({SHEET_BASE_URL + str(rec["gid"])})'
                for _, rec in others.iterrows()
            ]
            st.write("、".join(links))
        else:
            st.write("その他の近いコンテンツは見つかりませんでした。")
    else:
        st.info("条件に合うおすすめが見つかりませんでした。検索ワードを変えてみてください。")
else:
    st.write("上の検索欄に希望を入力して「おすすめを表示」ボタンを押してください。")
