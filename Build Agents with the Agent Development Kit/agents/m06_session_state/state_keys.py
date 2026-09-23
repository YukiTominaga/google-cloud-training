# =====================================================================
# M6 Code 4. state はスキーマであり契約である
# ---------------------------------------------------------------------
# state のキーは、複数の agent / tool / callback が共有する「契約」です。
# 文字列をあちこちに直書きすると、1 文字のタイプミスで
# 「書いたのに読めない」バグになり、しかもエラーにならずに静かに壊れます。
# → キー名は 1 か所に定数として集め、全員がここから import する。
#
# ■ 4 つのスコープ（Code 1）― キーの接頭辞で決まる
#   接頭辞なし  … この会話（session）の中だけ
#   user:       … このユーザーの全セッションで共有
#   app:        … 全ユーザー共通
#   temp:       … 今回の呼び出し（invocation）の中だけ。永続化されない
#
# ※ 「永続する」のは DatabaseSessionService / VertexAiSessionService を
#   使っている場合だけ。InMemorySessionService（adk web の既定）は
#   プロセスが終われば全部消える。
# =====================================================================

# --- session スコープ（接頭辞なし）---
SESSION_USER_ID = "session_user_id"  # アプリがセッション開始時に入れる
VERIFIED_ACCOUNT_ID = "verified_account_id"  # lookup_account が成功時に入れる
BILLING_RESPONSE = "billing_response"  # billing_agent の output_key
SHIPPING_RESPONSE = "shipping_response"  # shipping_agent の output_key（M7）
CART = "cart"  # add_to_cart が更新する

# --- user スコープ ---
USER_LANGUAGE = "user:language_preference"

# --- app スコープ ---
APP_RETURN_POLICY_VERSION = "app:return_policy_version"

# --- temp スコープ ---
TEMP_RAW_SQL_RESULT = "temp:raw_sql_result"
