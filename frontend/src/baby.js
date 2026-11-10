// 示例档案，部署后可在设置页修改
// birth 默认 2024-01-01；系统设置页可修改（PUT /api/settings 后调 setBirthDate 全站生效）
import { reactive } from 'vue'

export const BABY = reactive({
  name: '小满',
  nickname: '小满',
  birth: '2024-01-01',
  avatar: '', // 自定义头像 URL（设置页上传后更新）
})

function birthDate() {
  return new Date(BABY.birth + 'T00:00:00')
}

export function setBirthDate(iso) {
  if (!iso) return
  const d = new Date(iso + 'T00:00:00')
  if (Number.isNaN(d.getTime())) return
  BABY.birth = iso
}

/** 年龄文案：满12个月前显示"X个月"，之后显示"X岁Y个月" */
export function ageText(now = new Date()) {
  const b = birthDate()
  let months =
    (now.getFullYear() - b.getFullYear()) * 12 +
    (now.getMonth() - b.getMonth())
  if (now.getDate() < b.getDate()) months -= 1
  if (months < 0) return '即将出生'
  const y = Math.floor(months / 12)
  const m = months % 12
  if (months < 12) return `${months}个月`
  return m ? `${y}岁${m}个月` : `${y}岁`
}

/** 出生天数文案（按 birth 日期计算） */
export function daysText(now = new Date()) {
  const b = birthDate()
  const days = Math.floor((now - b) / 86400000) + 1
  return `出生第 ${days} 天`
}
