from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_enterprise_contact_installer_wires_safe_internal_timers():
    text = (
        ROOT / "scripts/install_enterprise_contact_intelligence.sh"
    ).read_text()

    assert "empire-ops-privileged-helper.service" in text
    assert "empire-buyer-deferred-enrichment.service" in text
    assert "empire-buyer-deferred-enrichment.timer" in text
    assert "empire-predictive-revenue-enterprise-activation.service" in text
    assert "empire-predictive-revenue-enterprise-activation.timer" in text
    assert "empire-enterprise-contact-sync.service" in text
    assert "empire-enterprise-contact-repair.service" in text
    assert "empire-enterprise-contact-repair.timer" in text
    assert "/home/ubuntu/empire_os_repair_worktrees" in text
    assert "systemctl daemon-reload" in text
    assert "systemctl restart empire-ops-privileged-helper.service" in text
    assert (
        "systemctl enable --now empire-buyer-deferred-enrichment.timer"
        in text
    )
    assert (
        "systemctl enable --now "
        "empire-predictive-revenue-enterprise-activation.timer"
        in text
    )
    assert (
        "systemctl enable --now empire-enterprise-contact-repair.timer"
        in text
    )
    assert "outbound-governor" not in text
    assert "payment" not in text.lower()
