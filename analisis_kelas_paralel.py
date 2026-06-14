# ============================================================
# DASHBOARD ANALISIS KELAS PARALEL 
# ============================================================

import streamlit as st
import pandas as pd
import plotly.express as px
from scipy import stats

st.set_page_config(page_title="Dashboard Analisis Kelas Paralel", layout="wide")


st.markdown("""
    <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 1rem;
        }
        .viz-header {
            font-size: 28px !important;
            font-weight: bold !important;
            color: var(--text-color) !important;
            text-align: left;
            margin-bottom: 5px;
        }
        .metric-box {
            background-color: #f8f9fa;
            border-radius: 8px;
            padding: 10px;
            text-align: center;
            border: 1px solid #ddd;
            margin: 5px;
        }
        .metric-value {
            font-size: 18px !important;
            font-weight: bold !important;
            color: #007bff;
        }
        .metric-label {
            font-size: 12px !important;
            color: #666;
        }
        .box-green { background-color: #d4edda; border-color: #c3e6cb; }
        .box-red { background-color: #f8d7da; border-color: #f5c6cb; }
        .box-blue { background-color: #cfe2ff; border-color: #b6d4fe; }
    </style>
""", unsafe_allow_html=True)


menu = st.sidebar.radio("Menu", ["Grafik", "Data"])
uploaded_file = st.sidebar.file_uploader("Upload File Excel", type=["xlsx"])

