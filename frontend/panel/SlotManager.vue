<script setup lang="ts">
import { computed, ref } from 'vue'
import { usePanel, type Option } from './bridge'

type Slot = {
  idx: number
  kind: 'native' | 'mas' | 'orphan'
  has_dir: boolean
  size: number
  owners: { userId: string; scriptName: string; userName: string }[]
}
type Recycle = {
  slot: number
  ts: string
  kind: 'slot' | 'mas'
  files: number
  size: number
  path: string
}

const { disabled, t, context, get, post, run, confirm, notify } = usePanel()
const slots = ref<Slot[]>([])
const recycle = ref<Recycle[]>([])
const loaded = ref(false)
const restoring = ref<Recycle>()
const users = ref<Option[]>([])
const user = ref('')
const name = ref('')
const target = ref<'existing' | 'new'>('existing')
const orphanCount = computed(() => slots.value.filter(slot => slot.kind === 'orphan').length)
const kinds = { native: 'slotKindNative', mas: 'slotKindMas', orphan: 'slotKindOrphan' }

async function refresh() {
  const [slotsResponse, recycleResponse] = await Promise.all([
    get<{ data: Slot[] }>('slots'),
    get<{ data: Recycle[] }>('recycle'),
  ])
  slots.value = slotsResponse.data
  recycle.value = recycleResponse.data
  loaded.value = true
}

function load(event: Event) {
  if ((event.target as HTMLDetailsElement).open && !loaded.value) void run(refresh)
}

function clean() {
  void run(async () => {
    if (!(await confirm(t('slotsCleanConfirm', { count: orphanCount.value }), true))) return
    const result = await post<{ data: number[] }>('slots/clean')
    await notify('success', t('slotsCleanDone', { count: result.data.length }))
    await refresh()
  })
}

function clear() {
  void run(async () => {
    const size = formatSize(recycle.value.reduce((total, entry) => total + entry.size, 0))
    if (!(await confirm(t('recycleClearConfirm', { count: recycle.value.length, size }), true)))
      return
    const result = await post<{ data: number }>('recycle/clear')
    restoring.value = undefined
    await notify('success', t('recycleClearDone', { count: result.data }))
    await refresh()
  })
}

function select(entry: Recycle) {
  void run(async () => {
    users.value = (await context<{ users: Option[] }>()).users
    target.value = users.value.length ? 'existing' : 'new'
    user.value = ''
    name.value = t('recycleRestoreNewUserNameDefault')
    restoring.value = entry
  })
}

function restore(entry: Recycle) {
  void run(async () => {
    if (!(await confirm(t('recycleRestoreConfirm', { slot: entry.slot }), true))) return
    await post('recycle/restore', {
      slot: entry.slot,
      ts: entry.ts,
      ...(target.value === 'existing'
        ? { targetUser: user.value }
        : { newUserName: name.value.trim() }),
    })
    restoring.value = undefined
    await notify('success', t('recycleRestoreDone'))
    await refresh()
  })
}

function formatSize(size: number) {
  return new Intl.NumberFormat(document.documentElement.lang, {
    style: 'unit',
    unit: 'kilobyte',
    maximumFractionDigits: 1,
  }).format(size / 1024)
}
</script>

<template>
  <details class="card" @toggle="load">
    <summary>{{ t('slotsManage') }}</summary>
    <fieldset :disabled="disabled">
      <div class="actions">
        <button type="button" @click="run(refresh)">{{ t('slotsRefresh') }}</button>
        <button type="button" :disabled="!orphanCount" @click="clean">{{ t('slotsClean') }}</button>
      </div>
      <div v-if="slots.length" class="scroll-list">
        <table>
          <thead>
            <tr>
              <th>{{ t('slotColIdx') }}</th>
              <th>{{ t('slotColKind') }}</th>
              <th>{{ t('slotColOwner') }}</th>
              <th>{{ t('slotColDir') }}</th>
              <th>{{ t('slotColSize') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="slot in slots" :key="slot.idx">
              <td>{{ slot.idx }}</td>
              <td>
                {{ t(kinds[slot.kind]) }}
                <span v-if="slot.kind === 'native' && slot.owners.length" class="field-error">{{
                  t('slotNativeConflict')
                }}</span>
              </td>
              <td>
                {{
                  slot.owners.map(owner => owner.scriptName + ' / ' + owner.userName).join(', ') ||
                  '–'
                }}
              </td>
              <td>{{ t(slot.has_dir ? 'slotHasDir' : 'slotNoDir') }}</td>
              <td>{{ formatSize(slot.size) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else-if="loaded" class="hint">{{ t('slotEmpty') }}</p>

      <div class="actions">
        <h3>{{ t('slotTabRecycle') }}</h3>
        <button type="button" :disabled="!recycle.length" @click="clear">
          {{ t('recycleClear') }}
        </button>
      </div>
      <p v-if="loaded && !recycle.length" class="hint">{{ t('recycleEmpty') }}</p>
      <div v-if="recycle.length" class="scroll-list">
        <div v-for="entry in recycle" :key="entry.path" class="line">
          <div class="row">
            <strong>{{ t('recycleColSlot') }} {{ entry.slot }}</strong>
            <span>{{ t(entry.kind === 'mas' ? 'recycleKindMas' : 'recycleKindSlot') }}</span>
            <span>{{ entry.ts }}</span>
            <span>{{ t('recycleColFiles') }} {{ entry.files }} · {{ formatSize(entry.size) }}</span>
            <button v-if="entry.kind === 'slot'" type="button" @click="select(entry)">
              {{ t('recycleRestore') }}
            </button>
          </div>
          <code>{{ entry.path }}</code>
        </div>
      </div>
      <form v-if="restoring" class="line stack" @submit.prevent="restore(restoring)">
        <h3>{{ t('recycleRestore') }} · {{ restoring.ts }}</h3>
        <label>
          {{ t('restoreTarget') }}
          <select v-model="target">
            <option value="existing" :disabled="!users.length">
              {{ t('recycleRestoreToUser') }}
            </option>
            <option value="new">{{ t('recycleRestoreToNewUser') }}</option>
          </select>
        </label>
        <label v-if="target === 'existing'">
          {{ t('recycleRestoreToUser') }}
          <select v-model="user" required>
            <option disabled value="">{{ t('recycleRestoreUserPlaceholder') }}</option>
            <option v-for="option in users" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </label>
        <label v-else
          >{{ t('recycleRestoreNewUserName') }} <input v-model.trim="name" required
        /></label>
        <div class="row">
          <button :disabled="target === 'existing' ? !user : !name">
            {{ t('recycleRestore') }}
          </button>
          <button type="button" @click="restoring = undefined">{{ t('cancel') }}</button>
        </div>
      </form>
    </fieldset>
  </details>
</template>
