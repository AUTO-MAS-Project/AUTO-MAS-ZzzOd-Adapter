<script setup lang="ts">
import { ref } from 'vue'
import { usePanel } from './bridge'
import TaskSettings from './TaskSettings.vue'
import type { Task } from './types'

const props = defineProps<{ tasks: Task[]; instanceIdx?: number }>()
const emit = defineEmits<{ save: [tasks: Task[]] }>()
const { disabled, t } = usePanel()
const editing = ref<Task>()
const dragged = ref<number>()

function move(from: number, to: number) {
  if (disabled.value || from === to) return
  const list = [...props.tasks]
  list.splice(to, 0, list.splice(from, 1)[0])
  emit('save', list)
}

function drop(index: number) {
  if (dragged.value !== undefined) move(dragged.value, index)
  dragged.value = undefined
}

function toggle(task: Task, event: Event) {
  const input = event.target as HTMLInputElement
  input.checked = task.enabled
  emit(
    'save',
    props.tasks.map(item => (item === task ? { ...item, enabled: !item.enabled } : item))
  )
}

function sort() {
  emit(
    'save',
    [...props.tasks].sort((left, right) => Number(right.enabled) - Number(left.enabled))
  )
}
</script>

<template>
  <div class="row">
    <h3>{{ t('oneDragonConfig') }}</h3>
    <button type="button" :disabled="!tasks.length" @click="sort">{{ t('sortTasks') }}</button>
  </div>
  <p v-if="!tasks.length" class="hint">{{ t('noTasks') }}</p>
  <div v-else class="scroll-list">
    <div
      v-for="(task, index) in tasks"
      :key="task.app_id"
      class="row line"
      :draggable="!disabled"
      @dragstart="dragged = index"
      @dragend="dragged = undefined"
      @dragover.prevent
      @drop.prevent="drop(index)"
    >
      <label class="switch-tile">
        <input type="checkbox" :checked="task.enabled" @change="toggle(task, $event)" />
        {{ task.app_name }}
      </label>
      <button
        type="button"
        :disabled="index === 0"
        :aria-label="t('moveUp') + ' ' + task.app_name"
        @click="move(index, index - 1)"
      >
        ↑
      </button>
      <button
        type="button"
        :disabled="index === tasks.length - 1"
        :aria-label="t('moveDown') + ' ' + task.app_name"
        @click="move(index, index + 1)"
      >
        ↓
      </button>
      <button v-if="task.configurable" type="button" @click="editing = task">
        {{ t('taskSettings') }}
      </button>
      <span v-else-if="task.jump" class="hint">{{ t('taskNative') }}</span>
    </div>
  </div>
  <TaskSettings
    v-if="editing"
    :key="editing.app_id"
    :task="editing"
    :instance-idx="instanceIdx"
    @close="editing = undefined"
  />
</template>
