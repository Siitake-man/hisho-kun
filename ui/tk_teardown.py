#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - Tkinter/CustomTkinter 静かな終了処理モジュール (ui/tk_teardown.py)

CustomTkinter は ScalingTracker (DPI 監視) と AppearanceModeTracker (外観監視) という
クラスレベルのバックグラウンドループを ``window.after()`` で自己再スケジュールしている。
root.destroy() 後もこれらの after コールバックが残存し、

    invalid command name "2715320140288check_dpi_scaling"
    invalid command name "2715320023616update"

という Tcl バックグラウンドエラーが標準エラーへ漏出する (Jules 夜間タスクB・2026-09-06)。
Tcl レベルの bgerror は Python の report_callback_exception を経由しないため、
「破棄前に未消化 after を全件キャンセルする」根本治療を主策とし、
report_callback_exception の quiet ガードを保険 (Belt & Suspenders) として併用する。

契約:
- すべての関数は root が既に破棄済み / customtkinter 未導入でも例外を漏らさない (Fail-Safe)。
- 破棄以外のタイミングで stop_ctk_background_trackers() を呼んでも、次に CTk ウィジェットが
  生成されればトラッカーは add() 経由で自動的に再始動する (状態は冪等に初期化されるのみ)。
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def stop_ctk_background_trackers() -> None:
    """CustomTkinter のクラスレベル監視ループ (ScalingTracker / AppearanceModeTracker) を停止する。

    各トラッカーは window_widgets_dict / app_list に root を保持し、辞書が空になると
    再スケジュールをやめて ``update_loop_running = False`` に落ち着く設計である。
    したがって辞書を明示的にクリアすれば、破棄済み root への再スケジュールを
    根本から防止できる (ライブラリへのパッチは不要)。

    Notes:
        破棄済み root が辞書に残ったままだと ``window.winfo_exists() == False``
        の判定で見逃されつつ、次の生きた root に after を積み続ける挙動になる
        (scaling_tracker.py L196-204 / appearance_mode_tracker.py L90-95 参照)。
    """
    try:
        from customtkinter.windows.widgets.scaling.scaling_tracker import ScalingTracker

        ScalingTracker.window_widgets_dict.clear()
        ScalingTracker.window_dpi_scaling_dict.clear()
        ScalingTracker.update_loop_running = False
        logger.debug("ScalingTracker の DPI 監視ループを停止しました")
    except ImportError:
        logger.debug("customtkinter 未導入のため ScalingTracker の停止をスキップ")
    except Exception as e:  # ライブラリアップデートへの耐性 (Fail-Safe)
        logger.warning(f"ScalingTracker の停止処理で予期しない事象: {e}")

    try:
        from customtkinter.windows.widgets.appearance_mode.appearance_mode_tracker import (
            AppearanceModeTracker,
        )

        AppearanceModeTracker.app_list.clear()
        AppearanceModeTracker.callback_list.clear()
        AppearanceModeTracker.update_loop_running = False
        logger.debug("AppearanceModeTracker の外観監視ループを停止しました")
    except ImportError:
        logger.debug("customtkinter 未導入のため AppearanceModeTracker の停止をスキップ")
    except Exception as e:
        logger.warning(f"AppearanceModeTracker の停止処理で予期しない事象: {e}")


def cancel_pending_after_callbacks(root: Any) -> int:
    """root 上で未消化の after タイマーをすべてキャンセルする。

    Tcl の ``after info`` コマンドで待機中タイマーを列挙し、全件 after_cancel する。
    これにより root 破棄後の「invalid command name」残滅を根本から防止する。

    Args:
        root: tkinter.Tk / Toplevel インスタンス (破棄済みでも可)。

    Returns:
        int: キャンセルに成功したタイマー数 (列挙に失敗した場合は 0)。
    """
    try:
        pending_ids = list(root.tk.call("after", "info"))
    except Exception as e:
        logger.debug(f"after info の取得に失敗 (既に破棄済みの可能性): {e}")
        return 0

    cancelled = 0
    for timer_id in pending_ids:
        try:
            # 注意: root.after_cancel() は使用しない。after_cancel は内部で
            # deletecommand(script) を呼ぶため、CTk トラッカーが同一コマンド名を
            # 重複登録している場合「Tcl 側で削除済み + _tclCommands に重複残存」の
            # 不整合を生み、後続の root.destroy() が
            # TclError: can't delete Tcl command で中断する (2026-09-12 実機事象)。
            # 生の Tcl 呼び出しはタイマーのみを解除しコマンド登録には触れない。
            root.tk.call("after", "cancel", timer_id)
            cancelled += 1
        except Exception as e:
            logger.debug(f"after cancel に失敗 (id={timer_id}): {e}")
    return cancelled


