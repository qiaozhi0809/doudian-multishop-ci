import structlog

from app.shared.logging_setup import configure_logging


def test_logging_redacts(capsys):
    configure_logging(json=True)
    token = "tok_" + "x" * 8
    phone = "138" + "0000" + "0000"
    structlog.get_logger().info("call", token=token, mobile=phone, note=f"联系 {phone}")
    out = capsys.readouterr().out
    assert "call" in out
    assert token not in out
    assert phone not in out