if uploaded_file:

    df = pd.read_excel(uploaded_file)

    # ================= NORMALISASI =================
    df.columns = df.columns.str.strip().str.lower().str.replace(r"\s+", "_", regex=True)
    
    # 1. Total Mata Kuliah Awal (Raw)
    raw_mk_count = df.groupby(["th_ajaran", "kode_makul"]).size().count()

    # Mapping huruf ke angka
    mapping_huruf = {
        "A": 4.0, "A-": 3.7, "B+": 3.3, "B": 3.0, "B-": 2.7,
        "C+": 2.3, "C": 2.0, "C-": 1.7, "D": 1.0, "E": 0.0
    }
    
    if "nilai_huruf" in df.columns:
        df["nilai_angka_norm"] = df["nilai_huruf"].map(mapping_huruf)
        df["nilai_angka"] = df["nilai_angka"].fillna(df["nilai_angka_norm"])
    
    required = ["th_ajaran","kode_makul","nama_makul","grup","nilai_angka","dosen","kode_prodi"]
    if any(col not in df.columns for col in required):
        st.error(f"Kolom tidak lengkap. Kolom yang dibutuhkan: {', '.join(required)}")
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
    
    # 2. Hasil Filter Prodi S1
    s1_mk_count = df.groupby(["th_ajaran", "kode_makul"]).ngroups

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
    
    # 3. Filter Minimal 5 Mahasiswa
    min5_mk_count = df.groupby(["th_ajaran", "kode_makul"]).ngroups

    # ================= PARALLEL CHECK =================
    paralel = df.groupby(["th_ajaran","kode_makul"])["grup"].nunique().reset_index()
    df = df.merge(paralel[paralel["grup"] > 1][["th_ajaran","kode_makul"]])
    
    # 4. Hasil Kelas Paralel (Final)
    final_paralel_count = df.groupby(["th_ajaran", "kode_makul"]).ngroups

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
    if menu == "Grafik":
        # Format Tahun agar rapi dan tahan terhadap tipe data numeric/float
        if not tahun:
            tahun_str = "Semua Tahun"
        else:
            # Pastikan semua elemen adalah string, hapus .0, dan filter nilai kosong/aneh
            tahun_clean = sorted([str(t).replace(".0", "").strip() for t in tahun if str(t).strip()])
            
            if not tahun_clean:
                tahun_str = "Semua Tahun"
            elif len(tahun_clean) == 1:
                tahun_str = tahun_clean[0]
            else:
                tahun_str = f"{tahun_clean[0]}–{tahun_clean[-1]}"
        
       # st.markdown(f'<div class="viz-header"><b>Visualisasi Analisis Data Akademik Tahun Ajaran {tahun_str}</b></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="viz-header"><b>Visualisasi Analisis Data Akademik Tahun Ajaran 2024/2025–2025/2026</b></div>', unsafe_allow_html=True)

        # ================= RINGKASAN CARDS =================
        r_col1, r_col2, r_col3, r_col4 = st.columns(4)
        with r_col1:
            st.markdown(f'<div class="metric-box box-blue"><div class="metric-label">Total MK Awal</div><div class="metric-value">{raw_mk_count}</div></div>', unsafe_allow_html=True)
        with r_col2:
            st.markdown(f'<div class="metric-box box-blue"><div class="metric-label">Filter Prodi S1</div><div class="metric-value">{s1_mk_count}</div></div>', unsafe_allow_html=True)
        with r_col3:
            st.markdown(f'<div class="metric-box box-blue"><div class="metric-label">Filter Min 5 Mhs</div><div class="metric-value">{min5_mk_count}</div></div>', unsafe_allow_html=True)
        with r_col4:
            st.markdown(f'<div class="metric-box box-blue"><div class="metric-label">Hasil MK Paralel</div><div class="metric-value">{final_paralel_count}</div></div>', unsafe_allow_html=True)
        
        st.divider()
        
        # Row 1: Four Charts
        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
        
        with col1:
            # Stacked bar chart for Prodi
            prodi_stats = hasil_df.groupby("nama_prodi")["signifikan"].value_counts().unstack(fill_value=0).reset_index()
            prodi_stats = prodi_stats.rename(columns={"Ya": "Signifikan", "Tidak": "Tidak"})
            if "Signifikan" not in prodi_stats.columns: prodi_stats["Signifikan"] = 0
            if "Tidak" not in prodi_stats.columns: prodi_stats["Tidak"] = 0
            
            prodi_stats["Total"] = prodi_stats["Signifikan"] + prodi_stats["Tidak"]
            prodi_stats = prodi_stats.sort_values(by="Total", ascending=False)
            
            # Plotly stacked bar - Made larger
            st.caption("Signifikan per prodi")
            fig_prodi = px.bar(prodi_stats, x="nama_prodi", y=["Signifikan", "Tidak"], 
                               labels={"value": "Jumlah MK", "nama_prodi": "Prodi", "variable": "Status"},
                               height=350,
                               color_discrete_map={"Signifikan": "#ef553b", "Tidak": "#636efa"})
            
            # Tambahkan total di atas grafik
            fig_prodi.add_trace(
                px.scatter(prodi_stats, x="nama_prodi", y="Total", text="Total").data[0]
            )
            fig_prodi.update_traces(
                selector=dict(type='scatter'),
                mode='text',
                textposition='top center',
                marker=dict(size=0),
                showlegend=False
            )
            
            # Berikan ruang ekstra di atas sumbu Y agar angka total tidak terpotong
            max_total = prodi_stats["Total"].max() if not prodi_stats.empty else 10
            fig_prodi.update_layout(
                yaxis=dict(range=[0, max_total * 1.15]),
                margin=dict(l=10, r=10, t=30, b=10)
            )
            
            st.plotly_chart(fig_prodi, use_container_width=True)
    
        with col2:
            st.caption("Perbandingan Kelas: Signifikan vs Tidak Signifikan")
            sig = hasil_df["signifikan"].value_counts().reset_index()
            sig.columns = ["Status","Jumlah"]
            sig["Status"] = sig["Status"].map({"Ya": "Signifikan", "Tidak": "Tidak Signifikan"})
            
            total_s = sig["Jumlah"].sum()
            sig["Persentase"] = (sig["Jumlah"] / total_s * 100).round(1)
            
            # Made smaller height
            fig_sig = px.bar(sig, x="Status", y="Jumlah", 
                             text=sig["Jumlah"].astype(str) + " (" + sig["Persentase"].astype(str) + "%)", height=350)
            fig_sig.update_traces(textposition="outside")
            fig_sig.update_layout(margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig_sig, use_container_width=True)
    
        with col3:
            st.caption("Signifikansi: Dosen Sama vs Beda")
            dosen_stats = hasil_df.groupby("dosen_sama")["signifikan"].apply(lambda x: (x == "Ya").sum()).reset_index()
            dosen_stats.columns = ["dosen_sama", "jumlah"]
            
            total_sig_count = (hasil_df["signifikan"] == "Ya").sum()
            
            dosen_stats["Kategori"] = dosen_stats["dosen_sama"].map({True: "Sama", False: "Berbeda"})
            dosen_stats["Persen"] = (dosen_stats["jumlah"] / total_sig_count * 100).round(1) if total_sig_count > 0 else 0
            
            # Made smaller height
            fig_dosen = px.bar(dosen_stats, x="Kategori", y="jumlah", 
                                text=dosen_stats["jumlah"].astype(str) + " (" + dosen_stats["Persen"].astype(str) + "%)", height=350)
            fig_dosen.update_traces(textposition="outside")
            fig_dosen.update_layout(margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig_dosen, use_container_width=True)

        with col4:
            st.caption("Sebaran Nilai Mahasiswa (Semua Kelas Paralel)")
            fig_hist = px.histogram(df, x="nilai_angka", nbins=20, height=350)
            fig_hist.update_layout(
                yaxis_title="Jumlah", 
                xaxis_title="Nilai Angka", 
                xaxis=dict(dtick=25),
                margin=dict(l=10, r=10, t=30, b=10)
            )
            st.plotly_chart(fig_hist, use_container_width=True)
        
        # Row 2: BoxPlot
        st.caption("Perbandingan Nilai Antar Kelas")
        
        # Filter Prodi khusus untuk section ini - tambahkan opsi "Semua Prodi"
        prodi_options = ["Semua Prodi"] + sorted(hasil_df["nama_prodi"].unique().tolist())
        
        col_p, col_m = st.columns(2)
        with col_p:
            selected_prodi = st.selectbox("Pilih Prodi", prodi_options, key="prodi_box")
        
        # 1. Tentukan daftar MK yang akan ditampilkan di dropdown
        if selected_prodi == "Semua Prodi":
            # Ambil semua MK yang paralel (tanpa peduli prodi)
            parallel_mk_codes = hasil_df["kode_makul"].unique()
            df_for_map = df[df["kode_makul"].isin(parallel_mk_codes)]
            # Buat map unik berdasarkan kode_makul (agar satu MK hanya muncul sekali)
            mk_map = df_for_map[['kode_makul', 'nama_makul']].drop_duplicates(subset=['kode_makul'])
            mk_map['nama_prodi'] = "Semua Prodi"
        else:
            # Filter hanya untuk prodi yang dipilih
            df_for_map = df[df["nama_prodi"] == selected_prodi]
            mk_map = df_for_map[['kode_makul', 'nama_makul', 'nama_prodi']].drop_duplicates()
        
        mk_names = mk_map['nama_makul'].tolist()

        with col_m:
            if not mk_names:
                st.warning("Tidak ada mata kuliah paralel untuk pilihan ini.")
            else:
                selected_mk_name = st.selectbox("Pilih Mata Kuliah", mk_names, key="mk_box")
        
        # Ambil informasi MK yang dipilih - PINDAH KE LUAR COLUMNS agar grafik full width
        if 'selected_mk_name' in locals() and not mk_names == []:
            mk_info = mk_map[mk_map['nama_makul'] == selected_mk_name].iloc[0]
            mk = mk_info['kode_makul']
            actual_prodi = mk_info['nama_prodi']
            
            # Filter data khusus untuk MK ini
            if selected_prodi == "Semua Prodi":
                plot_data_all = df[df["kode_makul"] == mk].copy()
            else:
                plot_data_all = df[(df["kode_makul"] == mk) & (df["nama_prodi"] == actual_prodi)].copy()
            
            if plot_data_all.empty:
                st.warning("Tidak ada data untuk mata kuliah ini pada pilihan filter saat ini.")
            else:
                # Ambil tahun terbaru yang tersedia dalam data yang sudah terfilter
                last_year = plot_data_all["th_ajaran"].max()
                plot_data = plot_data_all[plot_data_all["th_ajaran"] == last_year].copy()
                
                # Sederhanakan label dosen
                plot_data["dosen_label"] = plot_data["dosen"].apply(lambda x: ", ".join(x) if isinstance(x, list) else str(x))
                
                fig_box = px.box(plot_data, x="grup", y="nilai_angka", color="dosen_label", height=400)
                
                # Add mean markers
                mean_df = plot_data.groupby("grup")["nilai_angka"].mean().reset_index()
                fig_box.add_scatter(x=mean_df["grup"], y=mean_df["nilai_angka"], mode="markers", 
                                    marker=dict(size=8, symbol="diamond", color="red"), name="Mean")
                
                # Update layout agar lebih bersih dan padat
                fig_box.update_layout(
                    autosize=True,
                    showlegend=True,
                    legend=dict(
                        orientation="v",
                        yanchor="top",
                        y=1,
                        xanchor="left",
                        x=1.02
                    ),
                    legend_title_text="Dosen",
                    xaxis_title="Kelas/Grup",
                    yaxis_title="Nilai",
                    margin=dict(l=10, r=10, t=0, b=10)
                )
                
                # Check if this MK is significant
                mk_res = hasil_df[hasil_df["kode_makul"] == mk]
                if not mk_res.empty:
                    sig_status = mk_res["signifikan"].iloc[0]
                    col_sig, col_year = st.columns([1, 1])
                    col_sig.markdown(f"**Status Signifikansi:** { '🔴 Beda Signifikan' if sig_status == 'Ya' else '🟢 Tidak Beda Signifikan' }")
                    col_year.markdown(f"**Tahun Ajaran:** {last_year}")
                
                st.plotly_chart(fig_box, use_container_width=True)




                
    elif menu == "Data":

        st.subheader("📂 Data & Hasil Analisis")
        
        with st.expander("🔍 Detail Pembersihan Data"):
            st.write(f"Total Mata Kuliah Awal: {raw_mk_count}")
            st.write(f"Total Mata Kuliah Paralel (Setelah Filter Min 5 Mahasiswa): {len(hasil_df)}")
            st.write(f"MK yang dihapus karena tidak memenuhi syarat paralel/jumlah mahasiswa: {raw_mk_count - len(hasil_df)}")
        
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
    st.info("Membaca Data...")
