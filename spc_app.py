import matplotlib.pyplot as plt
import streamlit as st

def plot_selected_characteristics(df_long, stats):

    selected = [
        "AntriebHoheAR",
        "AntriebHoheBL",
        "AntriebHoheCU",
        "PM10Hohe",
        "PM30Gewicht",
        "PM5innen",
        "PM7aussen",
        "PM9Antrieb"
    ]

    for ch in selected:

        data = df_long[df_long["Characteristic"] == ch]
        spec = stats[stats["Characteristic"] == ch]

        if data.empty or spec.empty:
            st.warning(f"Missing data for {ch}")
            continue

        spec = spec.iloc[0]

        fig, ax = plt.subplots(figsize=(10, 4))

        # 🔹 Measurements
        ax.plot(
            data["Value"].values,
            marker="o",
            linewidth=1,
            label="Measurements"
        )

        # 🔹 Mean
        ax.axhline(
            spec["Xbar"],
            color="green",
            label=f"Mean (Xbar = {spec['Xbar']:.3f})"
        )

        # 🔹 USL
        ax.axhline(
            spec["USL"],
            color="red",
            label=f"USL = {spec['USL']:.3f}"
        )

        # 🔹 LSL
        ax.axhline(
            spec["LSL"],
            color="red",
            label=f"LSL = {spec['LSL']:.3f}"
        )

        ax.set_title(f"{ch} | Cp={spec['Cp']:.2f} | Cpk={spec['Cpk']:.2f}")
        ax.legend()
        ax.grid(True)

        st.pyplot(fig)
