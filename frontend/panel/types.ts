import type { Option, Value } from './bridge'

export type Instance = {
  idx: number
  name: string
  active: boolean
  active_in_od: boolean
  force_login_before_run: boolean
}

export type Task = {
  app_id: string
  app_name: string
  enabled: boolean
  configurable?: boolean
  jump?: boolean
}

export type NativeConfig = {
  instanceIdx: number
  account: { key: string; title: string; value: string; options: Option[] }[]
  tasks: Task[]
  instanceRun: string
  afterDone: string
  launchArgs: Record<string, Value>
}
