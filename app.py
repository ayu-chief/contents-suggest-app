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

# ---------------------------
# 目次シートを読み込む関数　←★これを必ず最初に定義！
# ---------------------------
@st.cache_data
def load_index_sheet():
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet("目次")
    data = ws.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    # gid列がなければ追加（自動付与）
    if "gid" not in df.columns:
        sheet_map = {ws.title: ws.id for ws in sh.worksheets()}
        df["gid"] = df["シート名"].map(sheet_map)
    return df

# ---------------------------
# 目次シートを自動同期（新シート追加）
# ---------------------------
def sync_index_sheet():
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet("目次")
    data = ws.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    already = set(df["シート名"])
    all_ws = [w for w in sh.worksheets() if w.title != "目次"]
    add_count = 0
    for w in all_ws:
        if w.title not in already:
            # D7/D17セル内容を取得して転記
            d7 = ""
            d17 = ""
            try:
                d7 = w.acell("D7").value or ""
            except Exception:
                pass
            try:
                d17 = w.acell("D17").value or ""
            except Exception:
                pass
            num_cols = len(df.columns)
            new_row = [w.title, d7, d17] + [""] * (num_cols - 4) + [w.id]
            ws.append_row(new_row, value_input_option="USER_ENTERED")
            add_count += 1
    return add_count

# ---------------------------
# 目次の分類を各シートのM/N列に転記
# ---------------------------
def write_categories_to_sheets():
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws_index = sh.worksheet("目次")
    index_data = ws_index.get_all_values()
    index_df = pd.DataFrame(index_data[1:], columns=index_data[0])

    count = 0
    for _, row in index_df.iterrows():
        sheet_name = row["シート名"]
        try:
            ws = sh.worksheet(sheet_name)
        except Exception:
            continue  # シートがなければスキップ

        daibun1 = row.get("大分類1", "")
        daibun2 = row.get("大分類2", "")
        daibun3 = row.get("大分類3", "")
        shoubun1 = row.get("小分類1", "")
        shoubun2 = row.get("小分類2", "")
        shoubun3 = row.get("小分類3", "")

        try:
            ws.update_acell("M1", "大分類")
            ws.update_acell("N1", "小分類")
            ws.update_acell("M3", daibun1)
            ws.update_acell("M5", daibun2)
            ws.update_acell("M7", daibun3)
            ws.update_acell("N3", shoubun1)
            ws.update_acell("N5", shoubun2)
            ws.update_acell("N7", shoubun3)
            count += 1
        except Exception as e:
            print(f"{sheet_name} 書き込み失敗: {e}")
            continue

    return count

# ---------------------------
# データフレーム取得
# ---------------------------
df = load_index_sheet()

# ---------------------------
# サイドバー（ページ選択 & 管理メニュー）
# ---------------------------
page = st.sidebar.selectbox(
    "ページを選択してください",
    ["チャットで探す", "分類で探す"]
)

st.sidebar.markdown("---")  # 区切り線

# 管理者メニュー（サイドバー下部に）
with st.sidebar.expander("管理者メニュー", expanded=False):
    if st.button("新しいシートを目次に追加（同期）", key="add_new_sheets_to_index"):
        n = sync_index_sheet()
        st.success(f"{n}件の新しいシートを目次に追加しました！")
    if st.button("全シートに分類を転記", key="write_categories"):
        n = write_categories_to_sheets()
        st.success(f"{n}シートに分類情報を転記しました！")

# ---------------------------
# チャットで探すページ
# ---------------------------
if page == "チャットで探す":
    st.markdown(
        '''
        <div style="color: #888888; font-size:15px; margin-bottom:15px; padding:6px 0;">
        <em>※画面左のサイドバーからページ切替・管理ができます</em>
        </div>
        ''',
        unsafe_allow_html=True
    )
    st.title("活動サジェストチャット")
    st.write("どんな活動を探していますか？（例：自然、工作、料理、実験、屋外 など単語で入力）")

    user_input = st.text_input("キーワードを入力", "")
    search_btn = st.button("おすすめを表示")
    run_search = (search_btn or user_input) and user_input != ""

    if run_search:
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
        others = results.iloc[3:15]

        if not top3.empty:
            st.subheader("おすすめコンテンツ")
            for _, rec in top3.iterrows():
                # 活動名リンク
                if "gid" in rec and pd.notna(rec["gid"]):
                    url = SHEET_BASE_URL + str(rec["gid"])
                    st.markdown(
                        f'### 活動名：[ {rec["シート名"]} ]({url})'
                    )
                else:
                    st.write(f'### 活動名: {rec["シート名"]}')
                # テーマ＋改行
                if "D7" in rec:
                    st.write(f'テーマ：{rec["D7"]}\n')
                # 参加者の反応＋改行
                if "D17" in rec:
                    st.write(f'参加者の反応：{rec["D17"]}\n')
                st.write("---")
            st.subheader("その他の近いコンテンツ")
            if not others.empty:
                # 活動名をクリックでシートを開く
                links = [
                    f"[{row['シート名']}]({SHEET_BASE_URL}{row['gid']})"
                    for _, row in others.iterrows() if pd.notna(row["gid"])
                ]
                if links:
                    st.markdown("、".join(links), unsafe_allow_html=True)
                else:
                    st.write("その他の近いコンテンツは見つかりませんでした。")
            else:
                st.write("その他の近いコンテンツは見つかりませんでした。")
        else:
            st.info("条件に合うおすすめが見つかりませんでした。検索ワードを変えてみてください。")
    else:
        st.write("上の検索欄に希望を入力して「おすすめを表示」ボタンを押してください。")

# ---------------------------
# 分類で探すページ
# ---------------------------
elif page == "分類で探す":
    st.title("分類で活動を一覧")

    daibunrui_cols = [c for c in df.columns if c.startswith("大分類")]
    shoubunrui_cols = [c for c in df.columns if c.startswith("小分類")]

    if not daibunrui_cols or not shoubunrui_cols:
        st.warning("大分類・小分類のカラムが見つかりません。")
    else:
        # 全大分類値をユニークで空白除外
        all_cats = pd.unique(pd.concat([df[col] for col in daibunrui_cols]).dropna())
        all_cats = [cat for cat in all_cats if str(cat).strip() != ""]
        selected_cat = st.selectbox("大分類を選んでください", sorted(all_cats))

        # 大分類が1/2/3のどれかに入っていればOK
        filtered = df[df[daibunrui_cols].apply(lambda row: selected_cat in row.values, axis=1)]

        # 全小分類値（大分類絞り込み後）空白除外
        all_subcats = pd.unique(pd.concat([filtered[col] for col in shoubunrui_cols]).dropna())
        all_subcats = [cat for cat in all_subcats if str(cat).strip() != ""]
        selected_sub = st.selectbox("小分類を選んでください", ["すべて"] + sorted(all_subcats))

        if selected_sub != "すべて":
            filtered = filtered[filtered[shoubunrui_cols].apply(lambda row: selected_sub in row.values, axis=1)]

        st.write(f"該当件数：{len(filtered)}")
        for _, rec in filtered.iterrows():
            if "gid" in rec and pd.notna(rec["gid"]):
                url = SHEET_BASE_URL + str(rec["gid"])
                st.markdown(f'### 活動名：[ {rec["シート名"]} ]({url})')
            else:
                st.write(f'### 活動名: {rec["シート名"]}')
            if "D7" in rec and rec["D7"]:
                st.write(f'テーマ：{rec["D7"]}\n')
            if "D17" in rec and rec["D17"]:
                st.write(f'参加者の反応：{rec["D17"]}\n')
            st.write("---")
