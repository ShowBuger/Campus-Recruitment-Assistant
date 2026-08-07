<template>
  <div class="modal-mask show" @mousedown.self="$emit('close')">
    <div class="modal settings-modal utility-modal settings-workspace">
      <div class="modal-hd">
        <div>
          <h2>系统设置</h2>
          <p>AI 服务与进度跟踪均按用户独立配置</p>
        </div>
        <button class="icon-btn" @click="$emit('close')" title="关闭">&times;</button>
      </div>

      <div class="settings-tabs" role="tablist">
        <button
          id="settings-tab-ai"
          class="btn"
          :class="{ active: tab === 'ai' }"
          type="button"
          @click="tab = 'ai'"
          role="tab"
        >AI 配置</button>
        <button
          id="settings-tab-tracker"
          class="btn"
          :class="{ active: tab === 'tracker' }"
          type="button"
          @click="tab = 'tracker'"
          role="tab"
        >进度跟踪</button>
      </div>

      <div class="modal-body">
        <!-- ========== AI Config Tab ========== -->
        <section id="settings-page-ai" class="settings-page" :class="{ active: tab === 'ai' }">
          <div class="form-group">
            <label for="cfg-ai-provider">当前服务商</label>
            <select id="cfg-ai-provider" v-model="config.ai_provider">
              <option value="deepseek">DeepSeek</option>
              <option value="openai">OpenAI GPT</option>
              <option value="anthropic">Anthropic Claude</option>
              <option value="kimi">Kimi</option>
            </select>
          </div>

          <!-- DeepSeek -->
          <div class="provider-panel" id="provider-deepseek" v-show="config.ai_provider === 'deepseek'" :class="{ active: config.ai_provider === 'deepseek' }">
            <div class="provider-name">DeepSeek</div>
            <div class="grid-2">
              <div class="form-group">
                <label for="cfg-deepseek-key">API Key</label>
                <input id="cfg-deepseek-key" type="password" autocomplete="off" :placeholder="maskedKeys.deepseek ? '已保存：'+maskedKeys.deepseek : 'sk-...'" :class="{ 'secret-saved': maskedKeys.deepseek }" v-model="config.deepseek_api_key">
                <div class="help" id="cfg-deepseek-key-help" :class="{ saved: maskedKeys.deepseek }">{{ maskedKeys.deepseek ? '已保存密钥：'+maskedKeys.deepseek : '尚未保存密钥' }}</div>
                <a class="provider-api-link" href="https://platform.deepseek.com/usage" target="_blank" rel="noopener">获取 API →</a>
              </div>
              <div class="form-group">
                <label for="cfg-deepseek-model-picker">模型名称</label>
                <div class="model-input-row">
                  <select id="cfg-deepseek-model-picker" v-model="config.deepseek_model" @change="selectModel('deepseek')">
                    <option value="deepseek-v4-flash">DeepSeek V4 Flash</option>
                    <option value="deepseek-v4-pro">DeepSeek V4 Pro</option>
                  </select>
                  <button class="btn" type="button" @click="loadProviderModels('deepseek')">读取模型</button>
                </div>
                <input id="cfg-deepseek-model" list="deepseek-models" placeholder="也可直接填写中转模型 ID" style="margin-top:7px" v-model="config.deepseek_model">
                <datalist id="deepseek-models">
                  <option value="deepseek-v4-flash"></option>
                  <option value="deepseek-v4-pro"></option>
                </datalist>
                <div class="help">上方直接选择官方模型；下方可填写中转服务的自定义模型 ID</div>
              </div>
              <div class="form-group provider-url">
                <label for="cfg-deepseek-base-url">API Base URL</label>
                <input id="cfg-deepseek-base-url" inputmode="url" placeholder="https://api.deepseek.com" v-model="config.deepseek_base_url">
                <div class="help">支持填写 Base URL 或完整的 /chat/completions 地址</div>
              </div>
            </div>
          </div>

          <!-- OpenAI -->
          <div class="provider-panel" id="provider-openai" v-show="config.ai_provider === 'openai'" :class="{ active: config.ai_provider === 'openai' }">
            <div class="provider-name">OpenAI GPT</div>
            <div class="grid-2">
              <div class="form-group">
                <label for="cfg-openai-key">API Key</label>
                <input id="cfg-openai-key" type="password" autocomplete="off" :placeholder="maskedKeys.openai ? '已保存：'+maskedKeys.openai : 'sk-...'" :class="{ 'secret-saved': maskedKeys.openai }" v-model="config.openai_api_key">
                <div class="help" id="cfg-openai-key-help" :class="{ saved: maskedKeys.openai }">{{ maskedKeys.openai ? '已保存密钥：'+maskedKeys.openai : '尚未保存密钥' }}</div>
              </div>
              <div class="form-group">
                <label for="cfg-openai-model-picker">模型名称</label>
                <div class="model-input-row">
                  <select id="cfg-openai-model-picker" v-model="config.openai_model" @change="selectModel('openai')">
                    <option value="">请选择或读取模型</option>
                    <option v-for="m in openaiModelOptions" :key="m" :value="m">{{ m }}</option>
                  </select>
                  <button class="btn" type="button" @click="loadProviderModels('openai')">读取模型</button>
                </div>
                <input id="cfg-openai-model" list="openai-models" placeholder="也可直接填写中转模型 ID" style="margin-top:7px" v-model="config.openai_model">
                <datalist id="openai-models">
                  <option value="gpt-5.6-sol"></option>
                  <option value="gpt-5.6-terra"></option>
                  <option value="gpt-5.6-luna"></option>
                  <option value="gpt-5.5"></option>
                  <option value="gpt-5.4"></option>
                  <option value="gpt-5.4-mini"></option>
                  <option value="gpt-5.4-nano"></option>
                  <option value="gpt-5.2"></option>
                  <option value="gpt-5-mini"></option>
                  <option value="gpt-4.1"></option>
                  <option value="gpt-4.1-mini"></option>
                  <option value="gpt-4o-mini"></option>
                </datalist>
                <div class="help">上方下拉选择模型；下方可填写中转服务的自定义模型 ID</div>
              </div>
              <div class="form-group provider-url">
                <label for="cfg-openai-base-url">API Base URL</label>
                <input id="cfg-openai-base-url" inputmode="url" placeholder="https://api.openai.com/v1" v-model="config.openai_base_url">
                <div class="help">支持 Base URL，也可填写完整的 /responses 或 /chat/completions 地址</div>
              </div>
              <div class="form-group">
                <label for="cfg-openai-api-mode">接口协议</label>
                <select id="cfg-openai-api-mode" v-model="config.openai_api_mode">
                  <option value="responses">Responses API（官方推荐）</option>
                  <option value="chat_completions">Chat Completions（中转兼容）</option>
                </select>
              </div>
            </div>
          </div>

          <!-- Anthropic -->
          <div class="provider-panel" id="provider-anthropic" v-show="config.ai_provider === 'anthropic'" :class="{ active: config.ai_provider === 'anthropic' }">
            <div class="provider-name">Anthropic Claude</div>
            <div class="grid-2">
              <div class="form-group">
                <label for="cfg-anthropic-key">API Key</label>
                <input id="cfg-anthropic-key" type="password" autocomplete="off" :placeholder="maskedKeys.anthropic ? '已保存：'+maskedKeys.anthropic : 'sk-ant-...'" :class="{ 'secret-saved': maskedKeys.anthropic }" v-model="config.anthropic_api_key">
                <div class="help" id="cfg-anthropic-key-help" :class="{ saved: maskedKeys.anthropic }">{{ maskedKeys.anthropic ? '已保存密钥：'+maskedKeys.anthropic : '尚未保存密钥' }}</div>
              </div>
              <div class="form-group">
                <label for="cfg-anthropic-model-picker">模型名称</label>
                <div class="model-input-row">
                  <select id="cfg-anthropic-model-picker" v-model="config.anthropic_model" @change="selectModel('anthropic')">
                    <option value="">请选择或读取模型</option>
                    <option v-for="m in anthropicModelOptions" :key="m" :value="m">{{ m }}</option>
                  </select>
                  <button class="btn" type="button" @click="loadProviderModels('anthropic')">读取模型</button>
                </div>
                <input id="cfg-anthropic-model" list="anthropic-models" placeholder="也可直接填写中转模型 ID" style="margin-top:7px" v-model="config.anthropic_model">
                <datalist id="anthropic-models">
                  <option value="claude-fable-5"></option>
                  <option value="claude-opus-4-8"></option>
                  <option value="claude-sonnet-5"></option>
                  <option value="claude-sonnet-4-6"></option>
                  <option value="claude-haiku-4-5"></option>
                </datalist>
                <div class="help">上方下拉选择模型；下方可填写中转服务的自定义模型 ID</div>
              </div>
              <div class="form-group provider-url">
                <label for="cfg-anthropic-base-url">API Base URL</label>
                <input id="cfg-anthropic-base-url" inputmode="url" placeholder="https://api.anthropic.com/v1" v-model="config.anthropic_base_url">
                <div class="help">支持填写 Base URL 或完整的 /messages 地址</div>
              </div>
            </div>
          </div>

          <!-- Kimi -->
          <div class="provider-panel" id="provider-kimi" v-show="config.ai_provider === 'kimi'" :class="{ active: config.ai_provider === 'kimi' }">
            <div class="provider-name">Kimi</div>
            <div class="grid-2">
              <div class="form-group">
                <label for="cfg-kimi-key">API Key</label>
                <input id="cfg-kimi-key" type="password" autocomplete="off" :placeholder="maskedKeys.kimi ? '已保存：'+maskedKeys.kimi : 'sk-...'" :class="{ 'secret-saved': maskedKeys.kimi }" v-model="config.kimi_api_key">
                <div class="help" id="cfg-kimi-key-help" :class="{ saved: maskedKeys.kimi }">{{ maskedKeys.kimi ? '已保存密钥：'+maskedKeys.kimi : '尚未保存密钥' }}</div>
                <a class="provider-api-link" href="https://platform.kimi.com/console/account" target="_blank" rel="noopener">获取 API →</a>
              </div>
              <div class="form-group">
                <label for="cfg-kimi-model-picker">模型名称</label>
                <div class="model-input-row">
                  <select id="cfg-kimi-model-picker" v-model="config.kimi_model" @change="selectModel('kimi')">
                    <option value="kimi-k3">Kimi K3</option>
                    <option value="kimi-k2.6">Kimi K2.6</option>
                  </select>
                  <button class="btn" type="button" @click="loadProviderModels('kimi')">读取模型</button>
                </div>
                <input id="cfg-kimi-model" list="kimi-models" placeholder="也可直接填写模型 ID" style="margin-top:7px" v-model="config.kimi_model">
                <datalist id="kimi-models">
                  <option value="kimi-k3"></option>
                  <option value="kimi-k2.6"></option>
                </datalist>
                <div class="help">可读取当前 Key 支持的完整模型列表</div>
              </div>
              <div class="form-group provider-url">
                <label for="cfg-kimi-base-url">API Base URL</label>
                <input id="cfg-kimi-base-url" inputmode="url" placeholder="https://api.moonshot.cn/v1" v-model="config.kimi_base_url">
                <div class="help">官方 Kimi API 地址，也支持 OpenAI Chat Completions 兼容中转</div>
              </div>
            </div>
          </div>

          <div class="secret-note">所有 API Key 按用户独立保存且不会明文回显；中转地址建议使用 HTTPS</div>
        </section>

        <!-- ========== Tracker Tab ========== -->
        <section id="settings-page-tracker" class="settings-page tracker-settings" :class="{ active: tab === 'tracker' }">
          <TrackerSettings ref="trackerRef" />
        </section>
      </div>

      <div class="modal-ft settings-footer">
        <div class="settings-page-actions" :class="{ active: tab === 'ai' }" id="settings-actions-ai">
          <button class="btn" id="config-test" @click="testConnection" :disabled="testing">测试连接</button>
          <button class="btn btn-primary" id="config-save" @click="saveConfig" :disabled="saving">保存 AI 配置</button>
        </div>
        <div class="settings-page-actions" :class="{ active: tab === 'tracker' }" id="settings-actions-tracker">
          <button class="btn btn-danger" id="tracker-reset" @click="trackerRef?.resetCache()" :disabled="trackerRef?.resetting">清空同步缓存</button>
          <button class="btn" id="tracker-test" @click="trackerRef?.testSync()" :disabled="trackerRef?.syncing">测试同步</button>
          <button class="btn" id="tracker-sync" @click="trackerRef?.startSync()" :disabled="trackerRef?.syncing">立即同步</button>
          <button class="btn btn-primary" id="tracker-save" @click="trackerRef?.save()" :disabled="trackerRef?.saving">保存跟踪配置</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { get, post } from '@/utils/api'
