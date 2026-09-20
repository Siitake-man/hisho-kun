import sys
import os
import database

def register_jev_insight():
    insight_id = database.add_user_insight(
        category="Project",
        content="TypeSafe Jev意思決定エンジン(1.13)をOpenRouter経由で配備。秘書くん本体には推論を持たせず、エージェント側でJev審査を行いDesk Pet承認要請にスコアを添える運用とする（引き算の美学）。",
        importance=5,
        context_tags="jev, architecture, openrouter, deskpet, security, tool_guard"
    )
    print(f"Registered UserInsight successfully: ID={insight_id}")

if __name__ == "__main__":
    register_jev_insight()
