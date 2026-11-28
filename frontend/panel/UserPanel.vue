<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { providePanel, type Value } from './bridge'
import type { Instance, NativeConfig, Task } from './types'
import FieldInput from './FieldInput.vue'
import InstanceManager from './InstanceManager.vue'
import TaskBoard from './TaskBoard.vue'
import TeamSettings from './TeamSettings.vue'
import UserGame from './UserGame.vue'

type Context = { rootPath: string; base: 'shared' | 'independent' | 'native' }
type App = Pick<Task, 'app_id' | 'enabled'>
type CatalogItem = Omit<Task, 'enabled'> & { default_group: boolean }

const {
  ready,
  config,
  revision,
  disabled,
  error,
  t,
  report,
  context,
  get,
  post,
  run,
  save,
  confirm,
} = providePanel()
const editor = ref<Context>()
const instances = ref<Instance[]>([])
const native = ref<NativeConfig>()
const catalog = ref<CatalogItem[]>([])
const importIdx = ref('')
const loading = ref(true)
const needsReload = ref(false)
const importRevision = ref(0)
const direct = computed(() => editor.value?.base === 'native')
const taskScope = computed(() =>
  JSON.stringify([
    editor.value?.rootPath,
    editor.value?.base,
    native.value?.instanceIdx,
    importRevision.value,
  ])
)
const taskList = computed(() => {
  if (direct.value) return native.value?.tasks ?? []
  let apps: App[]
  try {
    apps = JSON.parse(String(config.value.OneDragon?.AppList || '[]'))
  } catch (cause) {
    if (cause instanceof SyntaxError) return null
    throw cause
  }
  if (!Array.isArray(apps) || apps.some(item => typeof item?.app_id !== 'string')) return null
  const indexed = new Map(catalog.value.map(item => [item.app_id, item]))
  const saved = new Set(apps.map(item => item.app_id))
  return [
    ...catalog.value
      .filter(item => item.default_group && !saved.has(item.app_id))
      .map(item => ({ ...item, enabled: false })),
    ...apps.map(item => ({
      app_name: item.app_id,
      ...indexed.get(item.app_id),
      ...item,
      enabled: !!item.enabled,
    })),
  ]
})
const afterDoneOptions = computed(() => [
  { value: '无', label: t('afterDoneNone') },
  { value: '关闭游戏', label: t('afterDoneCloseGame') },
  { value: '关机', label: t('afterDoneShutdown') },
])
const instanceOptions = computed(() =>
  instances.value.map(item => ({
    label: `${item.idx} · ${item.name}`,
    value: String(item.idx),
  }))
)

function getNative(instanceIdx: number) {
  return get<NativeConfig>('native-config', { instanceIdx })
}

watch(
  [ready, revision],
  async ([isReady], _, onCleanup) => {
    if (!isReady) return
    let current = true
    onCleanup(() => {
      current = false
    })
    loading.value = true
    try {
      const status = await context<Context>()
      if (!current) return
      editor.value = status
      if (status.rootPath) {
        const [instanceData, taskData] = await Promise.all([
          get<{ data: Instance[] }>('instances'),
          status.base === 'native' ? null : get<{ data: CatalogItem[] }>('catalog'),
        ])
        if (!current) return
        const items = instanceData.data
        const selected =
          items.find(item => item.idx === native.value?.instanceIdx) ??
          items.find(item => item.active) ??
          items[0]
        instances.value = items
        catalog.value = taskData?.data ?? []
        native.value = undefined
        const next =
          status.base === 'native' && selected ? await getNative(selected.idx) : undefined
        if (current) native.value = next
      } else {
        instances.value = []
        native.value = undefined
        catalog.value = []
      }
      if (current) needsReload.value = false
    } catch (cause) {
      if (current) {
        report(cause)
      }
    } finally {
      if (current) loading.value = false
    }
  },
  { immediate: true }
)