def dedupe_tcl_commands(root: Any) -> int:
    """root._tclCommands の重複登録を排除する (destroy 時の二重 deletecommand 回避)。

    CTk のクラスメソッド (ScalingTracker.check_dpi_scaling 等) は毎 tick
    ``createcommand`` で同一コマンド名を再登録するため、``_tclCommands`` に
    同名が蓄積する。destroy 時は各名前を 1 回ずつ deletecommand する設計のため、
    2 つ目以降の同名で ``TclError: can't delete Tcl command`` が発生し
    destroy が中断する (2026-09-12 実機事象)。

    Args:
        root: tkinter.Tk / Toplevel インスタンス。

    Returns:
        int: 排除した重複件数 (0 = 重複なし・属性不在)。
    """
    commands = getattr(root, "_tclCommands", None)
    if not commands:
        return 0
    deduped = list(dict.fromkeys(commands))
    removed = len(commands) - len(deduped)
    if removed:
        root._tclCommands = deduped
        return removed
    return 0


def install_quiet_teardown(root: Any) -> None:
    """破棄レース時の TclError ("invalid command name") を debug ログへ格下げする。

    root.report_callback_exception を差し替えるが、抑制対象は「既に削除された
    after コマンドへの参照残滅」のみ。それ以外の例外は元のレポータへ委譲するため、
    本来のバグを握りつぶさない (AGENTS 規約: エラー握りつぶし禁止の遵守)。

    Args:
        root: tkinter.Tk (または report_callback_exception を持つオブジェクト)。
    """
    original = root.report_callback_exception

    def quiet_report_callback_exception(exc, val, tb) -> None:
        """after コマンド残滅のみ debug 記録し、それ以外は元レポータへ委譲する。"""
        if isinstance(val, Exception) and "invalid command name" in str(val):
            logger.debug(f"破棄済み after コマンドの残滅を debug 記録: {val}")
            return
        original(exc, val, tb)

    root.report_callback_exception = quiet_report_callback_exception


def quiet_destroy(root: Any) -> None:
    """監視ループ停止 → 未消化 after の全件キャンセル → destroy の順で静かに破棄する。

    destroy が Python 側の後始末 (deletecommand の重複破棄) で失敗した場合は、
    Tcl レベルの ``destroy`` コマンドを直接実行するフォールバックを持つ。

    Args:
        root: tkinter.Tk / Toplevel (None の場合は何もしない)。
    """
    if root is None:
        return

    stop_ctk_background_trackers()
    cancelled = cancel_pending_after_callbacks(root)
    if cancelled:
        logger.debug(f"破棄前に {cancelled} 件の未消化 after タイマーをキャンセルしました")
    deduped = dedupe_tcl_commands(root)
    if deduped:
        logger.info(f"🧹 quiet_destroy: 重複登録 Tcl コマンド {deduped} 件を dedupe")
    try:
        root.destroy()
        logger.info("🧹 quiet_destroy: root を破棄しました (after キャンセル件数: {})".format(cancelled))
    except Exception as e:
        logger.warning(f"quiet_destroy: root.destroy() で例外: {e} → Tcl destroy へフォールバック")
        # フォールバック: Python 側の後始末 (deletecommand) を迂回し、Tcl レベルで
        # ウィンドウ階層ごと破棄する。メインウィンドウ破棄 = Tk アプリケーション終了。
        try:
            root.tk.call("destroy", root._w)
            logger.info("🧹 quiet_destroy: Tcl destroy フォールバックで破棄に成功しました")
        except Exception as e2:
            logger.warning(f"quiet_destroy: Tcl destroy フォールバックも失敗: {e2}")
