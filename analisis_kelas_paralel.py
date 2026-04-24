# ============================================================
# DASHBOARD ANALISIS KELAS PARALEL (FINAL PERFECT VERSION)
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
        st.write(df.columns)
        st.stop()

    # ================= CLEANING =================
    
    # ================= PARALEL =================
    paralel = df.groupby(["th_ajaran","kode_makul"])["grup"].nunique().reset_index()
    df = df.merge(paralel[paralel["grup"] > 1][["th_ajaran","kode_makul"]])
    
    df["nilai_angka"] = pd.to_numeric(df["nilai_angka"], errors="coerce")
    df = df.dropna(subset=["nilai_angka","kode_prodi","th_ajaran"])
    df = df[(df["nilai_angka"] >= 0) & (df["nilai_angka"] <= 100)]

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

    # ================= MAPPING PRODI =================
    mapping_prodi = {
        1: "Filsafat Keilahian",
        11: "Manajemen",
        12: "Akuntansi",
        13: "Magister Manajemen",
        31: "Biologi",
        41: "Kedokteran",
        50: "Magister Filsafat Keilahian",
        56: "Magister Teologi Publik",
        57: "Doktor Teologi",
        59: "Magister Kependetaan",
        61: "Arsitektur",
        62: "Desain Produk",
        63: "Magister Arsitektur",
        71: "Informatika",
        72: "Sistem Informasi",
        81: "Pendidikan Bahasa Inggris",
        82: "Humaniora",
        91: "Tidak Tahu"
    }

    df["nama_prodi"] = df["kode_prodi"].map(mapping_prodi)

    # ================= FILTER S1 =================
    df = df[~df["nama_prodi"].str.contains("Magister|Doktor", na=False)]

    # ================= FILTER UI =================
    prodi_options = sorted(df["kode_prodi"].unique())
    tahun_options = sorted(df["th_ajaran"].unique())

    prodi = st.sidebar.multiselect("Prodi", prodi_options, default=prodi_options)
    tahun = st.sidebar.multiselect("Tahun", tahun_options, default=tahun_options)

    df = df[(df["kode_prodi"].isin(prodi)) & (df["th_ajaran"].isin(tahun))]

    # ================= MIN 5 =================
    kelas_count = df.groupby(["th_ajaran","kode_makul","grup"]).size().reset_index(name="n")
    df = df.merge(kelas_count[kelas_count["n"] >= 5][["th_ajaran","kode_makul","grup"]])

    # ================= ANOVA =================
    results = []

    for (tahun,mk), group in df.groupby(["th_ajaran","kode_makul"]):

        kelas = group["grup"].unique()
        nilai = [group[group["grup"]==k]["nilai_angka"] for k in kelas]

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

    # ================= DASHBOARD =================
    if menu == "Dashboard":

        # ===== ROW 1 =====
        col1, col2, col3 = st.columns(3)

        with col1:
            st.caption("Distribusi Nilai Mahasiswa")
            fig = px.histogram(df, x="nilai_angka", nbins=20, height=220)
            fig.update_layout(yaxis_title="Jumlah", xaxis_title="Nilai Angka")
            st.plotly_chart(fig, use_container_width=True)
            
        with col2:
            st.caption("Signifikansi ANOVA")
            sig = hasil_df["signifikan"].value_counts().reset_index()
            sig.columns = ["Status","Jumlah"]
            fig = px.bar(sig, x="Status", y="Jumlah", text="Jumlah", height=220)
            st.plotly_chart(fig, use_container_width=True)

        with col3:
            st.caption("Signifikan per Prodi")
            prodi_chart = hasil_df.groupby("nama_prodi")["signifikan"].apply(
                lambda x: (x == "Ya").sum()
            ).reset_index()

            prodi_chart.columns = ["Prodi", "Jumlah"]
            prodi_chart = prodi_chart.sort_values(by="Jumlah", ascending=False)

            fig = px.bar(prodi_chart, x="Prodi", y="Jumlah", text="Jumlah", height=220)
            st.plotly_chart(fig, use_container_width=True)

        # ===== ROW 2 =====
        col4, col5 = st.columns([1,2])

        # DOSEN
        with col4:
            st.caption("Dosen Sama vs Berbeda")
            dosen_chart = hasil_df.groupby("dosen_sama")["signifikan"].apply(
                lambda x: (x == "Ya").sum()
            ).reset_index()

            dosen_chart["dosen_sama"] = dosen_chart["dosen_sama"].map({True:"Sama", False:"Berbeda"})
            dosen_chart.columns = ["Kategori","Jumlah"]

            fig = px.bar(dosen_chart, x="Kategori", y="Jumlah", text="Jumlah", height=220)
            st.plotly_chart(fig, use_container_width=True)

        # BOXPLOT LEBAR
        with col5:
            st.caption("Perbandingan Kelas")

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

        # ===== RINGKASAN DI BAWAH =====
        st.divider()
        st.subheader("Ringkasan")

        c1,c2,c3 = st.columns(3)

        sig_total = (hasil_df["signifikan"]=="Ya").sum()
        total = len(hasil_df)

        c1.metric("Signifikan", f"{sig_total}/{total}", f"{(sig_total/total*100):.2f}%")

        if not hasil_df.empty:
            ps = hasil_df.groupby("nama_prodi")["signifikan"].apply(lambda x:(x=="Ya").sum())
            c2.metric("Prodi Timpang", ps.idxmax())
            c3.metric("Prodi Stabil", ps.idxmin())

    else:
        st.dataframe(df)
        st.dataframe(hasil_df)


else:
    st.info("Upload file Excel terlebih dahulu")