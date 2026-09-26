#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - Approval Policy 3段階コマンド判定エンジン (approval_policy.py)

AIコーディングエージェントからのコマンド実行要請を解析し、
認知負荷を削減しながら安全性を担保する3段階判定エンジン。

3段階の判定基準:
- 🟢 AUTO_ALLOW: 閲覧・テスト・状態確認など、副作用のない安全な操作。
               人間を煩わせず即座に自動承認し、AIの思考・開発ループを加速。
- 🟡 PROMPT: 通常の編集・パッケージ追加・ビルドなど、標準的な開発操作。
            スマホ Desk Pet に通知し、ワンタップ承認を促す。
- 🔴 STRICT: ファイル全削除・強制プッシュ・テーブル削除などの破壊的変更。
            スマホ画面が赤く警告点滅し、慎重な二重確認を求める。
"""

import logging
import re
import shlex
from dataclasses import dataclass, field
from typing import List, Optional, Pattern

from agent_adapter import RiskLevel

logger = logging.getLogger(__name__)


@dataclass
class PolicyDecision:
    """コマンド評価の結果を表すデータクラス。

    Attributes:
        risk_level: 判定された危険度レベル (AUTO_ALLOW / PROMPT / STRICT)。
        reason: 判定理由の説明テキスト。
        matched_rule: マッチしたルール名またはパターン。
    """
    risk_level: RiskLevel
    reason: str
    matched_rule: str = ""

    @property
    def is_auto_allowed(self) -> bool:
        """即時自動許可可能かどうかを返す。"""
        return self.risk_level == RiskLevel.AUTO_ALLOW

    @property
    def is_strict(self) -> bool:
        """破壊的・高危険度コマンドかどうかを返す。"""
        return self.risk_level == RiskLevel.STRICT

    @property
    def requires_human_approval(self) -> bool:
        """人間による確認・タップ承認が必要かどうかを返す。"""
        return self.risk_level in (RiskLevel.PROMPT, RiskLevel.STRICT)


class ApprovalPolicyEngine:
    """エージェントが要求したコマンドの危険度を正規表現ベースで多重評価するエンジン。"""

    # 🛡️ P0-2 (2026-09-22): shlex 構造パースで「複合コマンド」と判定するシェル演算子。
    #    部分文字列（`;` 等）ではなくトークン単位で判定するため、引用符内の演算子を
    #    含む語（例: `echo "a;b"`）は単一コマンドとして扱われる。
    #    ※ 引用符が語全体を覆う純粋演算子（例: `echo ">"`）は保守的に複合扱い（安全側）。
    _PUNCT_CHARS = frozenset("();<>|&")

    # 展開構文（コマンド置換・変数展開）: shlex は展開を解釈しないため明示検知する。
    #  %VAR% (cmd.exe) / $env:X (PowerShell) / ${X} (bash) / $( ) / バッククォート
    _EXPANSION_RE: Pattern[str] = re.compile(
        r"\$\(|`|%[A-Za-z_][A-Za-z0-9_]*%|\$(env:|\{)", re.IGNORECASE
    )

    # パイプ・xargs 経由の実行で危険とみなすインタプリタ
    _INTERPRETER_TOKENS = frozenset({
        "sh", "bash", "zsh", "dash", "ksh", "pwsh", "powershell", "cmd",
        "python", "python3", "perl", "ruby", "node", "php",
    })

    # 🛡️ 電源操作（シャットダウン・再起動）: コマンド語として現れたら STRICT
    #    （`grep -r shutdown .` のような検索語は誤検知しないようトークンのコマンド位置で判定する）
    _POWER_COMMANDS = frozenset({
        "shutdown", "reboot", "halt", "poweroff", "stop-computer", "restart-computer",
    })
    _SYSTEMCTL_POWER_VERBS = frozenset({
        "poweroff", "reboot", "halt", "kexec", "suspend", "hibernate", "hybrid-sleep",
    })
    # コマンド語の直前に現れても「別コマンドの起動ラッパー」とみなすトークン
    _COMMAND_WRAPPERS = frozenset({
        "cmd", "/c", "/k", "start", "nohup", "env", "exec", "time", "nice", "timeout",
        "doas", "pwsh", "powershell", "-command", "-c",
    })

    # 🛡️ 機密ファイル: 秘密鍵そのもの（参照した時点で STRICT）
    _PRIVATE_KEY_RE: Pattern[str] = re.compile(
        r"(^|[/\\])id_(rsa|dsa|ecdsa|ed25519)(_sk)?$"
        r"|\.(ppk|kdbx)$"
        r"|(^|[/\\])\.gnupg([/\\]|$)"
        r"|^/etc/(shadow|gshadow)$",
        re.IGNORECASE,
    )
    # 🛡️ 機密ファイル: API キー・認証情報・証明書鍵（自動許可せず PROMPT で人間確認）
    #    `.env.example` / `.env.sample` / `.env.template` / `.env.dist` はテンプレートのため対象外。
    _SECRET_FILE_RE: Pattern[str] = re.compile(
        r"(^|[/\\=:])\.env(\.(?!(example|sample|template|dist)$)[^/\\]+)?$"
        r"|(^|[/\\])\.(ssh|aws|azure|kube|docker)([/\\]|$)"
        r"|(^|[/\\])\.config[/\\]gcloud([/\\]|$)"
        r"|(^|[/\\])\.(netrc|git-credentials|npmrc|pypirc|pgpass|sync_token)$"
        r"|(^|[/\\])(client_secret[^/\\]*|credentials?(\.[^/\\]+)?|secrets?(\.[^/\\]+)?"
        r"|service[-_]account[^/\\]*\.json)$"
        r"|\.(pem|key|p12|pfx|keystore|jks)$",
        re.IGNORECASE,
    )
    # 🛡️ 機密キーワードの検索（grep 等で API キー・トークンを探す行為は .env 等の中身を表示し得る）
    _SEARCH_COMMANDS = frozenset({
        "grep", "egrep", "fgrep", "rg", "ripgrep", "ag", "ack", "findstr", "select-string", "sls",
    })
    _SECRET_KEYWORD_RE: Pattern[str] = re.compile(
        r"(?<![a-z])(api[_-]?key|secrets?|tokens?|passw(or)?d|credentials?|private[_ -]?key|access[_-]?key"
        r"|bearer)(?![a-z])",
        re.IGNORECASE,
    )
    # 🛡️ ホーム・ルートそのものを対象にした横断検索（ホーム配下の機密を一括走査し得る）
    _HOME_ROOT_RE: Pattern[str] = re.compile(
        r"^(~[/\\]?|/|/root/?|/home(/[^/]+)?/?|/Users(/[^/]+)?/?|[a-z]:[/\\]?"
        r"|[a-z]:[/\\]users([/\\][^/\\]+)?[/\\]?)$",
        re.IGNORECASE,
    )
    _TREE_WALK_COMMANDS = frozenset({"find", "tree"})

    # 🛡️ pytest のプラグイン読込・設定差し替え系オプション（任意モジュールの読込になるため自動許可しない）
    #    `-p no:xxx`（プラグイン無効化）は安全側のため対象外。
    _PYTEST_UNSAFE_LONG_OPTIONS = ("--pyargs", "--override-ini", "--config-file", "--inifile",
                                   "--rootdir", "--confcutdir")
    _PYTEST_UNSAFE_SHORT_OPTIONS = ("-p", "-o", "-c")

    # 🔴 STRICT (破壊的・危険コマンド) の正規表現パターン
    DEFAULT_STRICT_PATTERNS: List[str] = [
        # 再帰的・強制削除 (rm -rf, rmdir /s, del /s, Remove-Item -Recurse -Force 等)
        r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f\b",
        r"\brm\s+-[a-zA-Z]*f[a-zA-Z]*r\b",
        r"\brmdir\s+/[sS]\b",
        r"\bdel\s+/[sS]\b",
        r"\bRemove-Item\b.*-[rR]ecurse.*-[fF]orce\b",
        r"\bRemove-Item\b.*-[fF]orce.*-[rR]ecurse\b",

        # Git 危険操作 (force push, reset --hard, clean -fdx 等)
        r"\bgit\s+push\b.*(--force|-f\b)",
        r"\bgit\s+reset\s+--hard\b",
        r"\bgit\s+clean\s+-[a-zA-Z]*f",

        # データベース破壊 (DROP TABLE, DROP DATABASE, TRUNCATE 等)
        r"\bDROP\s+(TABLE|DATABASE)\b",
        r"\bTRUNCATE\s+TABLE\b",

        # 権限昇格・全開放 (chmod 777, sudo 等)
        r"\bchmod\s+777\b",
        r"\bsudo\s+",
        r"\bchown\s+-R\b",

        # ディスク・OS破壊
        r"\bmkfs\b",
        r"\bformat\s+[a-zA-Z]:",
        r"\bdd\s+if=",

        # 🛡️ P0-2 (2026-09-22): 構造パースで検知する任意コード実行の複合形
        #    パイプ先がインタプリタ（シェル・スクリプト言語）＝無承認で任意コード実行
        r"\|\s*(sh|bash|zsh|dash|ksh|pwsh|powershell|cmd|python[0-9.]*|perl|ruby|node|php)\b",

        # 🛡️ P0-2: ファイル書込・破壊を伴う「読み取り系」の変種（無承認化の防止）
        r"\bgit\s+(status|diff|log|show)\b[^|;&]*--output",
        r"\bgit\s+branch\s+(-[dDmMfcu]|--delete|--set-upstream-to)",
        r"\bgit\s+tag\s+(?!(-l|-n|--list|--contains|--points-at|--merged|--sort|--format)\b)\S",
        r"\bgit\s+remote\s+(add|remove|set-url|rename|prune|set-head|set-branches|update)\b",
        r"\brm\b[^|;&]*(--recursive\b|-r\b)[^|;&]*(--force\b|-f\b)",
        r"\brm\b[^|;&]*(--force\b|-f\b)[^|;&]*(--recursive\b|-r\b)",
        r"\bRemove-Item\b[^|;&]*-[rR]ecurse\b",
    ]

    # 🟢 AUTO_ALLOW (安全・読み取り専用・テストコマンド) の正規表現パターン
    DEFAULT_AUTO_ALLOW_PATTERNS: List[str] = [
        # Git 読み取り系
        r"^git\s+(status|diff|log|branch|show|remote(\s+-v)?|tag(\s+-l)?)\b",

        # ディレクトリ・ファイル読み取り系
        r"^(ls|dir|pwd|echo|cat|type|head|tail|more|less)\b",
        r"^(which|where|find|grep|ripgrep|rg)\b",

        # テスト実行系 (自動テストランナー)
        r"^pytest\b",
        r"^python(\.exe)?\s+-m\s+unittest\b",
        r"^npm\s+test\b",
        r"^cargo\s+test\b",
        r"^cargo\s+check\b",
        r"^go\s+test\b",
    ]

    def __init__(self) -> None:
        self._strict_regexes: List[Pattern[str]] = [
            re.compile(p, re.IGNORECASE) for p in self.DEFAULT_STRICT_PATTERNS
        ]
        self._auto_allow_regexes: List[Pattern[str]] = [
            re.compile(p, re.IGNORECASE) for p in self.DEFAULT_AUTO_ALLOW_PATTERNS
        ]

    def add_strict_pattern(self, pattern: str) -> None:
        """危険コマンド判定パターンを動的に追加する。"""
        self._strict_regexes.insert(0, re.compile(pattern, re.IGNORECASE))

    def add_auto_allow_pattern(self, pattern: str) -> None:
        """自動許可コマンド判定パターンを動的に追加する。"""
        self._auto_allow_regexes.insert(0, re.compile(pattern, re.IGNORECASE))

    def _tokenize(self, command: str) -> Optional[List[str]]:
        """シェル字句解析（shlex）でトークン列を得る (P0-2)。

        Notes:
            🛡️ P0-2: `commenters` を無効化する。shlex の既定値は `'#'` をコメント開始と
            みなし **語中でも以降を読み捨てる**ため、`echo pwn#>~/.bashrc` が
            「複合なし」と誤判定され無承認書込に到達してしまう（bash は語中 `#` を
            リテラル扱いする）。解析不能（閉じない引用符等）は None を返し、
            呼び出し側が Fail-Closed（PROMPT）に倒す。

        Args:
            command (str): 実行予定のコマンドライン文字列。

        Returns:
            Optional[List[str]]: トークン列（解析不能時は None）。
        """
        try:
            lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
            lexer.whitespace_split = True
            lexer.commenters = ""
            return list(lexer)
        except ValueError as e:
            logger.warning("コマンド構文の解析に失敗しました (Fail-Closed で PROMPT に倒します): %s", e)
            return None

    def _detect_structural_strict(self, tokens: List[str]) -> str:
        """トークン列から構造的に危険な操作を検出する (P0-2)。

        引用符内の文字列（例: `grep -r 'eval(' .` の `eval(`）を誤検知しないよう、
        生文字列ではなくトークン（＝シェルが実際にコマンド語として解釈する単位）で判定する。

        Args:
            tokens (List[str]): `_tokenize` の結果。

        Returns:
            str: 検出理由（該当なしの場合は空文字）。
        """
        lowered = [t.lower() for t in tokens]
        for name in ("eval", "invoke-expression", "iex"):
            if name in lowered:
                return f"動的評価 ({name}) を検出しました"
        if "find" in lowered:
            # 🛡️ 完全一致ではなく**先頭一致**で判定する（-fprint0 / -okdir 等の派生形を取りこぼさない）
            for flag in ("-exec", "-execdir", "-delete", "-fprint", "-fprintf", "-fls", "-ok", "-okdir"):
                if any(token == flag or token.startswith(flag) for token in lowered):
                    return f"find の {flag} 系による任意操作を検出しました"
        if "xargs" in lowered:
            for name in self._INTERPRETER_TOKENS:
                if name in lowered:
                    return f"xargs 経由のインタプリタ実行 ({name}) を検出しました"
        # パイプ経由のインタプリタ実行はパス修飾形（/bin/bash・env bash 等）も検出する
        has_pipe = any(t and all(ch in self._PUNCT_CHARS for ch in t) and "|" in t for t in tokens)
        if has_pipe:
            for token in tokens:
                base = token.replace("\\", "/").rsplit("/", 1)[-1].lower()
                if base in self._INTERPRETER_TOKENS:
                    return f"パイプ経由のインタプリタ実行 ({base}) を検出しました"
        return ""

    @staticmethod
    def _command_base(token: str) -> str:
        """パス修飾・拡張子を除いたコマンド名（小文字）を返す（例: /sbin/shutdown.exe → shutdown）。"""
        base = token.replace("\\", "/").rsplit("/", 1)[-1].lower()
        return base[:-4] if base.endswith(".exe") else base

    def _split_simple_commands(self, tokens: List[str]) -> List[List[str]]:
        """演算子トークン（`|` `&&` `;` 等）で区切って単純コマンドのトークン列に分割する。"""
        commands: List[List[str]] = [[]]
        for token in tokens:
            if token and all(ch in self._PUNCT_CHARS for ch in token):
                commands.append([])
            else:
                commands[-1].append(token)
        return [c for c in commands if c]

    def _detect_power_command(self, tokens: List[str], depth: int = 0) -> str:
        """シャットダウン・再起動などの電源操作をコマンド位置で検出する。

        `grep -r shutdown .` のように検索語として現れる場合は誤検知しない。
        `cmd /c shutdown /s`・`timeout 5 reboot`・`bash -c "poweroff"` 等のラッパー経由も検出する。
        """
        for words in self._split_simple_commands(tokens):
            names = [self._command_base(w) for w in words]
            # 通常はコマンド語（先頭）のみ判定。ラッパー（cmd /c・timeout・env 等）経由なら後続語も判定する
            wrapped = names[0] in self._COMMAND_WRAPPERS or names[0] in self._INTERPRETER_TOKENS
            positions = range(len(names)) if wrapped else range(1)
            for i in positions:
                name = names[i]
                nxt = names[i + 1] if i + 1 < len(names) else ""
                if name in self._POWER_COMMANDS:
                    return f"電源操作 ({name}) を検出しました"
                if name == "systemctl" and nxt in self._SYSTEMCTL_POWER_VERBS:
                    return f"電源操作 (systemctl {nxt}) を検出しました"
                if name in ("init", "telinit") and nxt in ("0", "6"):
                    return f"電源操作 ({name} {nxt}) を検出しました"
            # `bash -c "shutdown now"` / `cmd /c "shutdown /s"` の文字列引数を再解析
            if depth < 2:
                for prev, word in zip(words, words[1:], strict=False):
                    if prev.lower() in ("-c", "-command", "/c", "/k") and " " in word.strip():
                        inner = self._tokenize(word)
                        if inner:
                            reason = self._detect_power_command(inner, depth + 1)
                            if reason:
                                return reason
        return ""

    @staticmethod
    def _path_args(tokens: List[str], raw_command: str) -> List[str]:
        """パス判定用の引数列を返す。

        shlex (posix) はバックスラッシュをエスケープとして消費するため、
        `C:\\Users\\x\\.ssh\\id_rsa` のような Windows パスは空白区切りの生の語でも判定する。
        """
        raw_words = [w.strip("'\"") for w in raw_command.split()]
        return tokens[1:] + raw_words[1:]

    def _detect_private_key_access(self, tokens: List[str], raw_command: str = "") -> str:
        """秘密鍵・パスワードハッシュ（~/.ssh/id_rsa・/etc/shadow 等）を参照する操作を検出する（STRICT）。"""
        for token in self._path_args(tokens, raw_command):
            if self._PRIVATE_KEY_RE.search(token.strip().rstrip("/\\")):
                return f"秘密鍵・認証情報ファイルへのアクセスを検出しました: {token}"
        return ""

    def _detect_sensitive_read(self, tokens: List[str], raw_command: str = "") -> str:
        """自動許可してはならない機密読み取り・プラグイン読込を検出する（PROMPT に倒す）。

        - .env / ~/.ssh / クラウド認証情報 / 証明書鍵ファイルの参照
        - grep 等での API キー・トークン・パスワード等の機密キーワード検索
        - ホーム・ルートそのものを対象にした横断検索（grep -r / find / tree）
        - pytest のプラグイン読込・設定差し替えオプション（-p / --pyargs / -o / -c 等）
        """
        if not tokens:
            return ""
        first = self._command_base(tokens[0])
        args = tokens[1:]
        for token in self._path_args(tokens, raw_command):
            if self._SECRET_FILE_RE.search(token.strip()):
                return f"機密情報を含む可能性のあるファイルへのアクセスのため確認が必要です: {token}"
        if first in self._SEARCH_COMMANDS:
            for token in args:
                if self._SECRET_KEYWORD_RE.search(token):
                    return f"機密キーワード ({token}) の検索のため確認が必要です"
        if first in self._SEARCH_COMMANDS or first in self._TREE_WALK_COMMANDS:
            for token in args:
                if self._HOME_ROOT_RE.match(token.strip()):
                    return f"ホーム/ルート全体 ({token}) の横断検索のため確認が必要です"
        if first in ("pytest", "py.test"):
            for i, token in enumerate(args):
                lowered = token.lower()
                if any(lowered == opt or lowered.startswith(opt + "=") for opt in self._PYTEST_UNSAFE_LONG_OPTIONS):
                    return f"pytest の設定差し替え・任意モジュール読込オプション ({token}) のため確認が必要です"
                for opt in self._PYTEST_UNSAFE_SHORT_OPTIONS:
                    if token == opt or (token.startswith(opt) and len(token) > len(opt) and not token.startswith("--")):
                        value = token[len(opt):] if token != opt else (args[i + 1] if i + 1 < len(args) else "")
                        if opt == "-p" and value.lower().startswith("no:"):
                            continue  # プラグイン無効化は安全側
                        return f"pytest のプラグイン読込・設定差し替えオプション ({token}) のため確認が必要です"
        return ""

    def _detect_composite(self, command: str) -> str:
        """シェル構造を字句解析し、複合コマンド・リダイレクト・展開を検出する (P0-2)。

        Notes:
            🛡️ P0-2 (2026-09-22): 旧実装は `;` `&&` `||` の**部分文字列**しか見ていなかったため、
            `cat evil.sh | bash`（パイプ）・`echo x > ~/.bashrc`（リダイレクト）・
            `ls & pytest`（バックグラウンド）・`cat $(whoami)`（置換）が AUTO_ALLOW を素通りしていた。
            shlex の punctuation_chars でシェル演算子をトークン化し、
            **句読点のみで構成されるトークン＝演算子ラン**（`>|` `&>` `&>>` 等の連結形を含む）を
            構造で判定する。

        Args:
            command (str): 実行予定のコマンドライン文字列。

        Returns:
            str: 複合と判定した理由（単一コマンドの場合は空文字）。
        """
        if self._EXPANSION_RE.search(command):
            return "コマンド置換・変数展開を含むため通常承認が必要です"
        if "\n" in command or "\r" in command:
            # 改行はシェルではコマンド区切り（shlex は空白として扱うため明示検知する）
            return "複数行コマンド（改行による複合）のため通常承認が必要です"
        tokens = self._tokenize(command)
        if tokens is None:
            return "シェル構文の解析に失敗したため通常承認が必要です"
        for token in tokens:
            if token and all(ch in self._PUNCT_CHARS for ch in token):
                return "複合コマンド（パイプ・チェイン・リダイレクト）のため通常承認が必要です"
        return ""

    def evaluate(self, command: str) -> PolicyDecision:
        """コマンドを評価し、3段階の危険度判定を下す。

        評価順序 (Fail-Safe 原則):
        1. まず 🔴 STRICT パターンに該当しないかを最優先検証 (複合コマンド内の危険操作を検知)。
        2. 次に 🟢 AUTO_ALLOW パターンに完全準拠しているかを検証。
        3. いずれにも当てはまらない通常の開発コマンドは 🟡 PROMPT (人間確認) にフォールバック。

        Args:
            command: 実行予定のコマンドライン文字列。

        Returns:
            PolicyDecision: 判定結果オブジェクト。
        """
        clean_cmd = command.strip()
        if not clean_cmd:
            return PolicyDecision(
                risk_level=RiskLevel.PROMPT,
                reason="空のコマンドです",
                matched_rule="empty_command",
            )

        # 1. 🔴 STRICT チェック (どこかに危険パターンが含まれていれば即座に赤判定)
        for pattern in self._strict_regexes:
            match = pattern.search(clean_cmd)
            if match:
                return PolicyDecision(
                    risk_level=RiskLevel.STRICT,
                    reason=f"破壊的または危険な操作を検出しました: {match.group(0)}",
                    matched_rule=pattern.pattern,
                )

        # 1.5 🔴 STRICT チェック（構造判定 / P0-2）: 引用符内の文字列を誤検知しないよう
        #     シェルが実際にコマンド語として解釈するトークン列で危険操作を判定する。
        tokens = self._tokenize(clean_cmd)
        if tokens is not None:
            structural_strict_reason = (
                self._detect_structural_strict(tokens)
                or self._detect_power_command(tokens)
                or self._detect_private_key_access(tokens, clean_cmd)
            )
            if structural_strict_reason:
                return PolicyDecision(
                    risk_level=RiskLevel.STRICT,
                    reason=structural_strict_reason,
                    matched_rule="structural_strict",
                )

        # 2. 🟢 AUTO_ALLOW チェック (安全なコマンドに適合するか)
        # 🛡️ P0-2 (2026-09-22): シェル構造をパースし、複合コマンド・リダイレクト・コマンド置換は
        # 安全のため PROMPT へ倒す（部分文字列判定を廃止し、構造判定へ移行）。
        composite_reason = self._detect_composite(clean_cmd)
        if composite_reason:
            return PolicyDecision(
                risk_level=RiskLevel.PROMPT,
                reason=composite_reason,
                matched_rule="composite_command",
            )

        # 2.5 🟡 機密読み取り・プラグイン読込は、閲覧/テスト系の見た目でも自動許可しない
        sensitive_reason = self._detect_sensitive_read(tokens or [], clean_cmd)
        if sensitive_reason:
            return PolicyDecision(
                risk_level=RiskLevel.PROMPT,
                reason=sensitive_reason,
                matched_rule="sensitive_read",
            )

        for pattern in self._auto_allow_regexes:
            if pattern.search(clean_cmd):
                return PolicyDecision(
                    risk_level=RiskLevel.AUTO_ALLOW,
                    reason="安全な閲覧またはテストコマンドとして自動許可されました",
                    matched_rule=pattern.pattern,
                )

        # 3. 🟡 PROMPT (デフォルト・通常承認)
        return PolicyDecision(
            risk_level=RiskLevel.PROMPT,
            reason="通常の開発・変更操作のため、確認・ワンタップ承認が必要です",
            matched_rule="default_prompt",
        )


# グローバル共有の判定エンジンインスタンス
_DEFAULT_POLICY_ENGINE: Optional[ApprovalPolicyEngine] = None


def get_default_policy_engine() -> ApprovalPolicyEngine:
    """デフォルトのポリシーエンジンインスタンスを返す。"""
    global _DEFAULT_POLICY_ENGINE
    if _DEFAULT_POLICY_ENGINE is None:
        _DEFAULT_POLICY_ENGINE = ApprovalPolicyEngine()
    return _DEFAULT_POLICY_ENGINE
