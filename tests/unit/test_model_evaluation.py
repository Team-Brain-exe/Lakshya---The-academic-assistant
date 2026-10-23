from ai.model_evaluation import summarize_tag_runs


def test_tag_run_summary_reports_repeat_consistency_per_chunk():
    report = summarize_tag_runs(
        ["chunk-1", "chunk-2"],
        [
            [{"chunk_id": "chunk-1", "cos": [1]}, {"chunk_id": "chunk-2", "cos": [1]}],
            [{"chunk_id": "chunk-1", "cos": [1]}],
        ],
    )

    assert report["repeat_count"] == 2
    assert report["exact_agreement_rate"] == 0.5
    assert report["mean_pairwise_jaccard"] == 0.5
    assert report["by_chunk"]["chunk-1"]["exact_agreement"] is True
    assert report["by_chunk"]["chunk-2"]["exact_agreement"] is False


def test_tag_run_summary_handles_all_untagged_repeated_chunks():
    report = summarize_tag_runs(["chunk-1"], [[], []])

    assert report["by_chunk"]["chunk-1"]["tags_by_run"] == [[], []]
    assert report["by_chunk"]["chunk-1"]["exact_agreement"] is True
    assert report["mean_pairwise_jaccard"] == 1.0
