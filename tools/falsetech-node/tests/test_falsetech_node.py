from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "falsetech_node.py"
spec = spec_from_file_location("falsetech_node", MODULE_PATH)
node = module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(node)


def test_opaque_hash_and_uuid_names_are_detected():
    assert node.is_opaque_name(Path("file_0000000075b0822fac893f0e0c403b71.jpg"))
    assert node.is_opaque_name(Path("bb7b2657-f516-4208-bf05-d4074e730715.md"))


def test_required_source_names_are_never_renamed():
    assert not node.is_opaque_name(Path("package.json"))
    assert not node.is_opaque_name(Path("README.md"))


def test_safe_rename_is_limited_to_approved_roots(tmp_path):
    approved = tmp_path / "Downloads"
    outside = tmp_path / "Projects"
    approved.mkdir()
    outside.mkdir()
    source = approved / "file_0000000075b0822fac893f0e0c403b71.jpg"
    source.write_bytes(b"image")
    renamed, reason = node.safe_rename(source, [approved])
    assert renamed.exists()
    assert renamed.name.startswith("FalseTech-Image-")
    assert reason and reason.startswith("opaque_user_facing_name:")

    code_file = outside / "file_0000000075b0822fac893f0e0c403b71.py"
    code_file.write_text("print('keep path')", encoding="utf-8")
    unchanged, reason = node.safe_rename(code_file, [approved])
    assert unchanged == code_file
    assert reason == "opaque_name_cataloged_not_renamed"


def test_local_queue_is_idempotent_after_mark_sent(tmp_path):
    state = node.LocalState(tmp_path / "cache.db")
    operation_id = state.enqueue("test", "simlay", {"ok": True})
    pending = state.unsent()
    assert len(pending) == 1
    assert pending[0]["operation_id"] == operation_id
    state.mark_sent([operation_id])
    assert state.unsent() == []
