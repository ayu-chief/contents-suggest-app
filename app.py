import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

# --- 認証・準備 ---
SERVICE_ACCOUNT_INFO = st.secrets["google_service_account"]
SPREADSHEET_ID = "15cpB2PddSHA6s_dNOuPzaTshMq9yE0WPVD8dqj_TXag"
SHEET_BASE_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit#gid="

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=scopes)
gc = gspread.authorize(creds)

# --- 目次シートにgid列を追加・更新 ---
def add_gid_to_index_sheet():
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws_index = sh.worksheet("目次")
    all_values = ws_index.get_all_values()
    df = pd.DataFrame(all_values[1:], columns=all_values[0])  # 1行目はヘッダー

    # シート名→gid の辞書を作成
    sheet_name_to_gid = {ws.title: ws.id for ws in sh.worksheets()}

    # gid列がなければ追加
    if "gid" not in df.columns:
        df["gid"] = ""

    # 各行のシート名でgidを埋める
    for i, row in df.iterrows():
        sheet_name = row["シート名"]
        gid = sheet_name_to_gid.get(sheet_name, "")
        df.at[i, "gid"] = gid

    # データをGoogleシートに一括反映
    values = [df.columns.tolist()] + df.values.tolist()
    ws_index.update(f"A1:{chr(65+len(df.columns)-1)}{len(values)}", values)
    return len(df)

# --- 目次データの読込 ---
@st.cache_data
def load_index_sheet():
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet("目次")
    all_values = ws.get_all_values()
    df = pd.DataFrame(all_values[1:], columns=all_values[0])
    return df

# --- 管理者ボタン ---
with st.expander("⚡ 管理者メニュー", expanded=True):
    if st.button("目次シートにgid列を自動追加/更新"):
        n = add_gid_to_index_sheet()
        st.success(f"目次シートにgid列を追加・更新しました（{n}件）")

# --- 活動サジェストチャット ---
st.title("活動サジェストチャット")
df = load_index_sheet()

user_input = st.text_input("どんな活動を探していますか？（例：自然系、工作、料理、実験、小学生、屋外 など）")
search_btn = st.button("おすすめを表示")

if search_btn and user_input:
    # 部分一致でフィルタ
    cond = (
        df["シート名"].str.contains(user_input, na=False) |
        df["D7"].str.contains(user_input, na=False) |
        df["D15"].str.contains(user_input, na=False) |
        df["分類①"].str.contains(user_input, na=False) |
        df["分類②"].str.contains(user_input, na=False) |
        df["分類③"].str.contains(user_input, na=False)
    )
    recs = df[cond].copy()
    top3 = recs.head(3)
    others = recs.iloc[3:10]

    if not top3.empty:
        st.subheader("おすすめコンテンツ")
        for _, rec in top3.iterrows():
            st.write(f'### 活動名: {rec["シート名"]}')
            st.write(f'テーマ: {rec["D7"]}')
            # シートへのリンク
            if "gid" in rec and rec["gid"]:
                url = SHEET_BASE_URL + str(rec["gid"])
                st.markdown(
                    f'<a href="{url}" target="_blank" style="font-size:16px; color:blue; text-decoration:underline;">この活動シートを開く</a>',
                    unsafe_allow_html=True
                )
            st.write(f'実施方法: {rec["D15"]}')
            st.write("---")
        if not others.empty:
            st.subheader("その他の近いコンテンツ")
            st.write("、".join(others["シート名"].tolist()))
    else:
        st.info("条件に合うおすすめが見つかりませんでした。検索ワードを変えてみてください。")
else:
    st.write("検索欄に希望ワードを入力し、「おすすめを表示」ボタンを押してください。")
