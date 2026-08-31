import unittest

from cosmatter.dsh_combination_lab import DshCombinationLabError, all_pairs, compact_report, minimise_failing_combination, normalize_package_selection


class DshCombinationLabTests(unittest.TestCase):
    def test_minimises_a_synthetic_two_bundle_conflict(self) -> None:
        bundles = ("mission", "research", "graph", "document")
        calls: list[tuple[str, ...]] = []

        def probe(combo: tuple[str, ...]) -> bool:
            calls.append(combo)
            return not {"research", "document"}.issubset(combo)

        minimal = minimise_failing_combination(bundles, probe)
        report = compact_report(selected=bundles, healthy=False, minimal_failure=minimal, probe_count=len(calls))
        self.assertEqual(minimal, ("research", "document"))
        self.assertEqual(report["minimal_failure_bundles"], ["research", "document"])
        self.assertNotIn("path", str(report))

    def test_selection_and_pair_inputs_fail_closed(self) -> None:
        available = ("mission", "research", "graph")
        self.assertEqual(normalize_package_selection(available, ("graph", "mission")), ("mission", "graph"))
        self.assertEqual(all_pairs(available), (("mission", "research"), ("mission", "graph"), ("research", "graph")))
        with self.assertRaises(DshCombinationLabError):
            normalize_package_selection(available, ("unknown",))
        with self.assertRaises(DshCombinationLabError):
            compact_report(selected=("mission",), healthy=True, minimal_failure=("mission",), probe_count=1)


if __name__ == "__main__":
    unittest.main()
