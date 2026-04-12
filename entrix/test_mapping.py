"""Cross-language test mapping with optional graph enrichment."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from entrix.runners.graph import GraphRunner
from entrix.structure.impact import filter_code_files, git_changed_files


def language_for_path(rel_path: str) -> str:
    suffix = Path(rel_path).suffix.lower()
    return {
        ".java": "java",
        ".js": "javascript",
        ".jsx": "jsx",
        ".rs": "rust",
        ".ts": "typescript",
        ".tsx": "tsx",
    }.get(suffix, "unknown")


def normalize_rel_path(path: str) -> str:
    return path.strip().strip('"').replace("\\", "/")


def generic_test_file(rel_path: str) -> bool:
    lowered = rel_path.lower()
    return (
        "/tests/" in lowered
        or "/__tests__/" in lowered
        or "/e2e/" in lowered
        or ".test." in lowered
        or ".spec." in lowered
    )


def normalized_tokens(value: str) -> set[str]:
    tokens = {
        token.lower()
        for token in "".join(ch if ch.isalnum() else " " for ch in value).split()
    }
    return {
        token
        for token in tokens
        if token not in {"test", "tests", "spec", "specs", "it", "mod", "main", "lib"}
    }


def _existing_paths(project_root: Path, candidates: set[str]) -> list[str]:
    return sorted(path for path in candidates if (project_root / path).exists())


def _file_contains_any(path: Path, needles: list[str]) -> bool:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return any(needle in content for needle in needles)


def _find_crate_root(path: Path, project_root: Path) -> Path | None:
    current = path.parent
    while current is not None:
        if (current / "Cargo.toml").exists():
            return current
        if current == project_root:
            break
        current = current.parent
    return None


@dataclass
class ResolverOutcome:
    related_test_files: list[str]
    has_inline_tests: bool = False
    can_assert_missing: bool = False
    resolver_kind: str = "unsupported"
    confidence: str = "unknown"


class AutoTestResolver:
    def supports(self, language: str) -> bool:
        raise NotImplementedError

    def is_test_file(self, rel_path: str) -> bool:
        raise NotImplementedError

    def resolve(self, project_root: Path, rel_path: str, language: str) -> ResolverOutcome:
        raise NotImplementedError


class TypeScriptResolver(AutoTestResolver):
    def supports(self, language: str) -> bool:
        return language in {"typescript", "tsx", "javascript", "jsx"}

    def is_test_file(self, rel_path: str) -> bool:
        return generic_test_file(rel_path)

    def resolve(self, project_root: Path, rel_path: str, language: str) -> ResolverOutcome:
        path = Path(rel_path)
        parent = path.parent
        stem = path.stem
        ext_family = {
            "typescript": ["ts", "tsx"],
            "tsx": ["ts", "tsx"],
            "javascript": ["js", "jsx"],
            "jsx": ["js", "jsx"],
        }.get(language, ["ts", "tsx", "js", "jsx"])

        candidates: set[str] = set()
        for ext in ext_family:
            for base_dir in (parent, parent / "__tests__", parent / "tests"):
                candidates.add((base_dir / f"{stem}.test.{ext}").as_posix())
                candidates.add((base_dir / f"{stem}.spec.{ext}").as_posix())

        return ResolverOutcome(
            related_test_files=_existing_paths(project_root, candidates),
            can_assert_missing=True,
            resolver_kind="path_heuristic",
            confidence="high",
        )


class JavaResolver(AutoTestResolver):
    def supports(self, language: str) -> bool:
        return language == "java"

    def is_test_file(self, rel_path: str) -> bool:
        lowered = rel_path.lower()
        return (
            "/src/test/java/" in lowered
            or lowered.endswith("test.java")
            or lowered.endswith("tests.java")
            or lowered.endswith("it.java")
        )

    def resolve(self, project_root: Path, rel_path: str, language: str) -> ResolverOutcome:
        del language
        candidates: set[str] = set()
        can_assert_missing = False
        if rel_path.startswith("src/main/java/"):
            can_assert_missing = True
            suffix = Path(rel_path.removeprefix("src/main/java/"))
            test_base = Path("src/test/java") / suffix
            parent = test_base.parent
            stem = test_base.stem
            candidates.add((parent / f"{stem}Test.java").as_posix())
            candidates.add((parent / f"{stem}Tests.java").as_posix())
            candidates.add((parent / f"{stem}IT.java").as_posix())

        return ResolverOutcome(
            related_test_files=_existing_paths(project_root, candidates),
            can_assert_missing=can_assert_missing,
            resolver_kind="path_heuristic",
            confidence="high" if can_assert_missing else "low",
        )


class RustResolver(AutoTestResolver):
    def supports(self, language: str) -> bool:
        return language == "rust"

    def is_test_file(self, rel_path: str) -> bool:
        lowered = rel_path.lower()
        return (
            generic_test_file(rel_path)
            or lowered.endswith("_test.rs")
            or lowered.endswith(".test.rs")
            or lowered.endswith("/tests.rs")
            or "/tests/" in lowered
            or (Path(rel_path).name.startswith("tests_") and lowered.endswith(".rs"))
        )

    def resolve(self, project_root: Path, rel_path: str, language: str) -> ResolverOutcome:
        del language
        source_path = project_root / rel_path
        has_inline_tests = _file_contains_any(source_path, ["#[cfg(test)]", "#[test]"])
        path = Path(rel_path)
        parent = path.parent
        stem = path.stem
        candidates: set[str] = set()

        if stem == "mod":
            dir_path = project_root / parent
            if dir_path.is_dir():
                for child in dir_path.iterdir():
                    if not child.is_file() or child.suffix.lower() != ".rs":
                        continue
                    name = child.name
                    if name == "tests.rs" or (name.startswith("tests_") and name.endswith(".rs")):
                        candidates.add(child.relative_to(project_root).as_posix())
        else:
            candidates.add((parent / f"{stem}_test.rs").as_posix())
            candidates.add((parent / f"{stem}_tests.rs").as_posix())
            candidates.add((parent / f"{stem}.test.rs").as_posix())

        crate_root = _find_crate_root(source_path, project_root)
        source_tokens = normalized_tokens(stem)
        if crate_root is not None and source_tokens:
            tests_dir = crate_root / "tests"
            if tests_dir.is_dir():
                for child in tests_dir.rglob("*.rs"):
                    test_tokens = normalized_tokens(child.stem)
                    if test_tokens and not source_tokens.isdisjoint(test_tokens):
                        candidates.add(child.relative_to(project_root).as_posix())

        existing = _existing_paths(project_root, candidates)
        return ResolverOutcome(
            related_test_files=existing,
            has_inline_tests=has_inline_tests,
            can_assert_missing=False,
            resolver_kind="inline_test" if has_inline_tests else "hybrid_heuristic",
            confidence="high" if has_inline_tests else ("medium" if existing else "low"),
        )


class ResolverRegistry:
    def __init__(self) -> None:
        self.resolvers: list[AutoTestResolver] = [
            TypeScriptResolver(),
            RustResolver(),
            JavaResolver(),
        ]

    def is_test_file(self, rel_path: str) -> bool:
        normalized = normalize_rel_path(rel_path)
        language = language_for_path(normalized)
        return any(
            resolver.is_test_file(normalized)
            for resolver in self.resolvers
            if resolver.supports(language)
        ) or generic_test_file(normalized)

    def analyze_file(
        self,
        project_root: Path,
        rel_path: str,
        changed_files: set[str],
        *,
        graph_test_files: list[str] | None = None,
    ) -> dict[str, Any]:
        normalized = normalize_rel_path(rel_path)
        language = language_for_path(normalized)
        outcome = next(
            (
                resolver.resolve(project_root, normalized, language)
                for resolver in self.resolvers
                if resolver.supports(language)
            ),
            ResolverOutcome([]),
        )
        graph_test_files = sorted(set(graph_test_files or []))
        has_inline_tests = outcome.has_inline_tests or normalized in graph_test_files
        related = sorted(set(outcome.related_test_files) | set(graph_test_files))
        resolver_kind = "semantic_graph" if graph_test_files else outcome.resolver_kind
        confidence = "high" if graph_test_files else outcome.confidence

        if has_inline_tests:
            status = "inline"
        elif any(test_file in changed_files for test_file in related):
            status = "changed"
        elif related:
            status = "exists"
        elif outcome.can_assert_missing:
            status = "missing"
        else:
            status = "unknown"

        return {
            "source_file": normalized,
            "language": language,
            "status": status,
            "related_test_files": related,
            "graph_test_files": graph_test_files,
            "resolver_kind": resolver_kind,
            "confidence": confidence,
            "has_inline_tests": has_inline_tests,
        }


def analyze_test_mappings(
    project_root: Path,
    changed_files: list[str] | None = None,
    *,
    base: str = "HEAD",
    use_graph: bool = True,
    build_mode: str = "auto",
) -> dict[str, Any]:
    raw_changed = list(changed_files) if changed_files is not None else git_changed_files(project_root, base)
    changed = list(dict.fromkeys(filter_code_files(raw_changed, project_root)))
    registry = ResolverRegistry()
    skipped_test_files = [path for path in changed if registry.is_test_file(path)]
    source_files = [path for path in changed if path not in skipped_test_files]
    changed_set = set(changed)

    graph_summary: dict[str, Any] = {
        "available": False,
        "status": "disabled" if not use_graph else "unavailable",
        "reason": "graph disabled" if not use_graph else "graph backend unavailable",
    }
    graph_test_files_by_source: dict[str, list[str]] = {}
    if use_graph:
        runner = GraphRunner(project_root)
        if runner.available:
            build = runner.build_graph(base=base, build_mode=build_mode)
            graph_summary = {
                "available": build.get("status") != "unavailable",
                "status": build.get("status", "ok"),
                "build": build,
            }
            if build.get("status") != "unavailable":
                for source_file in source_files:
                    query = runner.query("tests_for", source_file, base=base, build_mode="skip")
                    if query.get("status") != "ok":
                        continue
                    graph_test_files_by_source[source_file] = sorted(
                        {
                            item["file_path"]
                            for item in query.get("results", [])
                            if isinstance(item, dict) and isinstance(item.get("file_path"), str)
                        }
                    )

    mappings = [
        registry.analyze_file(
            project_root,
            source_file,
            changed_set,
            graph_test_files=graph_test_files_by_source.get(source_file, []),
        )
        for source_file in source_files
    ]
    counts: dict[str, int] = {}
    for mapping in mappings:
        counts[mapping["status"]] = counts.get(mapping["status"], 0) + 1

    return {
        "status": "ok",
        "summary": (
            f"Analyzed test mappings for {len(source_files)} changed source file(s); "
            f"skipped {len(skipped_test_files)} changed test file(s)."
        ),
        "base": base,
        "changed_files": changed,
        "skipped_test_files": skipped_test_files,
        "mappings": mappings,
        "status_counts": counts,
        "graph": graph_summary,
    }
