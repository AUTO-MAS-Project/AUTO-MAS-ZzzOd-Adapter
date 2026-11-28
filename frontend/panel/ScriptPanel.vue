<script setup lang="ts">
import { ref, watch } from 'vue'
import { providePanel, type Value } from './bridge'
import FieldInput from './FieldInput.vue'
import SlotManager from './SlotManager.vue'

const { config, ready, disabled, error, revision, t, report, get, context, run, save, pickExe } =
  providePanel()
const rootPath = ref('')
const launchers = ref<{ original_available: boolean; integrated_available: boolean }>()
const limits = [
  { field: 'HardTimeLimit', label: 'hardTimeLimit', min: 1 },
  { field: 'ProxyTimesLimit', label: 'dailyLimit', min: 0 },
  { field: 'RunTimesLimit', label: 'retryLimit', min: 1 },
  { field: 'RunTimeLimit', label: 'runTimeout', min: 1 },
]

watch(
  [ready, revision],
  async ([isReady], _, onCleanup) => {
    if (!isReady) return
    let current = true
    onCleanup(() => {
      current = false
    })
    try {
      const status = await context<{ rootPath: string }>()
      if (!current) return
      rootPath.value = status.rootPath
      launchers.value = undefined
      if (status.rootPath) {
        const result = await get<NonNullable<typeof launchers.value>>('launchers')
        if (current) launchers.value = result
      }
    } catch (cause) {
      if (current) report(cause)
    }
  },
  { immediate: true }
)

function saveGame(field: string, value: Value) {
  void run(() => save('Game', field, value))
}

function chooseGame() {
  void run(async () => {
    const path = await pickExe()
    if (path) await save('Game', 'Path', path)
  })
}
</script>

<template>
  <p id="status" role="status" :data-error="error ? '' : undefined">
    {{ error || (!ready ? t('loading') : '') }}
  </p>
  <template v-if="ready">
    <section class="card">
      <h2>{{ t('gameConfiguration') }}</h2>
      <fieldset :disabled="disabled" class="stack">
        <FieldInput
          :label="t('accountSwitch')"
          :value="config.Game.AccountSwitch"
          :options="[
            { value: '单实例切换', label: t('accountSwitchSingle') },
            { value: '多实例切换', label: t('accountSwitchMulti') },
          ]"
          @change="saveGame('AccountSwitch', $event)"
        />
        <FieldInput
          :label="t('enableGameConfiguration')"
          :value="config.Game.Enabled"
          @change="saveGame('Enabled', $event)"
        />
        <fieldset v-if="config.Game.Enabled" class="grid">
          <div class="row">
            <FieldInput
              :label="t('gamePath')"
              :value="config.Game.Path"
              @change="saveGame('Path', $event || null)"
            />
            <button type="button" @click="chooseGame">{{ t('browse') }}</button>
          </div>
          <FieldInput
            :label="t('gameArguments')"
            :value="config.Game.Arguments"
            @change="saveGame('Arguments', $event)"
          />
          <FieldInput
            :label="t('startupWait')"
            :value="config.Game.WaitTime"
            type="number"
            :min="0"
            :max="9999"
            @change="saveGame('WaitTime', $event)"
          />
          <FieldInput
            :label="t('launchGameBeforeTask')"
            :value="config.Game.LaunchBeforeTask"
            @change="saveGame('LaunchBeforeTask', $event)"
          />
          <FieldInput
            :label="t('closeGameOnFinish')"
            :value="config.Game.CloseOnFinish"
            @change="saveGame('CloseOnFinish', $event)"
          />
        </fieldset>
      </fieldset>
    </section>
    <section class="card">
      <h2>{{ t('runConfiguration') }}</h2>
      <fieldset :disabled="disabled" class="grid">
        <FieldInput
          v-for="limit in limits"
          :key="limit.field"
          :label="t(limit.label)"
          :value="config.Run[limit.field]"
          type="number"
          :min="limit.min"
          :max="9999"
          @change="run(() => save('Run', limit.field, $event))"
        />
      </fieldset>
    </section>
    <section class="card">
      <h2>{{ t('launcherMode') }}</h2>
      <p v-if="!rootPath" class="hint">{{ t('rootPathRequired') }}</p>
      <dl v-else-if="launchers">
        <dt>{{ t('launcherOriginal') }}</dt>
        <dd>{{ t(launchers.original_available ? 'available' : 'unavailable') }}</dd>
        <dt>{{ t('launcherIntegrated') }}</dt>
        <dd>{{ t(launchers.integrated_available ? 'available' : 'unavailable') }}</dd>
      </dl>
    </section>
    <SlotManager v-if="rootPath" :key="rootPath" />
  </template>
</template>
