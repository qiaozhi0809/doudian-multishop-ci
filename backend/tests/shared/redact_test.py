from app.shared.redact import mask_name, mask_phone, redact_mapping


def test_redact_mapping():
    out = redact_mapping({
        "cookies": "a",
        "token": "t",
        "user_name": "张三",
        "shop_name": "店A",
        "address": {"detail": "x"},
    })
    assert out == {
        "cookies": "***",
        "token": "***",
        "user_name": "张*",
        "shop_name": "店A",
        "address": "***",
    }


def test_redact_nested_and_lists():
    out = redact_mapping({
        "items": [{"mobile": "138" + "0000" + "0000", "proxy_url": "http://u:p@h:1"}],
        "tel": "x",
        "hotel": "keep",
    })
    assert out["items"][0] == {"mobile": "138****0000", "proxy_url": "***"}
    assert out["tel"] == "***"
    assert out["hotel"] == "keep"


def test_mask_phone_and_name():
    assert mask_phone("138" + "0000" + "0000") == "138****0000"
    assert mask_phone("138****0000") == "138****0000"
    assert mask_phone("123") == "***"
    assert mask_name("张三") == "张*"
    assert mask_name("张三丰") == "张**"
    assert mask_name("张") == "*"
    assert mask_name("") == ""


def test_redact_does_not_mutate_input():
    src = {"token": "t", "n": {"cookie": "c"}}
    redact_mapping(src)
    assert src == {"token": "t", "n": {"cookie": "c"}}


def test_display_and_id_keys_kept():
    out = redact_mapping({
        "proxy_display": "1.2.3.4:8000",
        "address_id": "106591750",
        "proxy_url": "http://u:p@h:1",
        "token_id": "t",
    })
    assert out == {
        "proxy_display": "1.2.3.4:8000",
        "address_id": "106591750",
        "proxy_url": "***",
        "token_id": "***",
    }
