import {
  host,
  TRANSCRIPT_DIRECTIVE_AREA,
  type HermesGatewayEvent,
  type HermesPlugin,
  type TranscriptDirectiveContribution
} from '@hermes/plugin-sdk'
import { useEffect, useSyncExternalStore } from 'react'

import { OpenUISurface } from './surface.tsx'
import { OpenUIStreamStore } from './stream.ts'

const OPENUI_ID_RE = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/
export const OPENUI_UNAVAILABLE = 'Interactive card unavailable.'
const QUERY_REST_TIMEOUT_MS = 15_000

type QueryToolProvider = Record<
  string,
  (args: Record<string, unknown>) => Promise<unknown>
>
type PluginRest = <T>(
  path: string,
  options?: {
    readonly body?: unknown
    readonly method?: string
    readonly timeoutMs?: number
  }
) => Promise<T>

export function createOpenUIQueryTools(rest: PluginRest): QueryToolProvider {
  return {
    query_data: args =>
      rest('/query', {
        body: { arguments: args },
        method: 'POST',
        timeoutMs: QUERY_REST_TIMEOUT_MS
      })
  }
}

type SessionPayload = Readonly<{
  stored_session_id?: unknown
}>

interface TranscriptMessage {
  readonly role?: unknown
  readonly text?: unknown
}

interface SessionHistory {
  readonly messages?: readonly TranscriptMessage[]
}

export type SessionHistoryReader = (sessionId: string) => Promise<readonly unknown[]>

function stringValue(value: unknown): string | null {
  return typeof value === 'string' && value.length > 0 ? value : null
}

export function shouldHydrateHistory(
  card: undefined | { readonly complete: boolean; readonly source: string },
  finished: boolean,
  id: null | string,
  sessionId: null | string
): boolean {
  return Boolean(
    finished &&
      id &&
      sessionId &&
      (!card || !card.complete || card.source.trim().length === 0)
  )
}

/**
 * The directive renderer receives the durable session id, while gateway
 * message frames carry the runtime id. `session.info` supplies both ids.
 */
export class OpenUIBridge {
  private readonly storedByRuntime = new Map<string, string>()
  private readonly runtimeByStored = new Map<string, string>()
  private readonly hydrating = new Map<string, Promise<boolean>>()
  private readonly hydrated = new Set<string>()
  private readonly store = new OpenUIStreamStore()

  constructor(
    private readonly readHistory: SessionHistoryReader = async sessionId => {
      const result = await host.request<SessionHistory>('session.history', {
        session_id: sessionId
      })

      return Array.isArray(result.messages) ? result.messages : []
    }
  ) {}

  getCard = (sessionId: string | null | undefined, id: string) =>
    sessionId ? this.store.getCard(this.storedByRuntime.get(sessionId) ?? sessionId, id) : undefined

  private liveSessionId(storedId: string): string {
    return this.runtimeByStored.get(storedId) ?? storedId
  }

  hydrate(sessionId: null | string): Promise<boolean> {
    const storedId = stringValue(sessionId)

    if (!storedId) {
      return Promise.resolve(false)
    }

    if (this.hydrated.has(storedId)) {
      return Promise.resolve(true)
    }

    const existing = this.hydrating.get(storedId)

    if (existing) {
      return existing
    }

    const hydration = (async (): Promise<boolean> => {
      try {
        const messages = await this.readHistory(this.liveSessionId(storedId))

        for (const value of messages) {
          if (typeof value !== 'object' || value === null) {
            continue
          }

          const message = value as TranscriptMessage
          const text = message.role === 'assistant' ? stringValue(message.text) : null

          if (text) {
            this.store.hydrateCompletedText(storedId, text)
          }
        }

        this.hydrated.add(storedId)
        return true
      } catch {
        return false
      }
    })().finally(() => {
      this.hydrating.delete(storedId)
    })

    this.hydrating.set(storedId, hydration)
    return hydration
  }

