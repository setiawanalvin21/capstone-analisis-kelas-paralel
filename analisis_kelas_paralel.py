# ============================================================
# DASHBOARD ANALISIS KELAS PARALEL 
# ============================================================

import streamlit as st
import pandas as pd
import plotly.express as px
from scipy import stats

st.set_page_config(page_title="Dashboard Analisis Kelas Paralel", layout="wide")
st.title("📊 Dashboard Analisis Nilai Kelas Paralel")

st.markdown("""
    <style>
        .block-container {
            padding-top: 3rem;
            padding-bottom: 1rem;
        }
    </style>
""", unsafe_allow_html=True)

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
            st.caption("Sebaran Nilai Mahasiswa di Semua Kelas Paralel")
            fig = px.histogram(df, x="nilai_angka", nbins=20, height=220)
            fig.update_layout(yaxis_title="Jumlah", xaxis_title="Nilai Angka",xaxis=dict(
            dtick=25   # jarak antar angka di sumbu X
        ))
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.caption("Perbandingan Kelas yang Nilainya Berbeda Signifikan vs Tidak Signifikan")
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
            st.caption("Jumlah Kelas dengan Perbedaan Nilai di Setiap Program Studi")
            prodi_chart = hasil_df.groupby("nama_prodi")["signifikan"].apply(
                lambda x: (x=="Ya").sum()
            ).reset_index()

            prodi_chart.columns = ["Prodi","Jumlah"]
            prodi_chart = prodi_chart.sort_values(by="Jumlah", ascending=False)

            fig = px.bar(prodi_chart, x="Prodi", y="Jumlah", text="Jumlah", height=220)
            st.plotly_chart(fig, use_container_width=True)

        col4, col5 = st.columns([1,2])

        with col4:
            st.caption("Perbandingan Perbedaan Nilai: Dosen Sama vs Dosen Berbeda")
            total_dosen = len(hasil_df) 

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
                y="total",
                text=dosen_chart["total"].astype(str) + " (" + dosen_chart["persen"].astype(str) + "%)",
                height=220
            )

            fig.update_layout(
                yaxis_title="Jumlah Kelas Paralel"
            )

            st.plotly_chart(fig, use_container_width=True)

        with col5:
            st.caption("Perbandingan Nilai Antar Kelas dalam Satu Mata Kuliah")
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

        c1, c2, c3= st.columns(3)

       # ================= SIGNIFIKAN =================
        sig_total = (hasil_df["signifikan"] == "Ya").sum()
        total = len(hasil_df)

        persen_sig = (sig_total / total * 100) if total > 0 else 0

        c1.metric(
            "Kelas dengan Perbedaan Nilai Signifikan",
            f"{sig_total}/{total}",
            f"{persen_sig:.2f}%"
        )

        # ================= PRODI =================
        ps = hasil_df.groupby("nama_prodi")["signifikan"].apply(lambda x: (x == "Ya").sum())

        if not ps.empty:
            prodi_timpang = ps.idxmax()
            prodi_stabil = ps.idxmin()

            c2.metric("Prodi Timpang", prodi_timpang)
            c3.metric("Prodi Stabil", prodi_stabil)
        else:
            prodi_timpang = "-"
            prodi_stabil = "-"

            c2.metric("Prodi Timpang", "-")
            c3.metric("Prodi Stabil", "-")

        # ================= INSIGHT OTOMATIS =================
        st.markdown("### 📊 Insight Otomatis")
        
        st.info(
            f"Dari {total} kelas paralel, terdapat {sig_total} kelas "
            f"({persen_sig:.1f}%) yang menunjukkan perbedaan nilai signifikan."
        )

        # Insight ketimpangan
        if persen_sig > 50:
            st.warning("Lebih dari setengah kelas menunjukkan ketimpangan nilai yang signifikan.")
        else:
            st.success("Sebagian besar kelas tidak menunjukkan ketimpangan nilai yang signifikan.")

        # Insight prodi
        if prodi_timpang != "-":
            st.write(
                f"Program studi dengan ketimpangan tertinggi adalah **{prodi_timpang}**, "
                f"sedangkan yang paling stabil adalah **{prodi_stabil}**."
            )
        else:
            st.write("Tidak ada program studi dengan ketimpangan signifikan.")
        
    else:
        st.subheader("📂 Data Nilai Mahasiswa (Setelah Cleaning)")
        st.dataframe(df)

        st.subheader("📊 Hasil Analisis ANOVA Kelas Paralel")
        st.dataframe(hasil_df)
        
        st.subheader("📈 Statistik Deskriptif Nilai")
        st.dataframe(df["nilai_angka"].describe())
        
        st.subheader("📊 Rata-rata Nilai per Prodi")

        avg_prodi = (
            df.groupby("nama_prodi")["nilai_angka"]
                .mean()
                .reset_index()
                .sort_values(by="nilai_angka", ascending=False)
                .reset_index(drop=True)
            )

        # jadikan ranking (mulai dari 1)
        avg_prodi.index += 1

        # opsional: rename kolom biar lebih jelas
        avg_prodi.columns = ["Prodi", "Rata-rata Nilai"]

        st.dataframe(avg_prodi)

else:
    st.info("Upload file Excel terlebih dahulu")