from app.adapter.browser.scrape import parse_bank_card, parse_entity, parse_shop_id


def test_parse_bank_card_masked_number():
    """平台把卡号中间打码，去掉非数字后末四位就是真实尾号。"""
    text = (
        "提现用卡\n开户名\n张三\n银行卡号\n6222 **** **** 1234 567\n"
        "开户银行\n示例银行\n微信商户号\n1234567890\n"
    )

    assert parse_bank_card(text) == {"bank_name": "示例银行", "bank_tail": "4567"}


def test_parse_bank_card_returns_empty_when_absent():
    assert parse_bank_card("页面没有这些内容") == {}


def test_parse_shop_id():
    assert parse_shop_id("店铺管理\n店铺ID: 141327228\n开店时间 2026-03-22") == {
        "platform_shop_id": "141327228"
    }
    assert parse_shop_id("没有编号") == {}


def test_parse_entity():
    text = "主体信息\n公司名称\n示例商贸有限公司\n营业期限\n长期\n"
    assert parse_entity(text) == {"entity": "示例商贸有限公司"}
    assert parse_entity("未渲染出来") == {}
