## 附录 E：售后聚合模块 UI → 接口映射（2026-11-24 验证）

> 覆盖「售后工作台 / 售后管理 / 售后详情」。目标：多店售后聚合看板 + 待办提醒。
> 结论：**只读层完整可用**；处理动作（同意退款/填运单号）为写接口，待真实操作验证。

### E.1 售后列表

```
POST /after_sale/pc/list   (_bid=ffa_aftersale)
```

**请求体（验证）**：

```json
{"pageSize":10,"page":1,"order_by":["status_deadline asc"],
 "conf_version":"v13","search_receiver":"","after_sale_status":"",
 "after_sale_type":"","order_flag":[],"order_logistics_state":[],
 "shop_hit_gray_info":{"list_v1":{"hit":true}}}
```

- `page` **1-based**
- `order_by: ["status_deadline asc"]` 即按处理截止时间排序（做待办列表用这个）
- 筛选：`after_sale_status`、`after_sale_type`、`search_receiver`（买家）
- `conf_version: "v13"` 需保留，可能是接口契约版本

**响应**：`total` + `data.items[]`，每项 9 个分组：

| 分组 | 内容 |
|---|---|
| `after_sale_info` | 售后主数据（40+ 字段，见下） |
| `order_info` | 订单号、关联订单明细、买家收货（脱敏） |
| `buttons` | 可用操作按钮（`button` code + 文案 + disabled） |
| `text_part` | 展示文案（状态/类型/原因/物流，全部现成） |
| `metrics` | `platform_intervene`（平台是否介入） |
| `seller_logs` | 商家备注日志 |
| `show_infos` | 需要展示的区块（如物流） |
| `extra` / `summary_info_list` | 附加数据 |

**`after_sale_info` 关键字段**：

`after_sale_id`、`related_id`（关联订单号）、`shop_id`、
`after_sale_type` / `after_sale_status`（数字枚举）、
`refund_amount`（分）、`refund_post_amount`、`after_sale_quantity`、
`apply_time` / `create_time` / `update_time`（秒）、
**`status_deadline`（处理截止时间）**、`left_node_time`（剩余秒数）、
`arbitrate_status`（仲裁状态）、`risk_decision_code`（风控决策）、
`encrypted_buyer_info`（昵称脱敏）、`detail_link`（详情页 URL）、
`return_logistics_code`、`after_sale_tags`、`reason_second_labels`

### E.2 状态计数

```
GET /shopuser/aftersale/counts?fields=<逗号分隔的状态名>
    &appid=1&_bid=ffa_aftersale&aid=4272&aftersale_platform_source=fxg
```

- `fields` 参数显式声明要查哪些状态（不传可能返回全量或报错，需验证）
- 验证返回 **50+ 状态位**，关键分组：

| 分组 | 字段 |
|---|---|
| 待审核 | `all_audit`、`refund_audit`（退款）、`return_audit`（退货）、`exchange_audit`（换货）、`resend_audit`（补发）、`repair_audit`（维修）、`presale_all_audit` |
| 时效预警 | `urge_audit`（催审）、`approaching_deadline_audit`（临近超时）、`audit_ddl_in_one_day` |
| 待收货/发货 | `return_for_receive`（待商家收货）、`exchange_for_receive`、`wait_user_delivery`（待消费者发货）、`wait_for_receive_and_delivery` |
| 待签收 | `wait_user_sign`、`all_wait_user_sign`、`exchange_wait_user_sign`、`resend_wait_user_sign` |
| 仲裁 | `arbitrate_pending`、`arbitrate_pending_negotiation`、`arbitrate_pending_evidence`、`arbitrate_shop_evidence`、`arbitrate_unsettled` |
| 自动审核 | `auto_audit_pre_sale_fast_refund`、`auto_audit_return_fast_refund`、`auto_audit_thunder_return` |
| 聚合 | `urgent_aggregate_count`、`wait_shop_audit_aggregate_count`、`wait_shop_receive_or_send_aggregate_count`、`wait_user_deal_aggregate_count`、`dispute_aggregate_count`、`platform_auto_deal_aggregate_count` |
| 其他 | `logistics_abnormal`、`suspected_violation`、`appeal_todo`、`govern_auto_agree`、`negotiate_close` |

样本值：`total=8` 单售后单中 `return_for_receive=1`、`all_audit=1`、`wait_user_delivery=1`。

### E.3 售后详情

```
GET /v1/aftersale/pc/detail?after_sale_id=<id>
    &extra={"detail_upgrade_hit":"new","proof_record_show":"new"}
    &appid=1&_bid=ffa_aftersale&aid=4272&aftersale_platform_source=fxg
```

