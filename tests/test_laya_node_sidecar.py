from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "tools/laya_node/server.mjs"
PRELOAD = ROOT / "tools/laya_node/preload.mjs"
PACKAGE = ROOT / "tools/laya_node/package.json"
SERVICE = ROOT / "empire-laya-shadow.service"
BOOTSTRAP = ROOT / "scripts/bootstrap_laya_node.sh"


def test_laya_node_sidecar_is_loopback_only_and_shadow_only():
    server = SERVER.read_text(encoding="utf-8")
    assert '"127.0.0.1"' in server
    assert '"/v1/systemone"' in server
    assert "shadow_only: true" in server
    assert 'execution_authority: "none"' in server
    assert ".systemOne(" in server


def test_laya_node_dependency_is_exactly_pinned():
    package = PACKAGE.read_text(encoding="utf-8")
    assert '"@receptron/laya": "0.1.2"' in package


def test_laya_service_blocks_external_network_after_preload():
    service = SERVICE.read_text(encoding="utf-8")
    assert "IPAddressDeny=any" in service
    assert "IPAddressAllow=localhost" in service
    assert "MemoryMax=4G" in service
    assert "ReadWritePaths=/srv/empire_os/runtime/laya" in service


def test_laya_bootstrap_has_ram_and_disk_gates():
    bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
    assert "MemAvailable_kB" in bootstrap
    assert "DiskAvailable_kB" in bootstrap
    assert "2800000" in bootstrap
    assert "4000000" in bootstrap
    assert "preload.mjs" in bootstrap
