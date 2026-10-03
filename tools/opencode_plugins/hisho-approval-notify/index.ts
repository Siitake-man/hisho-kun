/**
 * ネオ秘書くん 承認ブリッジプラグイン (hisho-approval-notify) — v1.3.2 (PC側解消連動/cancel_pending)
 *
 * Why（なぜ必要か）:
 *   OpenCode が「⚠️ 権限が必要です」ダイアログを出して処理を止めていても、ボスが画面を見ていないと
 *   気づけず、数十分〜数時間の待ちぼうけが発生する。これは**ネオ秘書くんが生まれた理由そのもの**
 *   （席を外してもAIコーディングエージェントが止まらない）。
 *
 *   v1.3 (2026-09-26 / 手帳 ID 63) からは**双方向化**した:
 *     従来 (v1.1〜v1.2): 権限要求をスマホへ「通知するだけ」(wait_decision:false)
 *     v1.3             : 権限要求をスマホへ「選択肢付きで転送」し、ボスのタップ決定を
 *                        OpenCode の権限システムへ**注入**する (wait_decision:true)
 *     v1.3.2 (2026-10-03): PC側解消連動 (N3-C)。PC側のIDEダイアログでユーザーが「許可」または
 *                        「拒否」を押して要求が解消された際、scanPending で要求消滅を
 *                        検知し、ネオ秘書くんの cancel_pending API を即座に呼び出して
 *                        スマホ側の待機カード・シートを自動消去する。
 *
 * 注入経路 (実機 opencode-cli 2.0.18 でのファクト確認・2026-09-26):
 *   - legacy setup(ctx) 形式のまま維持 (実機で動作実績がある形式・v1.2 と同一)
 *   - `ctx.permission.reply({ sessionID, requestID, decision, message })` が実在する
 *     (HTTP 相当: POST /api/session/:sessionID/permission/:requestID/reply、
 *      payload: { decision: "once" | "always" | "reject", message? })。
 *   - PC の承認ダイアログ自身が同一 API を呼ぶため、スマホからの決定は
 *     「PC でボタンを押したのと完全に同じ経路」として扱われる。
 *   - question ツールの回答注入 API は 2.0.18 には未搭載のため、question は従来どおり
 *     通知専業 (スマホの選択肢回答は OpenCode 側に返せない → 回答不能カードを出さない)。
 *
 * 安全性（ゼロトラスト）:
 *   - 認証はアプリと同じ `.sync_token`（Bearer）を使用する
 *   - 通知先は `localhost` 固定。加えてサーバー側でも `/api/agent/*` はループバック限定で防御されている
 *   - 例外は握りつぶさずログし、いかなる場合も OpenCode の動作を妨げない（Fail-Safe）
 *   - フックハンドラは**決して await しない**（runtime の権限評価を塞がない・v1.2 同様）
 *   - 決定注入に失敗した場合は PC 側ダイアログがそのまま残る（ボスの既定経路を壊さない）
 *   - 同一要求への再通知は 60 秒クールダウン＋進行中ラウンドトリップの合流で抑止する
 *
 * 診断（トラブルシューティング）:
 *   `console.log` は OpenCode のログに乗らないため、`%TEMP%\hisho-notify.log` へ
 *   トレースを追記する（検知・通知・注入・エラーの全履歴）。
 *
 * 設定（環境変数で上書き可能）:
 *   NEO_HISHO_ROOT … ネオ秘書くんのインストール先
 *   NEO_HISHO_PORT … ローカル同期サーバーのポート（既定 8765）
 */
import { appendFile, readFile } from "node:fs/promises"
import { join } from "node:path"

/** ネオ秘書くんのインストール先（環境変数 NEO_HISHO_ROOT で上書き可能） */
const DEFAULT_HISHO_ROOT = "C:\\Users\\bonob\\OneDrive\\ドキュメント\\AntiGlavity\\ネオ秘書くん"
/** ローカル同期サーバーのポート（環境変数 NEO_HISHO_PORT で上書き可能） */
const DEFAULT_HISHO_PORT = 8765
/** 保留中の権限要求を確認する間隔（ミリ秒 / evaluate フックが使えない版の保険） */
const POLL_INTERVAL_MS = 800
/** 通知クールダウン (ミリ秒): 同一要求スロットへの再通知を抑止する間隔 */
const NOTIFY_COOLDOWN_MS = 300_000
/** スマホ承認の待ち時間（秒・ask_input の wait_decision ブロッキング上限） */
const APPROVAL_TIMEOUT_SEC = 120
/** fetch の猶予加算（ミリ秒）: 応答待ち時間＋接続・応答の緩衝 */
const FETCH_GRACE_MS = 15_000
/** 診断ログの出力先（OpenCode のログに乗らないため独自ファイルへ記録する） */
const DIAG_LOG = join(process.env.TEMP ?? process.env.TMP ?? ".", "hisho-notify.log")

