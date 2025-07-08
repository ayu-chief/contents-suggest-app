import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

# --- Google Sheets認証情報（Secretsに格納推奨） ---
SERVICE_ACCOUNT_INFO = st.secrets["google_service_account"]
SPREADSHEET_ID = "15cpB2PddSHA6s_dNOuPzaTshMq9yE0WPVD8dqj_TXag"  # スプレッドシートID

# --- gspread認証 ---
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=scopes)
gc = gspread.authorize(creds)

# --- 「目次」シートの読み込み ---
@st.cache_data
def load_index_sheet():
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet("目次")
    data = ws.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])  # 1行目をヘッダー扱い
    return df

df = load_index_sheet()
st.write("【目次シートの内容プレビュー】")
st.dataframe(df.head())

# --- サジェスト検索UI ---
st.title("おすすめ活動サジェスト（目次シート参照）")
user_input = st.text_input("どんな活動を探していますか？（例：自然系、校外学習、調理、小学生向け など）")
search_btn = st.button("おすすめを表示")

if search_btn and user_input:
    # 検索対象カラム（必要に応じて拡張/変更）
    search_cols = [col for col in df.columns if "分類" in col or "シート名" in col or "D7" in col or "D17" in col]
    cond = df[search_cols].apply(lambda x: user_input in str(x.values), axis=1)
    recs = df[cond]

    top3 = recs.head(3)
    others = recs.iloc[3:10]

    if not top3.empty:
        st.subheader("おすすめコンテンツ")
        for _, rec in top3.iterrows():
            st.write(f'### {rec["シート名"]}' if "シート名" in rec else "")
            for col in df.columns:
                if "分類" in col and pd.notna(rec[col]):
                    st.write(f'{col}: {rec[col]}')
            if "D7" in rec: st.write(f'D7: {rec["D7"]}')
            if "D17" in rec: st.write(f'D17: {rec["D17"]}')
            st.write("---")
        if not others.empty:
            st.subheader("その他の近いコンテンツ")
            st.write("、".join(others["シート名"].tolist()))
    else:
        st.info("条件に合うおすすめが見つかりませんでした。検索ワードを変えてみてください。")
else:
    st.write("上の検索欄に希望を入力して「おすすめを表示」ボタンを押してください。")
