<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { usePanel, type Option } from './bridge'
import FieldInput from './FieldInput.vue'

type Team = { idx: number; name: string; autoBattle: string; agents: string[] }
type TeamConfig = { teams: Team[]; autoBattle: Option[]; agentOptions: Option[] }

const props = defineProps<{ instanceIdx?: number }>()
const { t, get, post, run, notify, revision } = usePanel()
const data = ref<TeamConfig>()
const baseline = ref('')
const dirty = computed(() => data.value && JSON.stringify(data.value.teams) !== baseline.value)
const agents = computed(() => [
  { value: 'unknown', label: t('teamAgentEmpty') },
  ...(data.value?.agentOptions ?? []).filter(item => item.value !== 'unknown'),
])

async function reload() {
  const result = await get<TeamConfig>('teams', { instanceIdx: props.instanceIdx })
  for (const team of result.teams) {
    team.agents = Array.from({ length: 3 }, (_, index) => team.agents[index] || 'unknown')
  }
  data.value = result
  baseline.value = JSON.stringify(result.teams)
}

function load(event: Event) {
  if ((event.target as HTMLDetailsElement).open && !data.value) void run(reload)
}

watch(revision, () => {
  // Host reloads may follow a restore or a native editor session.
  if (!dirty.value) data.value = undefined
})

function save() {
  void run(async () => {
    const teams = data.value!.teams.map(team => ({
      name: team.name,
      autoBattle: team.autoBattle,
      agent_id_list: team.agents,
    }))
    await post('teams/save', { instanceIdx: props.instanceIdx, teams })
    await reload()
    await notify('success', t('teamsSaved'))
  })
}
</script>

<template>
  <details @toggle="load">
    <summary>{{ t('predefinedTeams') }}</summary>
    <div class="actions">
      <button type="button" @click="run(reload)">{{ t('slotsRefresh') }}</button>
      <button type="button" :disabled="!dirty" @click="save">{{ t('teamsSaveButton') }}</button>
    </div>
    <div v-if="data" class="scroll-list">
      <div v-for="team in data.teams" :key="team.idx" class="line stack">
        <div class="row">
          <FieldInput
            :label="`${team.idx + 1} · ${t('teamName')}`"
            :value="team.name"
            @change="team.name = String($event)"
          />
          <FieldInput
            :label="t('teamBattleConfig')"
            :value="team.autoBattle"
            :options="data.autoBattle"
            @change="team.autoBattle = String($event)"
          />
        </div>
        <div class="row">
          <FieldInput
            v-for="(agent, index) in team.agents"
            :key="index"
            :label="t('teamAgent', { count: index + 1 })"
            :value="agent"
            :options="agents"
            @change="team.agents[index] = String($event)"
          />
        </div>
      </div>
    </div>
  </details>
</template>
