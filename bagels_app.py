import streamlit as st
import pandas as pd
from datetime import timedelta

FILE_PATH = "Varso_cleaned.xlsx"

BAGELS_MENU = [
    # Bagels "pré-faits"
    "Cheddar i boczuś",
    "Warszawski LOX",
    "Vege Halloumi",
    "Sezonowa Nocciola",

    # Bases de bagels
    "Bajgiel Chałka",
    "Bajgiel Cheddar",
    "Bajgiel Golas",
    "Bajgiel Mak",
    "Bajgiel Mix",
    "Bajgiel Sezam",
]

@st.cache_data
def load_data(path: str):
    # Products
    products = pd.read_excel(path, sheet_name="Products_clean")
    products["quantity"] = pd.to_numeric(products["quantity"], errors="coerce").fillna(0)
    products["quantity"] = products["quantity"] / 1000  # 147.000 => 147

    # Keep only bagels
    bagels = products[products["product_name"].isin(BAGELS_MENU)].copy()

    # Customers (for weekday pattern)
    customers = pd.read_excel(path, sheet_name="Customers_clean")
    customers["date"] = pd.to_datetime(customers["date"])
    customers["weekday"] = customers["date"].dt.day_name()

    nb_days = customers["date"].nunique()

    weekday_avg = customers.groupby("weekday")["customers"].mean()
    weekday_pattern = weekday_avg / weekday_avg.mean()

    last_date = customers["date"].max()

    return bagels, weekday_pattern, nb_days, last_date


def compute_forecast_for_range(
    bagels: pd.DataFrame,
    weekday_pattern: pd.Series,
    nb_days: int,
    start_date,
    end_date,
    safety_factor: float = 1.2,
) -> pd.DataFrame:
    # moyenne vendue par jour pour chaque bagel
    bagels = bagels.copy()
    bagels["avg_per_day"] = bagels["quantity"] / nb_days

    # calendrier
    dates = pd.date_range(start=start_date, end=end_date)
    calendar = pd.DataFrame({"date": dates})
    calendar["weekday"] = calendar["date"].dt.day_name()

    calendar["key"] = 1
    bagels["key"] = 1
    df = calendar.merge(bagels, on="key").drop("key", axis=1)

    df["weekday_factor"] = df["weekday"].map(weekday_pattern)
    df["forecast_qty"] = df["avg_per_day"] * df["weekday_factor"]

    df["qty_with_safety"] = (df["forecast_qty"] * safety_factor).round()

    result = (
        df[["date", "weekday", "product_name", "qty_with_safety"]]
        .rename(columns={"qty_with_safety": "qty_to_prepare"})
        .sort_values(["date", "product_name"])
    )

    return result


# ----------------- UI STREAMLIT -----------------

st.set_page_config(page_title="Varsobagel – Bagels Forecast", layout="wide")

st.title("🥯 Varsobagel – Préparation quotidienne des bagels")

bagels, weekday_pattern, nb_days, last_date = load_data(FILE_PATH)

st.sidebar.header("Options")

# Date à prévoir
default_date = last_date + timedelta(days=1)
target_date = st.sidebar.date_input(
    "Jour à prévoir",
    value=default_date,
    min_value=default_date,
)

# Horizon optionnel (nombre de jours à afficher)
horizon = st.sidebar.slider("Nombre de jours à afficher", 1, 7, 1)

# Safety stock
safety_factor = st.sidebar.slider("Safety stock (+%)", 0.0, 0.5, 0.2, step=0.05)

start_date = pd.to_datetime(target_date)
end_date = start_date + timedelta(days=horizon - 1)

forecast_df = compute_forecast_for_range(
    bagels,
    weekday_pattern,
    nb_days,
    start_date=start_date,
    end_date=end_date,
    safety_factor=1 + safety_factor,
)

# Vue du jour sélectionné
today_df = forecast_df[forecast_df["date"] == start_date].copy()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(
        "Total bagels à préparer",
        int(today_df["qty_to_prepare"].sum()),
    )
with col2:
    st.metric(
        "Nombre de références",
        today_df.shape[0],
    )
with col3:
    st.metric(
        "Safety stock",
        f"{int(safety_factor*100)} %",
    )

st.subheader(f"Bagels à préparer pour le {start_date.date()}")

st.dataframe(
    today_df[["product_name", "qty_to_prepare"]]
    .sort_values("qty_to_prepare", ascending=False)
    .reset_index(drop=True),
    use_container_width=True,
)

st.subheader("Répartition des bagels (jour sélectionné)")

chart_data = (
    today_df[["product_name", "qty_to_prepare"]]
    .sort_values("qty_to_prepare", ascending=False)
    .set_index("product_name")
)

st.bar_chart(chart_data)

st.subheader("Vue multi-jours")

st.dataframe(
    forecast_df.pivot_table(
        index="product_name",
        columns="date",
        values="qty_to_prepare",
        aggfunc="sum",
    ).fillna(0),
    use_container_width=True,
)
