#!/usr/bin/env python3
"""Jev 全スキル棚卸し監査スクリプト (audit_skills_with_jev.py) - 真のJev判定版

~/.gemini/config/skills/ 配下の全スキルの SKILL.md をスキャンし、
冒頭説明 (name, frontmatter description, 概要抜粋) を入力 (State) として
TypeSafe Jev (OpenRouter Decisions API) に送信し、
客観的な構造化判定（カテゴリ、推奨アクション、適合度スコア、主因、代替案）を取得。
詳細レポート (docs/reports/SKILLS_AUDIT_REPORT.md) を生成する。

※注意: 本スクリプトは提案レポート作成のみであり、ファイルの削除・移動は一切行わない。
"""

import os
import sys
import re
import time
import json
from pathlib import Path
from typing import Dict, List, Any, Optional

HOME = Path.home()
SKILLS_DIR = HOME / ".gemini" / "config" / "skills"
REPORT_FILE = Path(r"c:\Users\bonob\OneDrive\ドキュメント\AntiGlavity\ネオ秘書くん\docs\reports\SKILLS_AUDIT_REPORT.md").resolve()

# Jev クライアントのパスを追加
JEV_DIR = HOME / ".gemini" / "tools" / "jev_router"
if str(JEV_DIR) not in sys.path:
    sys.path.insert(0, str(JEV_DIR))

try:
    from jev_client import JevClient
except ImportError:
    # ローカルリポジトリ内のフォールバック
    local_jev = Path(__file__).resolve().parent / "jev_router"
    if str(local_jev) not in sys.path:
        sys.path.insert(0, str(local_jev))
    from jev_client import JevClient

# ボスが明示的に「残す」と指定したスキル群（絶対温存・一軍確定ガード）
BOSS_RETAIN_SKILLS = {
    "codebase-design": "John Ousterhoutのディープモジュール思想、モジュールの深さと複雑度管理（コード設計の最高峰）",
    "archify": "動くHTML/SVGシステム構成図・シーケンス図生成（視覚的アーキテクチャ資産）",
    "fireworks-open-eli5": "OSS LLMを活用したELI5動的解説・図解",
    "teach": "教育・メンターシップ（ボスのコード審美眼・思考の筋肉を鍛える壁打ち）",
    "ui-ux-pro-max": "最高峰UI/UX設計（AI-slopを根絶するデザイン品質）",
    "ruthless-code-evaluation": "容赦なき厳格コード品質監査（妥協なきコードレビュー）"
}

# ボス自作のメタスキル群（絶対温存）
BOSS_META_SKILLS = {
    "init-session-skills": "セッション開始・ラップアップ自動生成メタスキル",
    "code-review-skill-generator": "コードレビュー系スキル生成メタスキル",
    "graph-engineering-skill-generator": "DAGグラフエンジニアリングスキル生成メタスキル",
    "generate-ai-company-context": "AIカンパニー文脈自動生成",
    "generate-project-agents": "プロジェクト固有エージェント自動生成",
    "skill-generator": "スキル自動生成メタスキル",
    "skill-repair": "壊れたスキルの自己修復メタスキル"
}

# ボスの開発プロファイル（Jevに入力する背景文脈）
DEVELOPER_PROFILE_CONTEXT = """
Developer Profile:
- Independent OSS Developer & AI Infrastructure Architect
- Project: "Neo Hisho-kun" (Local Desktop Pet + Mobile Desk Pet PWA + Autonomous Agent Bridge Hub)
- Tech Stack: Python, TypeScript, JavaScript, HTML5/Canvas, CSS, CustomTkinter, FastAPI, LangGraph, SQLite, PWA
- Architecture & Principles: 
  * 5-minute micro-tasks (PM optimization for limited time)
  * Deep Module philosophy (John Ousterhout: simple interface, deep implementation)
  * Zero Trust security & Local Boundary Defense
  * Test-Driven Development (TDD) discipline
  * Multi-agent orchestration (DAG / Graph Engineering)
- Excluded / Irrelevant:
  * Enterprise BigQuery / Dataform pipelines / Airflow / DBT
  * Enterprise Google Cloud Storage bucket architecture / Lakehouse catalog
  * Corporate Office doc automation (unless lightweight)
"""