function selectInstance(value: Value) {
  void run(async () => {
    native.value = await getNative(Number(value))
  })
}

async function updateInstances(items: Instance[], added?: number) {
  // The parent operation already holds the panel write guard.
  instances.value = items
  const selected =
    added ??
    items.find(item => item.idx === native.value?.instanceIdx)?.idx ??
    items.find(item => item.active)?.idx ??
    items[0]?.idx
  if (selected !== native.value?.instanceIdx) {
    native.value = undefined
    if (selected !== undefined) native.value = await getNative(selected)
  }
}

async function persistNative(patch: object) {
  native.value = await post<NativeConfig>('native-config/save', {
    instanceIdx: native.value!.instanceIdx,
    ...patch,
  })
}

function saveNative(patch: object) {
  void run(() => persistNative(patch))
}

function saveTasks(tasks: Task[]) {
  const values = tasks.map(({ app_id, enabled }) => ({ app_id, enabled }))
  if (direct.value) saveNative({ tasks: values })
  else void run(() => save('OneDragon', 'AppList', JSON.stringify(values)))
}

function importConfig() {
  void run(async () => {
    if (!(await confirm(t('importConfirmDesc'), true))) return
    const previousRevision = revision.value
    await post('import', { instanceIdx: Number(importIdx.value) })
    importRevision.value++
    needsReload.value = revision.value === previousRevision
  })
}
</script>

<template>
  <p id="status" role="status" :data-error="error ? '' : undefined">
    {{ error || (loading ? t('loading') : '') }}
  </p>
  <p v-if="needsReload" role="status" class="card">{{ t('importReload') }}</p>
  <fieldset v-else-if="editor" :disabled="disabled || loading" class="stack">
    <p v-if="!editor.rootPath" class="hint">{{ t('rootPathRequired') }}</p>
    <section v-else class="card stack">
      <template v-if="direct">
        <div class="grid" v-if="instances.length">
          <FieldInput
            :label="t('directInstance')"
            :value="native ? String(native.instanceIdx) : ''"
            :options="instanceOptions"
            @change="selectInstance"
          />
          <FieldInput
            v-if="native"
            :label="t('directInstanceRun')"
            :value="native.instanceRun"
            :options="[
              { value: '仅运行当前', label: t('instanceRunCurrent') },
              { value: '全部实例', label: t('instanceRunAll') },
            ]"
            @change="saveNative({ instanceRun: $event })"
          />
        </div>
        <p v-else class="hint">{{ t('directPickInstanceFirst') }}</p>
        <InstanceManager :instances="instances" :update-instances="updateInstances" />
      </template>
      <div v-else-if="instances.length" class="row">
        <label>
          {{ t('quickImport') }}
          <select v-model="importIdx">
            <option disabled value="">{{ t('importPlaceholder') }}</option>
            <option v-for="item in instanceOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </option>
          </select>
        </label>
        <button type="button" :disabled="!importIdx" @click="importConfig">
          {{ t('import') }}
        </button>
      </div>
    </section>
    <template v-if="!direct || native">
      <UserGame :native="native" :persist-native="persistNative" @save-native="saveNative" />
      <section class="card stack">
        <FieldInput
          :label="t('afterDone')"
          :value="native?.afterDone ?? config.OneDragon.AfterDone"
          :options="afterDoneOptions"
          @change="
            direct
              ? saveNative({ afterDone: $event })
              : run(() => save('OneDragon', 'AfterDone', $event))
          "
        />
        <template v-if="editor.rootPath">
          <TaskBoard
            v-if="taskList"
            :key="'tasks' + taskScope"
            :tasks="taskList"
            :instance-idx="native?.instanceIdx"
            @save="saveTasks"
          />
          <p v-else class="field-error">{{ t('appListInvalid') }}</p>
          <TeamSettings :key="'teams' + taskScope" :instance-idx="native?.instanceIdx" />
        </template>
      </section>
    </template>
  </fieldset>
</template>
