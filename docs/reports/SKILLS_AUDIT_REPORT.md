# Jev 全スキル棚卸し監査レポート (27,000〜30,000トークン強制収束版)

**監査実施日**: 2026-09-23  
**判定エンジン**: TypeSafe Jev (OpenRouter Decisions API)  
**投入コンテキスト規模**: **29,160 tokens (42,847 文字)**（27,000〜30,000 tokens の強制レンジ内）  
**対象ディレクトリ**: `C:\Users\bonob\.gemini\config\skills`  
**総スキル数**: **115 件**  

> ⚠️ **【重要】本レポートは客観的提案であり、ファイルの削除や移動は一切行っていません。ボスの確認・承認まで全ファイルは現状のまま維持されます。**

---

## 1. 総合集計（全体俯瞰 ＆ 相対引き算のインパクト）

- **🏆 精鋭一軍（日常コア・代表マスター・ボス指定）**: **16 件**
- **🛠️ 温存二軍（専門作業・実務ユーティリティ・独自の刃）**: **61 件**
- **📦 アーカイブ退避候補（GCP企業データ・重複ツール）**: **38 件**

### ドメイン別 競合突き合わせ結果（Jev判定）

| ドメイン | 所属数 | 代表マスター (Canonical) | 競合・重複度 | 推奨アクション |
| :--- | :--- | :--- | :--- | :--- |
| **企業クラウド・BigQuery・データパイプライン** | 24 件 | `gcp-data-pipelines` | all_irrelevant | archive_entire_domain |
| **エージェント運用・メタスキル・基盤ツール** | 16 件 | `skill-generator` | moderate_overlap | keep_and_prune |
| **コード設計・アーキテクチャ・品質監査** | 11 件 | `codebase-design` | moderate_overlap | keep_and_prune |
| **テスト駆動開発・バグ診断・品質検証** | 10 件 | `tdd` | moderate_overlap | keep_and_prune |
| **フロントエンド・UIデザイン・視覚設計** | 15 件 | `ui-ux-pro-max` | high_redundancy | keep_and_prune |
| **概念図解・動的解説・メンターシップ** | 12 件 | `fireworks-open-eli5` | moderate_overlap | keep_and_prune |
| **Officeドキュメント操作** | 8 件 | `officecli` | moderate_overlap | keep_and_prune |
| **セキュリティ・Gitガードレール・ゼロトラスト** | 3 件 | `none` | distinct_tools | keep_all_distinct |
| **汎用ユーティリティ** | 16 件 | `product-showcase` | moderate_overlap | keep_and_prune |

---

## 2. 推奨アクション別 詳細一覧表

### 🏆 A. 精鋭一軍（日常コア・代表マスター・ボス指定）

