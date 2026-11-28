import { createApp } from 'vue'
import ScriptPanel from './ScriptPanel.vue'
import UserPanel from './UserPanel.vue'
import './panel.css'

createApp(document.body.dataset.page === 'script' ? ScriptPanel : UserPanel).mount('#app')
