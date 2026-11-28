import { computed, inject, onMounted, provide, ref, shallowRef, type InjectionKey } from 'vue'
import locale from '../../src/zzzod_adapter/i18n/zh-CN.json'

export type Value = string | number | boolean | null
export type Option = { label: string; value: string }
type Config = Record<string, Record<string, Value>>
type State = { locale: string; i18nRevision: number; locked: boolean; busy: boolean }
type Target = { scriptId: string; userId: string | null }
type Snapshot = { config: Config }
type Reply<T> = {
  ok: boolean
  status: number
  data: T & { code?: number; message?: string; detail?: string }
}
type Confirmation = { title?: string; message: string; danger?: boolean }
type Translation = { key: string; params: Record<string, string> }

declare function connectPanel(): {
  getContext(): Promise<Snapshot & State & { target: Target }>
  translate(keys: Translation[]): Promise<{ messages: Record<string, string> }>
  saveConfig(
    changes: { group: string; field: string; value: Value }[],
    phase: 'commit'
  ): Promise<{ ok: boolean; message?: string }>
  request<T>(method: 'GET' | 'POST', path: string, body?: object): Promise<Reply<T>>
  pickPath(options: {
    mode: 'file'
    filters: { name: string; extensions: string[] }[]
  }): Promise<{ path?: string; code?: string }>
  confirm(options: Confirmation): Promise<{ confirmed: boolean }>
  notify(severity: 'success', message: string): Promise<void>
  onStateChange(callback: (state: State) => void): void
  onConfigReloaded(callback: (snapshot: Snapshot) => void): void
}

const namespace = 'plugins.zzzod_adapter.'
const labels = Object.entries(locale)
  .filter(([key]) => key.startsWith(namespace + 'panel.'))
  .map(([key, text]) => ({
    key: key.slice(namespace.length),
    params: Object.fromEntries(
      [...text.matchAll(/\{(\w+)\}/g)].map(([token, name]) => [name, token])
    ),
  }))
const fallback: Record<string, string> = locale
const panelKey: InjectionKey<ReturnType<typeof createPanel>> = Symbol()

function createPanel() {
  const panel = connectPanel()
  const config = shallowRef<Config>({})
  const target = shallowRef<Target>()
  const state = shallowRef<State>()
  const messages = shallowRef<Record<string, string>>({})
  const revision = ref(0)
  const error = ref('')
  const ready = ref(false)
  const working = ref(false)
  const disabled = computed(
    () => !ready.value || state.value?.locked || state.value?.busy || working.value
  )

  function t(key: string, params: Record<string, string | number> = {}) {
    const label = 'panel.' + key
    return (messages.value[label] ?? fallback[namespace + label] ?? key).replace(
      /\{(\w+)\}/g,
      (token, name: string) => String(params[name] ?? token)
    )
  }

  function report(cause: unknown) {
    error.value = cause instanceof Error ? cause.message : String(cause)
  }

  async function applyState(next: State) {
    const previous = state.value
    state.value = next
    if (previous?.locale === next.locale && previous.i18nRevision === next.i18nRevision) return
    const { messages: translated } = await panel.translate(labels)
    if (state.value.locale === next.locale && state.value.i18nRevision === next.i18nRevision) {
      document.documentElement.lang = next.locale
      messages.value = translated
    }
  }

  onMounted(async () => {
    try {
      const initial = await panel.getContext()
      target.value = initial.target
      config.value = initial.config
      panel.onStateChange(next => void applyState(next).catch(report))
      panel.onConfigReloaded(snapshot => {
        config.value = snapshot.config
        revision.value++
      })
      await applyState(initial)
      ready.value = true
    } catch (cause) {
      report(cause)
    }
  })

  async function request<T>(method: 'GET' | 'POST', path: string, body?: object) {
    const result = await panel.request<T>(method, path, body)
    if (!result.ok || (result.data?.code !== undefined && result.data.code !== 200)) {
      throw new Error(result.data?.message || result.data?.detail || `HTTP ${result.status}`)
    }
    return result.data
  }

  function ids() {
    const { scriptId, userId } = target.value!
    return userId ? { scriptId, userId } : { scriptId }
  }

  function get<T>(path: string, query: Record<string, string | number | undefined> = {}) {
    const params = new URLSearchParams()
    for (const [key, value] of Object.entries({ ...ids(), ...query })) {
      if (value !== undefined) params.set(key, String(value))
    }
    return request<T>('GET', `/zzzod/${path}?${params}`)
  }

  function post<T>(path: string, fields: object = {}) {
    return request<T>('POST', '/zzzod/' + path, { ...ids(), ...fields })
  }

  function context<T>() {
    const { scriptId, userId } = ids()
    return request<T>(
      'GET',
      userId ? `/editor/user/${scriptId}/${userId}` : `/editor/script/${scriptId}`
    )
  }

  async function run(operation: () => Promise<void>) {
    if (disabled.value) return
    error.value = ''
    working.value = true
    try {
      await operation()
    } catch (cause) {
      report(cause)
    } finally {
      working.value = false
    }
  }

  async function save(group: string, field: string, value: Value) {
    const result = await panel.saveConfig([{ group, field, value }], 'commit')
    if (!result.ok) throw new Error(result.message || t('saveFailed'))
    config.value = { ...config.value, [group]: { ...config.value[group], [field]: value } }
  }

  async function pickExe() {
    const result = await panel.pickPath({
      mode: 'file',
      filters: [{ name: '*.exe', extensions: ['exe'] }],
    })
    if (result.code) throw new Error(t('pickerUnavailable'))
    if (result.path && result.path.split(/[\\/]/).pop()?.toLowerCase() !== 'zenlesszonezero.exe') {
      throw new Error(t('pickGameExe'))
    }
    return result.path
  }

  async function confirm(message: string, danger = false) {
    return (await panel.confirm({ message, danger })).confirmed
  }

  return {
    config,
    ready,
    disabled,
    error,
    revision,
    t,
    report,
    get,
    post,
    context,
    run,
    save,
    pickExe,
    confirm,
    notify: panel.notify,
  }
}

export function providePanel() {
  const panel = createPanel()
  provide(panelKey, panel)
  return panel
}

export function usePanel() {
  return inject(panelKey)!
}