import { useToastStore } from '@/stores/toast'
import TrackerSettings from '@/components/TrackerSettings.vue'

const toast = useToastStore()

const tab = ref('ai')
const trackerRef = ref(null)
const testing = ref(false)
const saving = ref(false)

// Loaded model options for providers that support dynamic loading
const openaiModelOptions = ref([])
const anthropicModelOptions = ref([])

// Masked keys from the server (read-only display helpers)
const maskedKeys = reactive({
  deepseek: '',
  openai: '',
  anthropic: '',
  kimi: '',
})

const deepseekKeyHelp = computed(() =>
  maskedKeys.deepseek ? maskedKeys.deepseek : '尚未保存密钥'
)
const openaiKeyHelp = computed(() =>
  maskedKeys.openai ? maskedKeys.openai : '尚未保存密钥'
)
const anthropicKeyHelp = computed(() =>
  maskedKeys.anthropic ? maskedKeys.anthropic : '尚未保存密钥'
)
const kimiKeyHelp = computed(() =>
  maskedKeys.kimi ? maskedKeys.kimi : '尚未保存密钥'
)

const config = reactive({
  ai_provider: 'deepseek',
  deepseek_api_key: '',
  deepseek_model: 'deepseek-v4-flash',
  deepseek_base_url: 'https://api.deepseek.com',
  openai_api_key: '',
  openai_model: 'gpt-5.4-mini',
  openai_base_url: 'https://api.openai.com/v1',
  openai_api_mode: 'responses',
  anthropic_api_key: '',
  anthropic_model: 'claude-sonnet-5',
  anthropic_base_url: 'https://api.anthropic.com/v1',
  kimi_api_key: '',
  kimi_model: 'kimi-k3',
  kimi_base_url: 'https://api.moonshot.cn/v1',
})

