"""Tests for the built-in structural analyzer."""

import importlib.util
from pathlib import Path

import pytest

from routa_fitness.structure.builtin import BuiltinGraphAdapter


pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("tree_sitter_language_pack") is None,
    reason="tree-sitter-language-pack is not installed",
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_builtin_graph_parses_typescript_and_links_tests(tmp_path: Path):
    _write(
        tmp_path / "src" / "mod.ts",
        "export function run() { return helper() }\nfunction helper() { return 1 }\n",
    )
    _write(
        tmp_path / "src" / "mod.test.ts",
        "import { run } from './mod'\ntest('run works', () => run())\n",
    )

    adapter = BuiltinGraphAdapter(tmp_path)
    build = adapter.build_or_update(full=True)
    query = adapter.query("tests_for", "src/mod.ts:run")

    assert build["status"] == "ok"
    assert "typescript" in build["languages"]
    assert query["status"] == "ok"
    assert [item["file_path"] for item in query["results"]] == ["src/mod.test.ts"]


def test_builtin_graph_scans_repo_beyond_default_roots(tmp_path: Path):
    _write(
        tmp_path / "pkg" / "service.py",
        "def run():\n    return 1\n",
    )
    _write(
        tmp_path / "tests" / "service_test.py",
        "from pkg.service import run\n\n\ndef test_run():\n    assert run() == 1\n",
    )

    adapter = BuiltinGraphAdapter(tmp_path)
    build = adapter.build_or_update(full=True)
    tests = adapter.query("tests_for", "pkg/service.py:run")

    assert build["status"] == "ok"
    assert build["files_updated"] == 2
    assert [item["qualified_name"] for item in tests["results"]] == [
        "tests/service_test.py:test_run"
    ]


def test_builtin_graph_parses_python_and_tracks_import_impact(tmp_path: Path):
    _write(
        tmp_path / "src" / "service.py",
        "def run():\n    return helper()\n\n\ndef helper():\n    return 1\n",
    )
    _write(
        tmp_path / "src" / "consumer.py",
        "from .service import run\n\n\ndef consume():\n    return run()\n",
    )
    _write(
        tmp_path / "src" / "test_service.py",
        "from .service import run\n\n\ndef test_run():\n    assert run() == 1\n",
    )

    adapter = BuiltinGraphAdapter(tmp_path)
    adapter.build_or_update(full=True)
    impact = adapter.impact_radius(["src/service.py"], depth=1)
    tests = adapter.query("tests_for", "src/service.py:run")

    assert impact["status"] == "ok"
    assert sorted(impact["impacted_files"]) == ["src/consumer.py", "src/test_service.py"]
    assert [item["qualified_name"] for item in tests["results"]] == ["src/test_service.py:test_run"]


def test_builtin_graph_qualifies_python_class_methods(tmp_path: Path):
    _write(
        tmp_path / "src" / "service.py",
        "class Service:\n    def run(self):\n        return helper()\n\n\ndef helper():\n    return 1\n",
    )

    adapter = BuiltinGraphAdapter(tmp_path)
    adapter.build_or_update(full=True)
    children = adapter.query("children_of", "src/service.py")
    callees = adapter.query("callees_of", "src/service.py:Service.run")

    assert {item["qualified_name"] for item in children["results"]} == {
        "src/service.py:Service",
        "src/service.py:Service.run",
        "src/service.py:helper",
    }
    assert [item["qualified_name"] for item in callees["results"]] == ["src/service.py:helper"]


def test_builtin_graph_parses_rust_test_attributes(tmp_path: Path):
    _write(
        tmp_path / "crates" / "demo" / "src" / "lib.rs",
        "pub fn compute() -> i32 { 1 }\n\n#[cfg(test)]\nmod tests {\n    use super::compute;\n\n    #[test]\n    fn compute_works() {\n        assert_eq!(compute(), 1);\n    }\n}\n",
    )

    adapter = BuiltinGraphAdapter(tmp_path)
    build = adapter.build_or_update(full=True)
    tests = adapter.query("tests_for", "crates/demo/src/lib.rs:compute")
    stats = adapter.stats()

    assert build["status"] == "ok"
    assert "rust" in build["languages"]
    assert tests["status"] == "ok"
    assert [item["qualified_name"] for item in tests["results"]] == [
        "crates/demo/src/lib.rs:compute_works"
    ]
    assert stats["backend"] == "builtin-tree-sitter"


def test_builtin_graph_qualifies_rust_impl_methods(tmp_path: Path):
    _write(
        tmp_path / "crates" / "demo" / "src" / "lib.rs",
        "struct Runner;\n\nimpl Runner {\n    fn run(&self) -> i32 {\n        helper()\n    }\n}\n\nfn helper() -> i32 {\n    1\n}\n",
    )

    adapter = BuiltinGraphAdapter(tmp_path)
    adapter.build_or_update(full=True)
    children = adapter.query("children_of", "crates/demo/src/lib.rs")
    callees = adapter.query("callees_of", "crates/demo/src/lib.rs:Runner.run")

    assert "crates/demo/src/lib.rs:Runner.run" in {
        item["qualified_name"] for item in children["results"]
    }
    assert [item["qualified_name"] for item in callees["results"]] == [
        "crates/demo/src/lib.rs:helper"
    ]


