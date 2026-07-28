import pandas as pd

from app.processing.preprocessing import DataPreprocessor


def test_process_daily_measures_normalizes_rawametrix_budget_columns():
    df = pd.DataFrame(
        [
            {
                "date": "2024-01-01",
                "production": 100.0,
                "temperature": 25.0,
                "irradiation": 800.0,
                "budget_net_production": 120.0,
                "budget_real_irradiation": 1000.0,
                "budget_t_amb": 20.0,
            }
        ]
    )

    preprocessor = DataPreprocessor()
    cleaned = preprocessor.process_daily_measures(df)

    assert "budget_production" in cleaned.columns
    assert "budget_irradiation" in cleaned.columns
    assert "budget_temperature" in cleaned.columns
    assert cleaned.loc[0, "budget_production"] == 120.0
    assert cleaned.loc[0, "budget_irradiation"] == 1000.0
    assert cleaned.loc[0, "budget_temperature"] == 20.0
