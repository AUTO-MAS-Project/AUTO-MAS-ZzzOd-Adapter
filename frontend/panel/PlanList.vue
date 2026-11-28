<script setup lang="ts">
import { usePanel, type Value } from './bridge'
import FieldInput from './FieldInput.vue'
import type { Category, Plan, PlanColumn } from './TaskSettings.vue'

const props = defineProps<{ columns: PlanColumn[]; newItem: Plan; categories: Category[] }>()
const plans = defineModel<Plan[]>({ required: true })
const { t } = usePanel()

const categoryOf = (plan: Plan) =>
  props.categories.find(category => category.name === plan.category_name)
const missionTypeOf = (plan: Plan) =>
  categoryOf(plan)?.mission_types.find(type => type.name === plan.mission_type_name)

function optionsFor(column: PlanColumn, plan: Plan) {
  if (column.type !== 'cascade') return column.options
  if (column.field === 'mission_type_name') {
    return (categoryOf(plan)?.mission_types ?? []).map(item => ({
      value: item.name,
      label: item.display,
    }))
  }
  if (column.field === 'mission_name') {
    return (missionTypeOf(plan)?.missions ?? []).map(item => ({
      value: item.name,
      label: item.display,
    }))
  }
  return props.categories.map(item => ({ value: item.name, label: item.label }))
}

function visibleColumns(plan: Plan) {
  return props.columns.filter(column => {
    if (column.type === 'cascade' && !optionsFor(column, plan)?.length) return false
    const conditions = Array.isArray(column.showWhen)
      ? column.showWhen
      : column.showWhen
        ? [column.showWhen]
        : []
    return conditions.every(
      ({ field, value, not }) => (String(plan[field] ?? '') === value) !== !!not
    )
  })
}

function update(plan: Plan, field: string, value: Value) {
  plan[field] = value
  if (field === 'category_name')
    plan.mission_type_name = categoryOf(plan)?.mission_types[0]?.name ?? ''
  if (field === 'category_name' || field === 'mission_type_name') {
    plan.mission_name = missionTypeOf(plan)?.missions[0]?.name ?? null
  }
}

function move(from: number, to: number) {
  const list = [...plans.value]
  list.splice(to, 0, list.splice(from, 1)[0])
  plans.value = list
}

function remove(index: number) {
  plans.value = plans.value.filter((_, item) => item !== index)
}
</script>

<template>
  <div class="stack">
    <div v-for="(plan, index) in plans" :key="index" class="line stack">
      <div class="grid">
        <FieldInput
          v-for="column in visibleColumns(plan)"
          :key="column.field"
          :label="column.title"
          :value="plan[column.field] ?? null"
          :type="column.type === 'number' ? 'number' : undefined"
          :options="optionsFor(column, plan)"
          @change="update(plan, column.field, $event)"
        />
      </div>
      <div class="row">
        <span>{{ t('planRunTimes', { count: Number(plan.run_times) || 0 }) }}</span>
        <button
          type="button"
          :disabled="!index"
          :aria-label="t('moveUp')"
          @click="move(index, index - 1)"
        >
          ↑
        </button>
        <button
          type="button"
          :disabled="index === plans.length - 1"
          :aria-label="t('moveDown')"
          @click="move(index, index + 1)"
        >
          ↓
        </button>
        <button type="button" @click="remove(index)">{{ t('planDelete') }}</button>
      </div>
    </div>
    <div>
      <button type="button" @click="plans = [...plans, { ...newItem, run_times: 0 }]">
        {{ t('planAdd') }}
      </button>
    </div>
  </div>
</template>