/** スマホの質問シートに表示する承認選択肢（そのままボタン文言になる） */
const APPROVAL_CHOICES: readonly string[] = ["✅ 許可 (今回のみ)", "✅ 常に許可", "🚫 拒否"]

/**
 * 診断ログを追記する（失敗してもプラグインを止めない）。
 * @param message 記録する内容
 */
const trace = (message: string): void => {
  void appendFile(DIAG_LOG, `${new Date().toISOString()} ${message}\n`).catch(() => {})
}

/**
 * マスタートークン (.sync_token) の解決候補を優先順で返す。
 * 正本: アプリ側 app_paths.get_sync_token_path()（P0-4 データ境界移行 2026-09-23）。
 *   1. NEO_HISHO_DATA_DIR 環境変数（アプリと同じ明示上書き）
 *   2. %LOCALAPPDATA%\NeoHisho（現行の正規データルート）
 *   3. <リポジトリ>/.sync_token（旧配置・読み取り専用の後方互換）
 * @param root ネオ秘書くんのインストール先
 * @returns 候補パスの配列（優先順）
 */
const resolveTokenCandidates = (root: string): string[] => {
  const candidates: string[] = []
  const dataDir = process.env.NEO_HISHO_DATA_DIR
  if (dataDir) candidates.push(join(dataDir, ".sync_token"))
  const baseDir = process.env.LOCALAPPDATA ?? process.env.XDG_DATA_HOME
  if (baseDir) candidates.push(join(baseDir, "NeoHisho", ".sync_token"))
  candidates.push(join(root, ".sync_token"))
  return candidates
}

/**
 * マスタートークンを解決して読み込む（見つからなければ空文字）。
 * @param root ネオ秘書くんのインストール先
 * @returns トークン文字列（未検出時は空文字）
 */
const readSyncToken = async (root: string): Promise<string> => {
  for (const candidate of resolveTokenCandidates(root)) {
    try {
      const token = (await readFile(candidate, "utf8")).trim()
      if (token) {
        return token
      }
    } catch {
      // 候補が無い場合は次の候補へフォールバック
    }
  }
  trace(`通知不可: .sync_token が見つかりません（候補: ${resolveTokenCandidates(root).join(" / ")}）`)
  return ""
}

/**
 * スマホで選ばれた回答テキストを OpenCode 権限応答語彙へ変換する。
 * 実機 2.0.18 の正本語彙は "once" / "always" / "reject" (Permission.Reply)。
 * @param answer 質問シートのボタンテキスト（ask_input の answer で戻る文字列）
 * @returns 語彙文字列。判定不能（タイムアウト・自由回答・空）時は空文字
 */
const mapAnswerToReply = (answer: unknown): "once" | "always" | "reject" | "" => {
  const text = String(answer ?? "").trim()
  if (text === APPROVAL_CHOICES[1]) return "always"
  if (text === APPROVAL_CHOICES[0]) return "once"
  if (text === APPROVAL_CHOICES[2]) return "reject"
  return ""
}