def test_builtin_graph_qualifies_typescript_class_methods(tmp_path: Path):
    _write(
        tmp_path / "src" / "runner.ts",
        "class Runner {\n  run() {\n    return helper();\n  }\n}\n\nfunction helper() {\n  return 1;\n}\n",
    )

    adapter = BuiltinGraphAdapter(tmp_path)
    adapter.build_or_update(full=True)
    children = adapter.query("children_of", "src/runner.ts")
    callees = adapter.query("callees_of", "src/runner.ts:Runner.run")

    assert "src/runner.ts:Runner.run" in {item["qualified_name"] for item in children["results"]}
    assert [item["qualified_name"] for item in callees["results"]] == ["src/runner.ts:helper"]


def test_builtin_graph_limits_call_edges_to_local_or_imported_symbols(tmp_path: Path):
    _write(
        tmp_path / "src" / "dep.py",
        "def run():\n    return 1\n",
    )
    _write(
        tmp_path / "src" / "other.py",
        "def run():\n    return 2\n",
    )
    _write(
        tmp_path / "src" / "consumer.py",
        "from .dep import run\n\n\ndef consume():\n    return run()\n",
    )

    adapter = BuiltinGraphAdapter(tmp_path)
    adapter.build_or_update(full=True)
    callees = adapter.query("callees_of", "src/consumer.py:consume")

    assert [item["qualified_name"] for item in callees["results"]] == ["src/dep.py:run"]


def test_builtin_graph_avoids_ambiguous_global_call_matches(tmp_path: Path):
    _write(
        tmp_path / "src" / "first.py",
        "def run():\n    return 1\n",
    )
    _write(
        tmp_path / "src" / "second.py",
        "def run():\n    return 2\n",
    )
    _write(
        tmp_path / "src" / "consumer.py",
        "def consume():\n    return run()\n",
    )

    adapter = BuiltinGraphAdapter(tmp_path)
    adapter.build_or_update(full=True)
    callees = adapter.query("callees_of", "src/consumer.py:consume")

    assert callees["results"] == []


def test_builtin_graph_limits_tests_to_matching_symbols(tmp_path: Path):
    _write(
        tmp_path / "src" / "mod.ts",
        "export function run() { return 1 }\nexport function helper() { return 2 }\n",
    )
    _write(
        tmp_path / "src" / "mod.test.ts",
        "import { run, helper } from './mod'\ntest('run works', () => run())\nvoid helper\n",
    )

    adapter = BuiltinGraphAdapter(tmp_path)
    adapter.build_or_update(full=True)
    run_tests = adapter.query("tests_for", "src/mod.ts:run")
    helper_tests = adapter.query("tests_for", "src/mod.ts:helper")

    assert [item["qualified_name"] for item in run_tests["results"]] == ["src/mod.test.ts:test:2"]
    assert helper_tests["results"] == []


def test_builtin_graph_matches_mocked_function_targets_in_tests(tmp_path: Path):
    _write(
        tmp_path / "src" / "boards.ts",
        "export async function ensureDefaultBoard() { return { id: 'board-1' } }\n",
    )
    _write(
        tmp_path / "src" / "task-board-context.test.ts",
        "import { describe, expect, it, vi } from 'vitest'\n"
        "import { ensureDefaultBoard } from './boards'\n"
        "vi.mock('./boards', () => ({ ensureDefaultBoard: vi.fn() }))\n"
        "describe('ctx', () => {\n"
        "  it('uses default board', async () => {\n"
        "    vi.mocked(ensureDefaultBoard).mockResolvedValue({ id: 'board-1' })\n"
        "    expect(ensureDefaultBoard).toBeDefined()\n"
        "  })\n"
        "})\n",
    )

    adapter = BuiltinGraphAdapter(tmp_path)
    adapter.build_or_update(full=True)
    tests = adapter.query("tests_for", "src/boards.ts:ensureDefaultBoard")

    assert [item["qualified_name"] for item in tests["results"]] == [
        "src/task-board-context.test.ts:test:5"
    ]


def test_builtin_graph_queries_from_persisted_index_without_file_cache(tmp_path: Path):
    _write(
        tmp_path / "src" / "service.py",
        "def run():\n    return helper()\n\n\ndef helper():\n    return 1\n",
    )
    _write(
        tmp_path / "src" / "consumer.py",
        "from .service import run\n\n\ndef consume():\n    return run()\n",
    )
    _write(
        tmp_path / "src" / "test_service.py",
        "from .service import run\n\n\ndef test_run():\n    assert run() == 1\n",
    )

    adapter = BuiltinGraphAdapter(tmp_path)
    adapter.build_or_update(full=True)
    adapter.files_cache_path.unlink()

    persisted = BuiltinGraphAdapter(tmp_path)
    stats = persisted.stats()
    impact = persisted.impact_radius(["src/service.py"], depth=1)
    tests = persisted.query("tests_for", "src/service.py:run")

    assert stats["status"] == "ok"
    assert stats["files"] == 3
    assert sorted(impact["impacted_files"]) == ["src/consumer.py", "src/test_service.py"]
    assert [item["qualified_name"] for item in tests["results"]] == ["src/test_service.py:test_run"]
