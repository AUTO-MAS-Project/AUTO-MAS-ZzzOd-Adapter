<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { usePanel, type Option, type Value } from './bridge'
import FieldInput from './FieldInput.vue'
import PlanList from './PlanList.vue'
import type { Task } from './types'

type Condition = { field: string; value: string; not?: boolean }
export type PlanColumn = {
  field: string
  title: string
  type: 'cascade' | 'select' | 'number' | 'team'
  options?: Option[]
  showWhen?: Condition | Condition[]
}
export type Plan = Record<string, Value>
export type Category = {
  name: string
  label: string
  mission_types: { name: string; display: string; missions: { name: string; display: string }[] }[]
}
type TaskField = {
  field: string
  title: string
  type: 'select' | 'bool' | 'number' | 'team' | 'plan_list'
  value: Value | Plan[]
  options: Option[]
  columns?: PlanColumn[]
  newItem?: Plan
}

const props = defineProps<{ task: Task; instanceIdx?: number }>()
const emit = defineEmits<{ close: [] }>()
const { t, get, post, run, report, notify } = usePanel()
const fields = ref<TaskField[]>()
const categories = ref<Category[]>([])
const loading = ref(true)

onMounted(async () => {
  const { app_id: appId } = props.task
  try {
    const result = await get<{ fields: TaskField[] }>('app-config', {
      appId,
      instanceIdx: props.instanceIdx,
    })
    if (result.fields.some(field => field.type === 'plan_list')) {
      categories.value = (
        await get<{ trainCategories: Category[] }>('options', { appId })
      ).trainCategories
    }
    fields.value = result.fields
  } catch (cause) {
    report(cause)
  } finally {
    loading.value = false
  }
})

function save() {
  void run(async () => {
    if (!fields.value) return
    const values = Object.fromEntries(fields.value.map(field => [field.field, field.value]))
    await post('app-config/save', {
      appId: props.task.app_id,
      instanceIdx: props.instanceIdx,
      values,
    })
    emit('close')
    await notify('success', t('taskConfigSaved'))
  })
}
</script>

<template>
  <section class="line stack">
    <h3>{{ task.app_name }} · {{ t('taskSettings') }}</h3>
    <p v-if="loading" class="hint">{{ t('loading') }}</p>
    <template v-for="field in fields" :key="field.field">
      <PlanList
        v-if="field.type === 'plan_list'"
        v-model="field.value as Plan[]"
        :columns="field.columns ?? []"
        :new-item="field.newItem ?? {}"
        :categories="categories"
      />
      <FieldInput
        v-else
        :label="field.title"
        :value="field.value as Value"
        :type="field.type === 'number' ? 'number' : undefined"
        :options="field.type === 'select' || field.type === 'team' ? field.options : undefined"
        @change="field.value = $event"
      />
    </template>
    <div class="row">
      <button type="button" :disabled="!fields?.length" @click="save">{{ t('save') }}</button>
      <button type="button" @click="emit('close')">{{ t('cancel') }}</button>
    </div>
  </section>
</template>
