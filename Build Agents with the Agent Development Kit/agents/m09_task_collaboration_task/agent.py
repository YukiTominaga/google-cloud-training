# =====================================================================
# M9 mode="task" を adk web で直接選べるようにする入口
# ---------------------------------------------------------------------
# adk web のドロップダウンには agents/ 直下のフォルダが並ぶ。
# 3 体の specialist を同じ mode にした coordinator を root_agent として公開している。
#   全員 mode="task"（聞き返しながら進め、終わったら親に戻る）
# 組み立て方と試すプロンプトは m09_task_collaboration/mode_variants.py を参照。
# =====================================================================

from m09_task_collaboration.mode_variants import build_coordinator

root_agent = build_coordinator("task")
