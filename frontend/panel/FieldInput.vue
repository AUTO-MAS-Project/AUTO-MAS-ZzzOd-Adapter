<script setup lang="ts">
import type { Option, Value } from './bridge'

const props = defineProps<{
  label: string
  value: Value
  options?: Option[]
  type?: 'text' | 'number' | 'password'
  min?: number
  max?: number
}>()
const emit = defineEmits<{ change: [value: Value] }>()

function change(event: Event) {
  const input = event.target as HTMLInputElement
  if (!input.reportValidity() || (props.type === 'number' && input.value === '')) {
    input.value = String(props.value ?? '')
    return
  }
  const value =
    typeof props.value === 'boolean'
      ? input.checked
      : props.type === 'number'
        ? input.valueAsNumber
        : input.value
  input.value = String(props.value ?? '')
  if (typeof props.value === 'boolean') input.checked = props.value
  if (value !== props.value) emit('change', value)
}
</script>

<template>
  <label v-if="typeof value === 'boolean'" class="switch-tile">
    <input type="checkbox" :checked="value" @change="change" />
    {{ label }}
  </label>
  <label v-else>
    {{ label }}
    <select v-if="options" :value="String(value ?? '')" @change="change">
      <option
        v-if="!options.some(option => option.value === String(value ?? ''))"
        :value="String(value ?? '')"
      >
        {{ value }}
      </option>
      <option v-for="option in options" :key="option.value" :value="option.value">
        {{ option.label }}
      </option>
    </select>
    <input
      v-else
      :type="type ?? 'text'"
      :value="value ?? ''"
      :min="min"
      :max="max"
      @change="change"
    />
  </label>
</template>
