<script setup>
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { post } from '@/utils/api'
import UserAvatar from '@/components/UserAvatar.vue'
import AvatarPickerModal from '@/components/AvatarPickerModal.vue'

const emit = defineEmits(['close'])
const auth = useAuthStore()
const toast = useToastStore()
const nickname = ref(auth.user?.nickname || auth.user?.username || '')
const showAvatarPicker = ref(false)
const currentPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const savingProfile = ref(false)
const savingPassword = ref(false)

async function saveProfile() {
  if (!nickname.value.trim()) return toast.error('请填写昵称')
  savingProfile.value = true
  try {
    const data = await post('/api/auth/profile', { nickname: nickname.value.trim(), avatar_key: auth.user?.avatar_key || 'indigo' })
    auth.setUser(data.user)
    toast.success(data.message || '昵称已更新')
  } catch (e) { toast.error(e.message) }
  finally { savingProfile.value = false }
}

async function savePassword() {
  if (!currentPassword.value) return toast.error('请输入当前密码')
  if (newPassword.value.length < 4) return toast.error('新密码至少 4 个字符')
  if (newPassword.value !== confirmPassword.value) return toast.error('两次输入的新密码不一致')
  savingPassword.value = true
  try {
    const data = await post('/api/auth/password', {
      current_password: currentPassword.value,
      new_password: newPassword.value,
    })
    currentPassword.value = ''; newPassword.value = ''; confirmPassword.value = ''
    toast.success(data.message || '密码已修改')
  } catch (e) { toast.error(e.message) }
  finally { savingPassword.value = false }
}
</script>

<template>
  <Teleport to="body"><div class="modal-mask show" @mousedown.self="emit('close')">
    <div class="modal user-profile-modal">
      <div class="modal-hd">
        <div><h2>用户信息</h2><p>管理你的公开昵称和登录密码</p></div>
        <button class="icon-btn" type="button" title="关闭" @click="emit('close')">&times;</button>
      </div>
      <div class="modal-body">
        <section class="profile-summary">
          <button class="profile-avatar-large" type="button" title="更换头像" aria-label="更换头像" @click="showAvatarPicker = true"><UserAvatar :avatar-key="auth.user?.avatar_key" :avatar-url="auth.user?.avatar_url" :label="nickname"/></button>
          <div><b>{{ auth.user?.nickname || auth.user?.username }}</b><span>@{{ auth.user?.username }}</span></div>
        </section>
        <form class="profile-section" @submit.prevent="saveProfile">
          <div class="profile-section-head"><b>昵称</b><span>昵称会显示在聊天联系人中</span></div>
          <div class="profile-inline"><input v-model="nickname" maxlength="20" autocomplete="nickname"><button class="btn btn-primary" :disabled="savingProfile">{{ savingProfile ? '保存中' : '保存资料' }}</button></div>
        </form>
        <form class="profile-section" @submit.prevent="savePassword">
          <div class="profile-section-head"><b>修改密码</b><span>修改后下次登录使用新密码</span></div>
          <div class="profile-password-grid">
            <input v-model="currentPassword" type="password" autocomplete="current-password" placeholder="当前密码">
            <input v-model="newPassword" type="password" autocomplete="new-password" placeholder="新密码">
            <input v-model="confirmPassword" type="password" autocomplete="new-password" placeholder="确认新密码">
          </div>
          <div class="profile-password-action"><button class="btn" :disabled="savingPassword">{{ savingPassword ? '修改中' : '修改密码' }}</button></div>
        </form>
      </div>
    </div>
    <AvatarPickerModal v-if="showAvatarPicker" @close="showAvatarPicker = false" />
  </div></Teleport>
</template>

<style scoped>
.user-profile-modal{width:min(520px,calc(100vw - 28px))}.profile-summary{display:flex;align-items:center;gap:16px;padding:4px 0 20px;border-bottom:1px solid var(--line)}
.profile-avatar-large{position:relative;width:72px;height:72px;flex:0 0 72px;padding:0;border:2px solid var(--ink);border-radius:50%;background:transparent;box-shadow:3px 3px 0 var(--ink);cursor:pointer;overflow:hidden}
.profile-summary b,.profile-summary span{display:block}.profile-summary b{font-size:20px}.profile-summary span{margin-top:4px;color:var(--muted);font-size:12px}
.profile-section{padding:20px 0 0}.profile-section+.profile-section{margin-top:20px;border-top:1px solid var(--line)}.profile-section-head{margin-bottom:10px}.profile-section-head b,.profile-section-head span{display:block}.profile-section-head span{margin-top:3px;color:var(--muted);font-size:11px}
.profile-inline{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px}.profile-password-grid{display:grid;gap:8px}.profile-password-action{display:flex;justify-content:flex-end;margin-top:10px}
@media(max-width:520px){.profile-inline{grid-template-columns:1fr}.profile-inline .btn{width:100%}}
</style>
