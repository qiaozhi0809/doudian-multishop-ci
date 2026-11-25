# M2 写接口样本（结构按 docs/api/write.md 已记录的实测请求 / 响应构造）

2026-11-25 的真实调用只覆盖了单订单、单 SKU、中通场景（A.2.2 / A.2.5 / A.2.6），
当时仓库里没有「商家自发、可打单」的订单样本可脱敏（gaps API-04），因此本目录文件是
**按已记录字段结构构造**的样本，编号与运单号全部为占位值，不是线上原样抓包。

| 文件 | 依据 | 说明 |
|---|---|---|
| `batch_fetch_tracking_nos.json` | A.2.2 | 1 单成功：运单号 / `print_data` / `sign` |
| `batch_fetch_fail.json` | A.2.2 第 8 条 | 只给 `fail_msg`、不带订单引用的失败（最坏情况） |
| `batch_fetch_partial_fail.json` | A.2.2 | 一成一败；失败项带 `shop_order_list`（该结构**未实测**，解析按容错实现） |
| `query_product_types.json` | A.2.7 | `logistics_product[0].selectedValue` 与 `added_services` |
| `cancel_tracking_nos.json` | A.2.6 | `success_list` / `fail_list` / 顶层 `fail_msg` |
| `fetch_and_ship.json` | A.2.5 | `success_deliver_list`（该接口失败结构未实测） |
| `receiveinfo.json` | read.md A.1 | `receive_info` + `post_addr` + `expire_time` + 空 `verify_type` |
| `get_order_logistics.json` | read.md A.1 / backend 5.5 | `logistics[].logistics_code` 即运单号 |

脱敏规则同上级目录 README：手机号 `138****0000`、姓名 `张*`、详细地址 `<详细地址>`；
订单号 `69000000000000000xx`、运单号 `792000000000xx`、`print_data` / `sign` 为占位串。
API-04 / 19 / 21 / 06 有真实结论后，用真实样本替换本目录并更新本说明。
