import pandas as pd

from ceb import config as C, explore


def test_detects_planted_hotspot(clustered):
    gdf = explore.run(clustered)
    glob = pd.read_csv(C.REPORTS / "global_morans_i.csv")
    q = glob.query("variable == 'burden' and weights == 'queen'").iloc[0]
    assert q.I > 0.3 and q.p_perm < 0.01

    hh = gdf[gdf["burden_cluster_fdr"] == "High-High"]
    assert len(hh) >= 8                                    # most of the 16 planted tracts
    assert (hh["community_area"] == "Englewood").mean() > 0.9
    assert (gdf["burden_cluster_fdr"] != "Not significant").sum() <= \
           (gdf["burden_cluster_p05"] != "Not significant").sum()  # FDR is stricter

    report = (C.REPORTS / "spatial_analysis_report.md").read_text()
    assert "positive and statistically significant" in report and "Englewood" in report
    assert "—" not in report
    for f in ["lisa_burden.png", "lisa_share_severe.png", "moran_scatter_burden.png", "small_multiples.png"]:
        assert (C.REPORTS / "figures" / f).exists()


def test_no_false_clustering_on_random_data(random_pattern):
    gdf = explore.run(random_pattern)
    glob = pd.read_csv(C.REPORTS / "global_morans_i.csv")
    q = glob.query("variable == 'burden' and weights == 'queen'").iloc[0]
    assert q.p_perm > 0.05
    assert (gdf["burden_cluster_fdr"] == "High-High").sum() <= 2


def test_runs_without_community_areas(clustered):
    gdf = explore.run(None)
    assert gdf["community_area"].isna().all()
