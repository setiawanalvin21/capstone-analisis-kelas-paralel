# ============================================================
# DASHBOARD ANALISIS KELAS PARALEL 
# ============================================================

import streamlit as st
import pandas as pd
import plotly.express as px
from scipy import stats

st.set_page_config(page_title="Dashboard Analisis Kelas Paralel", layout="wide")
st.markdown("## 📊 Dashboard Analisis Nilai Kelas Paralel")

st.markdown("""
    <style>
        .block-container {
            padding-top: 3rem;
            padding-bottom: 1rem;
        }
    </style>
""", unsafe_allow_html=True)

menu = st.sidebar.radio("Menu", ["Ringkasan", "Grafik", "Data"])
uploaded_file = st.sidebar.file_uploader("Upload File Excel", type=["xlsx"])

if uploaded_file:

    df = pd.read_excel(uploaded_file)

    # ================= NORMALISASI =================
    df.columns = df.columns.str.strip().str.lower().str.replace(r"\s+", "_", regex=True)

    # Mapping huruf ke angka
    mapping_huruf = {
        "A": 4.0, "A-": 3.7, "B+": 3.3, "B": 3.0, "B-": 2.7,
        "C+": 2.3, "C": 2.0, "C-": 1.7, "D": 1.0, "E": 0.0
    }

    if "nilai_huruf" in df.columns:
        df["nilai_angka_norm"] = df["nilai_huruf"].map(mapping_huruf)
        # Jika nilai_angka kosong, gunakan nilai_angka_norm
        df["nilai_angka"] = df["nilai_angka"].fillna(df["nilai_angka_norm"])
    
    required = ["th_ajaran","kode_makul","grup","nilai_angka","dosen","kode_prodi"]
    if any(col not in df.columns for col in required):
        st.error("Kolom tidak lengkap")
        st.stop()

    # ================= CLEANING =================
    df["nilai_angka"] = pd.to_numeric(df["nilai_angka"], errors="coerce")
    df = df.dropna(subset=["nilai_angka","kode_prodi","th_ajaran"])
    df = df[(df["nilai_angka"] >= 0) & (df["nilai_angka"] <= 100)]

    # Simpan info pembersihan
    init_mk_count = df.groupby(["th_ajaran", "kode_makul"]).size().count()

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
    if menu == "Ringkasan":
        st.subheader("📋 Ringkasan Analisis")
        
        # Hitung statistik global
        total_mk_all = df.groupby(["th_ajaran", "kode_makul"]).size().count() # Ini kurang tepat, harusnya unique mk
        # Lebih tepat:
        all_mk = df.groupby(["th_ajaran", "kode_makul"]).size().reset_index()
        total_mk_count = len(all_mk)
        
        # MK Paralel (sudah di-filter di df awal, tapi hasil_df lebih akurat untuk ANOVA)
        total_paralel = len(hasil_df)
        sig_count = (hasil_df["signifikan"] == "Ya").sum()
        dosen_sama_count = hasil_df["dosen_sama"].sum()
        dosen_beda_count = total_paralel - dosen_sama_count

        # Styling boxes
        st.markdown("""
            <style>
            .metric-box {
                background-color: #f0f2f6;
                border-radius: 10px;
                padding: 20px;
                text-align: center;
                border: 1px solid #ddd;
                margin-bottom: 10px;
            }
            .metric-value {
                font-size: 24px;
                font-weight: bold;
                color: #007bff;
            }
            .metric-label {
                font-size: 14px;
                color: #666;
            }
            .box-green { background-color: #d4edda; border-color: #c3e6cb; }
            .box-red { background-color: #f8d7da; border-color: #f5c6cb; }
            .box-blue { background-color: #cfe2ff; border-color: #b6d4fe; }
            </style>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f'<div class="metric-box box-blue"><div class="metric-label">Total Mata Kuliah</div><div class="metric-value">{total_mk_count}</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-box box-blue"><div class="metric-label">Total Kelas Paralel</div><div class="metric-value">{total_paralel}</div></div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f'<div class="metric-box"><div class="metric-label">Dosen Sama</div><div class="metric-value">{dosen_sama_count}</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-box"><div class="metric-label">Dosen Berbeda</div><div class="metric-value">{dosen_beda_count}</div></div>', unsafe_allow_html=True)
        with col3:
            st.markdown(f'<div class="metric-box box-red"><div class="metric-label">Beda Signifikan</div><div class="metric-value">{sig_count}</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-box box-green"><div class="metric-label">Tidak Signifikan</div><div class="metric-value">{total_paralel - sig_count}</div></div>', unsafe_allow_html=True)

        st.divider()
        
        # Insight Ringkasan
        st.markdown("### 📊 Insight Utama")
        persen_sig = (sig_count / total_paralel * 100) if total_paralel > 0 else 0
        st.info(f"Dari {total_paralel} mata kuliah paralel, terdapat {sig_count} ({persen_sig:.1f}%) yang menunjukkan perbedaan nilai signifikan.")
        
        if not hasil_df.empty:
            ps = hasil_df.groupby("nama_prodi")["signifikan"].apply(lambda x: (x == "Ya").sum())
            if not ps.empty:
                prodi_max = ps.idxmax()
                prodi_min = ps.idxmin()
                st.write(f"Prodi dengan jumlah nilai berbeda terbanyak adalah **{prodi_max}**, sedangkan yang paling stabil adalah **{prodi_min}**.")

    elif menu == "Grafik":
        st.subheader("📊 Visualisasi Analisis")
        
        # Row 1: Three Charts
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.caption("Perbandingan Prodi: Total vs Signifikan")
            # Stacked bar chart for Prodi
            prodi_stats = hasil_df.groupby("nama_prodi")["signifikan"].value_counts().unstack(fill_value=0).reset_index()
            if "Ya" not in prodi_stats.columns: prodi_stats["Ya"] = 0
            if "Tidak" not in prodi_stats.columns: prodi_stats["Tidak"] = 0
            
            prodi_stats["Total"] = prodi_stats["Ya"] + prodi_stats["Tidak"]
            prodi_stats = prodi_stats.sort_values(by="Total", ascending=False)
            
            # Plotly stacked bar
            fig_prodi = px.bar(prodi_stats, x="nama_prodi", y=["Ya", "Tidak"], 
                             labels={"value": "Jumlah MK", "nama_prodi": "Prodi", "variable": "Signifikan"},
                             title="Signifikansi per Prodi", height=300,
                             color_discrete_map={"Ya": "#ef553b", "Tidak": "#636efa"})
            st.plotly_chart(fig_prodi, use_container_width=True)

        with col2:
            st.caption("Perbandingan Kelas: Signifikan vs Tidak Signifikan")
            sig = hasil_df["signifikan"].value_counts().reset_index()
            sig.columns = ["Status","Jumlah"]
            # Map to requested names
            sig["Status"] = sig["Status"].map({"Ya": "Signifikan", "Tidak": "Tidak Signifikan"})
            
            total_s = sig["Jumlah"].sum()
            sig["Persentase"] = (sig["Jumlah"] / total_s * 100).round(1)
            
            fig_sig = px.bar(sig, x="Status", y="Jumlah", 
                           text=sig["Jumlah"].astype(str) + " (" + sig["Persentase"].astype(str) + "%)", height=300)
            fig_sig.update_traces(textposition="outside")
            st.plotly_chart(fig_sig, use_container_width=True)

        with col3:
            st.caption("Perbedaan Nilai: Dosen Sama vs Berbeda")
            dosen_stats = hasil_df.groupby("dosen_sama")["signifikan"].apply(lambda x: (x == "Ya").sum()).reset_index()
            dosen_stats.columns = ["dosen_sama", "sig_count"]
            
            # Get total per dosen category
            dosen_totals = hasil_df["dosen_sama"].value_counts().reset_index()
            dosen_totals.columns = ["dosen_sama", "total_count"]
            
            dosen_stats = dosen_stats.merge(dosen_totals, on="dosen_sama")
            dosen_stats["Kategori"] = dosen_stats["dosen_sama"].map({True: "Sama", False: "Berbeda"})
            dosen_stats["Persen"] = (dosen_stats["sig_count"] / dosen_stats["total_count"] * 100).round(1)
            
            fig_dosen = px.bar(dosen_stats, x="Kategori", y="sig_count", 
                             text=dosen_stats["sig_count"].astype(str) + " (" + dosen_stats["Persen"].astype(str) + "%)", height=300)
            fig_dosen.update_traces(textposition="outside")
            st.plotly_chart(fig_dosen, use_container_width=True)

        st.divider()
        
        # Row 2: Distribution and BoxPlot
        col4, col5 = st.columns([1,2])
        
        with col4:
            st.caption("Sebaran Nilai Mahasiswa (Semua Kelas)")
            fig_hist = px.histogram(df, x="nilai_angka", nbins=20, height=300)
            fig_hist.update_layout(yaxis_title="Jumlah", xaxis_title="Nilai Angka", xaxis=dict(dtick=25))
            st.plotly_chart(fig_hist, use_container_width=True)
            
        with col5:
            st.caption("Perbandingan Nilai Antar Kelas")
            mk_list = sorted(df["kode_makul"].unique())
            mk = st.selectbox("Pilih Mata Kuliah", mk_list)
            
            plot_data = df[df["kode_makul"] == mk].copy()
            plot_data = plot_data.explode("dosen")
            
            fig_box = px.box(plot_data, x="grup", y="nilai_angka", color="dosen", height=300)
            
            # Add mean markers
            mean_df = plot_data.groupby("grup")["nilai_angka"].mean().reset_index()
            fig_box.add_scatter(x=mean_df["grup"], y=mean_df["nilai_angka"], mode="markers", 
                              marker=dict(size=8, symbol="diamond"), name="Mean")
            
            # Check if this MK is significant
            mk_res = hasil_df[hasil_df["kode_makul"] == mk]
            if not mk_res.empty:
                sig_status = mk_res["signifikan"].iloc[0]
                st.markdown(f"**Status Signifikansi:** { '🔴 Beda Signifikan' if sig_status == 'Ya' else '🟢 Tidak Beda Signifikan' }")
            
            st.plotly_chart(fig_box, use_container_width=True)

    elif menu == "Data":
        st.subheader("📂 Data & Hasil Analisis")
        
        with st.expander("🔍 Detail Pembersihan Data"):
            st.write(f"Total Mata Kuliah Awal: {init_mk_count}")
            st.write(f"Total Mata Kuliah Paralel (Setelah Filter Min 5 Mahasiswa): {len(hasil_df)}")
            st.write(f"MK yang dihapus karena tidak memenuhi syarat paralel/jumlah mahasiswa: {init_mk_count - len(hasil_df)}")
        
        st.markdown("### Data Nilai Mahasiswa (Setelah Cleaning)")
        st.dataframe(df)
        
        st.markdown("### Hasil Analisis ANOVA")
        # Add styling to ANOVA table
        def highlight_sig(s):
            return ['background-color: #ffcccc' if v == 'Ya' else '' for v in s]
        
        styled_hasil = hasil_df.style.apply(highlight_sig, subset=['signifikan'])
        st.dataframe(styled_hasil)
        
        st.markdown("### Statistik Deskriptif Nilai")
        st.dataframe(df["nilai_angka"].describe())
        
        st.markdown("### Rata-rata Nilai per Prodi")
        avg_prodi = df.groupby("nama_prodi")["nilai_angka"].mean().reset_index().sort_values(by="nilai_angka", ascending=False)
        avg_prodi.columns = ["Prodi", "Rata-rata Nilai"]
        st.dataframe(avg_prodi)

else:
    st.info("Upload file Excel terlebih dahulu")
