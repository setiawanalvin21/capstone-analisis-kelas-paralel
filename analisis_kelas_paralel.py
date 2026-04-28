# ============================================================
# DASHBOARD ANALISIS KELAS PARALEL 
# ============================================================

import streamlit as st
import pandas as pd
import plotly.express as px
from scipy import stats

st.set_page_config(page_title="Dashboard Analisis Kelas Paralel", layout="wide")
st.title("📊 Dashboard Analisis Nilai Kelas Paralel")

menu = st.sidebar.radio("Menu", ["Dashboard", "Data"])
uploaded_file = st.sidebar.file_uploader("Upload File Excel", type=["xlsx"])

if uploaded_file:

    df = pd.read_excel(uploaded_file)

    # ================= NORMALISASI =================
    df.columns = df.columns.str.strip().str.lower().str.replace(r"\s+", "_", regex=True)

    required = ["th_ajaran","kode_makul","grup","nilai_angka","dosen","kode_prodi"]
    if any(col not in df.columns for col in required):
        st.error("Kolom tidak lengkap")
        st.stop()

    # ================= CLEANING =================
    df["nilai_angka"] = pd.to_numeric(df["nilai_angka"], errors="coerce")
    df = df.dropna(subset=["nilai_angka","kode_prodi","th_ajaran"])
    df = df[(df["nilai_angka"] >= 0) & (df["nilai_angka"] <= 100)]

    # ================= FORMAT PRODI (STRING AMAN) =================
    df["kode_prodi"] = (
        df["kode_prodi"]
        .astype(str)
        .str.replace(".0","", regex=False)
        .str.strip()
        .str.zfill(2)
    )

    # ================= MAPPING S1 =================
    mapping_prodi = {
        "01": "Filsafat Keilahian",
        "11": "Manajemen",
        "12": "Akuntansi",
        "31": "Biologi",
        "41": "Kedokteran",
        "61": "Arsitektur",
        "62": "Desain Produk",
        "71": "Informatika",
        "72": "Sistem Informasi",
        "81": "Pendidikan Bahasa Inggris",
        "82": "Humaniora",
    }

    df["nama_prodi"] = df["kode_prodi"].map(mapping_prodi)
    df = df.dropna(subset=["nama_prodi"])

    # ================= PARALLEL AWAL =================
    paralel = df.groupby(["th_ajaran","kode_makul"])["grup"].nunique().reset_index()
    df = df.merge(paralel[paralel["grup"] > 1][["th_ajaran","kode_makul"]])

    # ================= CLEAN DOSEN =================
    def clean_dosen(value):
        if pd.isna(value):
            return None
        return [p.strip() for p in str(value).split("<br>") if p.strip()]

    df["dosen"] = df["dosen"].apply(clean_dosen)

    def count_dosen(series):
        all_dosen = []
        for val in series.dropna():
            all_dosen.extend(val)
        return len(set(all_dosen))

    # ================= FILTER UI =================
    prodi = st.sidebar.multiselect("Prodi", sorted(df["kode_prodi"].unique()), default=sorted(df["kode_prodi"].unique()))
    tahun = st.sidebar.multiselect("Tahun", sorted(df["th_ajaran"].unique()), default=sorted(df["th_ajaran"].unique()))

    df = df[(df["kode_prodi"].isin(prodi)) & (df["th_ajaran"].isin(tahun))]

    # ================= MIN 5 =================
    kelas_count = df.groupby(["th_ajaran","kode_makul","grup"]).size().reset_index(name="n")
    df = df.merge(kelas_count[kelas_count["n"] >= 5][["th_ajaran","kode_makul","grup"]])

    # ================= RE-CHECK PARALLEL =================
    paralel2 = df.groupby(["th_ajaran","kode_makul"])["grup"].nunique().reset_index()
    df = df.merge(paralel2[paralel2["grup"] > 1][["th_ajaran","kode_makul"]])

    # ================= ANOVA =================
    results = []

    for (tahun,mk), group in df.groupby(["th_ajaran","kode_makul"]):

        kelas = group["grup"].unique()
        if len(kelas) < 2:
            continue

        nilai = [group[group["grup"]==k]["nilai_angka"].dropna() for k in kelas]

        if len(nilai) < 2:
            continue

        try:
            _, p = stats.f_oneway(*nilai)
        except:
            continue

        jml_dosen = count_dosen(group["dosen"])

        results.append({
            "kode_makul": mk,
            "tahun": tahun,
            "kode_prodi": group["kode_prodi"].iloc[0],
            "nama_prodi": group["nama_prodi"].iloc[0],
            "jumlah_kelas": len(kelas),
            "jumlah_dosen": jml_dosen,
            "dosen_sama": jml_dosen == 1,
            "p_value": round(p,5),
            "signifikan": "Ya" if p < 0.05 else "Tidak"
        })

    hasil_df = pd.DataFrame(results)

    if hasil_df.empty:
        st.error("Data kosong setelah ANOVA")
        st.stop()

    # ================= DASHBOARD =================
    if menu == "Dashboard":

        col1, col2, col3 = st.columns(3)

        with col1:
            st.caption("Distribusi Nilai Mahasiswa")
            st.caption("Sebaran nilai mahasiswa pada seluruh kelas paralel.")            
            fig = px.histogram(df, x="nilai_angka", nbins=20, height=220)
            fig.update_layout(yaxis_title="Jumlah", xaxis_title="Nilai Angka",xaxis=dict(
            dtick=25   # jarak antar angka di sumbu X
        ))
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.caption("Signifikansi ANOVA")
            st.caption("Perbandingan kelas yang signifikan dan tidak signifikan.")            
            sig = hasil_df["signifikan"].value_counts().reset_index()
            sig.columns = ["Status","Jumlah"]
            total = sig["Jumlah"].sum()
            # Hitung persentase
            sig["Persentase"] = (sig["Jumlah"] / total * 100).round(1)
            fig = px.bar(sig, x="Status", y="Jumlah",
            text=sig["Jumlah"].astype(str) + " (" + sig["Persentase"].astype(str) + "%)", height=220)
            fig.update_traces(textposition="outside")
            st.plotly_chart(fig, use_container_width=True)

        with col3:
            st.caption("Signifikan per Prodi")
            st.caption("Jumlah ketimpangan nilai pada tiap program studi.")            
            prodi_chart = hasil_df.groupby("nama_prodi")["signifikan"].apply(
                lambda x: (x=="Ya").sum()
            ).reset_index()

            prodi_chart.columns = ["Prodi","Jumlah"]
            prodi_chart = prodi_chart.sort_values(by="Jumlah", ascending=False)

            fig = px.bar(prodi_chart, x="Prodi", y="Jumlah", text="Jumlah", height=220)
            st.plotly_chart(fig, use_container_width=True)

        col4, col5 = st.columns([1,2])

        with col4:
            st.caption("Dosen Sama vs Berbeda")
            st.caption("Proporsi ketimpangan pada seluruh kelas paralel.")

            total_dosen = len(hasil_df)  # ← FIX: pakai total yang sama dengan metric

            dosen_chart = hasil_df["dosen_sama"].value_counts().reset_index()
            dosen_chart.columns = ["dosen_sama", "total"]

            dosen_chart["persen"] = (dosen_chart["total"] / total_dosen * 100).round(1)

            dosen_chart["Kategori"] = dosen_chart["dosen_sama"].map({
                True: "Sama",
                False: "Berbeda"
            })

            fig = px.bar(
                dosen_chart,
                x="Kategori",
                y="persen",
                text=dosen_chart["persen"].astype(str) + "%",
                height=220
            )

            fig.update_layout(
                yaxis_title="Persentase Ketimpangan (%)"
            )

            st.plotly_chart(fig, use_container_width=True)

        with col5:
            st.caption("Perbandingan Kelas")
            st.caption("Perbandingan distribusi nilai antar kelas dalam satu mata kuliah.")            
            mk = st.selectbox("Pilih MK", sorted(df["kode_makul"].unique()))

            plot_data = df[df["kode_makul"] == mk].copy()
            plot_data = plot_data.explode("dosen")

            fig = px.box(plot_data, x="grup", y="nilai_angka", color="dosen", height=250)

            mean_df = plot_data.groupby("grup")["nilai_angka"].mean().reset_index()
            fig.add_scatter(
                x=mean_df["grup"],
                y=mean_df["nilai_angka"],
                mode="markers",
                marker=dict(size=8, symbol="diamond"),
                name="Mean"
            )

            st.plotly_chart(fig, use_container_width=True)

        st.divider()
        st.subheader("Ringkasan")

        c1, c2, c3, c4, c5 = st.columns(5)

        # ================= SIGNIFIKAN =================
        sig_total = (hasil_df["signifikan"]=="Ya").sum()
        total = len(hasil_df)

        persen_sig = (sig_total / total * 100) if total > 0 else 0

        c1.metric(
            "Signifikan",
            f"{sig_total}/{total}",
            f"{persen_sig:.2f}%"
        )

        # ================= PRODI =================
        ps = hasil_df.groupby("nama_prodi")["signifikan"].apply(lambda x:(x=="Ya").sum())

        c2.metric("Prodi Timpang", ps.idxmax())
        c3.metric("Prodi Stabil", ps.idxmin())

        # ================= DOSEN SAMA =================
        dosen_sama = (hasil_df["dosen_sama"] == True).sum()
        persen_sama = (dosen_sama / total * 100) if total > 0 else 0

        c4.metric(
            "Dosen Sama",
            f"{dosen_sama}/{total}",
            f"{persen_sama:.2f}%"
        )

        # ================= DOSEN BERBEDA =================
        dosen_berbeda = (hasil_df["dosen_sama"] == False).sum()
        persen_berbeda = (dosen_berbeda / total * 100) if total > 0 else 0

        c5.metric(
            "Dosen Berbeda",
            f"{dosen_berbeda}/{total}",
            f"{persen_berbeda:.2f}%"
        )  

    else:
        st.subheader("📂 Data Nilai Mahasiswa (Setelah Cleaning)")
        st.dataframe(df)

        st.subheader("📊 Hasil Analisis ANOVA Kelas Paralel")
        st.dataframe(hasil_df)

else:
    st.info("Upload file Excel terlebih dahulu")