# =====================================================================
# M9 mode="single_turn" を adk web で直接選べるようにする入口
# ---------------------------------------------------------------------
# adk web のドロップダウンには agents/ 直下のフォルダが並ぶ。
# 3 体の specialist を同じ mode にした coordinator を root_agent として公開している。
#   全員 mode="single_turn"（ユーザーと対話せず、結果だけ返す）
# 組み立て方と試すプロンプトは m09_task_collaboration/mode_variants.py を参照。
# =====================================================================

from m09_task_collaboration.mode_variants import build_coordinator

root_agent = build_coordinator("single_turn")