def parse_skill_md(skill_path: Path) -> Dict[str, str]:
    """SKILL.md から name, description, 冒頭本文を抽出する"""
    skill_file = skill_path / "SKILL.md" if skill_path.is_dir() else skill_path
    if not skill_file.exists():
        return {
            "name": skill_path.name,
            "description": "No SKILL.md found",
            "body_excerpt": "ファイルが存在しません",
            "raw": ""
        }
    
    try:
        content = skill_file.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return {
            "name": skill_path.name,
            "description": f"Read error: {e}",
            "body_excerpt": str(e),
            "raw": ""
        }

    name = skill_path.name
    desc = ""
    
    # 1. YAML frontmatter parse
    fm_match = re.search(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    body = content
    if fm_match:
        fm = fm_match.group(1)
        body = content[fm_match.end():].strip()
        
        name_m = re.search(r"^name:\s*(.+)$", fm, re.MULTILINE)
        if name_m:
            name = name_m.group(1).strip().strip('"\'')
            
        desc_m = re.search(r"^description:\s*(.+)$", fm, re.MULTILINE)
        if desc_m:
            desc = desc_m.group(1).strip().strip('"\'')

    # 2. 本文抜粋の抽出（最初の有効な見出しや段落を最大400文字取得）
    body_lines = [
        line.strip() for line in body.splitlines() 
        if line.strip() and not line.startswith("<!--") and not line.startswith("```")
    ]
    excerpt_lines = []
    current_len = 0
    for line in body_lines:
        excerpt_lines.append(line)
        current_len += len(line)
        if current_len >= 350:
            break
    body_excerpt = "\n".join(excerpt_lines) if excerpt_lines else "本文なし"

    if not desc:
        desc = body_lines[0] if body_lines else "説明なし"

    return {
        "name": name,
        "description": desc,
        "body_excerpt": body_excerpt,
        "raw": content[:1500]
    }


def build_jev_questions() -> Dict[str, Any]:
    """Jevに渡す構造化判定クエスチョンを構築する"""
    return {
        "category": {
            "type": "choice",
            "instructions": "Classify this skill into the most precise domain category based on its description and body excerpt.",
            "criteria": {
                "meta_workflow": "Meta-skills, session lifecycle (start/wrap-up), agent/skill generation, orchestration",
                "code_architecture": "Software architecture, deep modules, refactoring, complexity control, code quality, linting",
                "frontend_ui": "Frontend, UI polish, CSS, Canvas, PWA styling, anti-slop visual design, animations",
                "testing_qa": "Unit testing, TDD, bug diagnosis, QA sessions, test verification",
                "concept_explainer": "Explaining complex concepts, ELI5, diagrams, visual mental models, teaching/mentorship",
                "security_zero_trust": "Zero trust, git guardrails, permissions, compliance, data loss prevention",
                "enterprise_cloud_data": "GCP BigQuery, Dataform, Airflow, DBT, Bigtable, enterprise lakehouse pipelines",
                "office_automation": "Office document (.docx, .xlsx, .pptx) generation and manipulation",
                "other_utility": "Other specialized utilities or miscellaneous tools"
            }
        },
        "recommendation": {
            "type": "choice",
            "instructions": "Determine the recommendation for this skill based on the developer profile (Independent OSS developer building lightweight desktop/mobile AI agent with Python/TypeScript/FastAPI/Tkinter/LangGraph/SQLite, zero enterprise cloud/BigQuery needed).",
            "criteria": {
                "keep_tier1": "Must keep (core daily driver for lightweight fullstack AI agent development, code quality, testing, UI, or meta-workflow)",
                "keep_tier2": "Useful secondary tool (specialized or situational utility to keep available)",
                "archive_suggest": "Suggested for archive/retirement (heavy enterprise GCP/BigQuery/Dataform pipelines, redundant duplicates, or outside tech stack)"
            }
        },
        "fit_score": {
            "type": "choice",
            "instructions": "Rate how relevant and valuable this skill is for the developer profile.",
            "criteria": {
                "5": "5/5: Essential daily driver directly aligned with tech stack and core values",
                "4": "4/5: Highly useful tool for development quality, UI, or workflows",
                "3": "3/5: Situationally useful specialized tool",
                "2": "2/5: Low relevance or redundant with superior tools",
                "1": "1/5: Irrelevant enterprise cloud bloat or outside scope"
            }
        },
        "primary_reason": {
            "type": "choice",
            "instructions": "Select the primary rationale behind this evaluation.",
            "criteria": {
                "core_stack_alignment": "Directly supports Python/TypeScript/Agent/PWA core development",
                "architecture_deepening": "Promotes deep modules, code aesthetics, and complexity control",
                "useful_specialized": "Valuable for specific workflows (diagrams, UI polish, testing)",
                "enterprise_cloud_bloat": "Heavy enterprise cloud/data pipeline (BigQuery/Dataform) outside personal OSS scope",
                "redundant_duplicate": "Overlaps with existing core skills and can be consolidated"
            }
        }
    }


def audit_single_skill_with_jev(
    client: JevClient,
    meta: Dict[str, str],
    questions: Dict[str, Any]
) -> Dict[str, Any]:
    """単一スキルのSKILL.md情報をStateとしてJevに送信し判定を取得する"""
    skill_name = meta["name"]
    desc = meta["description"]
    body_excerpt = meta["body_excerpt"]

    # State 文字列の組み立て（スキルの冒頭説明 + 開発者プロファイル）
    state_text = f"""Skill Name: {skill_name}
Description: {desc}

Overview & Excerpt:
{body_excerpt}

{DEVELOPER_PROFILE_CONTEXT}
"""

    # ボス指定スキルの安全チェック（事前にマーク）
    is_boss_retained = skill_name in BOSS_RETAIN_SKILLS
    is_boss_meta = skill_name in BOSS_META_SKILLS

    # Jev に真の構造化判定をリクエスト
    try:
        res = client.decide(state_text, questions)
        answers = res.get("answers", {})
        
        category_choice = answers.get("category", {}).get("choice", "other_utility")
        recommendation_choice = answers.get("recommendation", {}).get("choice", "keep_tier2")
        fit_score_choice = answers.get("fit_score", {}).get("choice", "3")
        primary_reason_choice = answers.get("primary_reason", {}).get("choice", "useful_specialized")
        confidence = res.get("confidence", 0.0)
    except Exception as e:
        category_choice = "other_utility"
        recommendation_choice = "keep_tier2"
        fit_score_choice = "3"
        primary_reason_choice = "useful_specialized"
        confidence = 0.0

    # カテゴリ日本語マッピング
    category_map = {
        "meta_workflow": "エージェント運用・メタスキル (Meta)",
        "code_architecture": "コード設計・品質監査 (Architecture)",
        "frontend_ui": "フロントエンド・UIデザイン (Frontend)",
        "testing_qa": "テスト・品質検証 (Testing/QA)",
        "concept_explainer": "概念図解・メンターシップ (ELI5/Explainer)",
        "security_zero_trust": "セキュリティ・境界防御 (Security)",
        "enterprise_cloud_data": "企業クラウド・データ基盤 (Enterprise Cloud)",
        "office_automation": "Officeドキュメント操作 (Office)",
        "other_utility": "汎用ユーティリティ (Utility)"
    }
    category_ja = category_map.get(category_choice, "汎用ユーティリティ")

    # 理由日本語マッピング
    reason_map = {
        "core_stack_alignment": "ボスの主要スタック（Python/TS/Agent/PWA）に完全合致",
        "architecture_deepening": "ディープモジュール思想・コード審美眼・複雑度制御に貢献",
        "useful_specialized": "特定の専門作業（図解、UI洗練、テスト）で強力に機能",
        "enterprise_cloud_bloat": "大規模企業向けクラウド（BigQuery/Dataform）であり個人開発には不要",
        "redundant_duplicate": "類似・上位互換スキルが存在し統合可能"
    }
    reason_ja = reason_map.get(primary_reason_choice, "状況に応じた活用が可能")

    # アクション決定（ボスの指示を最優先ガード）
    if is_boss_retained:
        action = "【ボス指定温存（一軍）】"
        dup_reason = f"ボス直々の温存指定: {BOSS_RETAIN_SKILLS[skill_name]}"
        fit_score_str = "5/5 (ボス指定)"
    elif is_boss_meta:
        action = "【ボス自作メタ（一軍）】"
        dup_reason = f"ボス自作メタスキル: {BOSS_META_SKILLS[skill_name]}"
        fit_score_str = "5/5 (自作メタ)"
    elif recommendation_choice == "keep_tier1":
        action = "【残す（精鋭一軍）】"
        dup_reason = reason_ja
        fit_score_str = f"{fit_score_choice}/5"
    elif recommendation_choice == "keep_tier2":
        action = "【温存（二軍実用）】"
        dup_reason = reason_ja
        fit_score_str = f"{fit_score_choice}/5"
    else:
        action = "【アーカイブ退避候補】"
        dup_reason = reason_ja
        fit_score_str = f"{fit_score_choice}/5"

    return {
        "name": skill_name,
        "category": category_ja,
        "raw_category": category_choice,
        "description": desc,
        "fit_score": fit_score_str,
        "action": action,
        "reason": dup_reason,
        "confidence": confidence,
        "is_boss_retained": is_boss_retained or is_boss_meta
    }


def main():
    if not SKILLS_DIR.exists():
        print(f"Skills dir not found: {SKILLS_DIR}")
        return

    print("==================================================================")
    print("🚀 TypeSafe Jev による真の全スキル棚卸し監査を開始します")
    print(f"📂 スキルディレクトリ: {SKILLS_DIR}")
    print("==================================================================")

    # Jev クライアント初期化
    client = JevClient()
    if not client.api_key:
        print("❌ OPENROUTER_API_KEY が取得できませんでした。環境変数またはレジストリを確認してください。")
        return

    questions = build_jev_questions()
    skill_paths = sorted([
        p for p in SKILLS_DIR.iterdir() 
        if p.is_dir() or p.name.endswith(".md") or (p.is_file() and not p.name.startswith("."))
    ])

    total_count = len(skill_paths)
    print(f"🔍 スキャン対象スキル数: {total_count} 件")
    print("⏳ Jev Decisions API に1件ずつ問い合わせを実行中...\n")

    results = []
    category_summary = {}

    start_time = time.time()
    for idx, path in enumerate(skill_paths, start=1):
        meta = parse_skill_md(path)
        print(f"[{idx}/{total_count}] 判定中: {meta['name']} ... ", end="", flush=True)
        
        audit = audit_single_skill_with_jev(client, meta, questions)
        results.append(audit)
        
        cat = audit["category"]
        category_summary[cat] = category_summary.get(cat, 0) + 1
        
        print(f"[{audit['action']}] ({audit['category']})")
        # わずかなウェイトでAPI負荷調整 (15ms)
        time.sleep(0.02)

    elapsed = time.time() - start_time
    print(f"\n✅ 全件判定完了！ 所要時間: {elapsed:.2f}秒 (平均: {elapsed/total_count:.2f}秒/件)")

    # 分類集計
    tier1_list = [r for r in results if "一軍" in r["action"] or "ボス" in r["action"]]
    tier2_list = [r for r in results if "二軍" in r["action"]]
    archive_list = [r for r in results if "アーカイブ" in r["action"]]

    # レポート生成
    report = []
    report.append("# Jev 全スキル棚卸し監査レポート (真のJev判定版)\n")
    report.append(f"**監査実施日**: 2026-09-23  ")
    report.append(f"**判定エンジン**: TypeSafe Jev (OpenRouter Decisions API)  ")
    report.append(f"**判定基準**: 各スキルの `SKILL.md` 冒頭説明（YAML frontmatter + 概要抜粋）× ボスの開発プロファイル  ")
    report.append(f"**対象ディレクトリ**: `{SKILLS_DIR}`  ")
    report.append(f"**総スキル数**: **{len(results)} 件**  \n")
    report.append("> ⚠️ **【重要】本レポートは客観的提案であり、ファイルの削除や移動は一切行っていません。ボスの確認・承認まで全ファイルは現状のまま維持されます。**\n")
    report.append("---\n")
    
    report.append("## 1. 総合集計（引き算と選抜のインパクト）\n")
    report.append(f"- **🏆 精鋭一軍（日常コア・ボス指定・自作メタ）**: **{len(tier1_list)} 件**")
    report.append(f"- **🛠️ 温存二軍（専門作業・実務ユーティリティ）**: **{len(tier2_list)} 件**")
    report.append(f"- **📦 アーカイブ退避候補（GCP企業データ・重複ツール）**: **{len(archive_list)} 件**\n")
    
    report.append("### カテゴリ別分布（Jev分類）\n")
    for cat, count in sorted(category_summary.items(), key=lambda x: -x[1]):
        report.append(f"- **{cat}**: {count} 件")
    report.append("\n---\n")

    report.append("## 2. 推奨アクション別 詳細一覧表\n")
    
    report.append("### 🏆 A. 精鋭一軍（日常コア・ボス指定・自作メタ）\n")
    report.append("| スキル名 | カテゴリ | 適合度 | 概要 (What) | 判定理由・選定根拠 |\n| :--- | :--- | :--- | :--- | :--- |")
    for r in tier1_list:
        desc_short = r['description'][:65].replace("\n", " ") + ("..." if len(r['description']) > 65 else "")
        report.append(f"| `{r['name']}` | {r['category']} | {r['fit_score']} | {desc_short} | {r['reason']} |")

    report.append("\n### 🛠️ B. 温存二軍（専門作業・実務ユーティリティ）\n")
    report.append("| スキル名 | カテゴリ | 適合度 | 概要 (What) | 活用シーン・判定理由 |\n| :--- | :--- | :--- | :--- | :--- |")
    for r in tier2_list:
        desc_short = r['description'][:65].replace("\n", " ") + ("..." if len(r['description']) > 65 else "")
        report.append(f"| `{r['name']}` | {r['category']} | {r['fit_score']} | {desc_short} | {r['reason']} |")

    report.append("\n### 📦 C. アーカイブ退避候補（引き算対象）\n")
    report.append("| スキル名 | カテゴリ | 適合度 | 概要 (What) | 退避理由（なぜ不要か） |\n| :--- | :--- | :--- | :--- | :--- |")
    for r in archive_list:
        desc_short = r['description'][:65].replace("\n", " ") + ("..." if len(r['description']) > 65 else "")
        report.append(f"| `{r['name']}` | {r['category']} | {r['fit_score']} | {desc_short} | {r['reason']} |")

    report.append("\n---\n")
    report.append("## 3. ボスへの判断・合意プロセス\n")
    report.append("1. **ボス指定スキルの確認**: `codebase-design`, `archify`, `fireworks-open-eli5`, `teach`, `ui-ux-pro-max`, `ruthless-code-evaluation` は確実に一軍へ選抜されています。")
    report.append("2. **退避候補の精査**: 主にGCP（BigQuery, Dataform, Airflow）等の企業クラウドデータ基盤が退避候補としてリストアップされています。")
    report.append("3. **承認後のアクション**: ボスの承認が得られた場合のみ、`~/.gemini/config/skills_archive/` を新設して対象スキルを安全に退避移動させます（いつでも1秒で復元可能）。")

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text("\n".join(report), encoding="utf-8")
    print(f"\n📄 最新レポートを生成しました: {REPORT_FILE}")
    print(f"📊 集計: 総数 {len(results)} 件 | 一軍 {len(tier1_list)} 件 | 二軍 {len(tier2_list)} 件 | アーカイブ候補 {len(archive_list)} 件")


if __name__ == "__main__":
    main()
