<script setup lang="ts">
import { computed } from 'vue'
import { usePanel, type Value } from './bridge'
import FieldInput from './FieldInput.vue'
import type { NativeConfig } from './types'

const props = defineProps<{
  native?: NativeConfig
  persistNative: (patch: object) => Promise<void>
}>()
const emit = defineEmits<{ saveNative: [patch: object] }>()
const { config, t, run, save, pickExe } = usePanel()

const regions = computed(() =>
  ['cn', 'cn_b', 'us', 'eu', 'asia', 'twhkmo'].map(value => ({
    value,
    label: t('region.' + value),
  }))
)
const languages = computed(() =>
  ['cn', 'en'].map(value => ({ value, label: t('language.' + value) }))
)
const nativeLabels: Record<string, string> = {
  game_region: 'gameRegion',
  game_path: 'gamePath',
  account: 'account',
  password: 'password',
  bilibili_account_name: 'bilibiliAccount',
  game_language: 'gameLanguage',
}

const launchFields = computed(() => [
  { field: 'LaunchArgument', native: 'launch_argument', label: t('launchArgsTitle') },
  {
    field: 'ScreenSize',
    native: 'screen_size',
    label: t('screenSize'),
    options: ['1920x1080', '2560x1440', '3840x2160'].map(value => ({ value, label: value })),
  },
  {
    field: 'FullScreen',
    native: 'full_screen',
    label: t('fullScreen'),
    options: [
      { value: '0', label: t('fullScreenWindowed') },
      { value: '1', label: t('fullScreenFullscreen') },
    ],
  },
  { field: 'PopupWindow', native: 'popup_window', label: t('popupWindow') },
  { field: 'Dx12', native: 'dx12', label: t('dx12') },
  {
    field: 'Monitor',
    native: 'monitor',
    label: t('monitor'),
    options: ['1', '2', '3', '4'].map(value => ({ value, label: value })),
  },
  { field: 'LaunchArgumentAdvance', native: 'launch_argument_advance', label: t('advanceArgs') },
])
const launchEnabled = computed(
  () => props.native?.launchArgs.launch_argument ?? config.value.Game.LaunchArgument
)

function saveManaged(field: string, value: Value) {
  void run(() => save('Game', field, value))
}

function saveAccount(field: string, value: Value) {
  emit('saveNative', { account: { [field]: value } })
}

function saveLaunch(field: string, nativeField: string, value: Value) {
  if (props.native)
    emit('saveNative', { launchArgs: { ...props.native.launchArgs, [nativeField]: value } })
  else saveManaged(field, value)
}

function chooseGame() {
  void run(async () => {
    const path = await pickExe()
    if (!path) return
    if (props.native) await props.persistNative({ account: { game_path: path } })
    else await save('Game', 'GamePath', path)
  })
}
</script>

<template>
  <section class="card stack">
    <h2>{{ t('gameConfiguration') }}</h2>
    <div v-if="native" class="grid">
      <div
        v-for="field in native.account"
        :key="field.key"
        :class="{ row: field.key === 'game_path' }"
      >
        <FieldInput
          :label="t(nativeLabels[field.key] ?? field.title)"
          :value="field.value"
          :type="field.key === 'password' ? 'password' : 'text'"
          :options="
            field.key === 'game_region'
              ? regions
              : field.key === 'game_language'
                ? languages
                : field.options.length
                  ? field.options
                  : undefined
          "
          @change="saveAccount(field.key, $event)"
        />
        <button v-if="field.key === 'game_path'" type="button" @click="chooseGame">
          {{ t('browse') }}
        </button>
      </div>
    </div>
    <div v-else class="grid">
      <FieldInput
        :label="t('gameRegion')"
        :value="config.Game.GameRegion"
        :options="regions"
        @change="saveManaged('GameRegion', $event)"
      />
      <FieldInput
        :label="t('gameLanguage')"
        :value="config.Game.GameLanguage"
        :options="languages"
        @change="saveManaged('GameLanguage', $event)"
      />
      <div class="row">
        <FieldInput
          :label="t('gamePath')"
          :value="config.Game.GamePath"
          @change="saveManaged('GamePath', $event || null)"
        />
        <button type="button" @click="chooseGame">{{ t('browse') }}</button>
      </div>
      <FieldInput
        v-if="config.Game.GameRegion === 'cn_b'"
        :label="t('bilibiliAccount')"
        :value="config.Game.BilibiliAccountName"
        @change="saveManaged('BilibiliAccountName', $event)"
      />
    </div>
    <div class="grid">
      <template v-for="field in launchFields" :key="field.field">
        <FieldInput
          v-if="field.field === 'LaunchArgument' || launchEnabled"
          :label="field.label"
          :value="native ? native.launchArgs[field.native] : config.Game[field.field]"
          :options="field.options"
          @change="saveLaunch(field.field, field.native, $event)"
        />
      </template>
    </div>
  </section>
</template>
