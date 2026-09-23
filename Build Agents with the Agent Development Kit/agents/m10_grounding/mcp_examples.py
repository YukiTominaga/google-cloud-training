# =====================================================================
# M10 Code 5. MCP ― agent と tool を分離する
# ---------------------------------------------------------------------
# MCP（Model Context Protocol）は、tool をモデルに公開するための標準。
# MCP サーバー側に tool を実装しておけば、agent 側はクライアントコードを
# 書かずに McpToolset で取り込める。
#   → tool の実装・権限管理を別チーム／別サービスに分離できる。
#
# ■ 接続方式は 2 種類
#   StdioConnectionParams          … ローカルでサブプロセスとして起動する
#   StreamableHTTPConnectionParams … リモートの MCP サーバーに HTTP で繋ぐ
#
# ■ tool_filter
#   サーバーが公開する tool のうち、この agent に見せるものだけを選ぶ。
#   書き込み系を外して「参照系だけ」にするのが定石（最小権限）。
#
# ※ McpToolset は作った時点ではサーバーに接続しない。
#   agent が実行されて tool 一覧が必要になったときに接続する。
# ※ Stdio の例は Node.js（npx）が必要。
# =====================================================================

from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import (
    StdioConnectionParams,
    StreamableHTTPConnectionParams,
)
from mcp import StdioServerParameters

# ---------------------------------------------------------------------
# ① ローカルの MCP サーバー（ファイルシステム）を Stdio で起動して使う
# ---------------------------------------------------------------------
filesystem_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "/data"],  # /data 以下だけ公開
        )
    ),
    tool_filter=["list_directory", "read_file"],  # 書き込み系（write_file 等）は見せない
)


# ---------------------------------------------------------------------
# ② リモートの MCP サーバーに HTTP で繋ぐ
# ---------------------------------------------------------------------
def fetch_fresh_token() -> str:
    """MCP サーバー用のアクセストークンを取得する（ダミー実装）。

    本番では Secret Manager や OAuth のトークン取得処理に置き換える。
    トークンをコードや .env に直書きしないこと。
    """
    return "dummy-token"


ticket_toolset = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url="https://tools.example.com/mcp",
        headers={"Authorization": f"Bearer {fetch_fresh_token()}"},
    ),
    tool_filter=["fetch_ticket", "add_comment"],
)
