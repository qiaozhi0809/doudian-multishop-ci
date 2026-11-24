## 附录 D：商品 / 库存模块 UI → 接口映射（2026-11-24 验证）

> 与[附录 C](order-page.md) 同源验证，覆盖「商品管理 / 商品创建 / 库存管理」三个页面。
> 结论：**展示层零缺口**；商品创建止步于表单配置（发布为写接口，未验证）。

### D.1 商品管理（`/ffa/g/list`）

#### 列表与计数

| 用途 | 方法 | 接口 | 备注 |
|---|---|---|---|
| 商品列表 | GET | `/product/tproduct/list` | **单条 192 字段**；`page` 0-based |
| 状态计数 | GET | `/product/tproduct/aggsProductCount` | 见下表 |
| 商品分组 | GET | `/product/tproduct/getProductGroupList` | `pageSize=100` |
| 类目树 | GET | `/product/tproduct/categoryOptionsN?cid=0` | 逐级下钻 |
| 经营指标 | GET | `/product/tproduct/listTractionItems` | 曝光/点击等 |
| 整改信息 | GET | `/product/tproduct/rectifyInfo` | 违规整改 |
| 质量分诊断 | GET | `/product_diagnose/tproduct/get_diagnose_quality_score_version` | 商品诊断 |
| 灰度开关 | GET | `/product/tproduct/isInAllowlist` | 一次性查大量 feature flag |

#### 状态计数（`aggsProductCount`）

| 字段 | 含义 | 样本 |
|---|---|---|
| `onsale` | 在售 | 6 |
| `audit` | 审核中 | 0 |
| `unpass` / `unpass_new` | 未通过 | 0 |
| `draft` | 草稿 | 0 |
| `forbidden` | 禁售/下架 | 0 |
| `sell_out_new` | 售罄 | 0 |

#### 列表筛选参数（`product/tproduct/list`）

`page`（0-based）、`pageSize`、`tab`（`onSale` 等）、`check_status`、`status`、
`draft_status`、`group_id`、`sku_type`、`supply_status`、`comment_percent`、
`order_field`、`sort`、`business_type`、`is_online`、`from_mng`、
`need_auto_rectify_info`、`need_pay_no_stock_skus`

#### 商品条目关键字段（192 中选摘）

| 分组 | 字段 |
|---|---|
| 标识 | `product_id`、`publish_id`、`out_product_id` |
| 名称图片 | `name`、`img`、`pics`、`product_url`、`product_url_for_copy` |
| 状态 | `status`、`check_status`、`tab`、`put_status`、`is_not_for_sale` |
| 价格 | `market_price`、`price_lower`、`price_higher`、`discount_price` |
| 库存 | `stock_num`、`self_sell_stock_num`、`promotion_stock_num`、`lock_stock_num`、`channel_stock_num` |
| SKU | `skus[]`、`spec_id`、`sku_price_read_only` |
| 类目 | `first_cid`、`second_cid`、`third_cid`、`category_leaf_id`、`category_name` |
| 运营 | `sell_num`、`sell_num_30d`、`collect_num`、`comment_num`、`comment_percent`、`quality_score` |
| 操作 | `operations`（可用操作列表，用于按钮渲染） |

### D.2 库存管理（`/ffa/morder/stock-manage/list`）

| 用途 | 方法 | 接口 | 备注 |
|---|---|---|---|
| 库存列表 | **POST** | `/stock/manage/list` | ⚠️ **`page` 1-based**；`_bid=ffa_order` |
| 仓库列表 | GET | `/stock/index/warehouse_list` | 多仓 |
| 操作权限 | GET | `/stock/manage/op_control` | 可否改库存 |
| SKU 诊断 | POST | `/stock/manage/sku_stock_diagnose` | 库存健康 |
| 增量排除 | GET | `/stock/increase/exclude` | 增量配置 |
| 编辑黑名单 | GET | `/stock/index/edit_black` | 不可编辑项 |

**请求体**（已验证）：

```json
{"page":1,"pageSize":10,"sort":0,"page_size":10,
 "appid":1,"__token":"...","_bid":"ffa_order","aid":4272,"_lid":"..."}
```

**响应顶层统计**：

| 字段 | 含义 |
|---|---|
| `total` | 商品数（样本 6） |
| `stock_alarm_cnt` | 库存预警数 |
| `sold_out_cnt` | 售罄数 |
| `stock_subscribe_cnt` | 到货订阅数 |
| `activity_stock_occupy_cnt` | 活动占用库存 |
| `channel_stock_occupy_cnt` | 渠道占用库存 |
| `advised_increase_spot_cnt` | 建议补货 |

**单条商品库存字段**（27 个中选摘）：

`total_stock_num`（总库存）、`spot_stock_num`（现货）、`future_stock_num`（未来库存）、
`total_occupied_stock_num`（占用）、`total_unoccupied_stock_num`（未占用）、
`skus[]`（SKU 级明细）、`warehouse_num`（仓数）、`is_alarming`（预警标位）、
`stock_type`、`shipping_mode`、`operations`、`stock_occupy_infos`

### D.3 商品创建（`/ffa/g/create`）

| 用途 | 方法 | 接口 | 状态 |
|---|---|---|---|
| 可创建检查 | GET | `/product/tproduct/canCreateGood?is_create=1` | ✅ 已识别 |
| 类目选择 | GET | `/product/tproduct/categoryOptionsN?cid=0` | ✅ 已识别 |
| 素材工具配置 | GET | `/material_api/product_material/check_gray` | ✅ 已识别 |
| 发布校验配置 | GET | `/product_diagnose/tproduct/diagnose_filed_config` | ✅ 已识别 |
| 类目属性模板 | — | 选完类目后加载 | ❌ 未触发（未选类目） |
| **提交发布** | — | 写接口 | ❌ 未触发，需真实提交一次 |

> 商品创建页的可展示部分 = 表单配置（类目树、属性 schema、素材工具）。
> 真正的「发布商品」是写接口，和订单的取号/发货同属 B 档验证范围。

### D.4 实现注意

1. **三处分页基准不同**（最易踩坑）：
   - `searchlist`（订单）：0-based
   - `product/tproduct/list`（商品）：0-based
   - `stock/manage/list`（库存）：**1-based**
   仓储层需按接口配置 `page_base`，禁止全局假设。
2. **现货与未来库存必须分开展示**：`spot_stock_num` 与 `future_stock_num` 是两套库存，
   简单相加会得出错误的"总可售"。
3. 三个模块的 `_bid` 不同：订单 `ffa_order`、商品 `ffa_goods`；
   库存接口虽挂在订单域（`ffa_order`）下，但路径是 `/stock/manage/`。
4. `operations` / `operation_actions` 字段可直接驱动按钮可用性，
   避免渲染平台不允许的操作。
5. 商品创建页未选类目时不会加载属性 schema，做「创建商品」功能时需按
   类目 → 属性 → 提交三段式实现，每段都有独立接口。

> 索引见 [README.md](README.md)。