/**
 * Build the AIConfig request body for the given provider using current form values.
 */
function buildConfigBody(provider) {
  const body = {
    ai_provider: provider,
    deepseek_api_key: provider === 'deepseek' ? config.deepseek_api_key : '',
    deepseek_model: provider === 'deepseek' ? config.deepseek_model : '',
    deepseek_base_url: provider === 'deepseek' ? config.deepseek_base_url : '',
    openai_api_key: provider === 'openai' ? config.openai_api_key : '',
    openai_model: provider === 'openai' ? config.openai_model : '',
    openai_base_url: provider === 'openai' ? config.openai_base_url : '',
    openai_api_mode: config.openai_api_mode,
    anthropic_api_key: provider === 'anthropic' ? config.anthropic_api_key : '',
    anthropic_model: provider === 'anthropic' ? config.anthropic_model : '',
    anthropic_base_url: provider === 'anthropic' ? config.anthropic_base_url : '',
    kimi_api_key: provider === 'kimi' ? config.kimi_api_key : '',
    kimi_model: provider === 'kimi' ? config.kimi_model : '',
    kimi_base_url: provider === 'kimi' ? config.kimi_base_url : '',
  }
  return body
}

function maskSavedKey(value) {
  const text = String(value || '').trim()
  if (!text) return ''
  return text.length <= 10 ? text.slice(0, 2) + '***' : text.slice(0, 6) + '***' + text.slice(-4)
}

