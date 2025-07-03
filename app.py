import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import openai

# OpenAI APIキーはSecretsから
OPENAI_API_KEY = st.secrets["openai_api_key"]

# Google Sheets認証情報もSecretsから
SERVICE_ACCOUNT_INFO = st.secrets["google_service_account"]  # Secrets名は後述
SPREADSHEET_ID = "1PFDBuFuqxC4OWMCPjErP8uYYRovE55t-0oWsXNMCMqc"
SHEET_BASE_URL = f"https://docs.google.com/spreadsheets/d/15cpB2PddSHA6s_dNOuPzaTshMq9yE0WPVD8dqj_TXag/edit#gid="

# 認証
scopes = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_FILE, scopes=scopes)
gc = gspread.authorize(creds)

# 全シートのデータ取得
@st.cache_data
def load_all_contents():
    sh = gc.open_by_key(SPREADSHEET_ID)
    sheets = sh.worksheets()
    all_contents = []
    for ws in sheets:
        try:
            df = pd.DataFrame(ws.get_all_records())
            if len(df) == 0:
                continue
            df["シート名"] = ws.title
            df["gid"] = ws.id
            all_contents.append(df)
        except Exception as e:
            continue
    if all_contents:
        return pd.concat(all_contents, ignore_index=True)
    else:
        return pd.DataFrame()

contents_df = load_all_contents()

# テーマ列（例：B7セル）の取得補助関数
def get_b7_value(ws):
    try:
        value = ws.acell("B7").value
        return value if value else ""
    except Exception:
        return ""

# AIで2層カテゴリー推定（OpenAI APIを使用）
def categorize_content(content_name, theme):
    prompt = f"""
あなたは学校教育のアクティビティを分類するプロです。
次の「コンテンツ名」と「テーマ」から、できるだけ一般的な2階層のカテゴリーを日本語で推定してください。
例: 「英語活動」→「外国語活動 > コミュニケーション」、「理科実験」→「理科 > 実験」
出力例：第一階層 > 第二階層
コンテンツ名: {content_name}
テーマ: {theme}
カテゴリー: 
"""
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role":"user", "content":prompt}],
        temperature=0.1,
        api_key=OPENAI_API_KEY
    )
    res = response.choices[0].message.content.strip()
    if ">" in res:
        cat1, cat2 = [x.strip() for x in res.split(">", 1)]
    elif "＞" in res:
        cat1, cat2 = [x.strip() for x in res.split("＞", 1)]
    else:
        cat1, cat2 = res, ""
    return cat1, cat2

# UIここから
st.title("おすすめ活動サジェストAI")

user_input = st.text_input("どんな活動を探していますか？（例：自然系、小学生向け、運動など）")
search_btn = st.button("おすすめを表示")

if search_btn and user_input:
    # 各コンテンツごとにカテゴリー推定＋テーマ抽出
    recs = []
    for i, row in contents_df.iterrows():
        # 各ワークシートのB7セル（テーマ）取得
        ws = gc.open_by_key(SPREADSHEET_ID).worksheet(row["シート名"])
        theme = get_b7_value(ws)
        cat1, cat2 = categorize_content(row["シート名"], theme)
        # 検索キーワードの部分一致でフィルタ
        cond = (user_input in cat1) or (user_input in cat2) or (user_input in theme) or (user_input in str(row["シート名"])) or (user_input in str(row.get("説明", "")))
        if cond:
            recs.append({
                "コンテンツ名": row["シート名"],
                "説明": row.get("説明", ""),
                "gid": row["gid"],
                "カテゴリー": f"{cat1} > {cat2}",
                "テーマ": theme
            })

    # おすすめ上位3件
    top3 = recs[:3]
    others = recs[3:10]

    if top3:
        st.subheader("おすすめコンテンツ")
        for rec in top3:
            st.write(f'### {rec["コンテンツ名"]}')
            st.write(f'カテゴリー: {rec["カテゴリー"]}')
            st.write(f'テーマ: {rec["テーマ"]}')
            st.write(f'説明: {rec["説明"] if rec["説明"] else "（説明なし）"}')
            sheet_url = SHEET_BASE_URL + str(rec["gid"])
            st.markdown(f'<a href="{sheet_url}" target="_blank" style="font-size:18px; color:blue; text-decoration:underline;">詳細を見る</a>', unsafe_allow_html=True)
            st.write("---")
        if others:
            st.subheader("その他の近いコンテンツ")
            st.write("、".join([rec["コンテンツ名"] for rec in others]))
    else:
        st.info("条件に合うおすすめが見つかりませんでした。検索ワードを変えてみてください。")

else:
    st.write("上の検索欄に希望を入力して「おすすめを表示」ボタンを押してください。")

