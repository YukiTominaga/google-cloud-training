# =====================================================================
# M7 Code 4. ParallelAgent を adk web で直接選べるようにする入口
# ---------------------------------------------------------------------
# adk web のドロップダウンには agents/ 直下のフォルダが並ぶ。
# m07_multi_agent/agent.py の root_agent を差し替えなくても試せるように、
# テンプレート agent をここで root_agent として公開している。
#   ParallelAgent ＋ gather（inventory / promotions / account → lookup_gather）
# 本体（agent の定義）と試すプロンプト（8）は m07_multi_agent/agent.py を参照。
# =====================================================================

from m07_multi_agent.agent import lookup_pipeline as root_agent  # noqa: F401
