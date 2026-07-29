<template>
  <div class="modal-mask show" @mousedown.self="$emit('close')">
    <div class="modal help-modal">
      <div class="modal-hd"><div><h2>欢迎使用校招信息看板</h2><p>几分钟了解主要功能与推荐使用顺序</p></div><button class="icon-btn" @click="$emit('close')" title="关闭帮助" aria-label="关闭帮助">&times;</button></div>
      <div class="modal-body help-body">
        <div class="help-intro"><span class="mark" aria-hidden="true"></span><div><b>从个人总表开始</b><p>先维护岗位信息，再加入投递流程。所有账号数据独立保存在云端。</p></div></div>
        <div class="help-grid">
          <article><i>01</i><div><b>维护岗位</b><p>在“总表信息”中新建、导入或从共享总表添加岗位；点击公司名称可打开完整详情。</p></div></article>
          <article><i>02</i><div><b>跟踪投递</b><p>把岗位加入投递后，可在投递信息和投递看板中维护进展、时间节点与结果。</p></div></article>
          <article><i>03</i><div><b>日历提醒</b><p>校招日历会汇总投递、机考、面试和截止时间，也可以添加自定义日程。</p></div></article>
          <article><i>04</i><div><b>使用 AI</b><p>先在右上角 AI 配置中保存自己的 API Key，再从岗位详情使用 AI 补全，或进入简历分析。</p></div></article>
          <article><i>05</i><div><b>共享与聊天</b><p>共享总表可供所有用户查找岗位；右上角聊天支持消息、图片和岗位转发。</p></div></article>
          <article><i>06</i><div><b>手机使用</b><p>表格区域可横向滑动，弹窗内可纵向滚动；常用操作会自动适配窄屏。</p></div></article>
        </div>
        <div class="help-note"><b>提示</b><span>AI Key 仅保存在你的独立配置中。重要岗位信息与截止时间仍建议打开官方入口核对。</span></div>
      </div>
      <div class="modal-ft"><a href="/guide" class="btn" style="margin-right:auto">使用文档</a><button class="btn btn-primary" @click="$emit('close')">开始使用</button></div>
    </div>
  </div>
</template>

<script setup>
defineEmits(['close'])
</script>
