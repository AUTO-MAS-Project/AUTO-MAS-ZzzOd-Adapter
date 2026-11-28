<script setup lang="ts">
import { ref } from 'vue'
import { usePanel } from './bridge'
import FieldInput from './FieldInput.vue'
import type { Instance } from './types'

const props = defineProps<{
  instances: Instance[]
  updateInstances: (instances: Instance[], added?: number) => Promise<void>
}>()
const { t, post, run, confirm } = usePanel()
const name = ref('')

function update(path: string, instanceIdx: number, fields: object = {}) {
  void run(async () => {
    const result = await post<{ data: Instance[] }>('instances/' + path, { instanceIdx, ...fields })
    await props.updateInstances(result.data)
  })
}

function add() {
  void run(async () => {
    const result = await post<{ data: Instance[] }>('instances/add', { name: name.value.trim() })
    const added = result.data.find(
      item => !props.instances.some(previous => previous.idx === item.idx)
    )
    name.value = ''
    await props.updateInstances(result.data, added?.idx)
  })
}

function remove(instance: Instance) {
  void run(async () => {
    if (!(await confirm(t('deleteInstanceConfirm', { inst: instance.name }), true))) return
    const result = await post<{ data: Instance[] }>('instances/delete', {
      instanceIdx: instance.idx,
    })
    await props.updateInstances(result.data)
  })
}
</script>

<template>
  <details>
    <summary>{{ t('instancesManage') }}</summary>
    <form class="row" @submit.prevent="add">
      <label>{{ t('instanceName') }} <input v-model.trim="name" required /></label>
      <button :disabled="!name">{{ t('addInstance') }}</button>
    </form>
    <div class="scroll-list">
      <section v-for="item in instances" :key="item.idx" class="line stack">
        <div class="row">
          <strong>{{ item.idx }} · {{ item.name }}</strong>
          <span v-if="item.active">{{ t('instanceActiveTag') }}</span>
          <button v-else type="button" @click="update('set-active', item.idx)">
            {{ t('setInstanceActive') }}
          </button>
          <button type="button" @click="remove(item)">{{ t('deleteInstance') }}</button>
        </div>
        <div class="grid">
          <FieldInput
            :label="t('renameInstance')"
            :value="item.name"
            @change="update('rename', item.idx, { name: String($event).trim() })"
          />
          <div>
            <FieldInput
              :label="t('instanceActiveInOd')"
              :value="item.active_in_od"
              @change="update('active-in-od', item.idx, { activeInOd: $event })"
            />
            <FieldInput
              :label="t('instanceForceLoginSwitch')"
              :value="item.force_login_before_run"
              @change="update('force-login', item.idx, { forceLogin: $event })"
            />
          </div>
        </div>
      </section>
    </div>
  </details>
</template>