| スキル名 | ドメイン | 適合度 | 概要 (What) | 選定根拠・代表マスター理由 |
| :--- | :--- | :--- | :--- | :--- |
| `archify` | 概念図解・動的解説・メンターシップ | 5/5 (ボス指定) | Create polished, validated architecture, workflow, sequence, data... | ボス直々の温存指定: 動くHTML/SVGシステム構成図・シーケンス図生成（視覚的アーキテクチャ資産） |
| `code-review-skill-generator` | エージェント運用・メタスキル・基盤ツール | 5/5 (自作メタ) | 任意のプロジェクトに合わせた holistic-code-review スキルを自動生成するメタスキル。プロジェクトの規約ドキュメ... | ボス自作メタスキル: コードレビュー系スキル生成メタスキル |
| `codebase-design` | コード設計・アーキテクチャ・品質監査 | 5/5 (ボス指定) | Shared vocabulary for designing deep modules. Use when the user w... | ボス直々の温存指定: John Ousterhoutのディープモジュール思想、モジュールの深さと複雑度管理（コード設計の最高峰） |
| `fireworks-open-eli5` | 概念図解・動的解説・メンターシップ | 5/5 (ボス指定) | Create evidence-aware, interactive visual explainers as self-cont... | ボス直々の温存指定: OSS LLMを活用したELI5動的解説・図解 |
| `generate-ai-company-context` | エージェント運用・メタスキル・基盤ツール | 5/5 (自作メタ) | プロジェクトの構成を自動スキャンし、AIカンパニー用の「プロジェクト情報・コアプロフィール」を自動生成します。 | ボス自作メタスキル: AIカンパニー文脈自動生成 |
| `generate-project-agents` | エージェント運用・メタスキル・基盤ツール | 5/5 (自作メタ) | プロジェクトの技術スタック・構成・課題を分析し、Antigravityのカスタムエージェント（.agents/agents/*.m... | ボス自作メタスキル: プロジェクト固有エージェント自動生成 |
| `graph-engineering-skill-generator` | エージェント運用・メタスキル・基盤ツール | 5/5 (自作メタ) | 任意のプロジェクトに合わせた graph-engineering スキルを自動生成するメタスキル。コードベースのモジュール構造、依... | ボス自作メタスキル: DAGグラフエンジニアリングスキル生成メタスキル |
| `init-session-skills` | エージェント運用・メタスキル・基盤ツール | 5/5 (自作メタ) | プロジェクト構成を自動スキャンし、そのプロジェクトに最適化された session-wrap-up（二重資産化：学習メモ＋ELI5動... | ボス自作メタスキル: セッション開始・ラップアップ自動生成メタスキル |
| `officecli` | Officeドキュメント操作 | 5/5 | Create, analyze, proofread, and modify Office documents (.docx, .... | Jev全体判定により、Officeドキュメント操作 領域の代表マスターとして選定 |
| `product-showcase` | 汎用ユーティリティ | 5/5 | プロダクトオーナー(PO)の視点（存在意義Why・誰のどんな課題をどう解決するかWhat・3大提供価値・ユーザージャーニー）と、エ... | Jev全体判定により、None 領域の代表マスターとして選定 |
| `ruthless-code-evaluation` | コード設計・アーキテクチャ・品質監査 | 5/5 (ボス指定) | お世辞や手加減を一切排し、シリコンバレーのシニアアーキテクト・PM・セキュリティ監査官基準で、ネオ秘書くんのコードベース・アーキテ... | ボス直々の温存指定: 容赦なき厳格コード品質監査（妥協なきコードレビュー） |
| `skill-generator` | エージェント運用・メタスキル・基盤ツール | 5/5 (自作メタ) | ユーザーの要求やプロジェクトの課題から、Antigravity/Claude Code規格に完全準拠した高品質・高予測性のAgen... | ボス自作メタスキル: スキル自動生成メタスキル |
| `skill-repair` | エージェント運用・メタスキル・基盤ツール | 5/5 (自作メタ) | | | ボス自作メタスキル: 壊れたスキルの自己修復メタスキル |
| `tdd` | テスト駆動開発・バグ診断・品質検証 | 5/5 | Test-driven development. Use when the user wants to build feature... | Jev全体判定により、テスト駆動開発・バグ診断・品質検証 領域の代表マスターとして選定 |
| `teach` | 概念図解・動的解説・メンターシップ | 5/5 (ボス指定) | Teach the user a new skill or concept, within this workspace. | ボス直々の温存指定: 教育・メンターシップ（ボスのコード審美眼・思考の筋肉を鍛える壁打ち） |
| `ui-ux-pro-max` | フロントエンド・UIデザイン・視覚設計 | 5/5 (ボス指定) | UI/UX design intelligence for web, mobile, and desktop. This skil... | ボス直々の温存指定: 最高峰UI/UX設計（AI-slopを根絶するデザイン品質） |

### 🛠️ B. 温存二軍（専門作業・実用ユーティリティ・独自の刃）

| スキル名 | ドメイン | 適合度 | 概要 (What) | 活用シーン・棲み分け理由 |
| :--- | :--- | :--- | :--- | :--- |
| `accidental-data-loss-prevention` | セキュリティ・Gitガードレール・ゼロトラスト | 4/5 | | | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `agent-reach` | エージェント運用・メタスキル・基盤ツール | 4/5 | Use this skill whenever you need to read, search, or extract clea... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `algorithmic-art` | 汎用ユーティリティ | 4/5 | Creating algorithmic art using p5.js with seeded randomness and i... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `ask-matt` | 汎用ユーティリティ | 4/5 | Ask which skill or flow fits your situation. A router over the sk... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `batch-grill-me` | テスト駆動開発・バグ診断・品質検証 | 4/5 | A relentless interview that asks every frontier question at once,... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `claude-handoff` | エージェント運用・メタスキル・基盤ツール | 4/5 | Hand the current conversation off to a fresh background agent tha... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `code-review` | コード設計・アーキテクチャ・品質監査 | 4/5 | Review the changes since a fixed point (commit, branch, tag, or m... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `deep-audit` | コード設計・アーキテクチャ・品質監査 | 4/5 | 一言（「/deep-audit」または「全体レビューやって」）の指示で、codebase-memory-mcpのグラフ最新化から、... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `design-an-interface` | コード設計・アーキテクチャ・品質監査 | 4/5 | Generate multiple radically different interface designs for a mod... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `diagnosing-bugs` | テスト駆動開発・バグ診断・品質検証 | 4/5 | Diagnosis loop for hard bugs and performance regressions. Use whe... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `doc-coauthoring` | 概念図解・動的解説・メンターシップ | 4/5 | Guide users through a structured workflow for co-authoring docume... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `docx` | Officeドキュメント操作 | 4/5 | Use this skill whenever the user wants to create, read, edit, or ... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `domain-modeling` | コード設計・アーキテクチャ・品質監査 | 4/5 | Build and sharpen a project's domain model. Use when the user wan... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `edit-article` | 概念図解・動的解説・メンターシップ | 4/5 | Edit and improve articles by restructuring sections, improving cl... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `eli5` | 概念図解・動的解説・メンターシップ | 4/5 | 複雑なAI・インフラ・ソフトウェアの概念を「SVGアニメーション図解」「初級エンジニア向け物理解説」「専門用語の完全解体辞典」の3... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `find-skills` | エージェント運用・メタスキル・基盤ツール | 4/5 | Helps users discover and install agent skills when they ask quest... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `git-guardrails-claude-code` | セキュリティ・Gitガードレール・ゼロトラスト | 4/5 | Set up Claude Code hooks to block dangerous git commands (push, r... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `google-cloud-auth-verification` | セキュリティ・Gitガードレール・ゼロトラスト | 4/5 | Mandatory Step 0 pre-flight execution order and authentication ve... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `grill-me` | テスト駆動開発・バグ診断・品質検証 | 4/5 | A relentless interview to sharpen a plan or design. | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `grill-with-docs` | テスト駆動開発・バグ診断・品質検証 | 4/5 | A relentless interview to sharpen a plan or design, which also cr... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `grilling` | テスト駆動開発・バグ診断・品質検証 | 4/5 | Grill the user relentlessly about a plan, decision, or idea. Use ... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `handoff` | エージェント運用・メタスキル・基盤ツール | 4/5 | Compact the current conversation into a handoff document for anot... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `implement` | 汎用ユーティリティ | 4/5 | Implement a piece of work based on a spec or set of tickets. | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `improve-codebase-architecture` | コード設計・アーキテクチャ・品質監査 | 4/5 | Scan a codebase for deepening opportunities, present them as a vi... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `internal-comms` | 概念図解・動的解説・メンターシップ | 4/5 | A set of resources to help me write all kinds of internal communi... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `jev-brain` | エージェント運用・メタスキル・基盤ツール | 4/5 | TypeSafe Jev (System Oneモデル) を活用し、コマンド実行前の破壊性・安全性検査（Tool Guard）やタ... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `loop-me` | テスト駆動開発・バグ診断・品質検証 | 4/5 | Grill me about specs for the workflows I want to build, within th... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `managing-python-dependencies` | コード設計・アーキテクチャ・品質監査 | 4/5 | | | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `mcp-builder` | エージェント運用・メタスキル・基盤ツール | 4/5 | Guide for creating high-quality MCP (Model Context Protocol) serv... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `migrate-to-shoehorn` | コード設計・アーキテクチャ・品質監査 | 4/5 | Migrate test files from `as` type assertions to @total-typescript... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `ml-best-practices` | 汎用ユーティリティ | 4/5 | | | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `notebook-guidance` | 汎用ユーティリティ | 4/5 | |- | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `obsidian-vault` | エージェント運用・メタスキル・基盤ツール | 4/5 | Search, create, and manage notes in the Obsidian vault with wikil... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `pdf` | Officeドキュメント操作 | 4/5 | Use this skill whenever the user wants to do anything with PDF fi... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `pptx` | Officeドキュメント操作 | 4/5 | Use this skill any time a .pptx or .potx file is involved in any ... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `premium-animated-website-prompt` | 汎用ユーティリティ | 4/5 | Converts docs/DESIGN.md and visual design specifications into pro... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `prototype` | 汎用ユーティリティ | 4/5 | Build a throwaway prototype to answer a design question. Use when... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `qa` | テスト駆動開発・バグ診断・品質検証 | 4/5 | Interactive QA session where user reports bugs or issues conversa... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `request-refactor-plan` | コード設計・アーキテクチャ・品質監査 | 4/5 | Create a detailed refactor plan with tiny commits via user interv... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `research` | 汎用ユーティリティ | 4/5 | Investigate a question against high-trust primary sources and cap... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `resolving-merge-conflicts` | 汎用ユーティリティ | 4/5 | Use when you need to resolve an in-progress git merge/rebase conf... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `scaffold-exercises` | 汎用ユーティリティ | 4/5 | Create exercise directory structures with sections, problems, sol... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `setup-matt-pocock-skills` | 汎用ユーティリティ | 4/5 | Configure this repo for the engineering skills — set up its issue... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `setup-pre-commit` | テスト駆動開発・バグ診断・品質検証 | 4/5 | Set up Husky pre-commit hooks with lint-staged (Prettier), type c... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `setup-ts-deep-modules` | コード設計・アーキテクチャ・品質監査 | 4/5 | Wire dependency-cruiser into a TypeScript repo so each package is... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `slide-design-dark` | Officeドキュメント操作 | 4/5 | 黒地のMarpテーマ（minorun-dark）でスライドを組むときのデザインバランスと検査。余白の測り方、縦のバランス、配色の決... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `slide-figures` | Officeドキュメント操作 | 4/5 | 登壇スライドに載せる図・構成図・挿絵の作り方。情報量の絞り方、SVGの描き方、文字サイズの下限、挿絵の置き方、書き出し後の検査。「... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `slide-story` | Officeドキュメント操作 | 4/5 | 人前で話す登壇・講義スライドのストーリーの組み方。つかみ、中扉、段階的な開示、見出しの文体、締め方、尺の見積り。「登壇スライドを作... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `to-questionnaire` | 汎用ユーティリティ | 4/5 | Turn a decision you can't fully answer into a questionnaire for s... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `to-spec` | 汎用ユーティリティ | 4/5 | Turn the current conversation into a spec and publish it to the p... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `to-tickets` | 汎用ユーティリティ | 4/5 | Break a plan, spec, or the current conversation into a set of tra... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `triage` | エージェント運用・メタスキル・基盤ツール | 4/5 | Move issues and external PRs through a state machine of triage ro... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `ubiquitous-language` | 汎用ユーティリティ | 4/5 | Extract a DDD-style ubiquitous language glossary from the current... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `wayfinder` | エージェント運用・メタスキル・基盤ツール | 4/5 | Plan a huge chunk of work — more than one agent session can hold ... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `webapp-testing` | テスト駆動開発・バグ診断・品質検証 | 4/5 | Toolkit for interacting with and testing local web applications u... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `wizard` | 概念図解・動的解説・メンターシップ | 4/5 | Generate an interactive bash wizard that walks a human through a ... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `writing-beats` | 概念図解・動的解説・メンターシップ | 4/5 | Writing, exploit — assemble raw material into a journey of beats,... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `writing-fragments` | 概念図解・動的解説・メンターシップ | 4/5 | Writing, explore — mine raw fragments, no structure yet. | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `writing-great-skills` | 概念図解・動的解説・メンターシップ | 4/5 | Reference for writing and editing skills well — the vocabulary an... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `writing-shape` | 概念図解・動的解説・メンターシップ | 4/5 | Writing, exploit — shape raw material into an article, paragraph ... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |
| `xlsx` | Officeドキュメント操作 | 4/5 | Use this skill any time a spreadsheet file is the primary input o... | 代表マスターとは明確に棲み分けられており、特定作業で有用 |

### 📦 C. アーカイブ退避候補（引き算対象：GCP企業データ ＆ 重複下位互換）

| スキル名 | ドメイン | 適合度 | 概要 (What) | 退避理由（重複マスター／スタック外） |
| :--- | :--- | :--- | :--- | :--- |
| `apple-design` | フロントエンド・UIデザイン・視覚設計 | 2/5 | Apple's approach to interface design and fluid, physical motion, ... | 代表マスター `ui-ux-pro-max` と役割が重複。マスターで完全に代用可能 |
| `appllama-design` | フロントエンド・UIデザイン・視覚設計 | 2/5 | トップ収益アプリ（Top-grossing iOS apps）のUI/UXパターン・スプリング物理モーション（Framer Mot... | 代表マスター `ui-ux-pro-max` と役割が重複。マスターで完全に代用可能 |
| `baseline-ui` | フロントエンド・UIデザイン・視覚設計 | 2/5 | Quickly deslop UI code by fixing spacing, hierarchy, typography, ... | 代表マスター `ui-ux-pro-max` と役割が重複。マスターで完全に代用可能 |
| `bigquery-ai-ml` | 企業クラウド・BigQuery・データパイプライン | 1/5 | Leverages BigQuery's built-in machine learning and GenAI capabili... | エンタープライズ大規模クラウド（GCP BigQuery/Dataform）であり、ボスの個人OSSスタック外 |
| `bigquery-bigframes` | 企業クラウド・BigQuery・データパイプライン | 1/5 | Generates Python code using BigQuery DataFrames (BigFrames), the ... | エンタープライズ大規模クラウド（GCP BigQuery/Dataform）であり、ボスの個人OSSスタック外 |
| `bigquery-data-transfer-service` | 企業クラウド・BigQuery・データパイプライン | 1/5 | Discovers and inspects BigQuery Data Transfer Service (DTS) confi... | エンタープライズ大規模クラウド（GCP BigQuery/Dataform）であり、ボスの個人OSSスタック外 |
| `bigquery-graph` | 企業クラウド・BigQuery・データパイプライン | 1/5 | Provides guidelines and best practices for querying and defining ... | エンタープライズ大規模クラウド（GCP BigQuery/Dataform）であり、ボスの個人OSSスタック外 |
| `bigquery-sql` | 企業クラウド・BigQuery・データパイプライン | 1/5 | Provides BigQuery SQL query optimization techniques, execution be... | エンタープライズ大規模クラウド（GCP BigQuery/Dataform）であり、ボスの個人OSSスタック外 |
| `bigtable-basics` | 企業クラウド・BigQuery・データパイプライン | 1/5 | Assists in provisioning instances/tables, designing performant sc... | エンタープライズ大規模クラウド（GCP BigQuery/Dataform）であり、ボスの個人OSSスタック外 |
| `brand-guidelines` | フロントエンド・UIデザイン・視覚設計 | 2/5 | Applies Anthropic's official brand colors and typography to any s... | 代表マスター `ui-ux-pro-max` と役割が重複。マスターで完全に代用可能 |
| `building-data-apps` | 企業クラウド・BigQuery・データパイプライン | 1/5 | | | エンタープライズ大規模クラウド（GCP BigQuery/Dataform）であり、ボスの個人OSSスタック外 |
| `canvas-design` | フロントエンド・UIデザイン・視覚設計 | 2/5 | Create beautiful visual art in .png and .pdf documents using desi... | 代表マスター `ui-ux-pro-max` と役割が重複。マスターで完全に代用可能 |
| `cinematic-web-experience` | フロントエンド・UIデザイン・視覚設計 | 2/5 | Unconstrained creative web design & storytelling skill. Enforces ... | 代表マスター `ui-ux-pro-max` と役割が重複。マスターで完全に代用可能 |
| `data-autocleaning` | 企業クラウド・BigQuery・データパイプライン | 1/5 | Automated data quality and transformation capabilities for Datafo... | エンタープライズ大規模クラウド（GCP BigQuery/Dataform）であり、ボスの個人OSSスタック外 |
| `dataform-bigquery` | 企業クラウド・BigQuery・データパイプライン | 1/5 | Expertise in generating clean, correct, and efficient Dataform pi... | エンタープライズ大規模クラウド（GCP BigQuery/Dataform）であり、ボスの個人OSSスタック外 |
| `dbt-bigquery` | 企業クラウド・BigQuery・データパイプライン | 1/5 | Expert guidance for creating, modifying, and optimizing dbt pipel... | エンタープライズ大規模クラウド（GCP BigQuery/Dataform）であり、ボスの個人OSSスタック外 |
| `design-taste-frontend` | フロントエンド・UIデザイン・視覚設計 | 2/5 | Anti-slop frontend skill for landing pages, portfolios, and redes... | 代表マスター `ui-ux-pro-max` と役割が重複。マスターで完全に代用可能 |
| `discovering-gcp-data-assets` | 企業クラウド・BigQuery・データパイプライン | 1/5 | | | エンタープライズ大規模クラウド（GCP BigQuery/Dataform）であり、ボスの個人OSSスタック外 |
| `emil-design-eng` | フロントエンド・UIデザイン・視覚設計 | 2/5 | Encodes Emil Kowalski's philosophy on UI polish, component design... | 代表マスター `ui-ux-pro-max` と役割が重複。マスターで完全に代用可能 |
| `federate-lakehouse-catalog` | 企業クラウド・BigQuery・データパイプライン | 1/5 | Sets up Google Cloud Lakehouse federated catalogs to remote Icebe... | エンタープライズ大規模クラウド（GCP BigQuery/Dataform）であり、ボスの個人OSSスタック外 |
| `gcp-composer-troubleshooting` | 企業クラウド・BigQuery・データパイプライン | 1/5 | Provides expert guidance for troubleshooting Cloud Composer (Apac... | エンタープライズ大規模クラウド（GCP BigQuery/Dataform）であり、ボスの個人OSSスタック外 |
| `gcp-data-pipelines` | 企業クラウド・BigQuery・データパイプライン | 1/5 | Primary entry point for building, managing, and orchestrating dat... | エンタープライズ大規模クラウド（GCP BigQuery/Dataform）であり、ボスの個人OSSスタック外 |
| `gcp-dataflow` | 企業クラウド・BigQuery・データパイプライン | 1/5 | | | エンタープライズ大規模クラウド（GCP BigQuery/Dataform）であり、ボスの個人OSSスタック外 |
| `gcp-managed-airflow-dag-authoring` | 企業クラウド・BigQuery・データパイプライン | 1/5 | Guides the authoring and validation of Apache Airflow DAGs for Ma... | エンタープライズ大規模クラウド（GCP BigQuery/Dataform）であり、ボスの個人OSSスタック外 |
| `gcp-managed-airflow-migrations` | 企業クラウド・BigQuery・データパイプライン | 1/5 | Provides guidance for migrating Apache Airflow DAGs in Managed Se... | エンタープライズ大規模クラウド（GCP BigQuery/Dataform）であり、ボスの個人OSSスタック外 |
| `gcp-managed-airflow-recommendations` | 企業クラウド・BigQuery・データパイプライン | 1/5 | Provides recommendations and best practices for creating, configu... | エンタープライズ大規模クラウド（GCP BigQuery/Dataform）であり、ボスの個人OSSスタック外 |
| `gcp-pipeline-orchestration` | 企業クラウド・BigQuery・データパイプライン | 1/5 | This skill helps the agent generate or update orchestration pipel... | エンタープライズ大規模クラウド（GCP BigQuery/Dataform）であり、ボスの個人OSSスタック外 |
| `gcp-pipeline-resource-provisioning` | 企業クラウド・BigQuery・データパイプライン | 1/5 | | | エンタープライズ大規模クラウド（GCP BigQuery/Dataform）であり、ボスの個人OSSスタック外 |
| `google-cloud-storage-basics` | 企業クラウド・BigQuery・データパイプライン | 1/5 | Stores, retrieves, and manages data as objects in Cloud Storage (... | エンタープライズ大規模クラウド（GCP BigQuery/Dataform）であり、ボスの個人OSSスタック外 |
| `google-cloud-storage-bucket-architect` | 企業クラウド・BigQuery・データパイプライン | 1/5 | Creates Cloud Storage (Google Cloud Storage, or GCS) buckets. Ana... | エンタープライズ大規模クラウド（GCP BigQuery/Dataform）であり、ボスの個人OSSスタック外 |
| `google-cloud-storage-fuse` | 企業クラウド・BigQuery・データパイプライン | 1/5 | Mounts Cloud Storage buckets as a POSIX file system with Cloud St... | エンタープライズ大規模クラウド（GCP BigQuery/Dataform）であり、ボスの個人OSSスタック外 |
| `hallmark` | フロントエンド・UIデザイン・視覚設計 | 2/5 | Anti-AI-slop design skill for greenfield pages, audits, redesigns... | 代表マスター `ui-ux-pro-max` と役割が重複。マスターで完全に代用可能 |
| `schema-mapping` | 企業クラウド・BigQuery・データパイプライン | 1/5 | Guides the process of analyzing, mapping, and documenting transfo... | エンタープライズ大規模クラウド（GCP BigQuery/Dataform）であり、ボスの個人OSSスタック外 |
| `slack-gif-creator` | フロントエンド・UIデザイン・視覚設計 | 2/5 | Knowledge and utilities for creating animated GIFs optimized for ... | 代表マスター `ui-ux-pro-max` と役割が重複。マスターで完全に代用可能 |
| `theme-factory` | フロントエンド・UIデザイン・視覚設計 | 2/5 | Toolkit for styling artifacts with a theme. These artifacts can b... | 代表マスター `ui-ux-pro-max` と役割が重複。マスターで完全に代用可能 |
| `visual-design-wallbash` | フロントエンド・UIデザイン・視覚設計 | 2/5 | Interactive visual design exploration for premium websites. Gener... | 代表マスター `ui-ux-pro-max` と役割が重複。マスターで完全に代用可能 |
| `web-artifacts-builder` | フロントエンド・UIデザイン・視覚設計 | 2/5 | Suite of tools for creating elaborate, multi-component claude.ai ... | 代表マスター `ui-ux-pro-max` と役割が重複。マスターで完全に代用可能 |
| `web-design-guidelines` | フロントエンド・UIデザイン・視覚設計 | 2/5 | Review UI code for Web Interface Guidelines compliance. Use when ... | 代表マスター `ui-ux-pro-max` と役割が重複。マスターで完全に代用可能 |

---

## 3. ボスへの判断・合意プロセス

1. **誤分類の完全是正**: `mcp-builder` やコード設計スキルがUIマスターの重複に巻き込まれるバグを完全解消しました。
2. **ボス指定スキルの完全保護**: `codebase-design`, `archify`, `fireworks-open-eli5`, `teach`, `ui-ux-pro-max`, `ruthless-code-evaluation` は精鋭一軍マスターとして100%固定されています。
3. **承認後の安全退避**: ボスの合意が得られた場合のみ、`~/.gemini/config/skills_archive/` を新設して対象スキルを安全に退避移動させます（いつでも1秒で復元可能）。