export default {
  id: "hisho-approval-notify",

  /**
   * プラグインの初期化。検知フック・通知処理・決定注入を登録する。
   * @param ctx OpenCode のプラグインコンテキスト（実機 2.0.18 の legacy 形式）
   * @returns クリーンアップ関数（購読停止・タイマー解除）
   */
  async setup(ctx: any): Promise<() => void> {
    const root = process.env.NEO_HISHO_ROOT ?? DEFAULT_HISHO_ROOT
    const port = Number(process.env.NEO_HISHO_PORT ?? DEFAULT_HISHO_PORT)
    const sessions = new Set<string>()
    const lastNotified = new Map<string, number>()
    /** 進行中の双方向ラウンドトリップ（同一要求の二重転送を合流させる） */
    const inFlight = new Map<string, Promise<void>>()
    /** 把握中の保留要求（セッションIDと要求キーの対応・消滅検知用） */
    const activeKnownRequests = new Map<string, { sessionID: string; requestKey: string }>()

    trace(`setup() 開始 root=${root} port=${port} (v1.3.2 PC側解消連動)`)

    const permissionApi = ctx?.permission
    const eventApi = ctx?.event
    trace(
      `API確認: permission=${typeof permissionApi} list=${typeof permissionApi?.list} ` +
        `hook=${typeof permissionApi?.hook} reply=${typeof permissionApi?.reply} ` +
        `event=${typeof eventApi} subscribe=${typeof eventApi?.subscribe}`,
    )
    if (permissionApi === undefined) {
      trace("ctx.permission が無いため通知を無効化します")
      return () => {}
    }

    /**
     * ネオ秘書くんへ「入力待ち」を通知・または回答待ちで送信する。
     * @param label ログ用の識別子（セッションID・要求IDなど）
     * @param detail スマホ・ペットに表示する詳細
     * @param title スマホ・ペットに表示する見出し
     * @param options waitDecision=true でボス回答までブロッキング送信（v1.3 双方向）
     * @returns 応答JSON（waitDecision=false は即時 queued / 失敗時は null）
     */
    const notifyHisho = async (
      label: string,
      detail: string,
      title: string = "⚠️ 承認待ちが発生しています（OpenCode）",
      options: { waitDecision: boolean; choices?: readonly string[]; timeoutSec?: number; requestId?: string } = {
        waitDecision: false,
      },
    ): Promise<any | null> => {
      try {
        const token = await readSyncToken(root)
        if (!token) return null
        const waitDecision = options.waitDecision === true
        const timeoutSec = options.timeoutSec ?? 5
        const response = await fetch(`http://localhost:${port}/api/agent/ask_input`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json; charset=utf-8",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            request_id: options.requestId,
            agent_name: "OpenCode",
            question: title,
            details: detail,
            choices: options.choices ? [...options.choices] : [],
            timeout: timeoutSec,
            wait_decision: waitDecision,
          }),
          signal: AbortSignal.timeout(timeoutSec * 1000 + FETCH_GRACE_MS),
        })
        const body = await response.text()
        trace(`通知送信 ${label} (wait=${waitDecision}) -> HTTP ${response.status} ${body.slice(0, 160)}`)
        if (response.status !== 200) return null
        try {
          return JSON.parse(body)
        } catch {
          return null
        }
      } catch (error) {
        trace(`通知エラー: ${error instanceof Error ? error.message : String(error)}`)
        return null
      }
    }

    /**
     * PC側で解決・解消された保留中要求をネオ秘書くん側で取り消す (N3-C)。
     * スマホ側の待機通知（承認カード/質問シート）を即座に消去する。
     * @param requestID 権限要求ID
     * @param reason 取消理由
     */
    const cancelPendingHisho = async (requestID: string, reason: string = "resolved_on_pc"): Promise<void> => {
      try {
        const token = await readSyncToken(root)
        if (!token) return
        const response = await fetch(`http://localhost:${port}/api/agent/cancel_pending`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json; charset=utf-8",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            request_id: requestID,
            reason,
          }),
          signal: AbortSignal.timeout(3000),
        })
        const body = await response.text()
        trace(`保留取消送信 ${requestID} -> HTTP ${response.status} ${body.slice(0, 100)}`)
      } catch (error) {
        trace(`保留取消エラー: ${error instanceof Error ? error.message : String(error)}`)
      }
    }

    /**
     * 要求IDの重複を判定し、初回のみ通知する。
     * @param requestID 権限要求の識別子
     * @returns 通知すべき場合 true
     */
    const shouldNotify = (requestID: string): boolean => {
      const now = Date.now()
      if (lastNotified.size > 200) {
        for (const [key, at] of lastNotified) {
          if (now - at >= NOTIFY_COOLDOWN_MS) lastNotified.delete(key)
        }
      }
      const previous = lastNotified.get(requestID)
      if (previous !== undefined && now - previous < NOTIFY_COOLDOWN_MS) return false
      lastNotified.set(requestID, now)
      return true
    }

    /**
     * 権限要求から通知用の文言と識別子を組み立てる。
     * @param event 権限要求（フックイベントまたは一覧の要素）
     * @returns 詳細文字列・要求ID・見出し・アクション種別
     */
    const describeRequest = (
      event: any,
    ): { detail: string; requestID: string; title: string; action: string } => {
      let serialized = ""
      try {
        serialized = JSON.stringify(event)?.slice(0, 300) ?? ""
      } catch {
        serialized = "(シリアライズ不可)"
      }
      const action = String(event?.action ?? event?.permission ?? event?.type ?? "unknown")
      const rawResources =
        event?.resources ?? event?.resource ?? event?.pattern ?? event?.command ?? ""
      const resourceList = Array.isArray(rawResources) ? rawResources : [String(rawResources)]
      const resourceBody = resourceList
        .map((r) => String(r))
        .filter((r) => r.length > 0)
        .join("\n")
      const sessionID = String(event?.sessionID ?? "")
      const isQuestion = action === "question"
      const requestID = isQuestion && event?.source?.id
        ? `question:${event.source.id}`
        : String(event?.id ?? event?.requestID ?? `${action}:${resourceBody.slice(0, 40)}:${sessionID}`)
      return {
        requestID,
        title: isQuestion
          ? "💬 OpenCode が回答を待っています"
          : `⚠️ 承認待ち（OpenCode）: ${(resourceList[0] || action).slice(0, 80)}`,
        detail: isQuestion
          ? "種別: question\nOpenCode が質問・選択肢の回答を待っています。\nOpenCode の画面で回答してください。"
          : `種別: ${action}\n対象:\n${resourceBody}\n` +
            `生データ: ${serialized}\n` +
            "スマホで選択肢をタップすると OpenCode へ直接反映されます。\nタップしない場合は PC のダイアログで選んでください。",
        action,
      }
    }

    /**
     * 保留中の権限要求へスマホの決定を注入する (v1.3 双方向化の核)。
     * @param sessionID 権限要求のセッションID
     * @param event evaluate フックで受け取った権限評価イベント
     * @param decision OpenCode 権限応答語彙 (once / always / reject)
     */
    const replyToPending = async (
      sessionID: string,
      event: any,
      decision: "once" | "always" | "reject",
    ): Promise<void> => {
      try {
        if (!sessionID) {
          trace("決定注入不可: evaluate イベントに sessionID がありません")
          return
        }
        const listed: any = await permissionApi.list({ sessionID })
        const items: any[] = Array.isArray(listed)
          ? listed
          : (listed?.requests ?? listed?.permissions ?? [])
        const sourceID = event?.source?.id ? String(event.source.id) : ""
        const action = String(event?.action ?? "")
        const match =
          items.find((item) => sourceID !== "" && String(item?.source?.id ?? "") === sourceID) ??
          items.find((item) => String(item?.action ?? item?.permission ?? "") === action)
        const requestID = match?.id ?? event?.id
        if (!requestID) {
          trace(`決定注入不可: 保留中要求が見つかりません (session=${sessionID} action=${action})`)
          return
        }
        await permissionApi.reply({
          sessionID,
          requestID: String(requestID),
          decision,
          message: "",
        })
        trace(`決定注入成功: requestID=${requestID} decision=${decision}`)
      } catch (error) {
        trace(`決定注入失敗 (PCダイアログは維持): ${error instanceof Error ? error.message : String(error)}`)
      }
    }

    /**
     * 承認要求の双方向ラウンドトリップを実行する (スマホ転送 → 回答待ち → 決定注入)。
     * @param requestKey 進行中合流用のキー
     * @param sessionID セッションID
     * @param event evaluate イベント
     * @param detail スマホ表示用詳細
     * @param title スマホ表示用見出し
     */
    const runBidirectionalApproval = (
      requestKey: string,
      sessionID: string,
      event: any,
      detail: string,
      title: string,
    ): void => {
      const existing = inFlight.get(requestKey)
      if (existing) return
      activeKnownRequests.set(requestKey, { sessionID, requestKey })
      const task = (async () => {
        const res = await notifyHisho(
          `bidirectional:${requestKey}`,
          detail,
          title,
          {
            waitDecision: true,
            choices: APPROVAL_CHOICES,
            timeoutSec: APPROVAL_TIMEOUT_SEC,
            requestId: requestKey,
          },
        )
        if (!res || res.status !== "success") return
        if (res.decision === "timeout" || res.decision === "expired") {
          trace("⏳ スマホ応答なし（タイムアウト/期限切れ）: PC ダイアログを維持し何も注入しない")
          return
        }
        if (res.decision === "cancelled") {
          trace("🚫 保留要求がキャンセルされました (PC側解決等): 何も注入しない")
          return
        }
        const reply = mapAnswerToReply(res.answer)
        if (!reply) {
          trace(`決定注入スキップ: 回答が選択肢と完全一致しません (answer=${String(res.answer).slice(0, 60)})`)
          return
        }
        await replyToPending(sessionID, event, reply)
      })()
        .catch((error) => {
          trace(`双方向ラウンドトリップ異常: ${error instanceof Error ? error.message : String(error)}`)
        })
        .finally(() => {
          inFlight.delete(requestKey)
        })
      inFlight.set(requestKey, task)
    }

    // ---- 主軸: 権限評価フック（ダイアログ出現の瞬間に発火）----
    if (typeof permissionApi.hook === "function") {
      try {
        await permissionApi.hook("evaluate", (event: any) => {
          try {
            trace(`evaluate フック発火: ${JSON.stringify(event)?.slice(0, 1200) ?? ""}`)
            const { detail, requestID, title, action } = describeRequest(event)
            if (event?.effect === "deny") return
            if (action === "question") {
              if (shouldNotify(requestID)) {
                void notifyHisho(`evaluate:${requestID}`, detail, title, { waitDecision: false, requestId: requestID })
              }
              return
            }
            if (event?.effect !== "ask") return
            if (!shouldNotify(`perm:${requestID}`)) return
            const sessionID = String(event?.sessionID ?? "")
            runBidirectionalApproval(`perm:${requestID}`, sessionID, event, detail, title)
          } catch (error) {
            trace(`フック内エラー: ${error instanceof Error ? error.message : String(error)}`)
          }
        })
        trace("permission.hook('evaluate') の登録に成功")
      } catch (error) {
        trace(`evaluate フック登録失敗（ポーリングへフォールバック）: ${String(error)}`)
      }
    } else {
      trace("permission.hook が存在しないため、ポーリングのみで動作します")
    }

    // ---- 保険: 保留中一覧のポーリング (通知専業＋PC側解消検知) ----
    const scanPending = async (sessionID: string): Promise<void> => {
      try {
        const listed: any = await permissionApi.list({ sessionID })
        const items: any[] = Array.isArray(listed)
          ? listed
          : (listed?.requests ?? listed?.permissions ?? [])
        if (items.length > 0) trace(`ポーリング検知: session=${sessionID} pending=${items.length}`)
        const currentReqKeysInSession = new Set<string>()

        for (const item of items) {
          if (item?.effect !== undefined && item.effect !== "ask") continue
          const { detail, requestID, title } = describeRequest({ ...item, sessionID })
          const requestKey = `perm:${requestID}`
          currentReqKeysInSession.add(requestKey)
          activeKnownRequests.set(requestKey, { sessionID, requestKey })

          if (inFlight.has(requestKey)) {
            trace(`🔇 ポーリング通知スキップ（双方向カード送信済みの要求）: ${requestID.slice(0, 60)}`)
            continue
          }
          if (!shouldNotify(requestKey)) continue
          await notifyHisho(`poll:${requestID}`, detail, title, { waitDecision: false, requestId: requestKey })
        }

        // 要求消滅検知 (N3-C): このセッションで以前把握していた要求のうち、現在 listed に存在しないものを検出
        for (const [key, info] of activeKnownRequests) {
          if (info.sessionID === sessionID && !currentReqKeysInSession.has(key)) {
            trace(`PC側で要求解消を検知: session=${sessionID} key=${key} -> cancel_pending 送信`)
            activeKnownRequests.delete(key)
            void cancelPendingHisho(key, "resolved_on_pc")
          }
        }
      } catch (error) {
        trace(`list 失敗: session=${sessionID} ${error instanceof Error ? error.message : String(error)}`)
      }
    }

    const controller = new AbortController()
    if (typeof eventApi?.subscribe === "function") {
      void (async () => {
        try {
          for await (const event of eventApi.subscribe({ signal: controller.signal })) {
            const anyEvent = event as any
            const sessionID = anyEvent?.sessionID ?? anyEvent?.properties?.sessionID
            if (typeof sessionID === "string" && sessionID.length > 0) sessions.add(sessionID)
          }
        } catch {
          // abort による終了は正常
        }
      })()
      trace("event.subscribe を開始しました")
    }

    const timer = setInterval(() => {
      for (const sessionID of sessions) void scanPending(sessionID)
    }, POLL_INTERVAL_MS)

    trace(`有効化完了（セッション検知数=${sessions.size}）`)

    return () => {
      controller.abort()
      clearInterval(timer)
      trace("プラグインを停止しました")
    }
  },
}
