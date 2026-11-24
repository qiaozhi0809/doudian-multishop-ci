## 附录 C：订单管理页 UI → 接口字段映射（2026-11-24 验证）

> 目的：把抖店「订单管理」页面上可见的每一块内容，映射到可编程的数据来源。
> 结论：**展示层零缺口**；筛选参数 6/8 已确认；写操作类见 B 档。

### C.1 顶部 tab 计数

单接口覆盖全部 tab：`GET /api/order/tabcnt?tabcnt_version=v1&tab=all`

| UI tab | 响应字段 | 样本值 |
|---|---|---|
| 全部订单 | `all` | 18 |
| 待支付 | `unpaid` | 0 |
| 待发货 | `stock_up` | 0 |
| 24h需发货及揽收 | `exp_ship` | 0 |
| 超时未发货及揽收 | `ship_delay` | 0 |
| 已发货 | `on_delivery` | 6 |
| 售后中 | `in_aftersale` / `have_aftersale` | 2 |
| 已完成 | `received` | 1 |
| 已关闭 | `closed` | 11 |

附加可用字段（UI 未直接展示，做看板有价值）：
`under_sure`（待确认）、`handling`（处理中）、
`ship_and_logistics_delay` / `exp_ship_and_logistics`（发货+揽收超时组合）、
`cnt_report`（分组统计子对象）。

### C.2 订单列表字段分组（`searchlist` 单条 116 字段）

| UI 区域 | 关键字段 |
|---|---|
| 订单标识 | `shop_order_id`、`order_id_for_show`、`user_id` |
| 订单状态 | `order_status`（数字）、`order_status_info.order_status_text`、`order_type_desc` |
| 商品信息 | `product_item[]`：`item_order_id`、`product_id`、`product_name`、`sku_spec[]`、`img`、`quantity` |
| 金额（整数分） | `pay_amount`、`total_goods_amount`、`post_amount`、`promotion_amount`、`actual_receive_amount_int`（商家收入） |
| 时间 | `create_time`、`pay_time`、`exp_ship_time`（承诺发货）、`ship_time`、`receipt_time` |
| 收货信息 | `receiver_info`（**脱敏**：`辛*` / `1**********`）、`address_tag`、`receive_type` |
| 物流 | `latest_logistic_info.tracking_no`、`company_code`、`track`；`way_bill_url`；`logistics_status` |
| 买家 | `user_nickname`（脱敏）、`user_is_auth` |
| 操作按钮 | `operation_actions`、`action_map`、`button`（前端据此渲染按钮，可用于判断可用动作） |

**注意**：`receiver_info` 是脱敏值不是密文；要拿明文（打印面单必需）调
`GET /api/order/receiveinfo?order_id=<shop_order_id>`。

### C.3 筛选项 → 参数映射

| UI 筛选项 | 接口参数 | 验证 |
|---|---|---|
| 订单编号 | `order_id` | ✅ 已确认 |
| 物流单号 | `tracking_no` | ✅ 验证命中 1 单 |
| 达人ID | `author_id` | ✅ 验证过滤生效 |
| 搜索买家 | `buyer` | ✅ 验证过滤生效 |
| 承诺发货时间 | `exp_ship_time_start` / `exp_ship_time_end` | ✅ 验证 total 18→14 |
| 发货时间（接口支持，UI 未展示） | `ship_time_start` / `ship_time_end` | ✅ 验证 total 18→6 |
| 订单状态 | `order_status` + `tab`（**字符串枚举**） | ✅ 六值全部验证与 `tabcnt` 一致 |

**订单状态的枚举**（重要：筛选参数是**字符串**，而订单数据里的 `order_status` 字段是数字）：

| UI 选项 | `tab` / `order_status` 值 | 验证订单数 | tabcnt 对照 |
|---|---|---|---|
| 全部 | `tab=all`（order_status 留空） | 18 | 18 ✅ |
| 待支付 | `unpaid` | 0 | 0 ✅ |
| 待发货 | `stock_up` | 0 | 0 ✅ |
| 已发货 | `on_delivery` | 6 | 6 ✅ |
| 已完成 | `received` | 1 | 1 ✅ |
| 已关闭 | `closed` | 11 | 11 ✅ |

> ⚠️ 两套枚举不要混用：
> - **筛选参数**用字符串（`unpaid` / `stock_up` / `on_delivery` / `received` / `closed`）
> - **订单响应里的 `order_status`**是数字（3=已发货、4=已关闭、5=已完成）
> - 对账判定（[附录 G.2](reconcile.md)）用的是数字口径，筛选用的字符串口径，两者需在代码里分别建模
| 商品ID | **`product`** | ✅ 验证：`product=<商品ID>` → total 18→14 |
| 商品名称/商家编码 | **`product_name_code`** | ✅ 验证：选中联想商品后 → total 14 |

**商品ID 筛选验证记录**（2026-11-24）：页面手动输入商品ID 后发出
`product=3853991770601947295`，返回 14 单且全部包含该商品，确认参数名为 `product`
（此前试过的 `product_id` / `product_ids` / `product_id_list` 等 25 个候选名均无效）。

**商品名称/商家编码 的机制**（验证）：

1. 输入框输入文字 → 触发联想接口
   `GET /shopuser/power/searchProductDigest?productNameOrId=<输入>`
2. 从下拉选中某个商品后 → 查询请求带上 **`product_name_code=<商品ID>`**
3. 也就是说：UI 上写的是「商品名称/商家编码」，实际传的是**选中商品的商品ID**

补充：该店 6 个商品的 `out_product_id`（商家编码）**全部为空**，
所以「按商家编码筛选」在本店无法产生真实数据，机制以商品ID等价处理。

**时间筛选的完整参数形态**（页面实际发出）：

```
compact_time[select]=create_time_start,create_time_end
```

`compact_time[select]` 声明时间用哪两个字段，再配合对应起止参数；
未选具体时间时该参数常驻但不生效。

另需确认：UI 提示「多个单号用 / 空格隔开」时，接口是接收拼接字符串还是数组
（尚未测多值场景）。

### C.4 批量操作按钮 → 接口/页面

| UI 按钮 | 类型 | 目标 | 状态 |
|---|---|---|---|
| 批量备注 | 写接口 | `POST /api/order/addremarks` | ✅ 已验证（A.2.1） |
| 批量导入发货 | 页面 | `/ffa/morder/delivery/upload` | 跳转 |
| 打单发货 | 页面 | `/ffa/morder/logistics/ewaybill-delivery` | 跳转 |
| 在线寄件 | 页面 | 菜单内跳转 | 未识别 |
| 批量采购 | 写接口 | 未识别 | ❌ |
| 批量上传序列号 | 写接口 | 未识别 | ❌ |
| 表格配置 | 配置 | `GET /api/order/getPackageConfig?config_key=...` | 已识别 |

### C.5 实现注意

1. `page` 从 0 开始；`pageSize` 上限 200（201 及以上报 `602502051`）。
2. 筛选值为空时浏览器会带上空占位参数（`product_spec_desc=`、`search_condition_list=` 等），
   协议层可以省略，但保留空串更贴近页面行为。
3. 多店聚合时，`tabcnt` 与 `searchlist` 需按店分别拉取后在本地合并（跨店无统一接口）。
4. `operation_actions` / `action_map` 可用于判断某订单能否执行某操作，
   避免在界面渲染不可用按钮。

> 索引见 [README.md](README.md)。