  handleEvent(event: HermesGatewayEvent): boolean {
    const runtimeId = stringValue(event.session_id)

    if (!runtimeId) {
      return false
    }

    const payload = event.payload as SessionPayload | undefined
    const informedStoredId = stringValue(payload?.stored_session_id)

    if (informedStoredId) {
      this.storedByRuntime.set(runtimeId, informedStoredId)
      this.runtimeByStored.set(informedStoredId, runtimeId)
    }

    const storedId = informedStoredId ?? this.storedByRuntime.get(runtimeId)

    if (!storedId) {
      return false
    }

    return this.store.handleEvent({
      ...event,
      session_id: storedId
    })
  }

  subscribe = this.store.subscribe
}

function directiveId(attrs: Readonly<Record<string, string>>): string | null {
  const id = attrs.id?.trim() ?? ''
  return OPENUI_ID_RE.test(id) ? id : null
}

function OpenUIDirective({
  bridge,
  id,
  sessionId,
  status,
  streaming,
  queryTools
}: {
  readonly bridge: OpenUIBridge
  readonly id: null | string
  readonly queryTools: QueryToolProvider
  readonly sessionId: null | string
  readonly status?: 'complete' | 'error' | 'interrupted' | 'streaming'
  readonly streaming: boolean
}) {
  const finished = status ? status !== 'streaming' : !streaming
  const getCardSnapshot = () => id ? bridge.getCard(sessionId, id) : undefined
  const card = useSyncExternalStore(
    bridge.subscribe,
    getCardSnapshot,
    getCardSnapshot
  )
  const usable =
    Boolean(id && sessionId && card?.source.trim()) &&
    (!finished || Boolean(card?.complete))

  useEffect(() => {
    if (shouldHydrateHistory(card, finished, id, sessionId)) {
      void bridge.hydrate(sessionId).catch(() => false)
    }
  }, [bridge, card, finished, id, sessionId])

  return (
    <div
      className="hermes-openui-card-mount"
      data-hermes-openui-card
      style={{ display: 'contents' }}
    >
      {usable && id && sessionId && card ? (
        <OpenUISurface
          identity={id}
          onFollowUp={(message, destination) => submitOpenUIFollowUp(destination, message)}
          sessionId={sessionId}
          source={card.source}
          streaming={streaming || card.streaming}
          toolProvider={queryTools}
        />
      ) : finished ? (
        <p className="hermes-openui-unavailable" role="status">
          <style>{`
            .hermes-openui-unavailable {
              color: var(--ui-text-secondary);
              font-size: 0.75rem;
              margin: 6px 0;
            }
          `}</style>
          {OPENUI_UNAVAILABLE}
        </p>
      ) : null}
    </div>
  )
}

export function submitOpenUIFollowUp(
  sessionId: null | string,
  message: string
): boolean {
  const destination = sessionId?.trim()
  const text = message.trim()

  return Boolean(destination && text && host.composer.submit(destination, text))
}

const plugin: HermesPlugin = {
  id: 'hermes-openui',
  name: 'OpenUI cards',
  description: 'Renders interactive OpenUI cards inside assistant replies.',
  register(ctx) {
    const bridge = new OpenUIBridge()
    const queryTools = createOpenUIQueryTools(ctx.rest)
    const contribution: TranscriptDirectiveContribution = {
      name: 'openui',
      render: ({ attrs, sessionId, status, streaming }) => {
        const id = directiveId(attrs)

        return (
          <OpenUIDirective
            bridge={bridge}
            id={id}
            queryTools={queryTools}
            sessionId={sessionId}
            status={status}
            streaming={streaming}
          />
        )
      }
    }

    ctx.onEvent('*', event => {
      bridge.handleEvent(event)
    })

    ctx.register({
      id: 'transcript-directive',
      area: TRANSCRIPT_DIRECTIVE_AREA,
      data: contribution
    })
  }
}

export default plugin
