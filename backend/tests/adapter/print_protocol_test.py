"""打印组件协议（flows 10 节）：documents 组装、消息与回执解析。"""

import base64

from app.adapter.print import protocol


def doc(**over):
    base = {
        "waybill_no": "79200000000001", "print_data": "PRINT", "sign": "SIGN",
        "template_url": "https://example.test/t.xml", "params": None,
        "custom_print_data": None, "custom_template_url": None,
    }
    base.update(over)
    return protocol.DocumentSpec(**base)


def test_documents_map_standard_fields():
    docs = protocol.build_documents([doc()])
    assert docs == [{
        "documentID": "79200000000001",
        "standard": {
            "signature": "SIGN",
            "encryptedData": "PRINT",
            "templateURL": "https://example.test/t.xml",
            "params": "",
        },
    }]


def test_documents_add_custom_block_when_present():
    docs = protocol.build_documents([
        doc(custom_print_data="CUSTOM", custom_template_url="https://example.test/c.xml")
    ])
    assert docs[0]["custom"] == {
        "data": "CUSTOM", "templateURL": "https://example.test/c.xml"}


def test_documents_use_oauth_params_and_empty_defaults():
    docs = protocol.build_documents([doc(params="oauth=1", template_url=None)])
    assert docs[0]["standard"]["params"] == "oauth=1"
    assert docs[0]["standard"]["templateURL"] == ""


def test_print_message_shape():
    msg = protocol.build_print_message(
        request_id="r1", printer="Printer A", documents=[{"x": 1}])
    assert msg == {
        "cmd": "print", "requestID": "r1", "version": 2, "isOpen": False,
        "previewType": "pdf",
        "task": {
            "taskID": "r1", "preview": False, "printConfig": "waybill",
            "printer": "Printer A", "documents": [{"x": 1}],
        },
    }


def test_get_printers_message_shape():
    assert protocol.build_get_printers("r2") == {
        "cmd": "getPrinters", "requestID": "r2", "version": 2}


def test_parse_printers_response():
    default, names = protocol.parse_printers({
        "cmd": "getPrinters", "requestID": "r2",
        "defaultPrinter": "Microsoft Print to PDF",
        "printers": [{"name": "Microsoft Print to PDF"}, {"name": "XP-58"}],
    })
    assert default == "Microsoft Print to PDF"
    assert names == ("Microsoft Print to PDF", "XP-58")


def test_parse_printers_tolerates_missing_default():
    default, names = protocol.parse_printers(
        {"cmd": "getPrinters", "printers": [{"name": "A"}]})
    assert default is None
    assert names == ("A",)


def test_parse_result_success_with_decoded_detail():
    detail = base64.b64encode("渲染成功".encode()).decode()
    outcome = protocol.parse_print_result({
        "cmd": "notifyPrintResult", "requestID": "r1", "status": "success",
        "printStatus": [{"status": "success", "detail": detail}],
    })
    assert outcome.ok
    assert outcome.code == protocol.RESULT_SUCCESS
    assert "渲染成功" in outcome.detail


def test_parse_result_failure_keeps_decoded_detail():
    detail = base64.b64encode("打印机缺纸".encode()).decode()
    outcome = protocol.parse_print_result({
        "cmd": "notifyPrintResult", "requestID": "r1", "status": "failed",
        "printStatus": [{"status": "failed", "detail": detail}],
    })
    assert not outcome.ok
    assert outcome.code == protocol.RESULT_COMPONENT_FAILED
    assert "打印机缺纸" in outcome.detail


def test_parse_result_without_status_is_not_success():
    outcome = protocol.parse_print_result(
        {"cmd": "notifyPrintResult", "requestID": "r1"})
    assert not outcome.ok
    assert outcome.code == protocol.RESULT_UNRECOGNIZED
