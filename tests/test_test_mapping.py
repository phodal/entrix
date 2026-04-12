"""Tests for entrix.test_mapping."""

from pathlib import Path

import entrix.test_mapping as test_mapping_module
from entrix.test_mapping import analyze_test_mappings


def test_analyze_test_mappings_marks_changed_typescript_counterpart(tmp_path: Path):
    (tmp_path / "src" / "core" / "skills" / "__tests__").mkdir(parents=True)
    (tmp_path / "src" / "core" / "skills" / "skill-loader.ts").write_text(
        "export function load() {}\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "core" / "skills" / "__tests__" / "skill-loader.test.ts").write_text(
        "test('load', () => {})\n",
        encoding="utf-8",
    )

    result = analyze_test_mappings(
        tmp_path,
        [
            "src/core/skills/skill-loader.ts",
            "src/core/skills/__tests__/skill-loader.test.ts",
        ],
        use_graph=False,
    )

    assert result["status"] == "ok"
    assert result["skipped_test_files"] == ["src/core/skills/__tests__/skill-loader.test.ts"]
    assert result["mappings"][0]["status"] == "changed"
    assert result["mappings"][0]["resolver_kind"] == "path_heuristic"
    assert result["status_counts"] == {"changed": 1}
    assert result["resolver_counts"] == {"path_heuristic": 1}


def test_analyze_test_mappings_marks_inline_rust_tests(tmp_path: Path):
    (tmp_path / "crates" / "demo" / "src").mkdir(parents=True)
    (tmp_path / "crates" / "demo" / "Cargo.toml").write_text(
        "[package]\nname = 'demo'\nversion = '0.1.0'\n",
        encoding="utf-8",
    )
    (tmp_path / "crates" / "demo" / "src" / "pty.rs").write_text(
        "pub fn run() {}\n#[cfg(test)]\nmod tests {\n    #[test]\n    fn works() {}\n}\n",
        encoding="utf-8",
    )

    result = analyze_test_mappings(tmp_path, ["crates/demo/src/pty.rs"], use_graph=False)

    assert result["mappings"][0]["status"] == "inline"
    assert result["mappings"][0]["has_inline_tests"] is True
    assert result["status_counts"] == {"inline": 1}
    assert result["resolver_counts"] == {"inline_test": 1}


def test_analyze_test_mappings_marks_missing_java_main_source(tmp_path: Path):
    (tmp_path / "src" / "main" / "java" / "com" / "example").mkdir(parents=True)
    (tmp_path / "src" / "main" / "java" / "com" / "example" / "OrderService.java").write_text(
        "class OrderService {}\n",
        encoding="utf-8",
    )

    result = analyze_test_mappings(
        tmp_path,
        ["src/main/java/com/example/OrderService.java"],
        use_graph=False,
    )

    assert result["mappings"][0]["language"] == "java"
    assert result["mappings"][0]["status"] == "missing"
    assert result["status_counts"] == {"missing": 1}
    assert result["resolver_counts"] == {"path_heuristic": 1}


def test_analyze_test_mappings_prefers_graph_semantic_evidence(monkeypatch, tmp_path: Path):
    (tmp_path / "crates" / "demo" / "src").mkdir(parents=True)
    (tmp_path / "crates" / "demo" / "tests").mkdir(parents=True)
    (tmp_path / "crates" / "demo" / "Cargo.toml").write_text(
        "[package]\nname = 'demo'\nversion = '0.1.0'\n",
        encoding="utf-8",
    )
    (tmp_path / "crates" / "demo" / "src" / "git.rs").write_text(
        "pub fn read() {}\n",
        encoding="utf-8",
    )
    (tmp_path / "crates" / "demo" / "tests" / "rust_api_git_read_routes.rs").write_text(
        "#[test]\nfn routes() {}\n",
        encoding="utf-8",
    )

    class FakeGraphRunner:
        def __init__(self, project_root: Path):
            self.project_root = project_root
            self.available = True

        def build_graph(self, *, base: str = "HEAD", build_mode: str = "auto") -> dict:
            return {"status": "ok", "build_type": build_mode, "base": base}

        def query(self, query_type: str, target: str, *, base: str = "HEAD", build_mode: str = "auto") -> dict:
            del base, build_mode
            assert query_type == "tests_for"
            if target == "crates/demo/src/git.rs":
                return {
                    "status": "ok",
                    "results": [
                        {
                            "qualified_name": "crates/demo/tests/rust_api_git_read_routes.rs:test:1",
                            "file_path": "crates/demo/tests/rust_api_git_read_routes.rs",
                        }
                    ],
                }
            return {"status": "ok", "results": []}

    monkeypatch.setattr(test_mapping_module, "GraphRunner", FakeGraphRunner)

    result = analyze_test_mappings(tmp_path, ["crates/demo/src/git.rs"], use_graph=True, build_mode="skip")

    assert result["graph"]["available"] is True
    assert result["mappings"][0]["status"] == "exists"
    assert result["mappings"][0]["resolver_kind"] == "semantic_graph"
    assert result["mappings"][0]["graph_test_files"] == [
        "crates/demo/tests/rust_api_git_read_routes.rs"
    ]
    assert result["status_counts"] == {"exists": 1}
    assert result["resolver_counts"] == {"semantic_graph": 1}