返回 `data` 20 个区块：

| 区块 | 内容 |
|---|---|
| `title_info` | 标题、倒计时、处理状态、背景色 |
| `actions` | **可执行动作**（见 E.4） |
| `after_sale_info` | 售后基础信息、备注、物流、日志、单据 |
| `order_info` | 商品、买家、订单、物流信息 |
| `linked_info` | 仲裁证据模板、责任依据、用户账号 |
| `progress_node` | **进度节点数组**（文本 + 时间 + 状态 0/1/2） |
| `refund_records` | 退款记录、打款记录、补偿记录、剩余可退金额 |
| `token` | JWT（写操作可能需携带，待验证） |
| `detail_header_info` | 商品头图、价格、换货 SKU 快照 |
| `contact_list` / `metrics` / `notice` / `extra` | 联系人、平台介入、公告、灰度 |

**进度节点样本**：用户申请退货 → 同意申请 → 买家寄回 → 商家退款 → 售后完成

### E.4 操作按钮与写接口

**列表行按钮**（`buttons[].button`）：

| code | 文案 | 类型 |
|---|---|---|
| `urge_sms_return` | 提醒发货 | 写 |
| `refund_audit` | 同意退款 | 写 |
| `fill_logistics` | 代填运单号 | 写 |
| `im_contact_user` | 联系买家 | 跳转 IM |
| `order_ship_logistics` | 正向发货查看物流 | 只读 |
| `return_logistics` | 退货查看物流 | 只读 |
| `money_tracking` | 钱款去向 | 只读 |
| `exchange_logistics_extend` | 延长收货 | 写 |
| `handle` | 查看详情 | 跳转 |

**详情页动作**（`actions[].id`）：

| id | 文案 | server_url | 说明 |
|---|---|---|---|
| `im_contact_user` | 联系买家 | IM 工作台 URL | 直接跳转可用 |
| `return_refund_agree` | 已收到货，退款 | 空 | 写接口，前端另调（待抓） |
| `fill_logistics_for_user` | 代买家填写退货运单号 | 空 | 写接口（待抓） |

> ⚠️ 写接口 URL 在构建产物 中拼接，`server_url` 为空。需真实点击一次接口记录确认
> （属 B 档，且涉及资金动作，必须在测试单上操作）。

### E.5 辅助只读接口

| 用途 | 方法 | 接口 |
|---|---|---|
| 售后会话（协商记录） | GET | `/as/help/get_after_sale_conv?after_sale_id=&order_id=` |
| 消息盒 | GET | `/v1/aftersale/get_msg_box?msg_box_scene=1` |
| 列表展示配置 | GET | `/shopuser/aftersale/getAfterSaleListShowConfig` |
| 引导文案 | POST | `/aftersale/get_guide` |
| 灰度 | GET | `/v1/aftersale/grayHit?scene=list_v1` |
| 平台公告 | GET | `/common/index/alerts?from_day_before=7` |

### E.6 售后聚合实现建议

1. **多店聚合的数据源**：每店调一次 `counts`（轻量）+ 一次 `list`（分页），
   按 `status_deadline` 升序合并，形成跨店待办队列。
2. **优先级排序**：用 `left_node_time`（剩余秒数）做倒计时，
   `approaching_deadline_audit` / `audit_ddl_in_one_day` 做红色预警。
3. **状态展示直接用 `text_part`**：`after_sale_status_text` / `after_sale_type_text` /
   `reason_text` 都是平台下发的成品文案，不需要自己维护枚举映射表。
4. **按钮渲染用 `buttons[].button` + `disabled`**：与订单页 `operation_actions` 同思路，
   避免展示平台不允许的操作。
5. **详情页区块按需加载**：列表已含足够信息（商品、金额、状态、截止时间），
   详情接口在用户点开后再调，降低请求量。

### E.7 对设计文档的影响

- 售后只读聚合已纳入 MVP（overview 2.1）；售后处理写操作在阶段二（overview 2.2），需先验证写接口。
- 数据模型已按此新增 `aftersale` 表（data-model 6.2 ⑯）（字段参考 E.1 `after_sale_info`）：
  `after_sale_id`（PK）、`shop_id`、`order_no`、`type`、`status`、`refund_amount_cents`、
  `status_deadline`、`apply_time`、`detail_json`、`synced_at`。
- [backend.md](../design/backend.md) 5.8 对账可扩展：对账时同时比对售后单状态，发现「平台已退款、本地无记录」异常。

> 索引见 [README.md](README.md)。