function selectModel(provider) {
  // The v-model on the model-picker select already updates config.[provider]_model,
  // and the custom-model input also binds to the same config field.
  // This handler is kept for interface consistency with the original onclick attribute.
}

async function loadProviderModels(provider) {
  try {
    const body = buildConfigBody(provider)
    const data = await post('/api/config/models', body)
    toast.success(`已读取 ${data.count} 个模型`)
    const models = data.models || []
    if (provider === 'openai') {
      openaiModelOptions.value = models
    } else if (provider === 'anthropic') {
      anthropicModelOptions.value = models
    }
    // For deepseek/kimi, the options are static in the HTML, but we could also update
    if (models.length > 0 && !body[`${provider}_model`]) {
      config[`${provider}_model`] = models[0]
    }
  } catch (err) {
    toast.error(err.message || '读取模型失败')
  }
}

async function testConnection() {
  testing.value = true
  try {
    const body = buildConfigBody(config.ai_provider)
    const data = await post('/api/config/test', body)
    toast.success(data.message || '连接正常')
  } catch (err) {
    toast.error(err.message || '连接测试失败')
  } finally {
    testing.value = false
  }
}

async function saveConfig() {
  saving.value = true
  try {
    const body = {
      ai_provider: config.ai_provider,
      deepseek_api_key: config.deepseek_api_key,
      deepseek_model: config.deepseek_model,
      deepseek_base_url: config.deepseek_base_url,
      openai_api_key: config.openai_api_key,
      openai_model: config.openai_model,
      openai_base_url: config.openai_base_url,
      openai_api_mode: config.openai_api_mode,
      anthropic_api_key: config.anthropic_api_key,
      anthropic_model: config.anthropic_model,
      anthropic_base_url: config.anthropic_base_url,
      kimi_api_key: config.kimi_api_key,
      kimi_model: config.kimi_model,
      kimi_base_url: config.kimi_base_url,
    }
    const data = await post('/api/config', body)
    const provider = config.ai_provider
    const keyField = `${provider}_api_key`
    if (config[keyField]) {
      maskedKeys[provider] = maskSavedKey(config[keyField])
      config[keyField] = ''
    }
    toast.success(data.message || '配置已保存')
  } catch (err) {
    toast.error(err.message || '保存配置失败')
  } finally {
    saving.value = false
  }
}


