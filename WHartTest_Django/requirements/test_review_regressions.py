from django.test import SimpleTestCase

from requirements.services import (
    RequirementReviewService,
    normalize_score,
)


class NormalizeScoreTests(SimpleTestCase):
    def test_normalizes_missing_strings_and_out_of_range_values(self):
        self.assertEqual(normalize_score(None), 70)
        self.assertEqual(normalize_score("62"), 62)
        self.assertEqual(normalize_score(-5), 0)
        self.assertEqual(normalize_score(105), 100)
        self.assertEqual(normalize_score(True), 70)

    def test_report_fields_never_receive_null_scores(self):
        class Report:
            def save(self):
                self.saved = True

        report = Report()
        result = {
            "overall_score": "67",
            "overall_rating": "needs_improvement",
            "recommendations": [],
            "specialized_analyses": {
                "completeness_analysis": {"overall_score": 70},
                "consistency_analysis": {"overall_score": "62"},
                "clarity_analysis": {"overall_score": 78.4},
                "testability_analysis": {"overall_score": 52},
                "feasibility_analysis": {"overall_score": None},
                "logic_analysis": {"overall_score": 70},
            },
        }

        service = RequirementReviewService.__new__(RequirementReviewService)
        service._update_review_report(report, result)

        self.assertTrue(report.saved)
        self.assertEqual(report.completion_score, 67)
        self.assertEqual(report.consistency_score, 62)
        self.assertEqual(report.clarity_score, 78)
        self.assertEqual(report.feasibility_score, 70)
        self.assertEqual(
            report.specialized_analyses["feasibility_analysis"]["overall_score"],
            70,
        )
