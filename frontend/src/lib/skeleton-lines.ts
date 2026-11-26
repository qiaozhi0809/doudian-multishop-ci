/**
 * 骨架行数的全站约定（Arc Skeleton 最多画 6 行）。写 `lines={SKELETON_LINES.xxx}`，不写数字。
 */
export const SKELETON_LINES = {
  /** 页面主列表与长内容：表格、会话列表、消息记录。 */
  list: 6,
  /** 整页准备态与卡片内内容：读取店铺或登录状态、图表、浮层面板、折叠区。 */
  card: 4,
  /** 顶部计数卡那一行。 */
  count: 2,
  /** 单个数值。 */
  value: 1,
} as const;