onMounted(async () => {
  try {
    const data = await get('/api/config')
    const v = data?.values || {}
    config.ai_provider = v.ai_provider || 'deepseek'
    config.deepseek_model = v.deepseek_model || 'deepseek-v4-flash'
    config.deepseek_base_url = v.deepseek_base_url || 'https://api.deepseek.com'
    config.openai_model = v.openai_model || 'gpt-5.4-mini'
    config.openai_base_url = v.openai_base_url || 'https://api.openai.com/v1'
    config.openai_api_mode = v.openai_api_mode || 'responses'
    config.anthropic_model = v.anthropic_model || 'claude-sonnet-5'
    config.anthropic_base_url = v.anthropic_base_url || 'https://api.anthropic.com/v1'
    config.kimi_model = v.kimi_model || 'kimi-k3'
    config.kimi_base_url = v.kimi_base_url || 'https://api.moonshot.cn/v1'
    // Store masked keys for display help text
    maskedKeys.deepseek = v.deepseek_api_key_masked || ''
    maskedKeys.openai = v.openai_api_key_masked || ''
    maskedKeys.anthropic = v.anthropic_api_key_masked || ''
    maskedKeys.kimi = v.kimi_api_key_masked || ''
  } catch (err) {
    toast.error(err.message || '加载配置失败')
  }
})
</script>

<style scoped>
.settings-workspace{display:flex;max-height:min(820px,92dvh);flex-direction:column;overflow:hidden}.settings-workspace>.modal-hd{flex:0 0 auto;padding:20px 22px}.settings-workspace>.modal-hd h2{font-size:20px}.settings-tabs{flex:0 0 auto;padding:10px 22px 0}.settings-tabs .btn{border-radius:10px 10px 0 0;box-shadow:none}.settings-workspace>.modal-body{min-height:0;padding:16px 22px;overflow:auto;background:var(--bg)}.settings-page{padding:16px;background:var(--panel)}.settings-page>.form-group:first-child{max-width:330px}.provider-panel{margin-top:14px}.provider-name{padding-bottom:10px;border-bottom:1px solid var(--line)}.settings-footer{flex:0 0 auto;padding:13px 22px;background:var(--panel)}.settings-page-actions .btn{min-width:98px}@media(max-width:620px){.settings-workspace{max-height:96dvh}.settings-workspace>.modal-hd,.settings-workspace>.modal-body,.settings-footer{padding-left:14px;padding-right:14px}.settings-page-actions{width:100%;display:none;grid-template-columns:1fr 1fr}.settings-page-actions.active{display:grid}.settings-page-actions .btn{min-width:0}}
</style>
